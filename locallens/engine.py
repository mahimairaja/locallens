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
from collections.abc import Generator
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
        self._embedder_loaded = False

    # ── lazy initialization ──────────────────────────────────────────

    def _init_store(self) -> None:
        if self._store_initialized:
            return
        from locallens import store

        store.init()
        self._store_initialized = True

    def _get_embedder(self):
        from locallens.embedder import embed_query, embed_texts

        return embed_query, embed_texts

    def _get_bm25(self):
        from locallens import bm25

        bm25.load()
        return bm25

    # ── public API ───────────────────────────────────────────────────

    def index(self, force: bool = False, callback: Any = None) -> IndexResult:
        """Index files in the configured path.

        Args:
            force: Re-index all files regardless of content hash.
            callback: Optional ``callback(event_type, message, progress)``
                where event_type is one of scanning/extracting/embedding/done.

        Returns:
            IndexResult with file and chunk counts.
        """
        if self._path is None:
            raise ValueError(
                "No path configured. Pass a folder path to LocalLens() or index()."
            )

        self._init_store()

        from locallens.indexer import index_folder

        start = time.time()
        index_folder(self._path, force=force)
        elapsed = time.time() - start

        # Gather stats after indexing
        from locallens import store

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
        self._init_store()
        embed_query, _ = self._get_embedder()

        from locallens import store

        vector = embed_query(query)
        results = store.search(
            vector, top_k, file_type=file_type, path_prefix=path_prefix
        )

        return [
            SearchResult(
                file_path=hit.payload.get("file_path", ""),
                file_name=hit.payload.get("file_name", ""),
                file_type=hit.payload.get("file_type", ""),
                chunk_text=hit.payload.get("chunk_text", ""),
                chunk_index=hit.payload.get("chunk_index", 0),
                score=round(float(hit.score), 4),
                extractor=hit.payload.get("extractor"),
            )
            for hit in results
        ]

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
        except ConnectionError:
            raise OllamaUnavailableError()

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
        self._init_store()

        from locallens import store
        from locallens.rag import ask as rag_ask

        try:
            results_iter = rag_ask(question, store, top_k=top_k)
        except ConnectionError:
            raise OllamaUnavailableError()

        try:
            for token in results_iter:
                yield AskStreamEvent(event_type="token", data=token)
        except ConnectionError:
            raise OllamaUnavailableError()

    def stats(self) -> StatsResult:
        """Get collection statistics.

        Returns:
            StatsResult with file counts, chunk counts, and type breakdown.
        """
        self._init_store()
        from locallens import store

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
        """List all indexed files.

        Returns:
            List of FileInfo with metadata for each indexed file.
        """
        self._init_store()
        from locallens import store

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
        """Delete a file and all its chunks from the index.

        Returns:
            True if the file was found and deleted.
        """
        self._init_store()
        from locallens import store

        try:
            store.delete_by_file(file_path)
            return True
        except Exception:
            return False

    def doctor(self) -> list[DoctorCheck]:
        """Run health checks on all dependencies.

        Returns:
            List of DoctorCheck with status for each component.
        """
        import contextlib
        import io
        import os
        import warnings

        checks: list[DoctorCheck] = []

        # 1. Qdrant Edge
        try:
            self._init_store()
            from locallens import store

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
                    "Embedding Model", "ok", f"{self._embedding_model} ({len(vec)}-dim)"
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

        return checks
