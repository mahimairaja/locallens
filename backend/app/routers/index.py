from fastapi import APIRouter, BackgroundTasks, HTTPException, WebSocket, WebSocketDisconnect
from app.models import IndexRequest, IndexProgress
from app.services.indexer import index_folder
import asyncio
import uuid
import json

router = APIRouter()

# In-memory task storage
_tasks: dict[str, IndexProgress] = {}
# WebSocket subscribers per task
_subscribers: dict[str, list[WebSocket]] = {}


@router.post("/index")
async def start_index(req: IndexRequest, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())
    _tasks[task_id] = IndexProgress(status="scanning")
    _subscribers[task_id] = []

    def run_index():
        def on_progress(p: IndexProgress):
            _tasks[task_id] = p
            _notify_subscribers(task_id, p)

        try:
            result = index_folder(req.folder_path, req.force, on_progress)
            _tasks[task_id] = result
            _notify_subscribers(task_id, result)
        except Exception as e:
            error_progress = IndexProgress(status="error", error=str(e))
            _tasks[task_id] = error_progress
            _notify_subscribers(task_id, error_progress)

    background_tasks.add_task(run_index)
    return {"task_id": task_id}


def _notify_subscribers(task_id: str, progress: IndexProgress):
    """Send progress to all WebSocket subscribers (fire-and-forget from sync context)."""
    subs = _subscribers.get(task_id, [])
    msg = progress.model_dump_json()
    dead = []
    for ws in subs:
        try:
            asyncio.get_event_loop().call_soon_threadsafe(
                asyncio.ensure_future, ws.send_text(msg)
            )
        except Exception:
            dead.append(ws)
    for ws in dead:
        subs.remove(ws)


@router.websocket("/index/progress/{task_id}")
async def index_progress_ws(websocket: WebSocket, task_id: str):
    await websocket.accept()

    if task_id not in _tasks:
        await websocket.send_text(json.dumps({"error": "Task not found"}))
        await websocket.close()
        return

    _subscribers.setdefault(task_id, []).append(websocket)

    # Send current state immediately
    await websocket.send_text(_tasks[task_id].model_dump_json())

    try:
        # Keep connection open; also poll in case notifications were missed
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
            except asyncio.TimeoutError:
                pass

            current = _tasks.get(task_id)
            if current and current.status in ("done", "error"):
                await websocket.send_text(current.model_dump_json())
                break
    except WebSocketDisconnect:
        pass
    finally:
        subs = _subscribers.get(task_id, [])
        if websocket in subs:
            subs.remove(websocket)


@router.get("/index/status/{task_id}")
async def get_index_status(task_id: str):
    if task_id not in _tasks:
        raise HTTPException(404, "Task not found")
    return _tasks[task_id]


@router.get("/index/status")
async def get_all_status():
    return _tasks
