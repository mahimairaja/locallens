from fastapi import APIRouter, HTTPException
from app.models import IndexedFile
from app.services import store
from pathlib import Path

router = APIRouter()


@router.get("/files", response_model=list[IndexedFile])
async def list_files():
    points = store.scroll_all()
    files_map: dict[str, dict] = {}
    for p in points:
        fp = p.payload.get("file_path", "")
        if fp not in files_map:
            files_map[fp] = {
                "file_path": fp,
                "file_name": p.payload.get("file_name", ""),
                "file_type": p.payload.get("file_type", ""),
                "chunk_count": 0,
                "indexed_at": p.payload.get("indexed_at"),
            }
        files_map[fp]["chunk_count"] += 1
    return list(files_map.values())


@router.get("/files/{file_path:path}/content")
async def get_file_content(file_path: str):
    path = Path(file_path)
    if not path.exists():
        raise HTTPException(404, "File not found on disk")
    try:
        return {"content": path.read_text(errors="replace"), "file_path": str(path)}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/files/{file_path:path}/chunks")
async def get_file_chunks(file_path: str):
    points = store.scroll_all()
    chunks = [
        {"chunk_index": p.payload.get("chunk_index", 0), "chunk_text": p.payload.get("chunk_text", "")}
        for p in points
        if p.payload.get("file_path") == file_path
    ]
    return sorted(chunks, key=lambda c: c["chunk_index"])


@router.delete("/files/{file_path:path}")
async def delete_file(file_path: str):
    store.delete_by_file(file_path)
    return {"deleted": file_path}
