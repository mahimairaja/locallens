import json
import logging

import httpx

from app.config import settings
from app.models import AskSource
from app.services.searcher import search

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a helpful assistant. Answer the question based ONLY on the provided context. If you cannot find the answer in the context, say so. Be concise and accurate."""


def get_rag_context(
    question: str, top_k: int, collection: str | None = None
) -> tuple[str, list[AskSource]]:
    """Retrieve context and sources for RAG."""
    result = search(question, top_k, collection=collection)
    if not result.results:
        return "", []

    context_parts = []
    sources = []
    for r in result.results:
        context_parts.append(f"[From {r.file_name}]:\n{r.chunk_text}")
        sources.append(
            AskSource(
                file_name=r.file_name,
                file_path=r.file_path,
                chunk_preview=r.chunk_text[:200],
            )
        )

    return "\n\n---\n\n".join(context_parts), sources


def stream_answer(question: str, top_k: int = 3, collection: str | None = None):
    """Generator that yields (token, sources_or_none) tuples.
    Sources are yielded as the last item."""
    context, sources = get_rag_context(question, top_k, collection=collection)

    if not context:
        yield (
            "I don't have any indexed documents to answer this question. Please index some files first.",
            None,
        )
        yield (None, sources)
        return

    prompt = f"Context:\n{context}\n\nQuestion: {question}\nAnswer:"

    try:
        with httpx.Client(timeout=120.0) as client:
            with client.stream(
                "POST",
                f"{settings.ollama_url}/api/generate",
                json={
                    "model": settings.ollama_model,
                    "prompt": prompt,
                    "system": SYSTEM_PROMPT,
                    "stream": True,
                },
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        data = json.loads(line)
                        token = data.get("response", "")
                        if token:
                            yield (token, None)
                        if data.get("done"):
                            break
    except httpx.ConnectError:
        yield ("Error: Ollama is not running. Start it with: `ollama serve`", None)
    except Exception as e:
        yield (f"Error: {str(e)}", None)

    yield (None, sources)
