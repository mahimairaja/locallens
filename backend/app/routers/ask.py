from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from app.auth import check_namespace_access, require_auth
from app.config import collection_for_namespace
from app.models import AskRequest
from app.services import audit
from app.services.rag import stream_answer
import json

router = APIRouter()


@router.post("/ask")
async def ask(
    req: AskRequest,
    namespace: str = Query("default"),
    api_key: str | None = Depends(require_auth),
):
    check_namespace_access(api_key, namespace)
    collection = collection_for_namespace(namespace)

    def event_stream():
        for token, sources in stream_answer(req.question, req.top_k, collection=collection):
            if token is not None:
                yield f"event: token\ndata: {json.dumps({'text': token})}\n\n"
            if sources is not None:
                yield f"event: sources\ndata: {json.dumps({'sources': [s.model_dump() for s in sources]})}\n\n"
        yield f"event: done\ndata: {{}}\n\n"

    audit.log("ask", namespace=namespace, api_key=api_key, detail=req.question)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
