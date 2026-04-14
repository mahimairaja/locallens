from fastapi import APIRouter, Depends, Query
from app.auth import check_namespace_access, require_auth
from app.config import collection_for_namespace
from app.models import StatsResponse
from app.services import store

router = APIRouter()


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    namespace: str = Query("default"),
    api_key: str | None = Depends(require_auth),
):
    """Stats endpoint -- uses ``store.facet_file_types`` for the file-type
    breakdown (server-side aggregation on the payload index) instead of
    scrolling every chunk in Python. Still does a single scroll for the
    distinct-file count and ``last_indexed_at``.
    """
    from app.routers.search import _recent_searches

    check_namespace_access(api_key, namespace)
    collection = collection_for_namespace(namespace)

    try:
        info = store.get_collection_info(collection=collection)
    except Exception:
        return StatsResponse(
            total_files=0, total_chunks=0, file_types={},
            storage_size_mb=0, top_searches=[]
        )

    file_types = dict(store.facet_file_types(limit=20, collection=collection))

    files: set[str] = set()
    last_indexed = None
    try:
        for p in store.scroll_all(collection=collection):
            payload = p.payload or {}
            fp = payload.get("file_path")
            if fp:
                files.add(fp)
            ts = payload.get("indexed_at")
            if ts and (last_indexed is None or ts > last_indexed):
                last_indexed = ts
    except Exception:
        pass

    return StatsResponse(
        total_files=len(files),
        total_chunks=int(info.get("points_count", 0) or 0),
        file_types=file_types,
        storage_size_mb=0,
        last_indexed_at=last_indexed,
        top_searches=_recent_searches[:10],
    )
