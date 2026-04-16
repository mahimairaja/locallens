"""RAG module: retrieve chunks, build prompt, stream response from Ollama."""

from collections.abc import Generator

import httpx
from rich.console import Console

from locallens.config import OLLAMA_BASE_URL, OLLAMA_MODEL, RAG_TOP_K
from locallens.embedder import embed_query

console = Console()

_SYSTEM_PROMPT = (
    "You are a helpful assistant answering questions about the user's local files. "
    "Use the provided context to answer. The context is excerpts from the user's "
    "indexed files — it may include body text, metadata, references, or author info. "
    "Synthesize what you can from ALL the context: if body text is limited, infer "
    "from titles, section headings, authors, and references what the document is "
    "about and share that. Only say you cannot find relevant information if the "
    "context is truly unrelated to the question."
)


def _build_context(chunks: list) -> str:
    """Build the context block from retrieved chunks."""
    parts: list[str] = []
    for hit in chunks:
        file_name = hit.payload.get("file_name", "unknown")
        chunk_text = hit.payload.get("chunk_text", "")
        parts.append(f"[File: {file_name}]\n{chunk_text}")
    return "\n---\n".join(parts)


def ask(question: str, store, top_k: int = RAG_TOP_K) -> Generator[str, None, None]:
    """Retrieve relevant chunks and stream a RAG answer from Ollama.

    Yields tokens as they arrive. Prints sources after completion.
    """
    vector = embed_query(question)
    results = store.search(vector, top_k)

    if not results:
        yield "I couldn't find relevant information in your indexed files."
        return

    context = _build_context(results)
    prompt = f"Context:\n---\n{context}\n---\n\nQuestion: {question}\nAnswer:"

    # Stream from Ollama
    sources: list[str] = []
    seen_files: set[str] = set()
    for hit in results:
        fp = hit.payload.get("file_path", "")
        fn = hit.payload.get("file_name", "")
        if fp not in seen_files:
            seen_files.add(fp)
            sources.append(f"  - {fn} ({fp})")

    try:
        with httpx.stream(
            "POST",
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "system": _SYSTEM_PROMPT,
                "stream": True,
            },
            timeout=120.0,
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                import json

                data = json.loads(line)
                token = data.get("response", "")
                if token:
                    yield token
                if data.get("done"):
                    break
    except httpx.ConnectError:
        raise ConnectionError(
            "Ollama is not running. Start it with: ollama serve\n"
            "Then pull the model: ollama pull qwen2.5:3b"
        )

    # Print sources
    yield "\n"
    console.print("\n[dim]Sources:[/dim]")
    for src in sources:
        console.print(f"[dim]{src}[/dim]")
