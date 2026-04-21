from fastapi import APIRouter, Depends
from fastapi import Query as QueryParam

from app.auth import check_namespace_access, require_auth
from app.config import collection_for_namespace
from app.models import RefineRequest, SearchRequest, SearchResponse
from app.services import audit
from app.services.searcher import refine_search, search

router = APIRouter()

# In-memory recent searches (last 20)
_recent_searches: list[str] = []


@router.post("/search", response_model=SearchResponse)
async def do_search(
    req: SearchRequest,
    namespace: str = QueryParam("default"),
    api_key: str | None = Depends(require_auth),
):
    check_namespace_access(api_key, namespace)
    collection = collection_for_namespace(namespace)
    result = search(
        req.query,
        req.top_k,
        file_type=req.file_type,
        path_prefix=req.path_prefix,
        mode=req.mode,
        date_from=req.date_from,
        date_to=req.date_to,
        collection=collection,
    )
    # Track recent searches
    _recent_searches.insert(0, req.query)
    if len(_recent_searches) > 20:
        _recent_searches.pop()
    audit.log("search", namespace=namespace, api_key=api_key, detail=req.query)
    return result


@router.post("/search/refine", response_model=SearchResponse)
async def do_refine(
    req: RefineRequest,
    namespace: str = QueryParam("default"),
    api_key: str | None = Depends(require_auth),
):
    """Refine a search by boosting or suppressing specific result texts."""
    check_namespace_access(api_key, namespace)
    collection = collection_for_namespace(namespace)
    result = refine_search(
        req.base_query,
        add_texts=req.add_texts,
        subtract_texts=req.subtract_texts,
        top_k=req.top_k,
        file_type=req.file_type,
        mode=req.mode,
        collection=collection,
    )
    audit.log(
        "search_refine", namespace=namespace, api_key=api_key, detail=req.base_query
    )
    return result


@router.get("/search/recent")
async def recent_searches(api_key: str | None = Depends(require_auth)):
    return _recent_searches
