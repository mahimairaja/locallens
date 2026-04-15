import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import ask, files, fs, index, search, stats, voice
from app.routers import audit as audit_router
from app.routers import auth as auth_router
from app.routers import namespaces as namespaces_router
from app.routers import watcher as watcher_router
from app.services import bm25, voice_stt, voice_tts, watcher

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    voice_stt.load_model()
    voice_tts.load_model()
    bm25.load()
    watcher.start()
    yield
    # Shutdown
    watcher.stop()


app = FastAPI(title="LocalLens API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(index.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(ask.router, prefix="/api")
app.include_router(voice.router, prefix="/api")
app.include_router(files.router, prefix="/api")
app.include_router(stats.router, prefix="/api")
app.include_router(fs.router, prefix="/api")
app.include_router(watcher_router.router, prefix="/api")
app.include_router(namespaces_router.router, prefix="/api")
app.include_router(audit_router.router, prefix="/api")
app.include_router(auth_router.router, prefix="/api")


@app.get("/api/health")
async def health():
    qdrant_status = "unreachable"
    ollama_status = "unreachable"

    # Probe Qdrant via get_collections with 2s timeout
    try:
        from app.services.store import _get_client

        client = _get_client()
        client.get_collections(timeout=2)
        qdrant_status = "ok"
    except Exception:
        logger.debug("Qdrant health probe failed", exc_info=True)

    # Probe Ollama with 2s timeout
    try:
        async with httpx.AsyncClient(timeout=2.0) as http:
            resp = await http.get(settings.ollama_url)
            if resp.status_code < 500:
                ollama_status = "ok"
    except Exception:
        logger.debug("Ollama health probe failed", exc_info=True)

    search_available = qdrant_status == "ok"
    ask_available = qdrant_status == "ok" and ollama_status == "ok"

    return {
        "qdrant": qdrant_status,
        "ollama": ollama_status,
        "search_available": search_available,
        "ask_available": ask_available,
    }
