from fastapi import APIRouter
from app.models import SearchRequest, SearchResponse
from app.services.searcher import search

router = APIRouter()

# In-memory recent searches (last 20)
_recent_searches: list[str] = []

@router.post("/search", response_model=SearchResponse)
async def do_search(req: SearchRequest):
    result = search(req.query, req.top_k)
    # Track recent searches
    _recent_searches.insert(0, req.query)
    if len(_recent_searches) > 20:
        _recent_searches.pop()
    return result

@router.get("/search/recent")
async def recent_searches():
    return _recent_searches
