from fastapi import APIRouter
from app.models import StatsResponse
from app.services import store

router = APIRouter()


@router.get("/stats", response_model=StatsResponse)
async def get_stats():
    try:
        info = store.get_collection_info()
        points = store.scroll_all()
    except Exception:
        return StatsResponse(
            total_files=0, total_chunks=0, file_types={},
            storage_size_mb=0, top_searches=[]
        )

    files = set()
    file_types: dict[str, int] = {}
    last_indexed = None
    for p in points:
        fp = p.payload.get("file_path", "")
        ft = p.payload.get("file_type", "")
        ts = p.payload.get("indexed_at")
        files.add(fp)
        file_types[ft] = file_types.get(ft, 0) + 1
        if ts and (last_indexed is None or ts > last_indexed):
            last_indexed = ts

    from app.routers.search import _recent_searches

    return StatsResponse(
        total_files=len(files),
        total_chunks=info.get("count", 0),
        file_types=file_types,
        storage_size_mb=info.get("size_mb", 0),
        last_indexed_at=last_indexed,
        top_searches=_recent_searches[:10],
    )
