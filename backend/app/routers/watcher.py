from fastapi import APIRouter, Depends

from app.auth import require_auth
from app.services import watcher

router = APIRouter()


@router.get("/watcher/status")
async def watcher_status(api_key: str | None = Depends(require_auth)):
    return watcher.get_status()


@router.post("/watcher/watch")
async def watch_folder(body: dict, api_key: str | None = Depends(require_auth)):
    folder = body.get("folder", "")
    if folder:
        watcher.add_folder(folder)
    return {"status": "ok", "folders": list(watcher._watched_folders)}


@router.post("/watcher/unwatch")
async def unwatch_folder(body: dict, api_key: str | None = Depends(require_auth)):
    folder = body.get("folder", "")
    if folder:
        watcher.remove_folder(folder)
    return {"status": "ok", "folders": list(watcher._watched_folders)}
