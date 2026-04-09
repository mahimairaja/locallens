from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import index, search, ask, voice, files, stats


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown


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


@app.get("/api/health")
async def health():
    return {"status": "ok"}
