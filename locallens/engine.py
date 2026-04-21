"""LocalLens engine — the Python API for semantic file search.

Usage::

    from locallens import LocalLens

    lens = LocalLens("~/Documents")
    lens.index()
    results = lens.search("meeting notes")
    answer = lens.ask("What was discussed in the Q3 meeting?")
"""

from __future__ import annotations

import shutil
import time
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any

from locallens.models import (
    AskResult,
    AskStreamEvent,
    DoctorCheck,
    FileInfo,
    IndexResult,
    OllamaUnavailableError,
    SearchResult,
    StatsResult,
)


class LocalLens:
    """Semantic file search engine. 100% offline.

    Args:
        path: Folder to index and search. Can be set later via ``index()``.
        collection_name: Qdrant collection name.
        data_dir: Where to store the Qdrant Edge shard and BM25 index.
        embedding_model: Sentence-transformers model name.
        ollama_url: Ollama server URL (for ``ask()``).
        ollama_model: Ollama model name (for ``ask()``).
    """

    def __init__(
        self,
        path: str | Path | None = None,
        collection_name: str = "locallens",
        data_dir: str | Path | None = None,
        embedding_model: str = "all-MiniLM-L6-v2",
        ollama_url: str = "http://localhost:11434",
        ollama_model: str = "qwen2.5:3b",
    ) -> None:
        self._path = Path(path).expanduser().resolve() if path else None
        self._data_dir = (
            Path(data_dir or Path.home() / ".locallens").expanduser().resolve()
        )
        self._collection_name = collection_name
        self._embedding_model = embedding_model
        self._ollama_url = ollama_url
        self._ollama_model = ollama_model

        self._store_initialized = False
        self._store_module: Any = None
        self._embed_query_fn: Callable[..., list[float]] | None = None
        self._embed_texts_fn: Callable[..., list[list[float]]] | None = None

    # ── lazy initialization ──────────────────────────────────────────

    def _init_store(self) -> None:
        if self._store_initialized:
            return
        from locallens import store

        store.init()
        self._store_module = store
        self._store_initialized = True

    def _get_store(self) -> Any:
        self._init_store()
        return self._store_module

    def _get_embedder(
        self,
    ) -> tuple[Callable[..., list[float]], Callable[..., list[list[float]]]]:
        if self._embed_query_fn is None:
            from locallens.embedder import embed_query, embed_texts

            self._embed_query_fn = embed_query
            self._embed_texts_fn = embed_texts
        assert self._embed_texts_fn is not None
        return self._embed_query_fn, self._embed_texts_fn

    def _get_bm25(self) -> Any:
        from locallens import bm25

        bm25.load()
        return bm25

    # ── public API ───────────────────────────────────────────────────

    def index(
        self,
        force: bool = False,
        callback: Callable[[str, str, float], None] | None = None,
    ) -> IndexResult:
        """Index files in the configured path.

        Args:
            force: Re-index all files regardless of content hash.
            callback: Optional ``callback(event_type, message, progress)``
                where event_type is one of scanning/extracting/embedding/done.

        Returns:
            IndexResult with file and chunk counts.
        """
        if self._path is None:
            raise ValueError("No path configured. Pass a folder path to LocalLens().")

        store = self._get_store()

        from locallens.indexer import index_folder

        start = time.time()
        index_folder(self._path, force=force)
        elapsed = time.time() - start

        total_chunks = store.count()
        total_files = store.get_file_count()

        return IndexResult(
            total_files=total_files,
            total_chunks=total_chunks,
            duration_seconds=round(elapsed, 2),
        )

    def search(
        self,
        query: str,
        top_k: int = 5,
        mode: str = "hybrid",
        file_type: str | None = None,
        path_prefix: str | None = None,
    ) -> list[SearchResult]:
        """Search indexed files.

        Args:
            query: Search query text.
            top_k: Maximum results to return.
            mode: "semantic", "keyword", or "hybrid".
            file_type: Filter by file extension (e.g. ".pdf").
            path_prefix: Filter by file path prefix.

        Returns:
            List of SearchResult sorted by relevance.
        """
        if mode not in ("semantic", "keyword", "hybrid"):
            raise ValueError(
                f"Invalid mode '{mode}'. Use 'semantic', 'keyword', or 'hybrid'."
            )

        store = self._get_store()
        embed_query, _ = self._get_embedder()

        if mode == "keyword":
            # BM25 keyword-only search
            bm25 = self._get_bm25()
            hits = bm25.search(query, top_k)
            results: list[SearchResult] = []
            for doc_id, score in hits[:top_k]:
                # Look up payload from store — best effort
                try:
                    points = (
                        store.get_points([doc_id])
                        if hasattr(store, "get_points")
                        else []
                    )
                except Exception:
                    points = []
                if points:
                    payload = points[0].payload or {}
                    if file_type and payload.get("file_type") != file_type:
                        continue
                    results.append(self._payload_to_result(payload, score))
            return results

        # Semantic search (also used as base for hybrid)
        vector = embed_query(query)
        semantic_hits = store.search(
            vector,
            top_k if mode == "semantic" else top_k * 2,
            file_type=file_type,
            path_prefix=path_prefix,
        )

        if mode == "semantic":
            return [
                self._payload_to_result(hit.payload or {}, float(hit.score))
                for hit in semantic_hits
            ]

        # Hybrid: combine semantic + BM25 via RRF
        bm25 = self._get_bm25()
        bm25_hits = bm25.search(query, top_k * 2)

        if not bm25_hits:
            return [
                self._payload_to_result(hit.payload or {}, float(hit.score))
                for hit in semantic_hits[:top_k]
            ]

        rrf_k = 60
        scores: dict[str, float] = {}
        payloads: dict[str, dict[str, Any]] = {}

        for rank, hit in enumerate(semantic_hits, start=1):
            pid = str(hit.id)
            scores[pid] = scores.get(pid, 0) + 1.0 / (rrf_k + rank)
            payloads[pid] = hit.payload or {}

        for rank, (doc_id, _) in enumerate(bm25_hits, start=1):
            scores[doc_id] = scores.get(doc_id, 0) + 1.0 / (rrf_k + rank)

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        results = []
        for pid, score in ranked[:top_k]:
            payload = payloads.get(pid, {})
            if payload:
                results.append(self._payload_to_result(payload, score))
        return results

    def ask(self, question: str, top_k: int = 3) -> AskResult:
        """Ask a question about indexed files using RAG.

        Args:
            question: Natural language question.
            top_k: Number of context chunks to retrieve.

        Returns:
            AskResult with answer text and source citations.

        Raises:
            OllamaUnavailableError: When Ollama is not running.
        """
        start = time.time()
        tokens: list[str] = []
        sources: list[SearchResult] = []

        try:
            for event in self.ask_stream(question, top_k=top_k):
                if event.event_type == "token":
                    tokens.append(str(event.data))
                elif event.event_type == "sources":
                    sources = event.data or []
        except OllamaUnavailableError:
            raise
        except ConnectionError as exc:
            raise OllamaUnavailableError() from exc

        return AskResult(
            answer="".join(tokens),
            sources=sources,
            model=self._ollama_model,
            duration_seconds=round(time.time() - start, 2),
        )

    def ask_stream(
        self, question: str, top_k: int = 3
    ) -> Generator[AskStreamEvent, None, None]:
        """Stream a RAG answer token by token.

        Yields:
            AskStreamEvent with event_type "token" (data=str) or "sources" (data=list[SearchResult]).

        Raises:
            OllamaUnavailableError: When Ollama is not running.
        """
        store = self._get_store()

        from locallens.rag import ask as rag_ask

        # Collect source info before streaming
        embed_query, _ = self._get_embedder()
        vector = embed_query(question)
        context_hits = store.search(vector, top_k)
        sources = [
            self._payload_to_result(hit.payload or {}, float(hit.score))
            for hit in context_hits
        ]

        try:
            results_iter = rag_ask(question, store, top_k=top_k)
        except ConnectionError as exc:
            raise OllamaUnavailableError() from exc

        try:
            for token in results_iter:
                yield AskStreamEvent(event_type="token", data=token)
        except ConnectionError as exc:
            raise OllamaUnavailableError() from exc

        # Emit sources as the final event
        yield AskStreamEvent(event_type="sources", data=sources)

    def stats(self) -> StatsResult:
        """Get collection statistics."""
        store = self._get_store()

        total_chunks = store.count()
        total_files = store.get_file_count()
        file_types = dict(store.facet_file_types(limit=50))

        return StatsResult(
            total_files=total_files,
            total_chunks=total_chunks,
            file_types=file_types,
            collection_name=self._collection_name,
            data_dir=str(self._data_dir),
        )

    def files(self) -> list[FileInfo]:
        """List all indexed files."""
        store = self._get_store()

        all_points = store.scroll_all() if hasattr(store, "scroll_all") else []

        seen: dict[str, FileInfo] = {}
        for point in all_points:
            payload = point.payload or {} if hasattr(point, "payload") else {}
            fp = payload.get("file_path", "")
            if fp and fp not in seen:
                seen[fp] = FileInfo(
                    file_path=fp,
                    file_name=payload.get("file_name", ""),
                    file_type=payload.get("file_type", ""),
                    chunk_count=0,
                    indexed_at=payload.get("indexed_at"),
                )
            if fp in seen:
                seen[fp].chunk_count += 1

        return list(seen.values())

    def delete(self, file_path: str) -> bool:
        """Delete a file and all its chunks from the index."""
        store = self._get_store()
        try:
            store.delete_by_file(file_path)
            return True
        except Exception:
            return False

    def doctor(self) -> list[DoctorCheck]:
        """Run health checks on all dependencies."""
        import contextlib
        import io
        import os
        import warnings

        checks: list[DoctorCheck] = []

        # 1. Qdrant Edge
        try:
            store = self._get_store()
            n = store.count()
            checks.append(DoctorCheck("Qdrant Edge", "ok", f"{n} points in shard"))
        except Exception as exc:
            checks.append(DoctorCheck("Qdrant Edge", "fail", str(exc)[:80]))

        # 2. Ollama
        try:
            import httpx

            resp = httpx.get(f"{self._ollama_url}/api/tags", timeout=2.0)
            if resp.status_code == 200:
                checks.append(
                    DoctorCheck("Ollama", "ok", f"Running at {self._ollama_url}")
                )
            else:
                checks.append(DoctorCheck("Ollama", "warn", f"HTTP {resp.status_code}"))
        except Exception:
            checks.append(
                DoctorCheck("Ollama", "warn", "Not reachable (search still works)")
            )

        # 3. Embedding model
        try:
            os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
            os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
            with (
                warnings.catch_warnings(),
                contextlib.redirect_stderr(io.StringIO()),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                warnings.simplefilter("ignore")
                embed_query, _ = self._get_embedder()
                vec = embed_query("test")
            checks.append(
                DoctorCheck(
                    "Embedding Model",
                    "ok",
                    f"{self._embedding_model} ({len(vec)}-dim)",
                )
            )
        except Exception as exc:
            checks.append(DoctorCheck("Embedding Model", "fail", str(exc)[:80]))

        # 4. Voice STT
        try:
            import moonshine  # noqa: F401

            checks.append(DoctorCheck("Voice STT", "ok", "moonshine-voice available"))
        except ImportError:
            checks.append(DoctorCheck("Voice STT", "warn", "Not installed (optional)"))

        # 5. Voice TTS
        try:
            import piper  # noqa: F401

            checks.append(DoctorCheck("Voice TTS", "ok", "piper-tts available"))
        except ImportError:
            checks.append(DoctorCheck("Voice TTS", "warn", "Not installed (optional)"))

        # 6. Disk space
        try:
            _, _, free = shutil.disk_usage(str(self._data_dir.parent))
            free_gb = free / (1024**3)
            status = "ok" if free_gb >= 1.0 else "warn"
            checks.append(DoctorCheck("Disk Space", status, f"{free_gb:.1f} GB free"))
        except Exception:
            checks.append(DoctorCheck("Disk Space", "warn", "Could not check"))

        # 7. Rust extensions
        from locallens._rust import (
            HAS_RUST,
            HAS_RUST_BM25,
            HAS_RUST_CHUNKER,
            HAS_RUST_WALKER,
            HAS_RUST_WATCHER,
        )

        if HAS_RUST:
            modules = [
                k
                for k, v in {
                    "BM25": HAS_RUST_BM25,
                    "Chunker": HAS_RUST_CHUNKER,
                    "Walker": HAS_RUST_WALKER,
                    "Watcher": HAS_RUST_WATCHER,
                }.items()
                if v
            ]
            checks.append(
                DoctorCheck("Rust Extensions", "ok", f"Active: {', '.join(modules)}")
            )
        else:
            checks.append(
                DoctorCheck(
                    "Rust Extensions",
                    "warn",
                    "Not available (pure-Python fallback)",
                )
            )

        return checks

    # ── internal helpers ─────────────────────────────────────────────

    @staticmethod
    def _payload_to_result(payload: dict[str, Any], score: float) -> SearchResult:
        return SearchResult(
            file_path=payload.get("file_path", ""),
            file_name=payload.get("file_name", ""),
            file_type=payload.get("file_type", ""),
            chunk_text=payload.get("chunk_text", ""),
            chunk_index=payload.get("chunk_index", 0),
            score=round(score, 4),
            extractor=payload.get("extractor"),
        )
