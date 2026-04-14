from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import index, search, ask, voice, files, stats, fs, watcher as watcher_router
from app.routers import namespaces as namespaces_router, audit as audit_router, auth as auth_router
from app.services import bm25, voice_stt, voice_tts, watcher


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
    return {"status": "ok"}
