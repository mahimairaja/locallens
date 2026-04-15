from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import check_namespace_access, require_auth
from app.config import collection_for_namespace
from app.models import IndexedFile
from app.services import audit, store

router = APIRouter()


@router.get("/files", response_model=list[IndexedFile])
async def list_files(
    namespace: str = Query("default"),
    api_key: str | None = Depends(require_auth),
):
    check_namespace_access(api_key, namespace)
    collection = collection_for_namespace(namespace)
    points = store.scroll_all(collection=collection)
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
async def get_file_content(file_path: str, api_key: str | None = Depends(require_auth)):
    path = Path(file_path)
    if not path.exists():
        raise HTTPException(404, "File not found on disk")
    try:
        return {"content": path.read_text(errors="replace"), "file_path": str(path)}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/files/{file_path:path}/chunks")
async def get_file_chunks(
    file_path: str,
    namespace: str = Query("default"),
    api_key: str | None = Depends(require_auth),
):
    check_namespace_access(api_key, namespace)
    collection = collection_for_namespace(namespace)
    points = store.scroll_all(collection=collection)
    chunks = [
        {
            "chunk_index": p.payload.get("chunk_index", 0),
            "chunk_text": p.payload.get("chunk_text", ""),
        }
        for p in points
        if p.payload.get("file_path") == file_path
    ]
    return sorted(chunks, key=lambda c: c["chunk_index"])


@router.delete("/files/{file_path:path}")
async def delete_file(
    file_path: str,
    namespace: str = Query("default"),
    api_key: str | None = Depends(require_auth),
):
    check_namespace_access(api_key, namespace)
    collection = collection_for_namespace(namespace)
    store.delete_by_file(file_path, collection=collection)
    audit.log("delete", namespace=namespace, api_key=api_key, detail=file_path)
    return {"deleted": file_path}
