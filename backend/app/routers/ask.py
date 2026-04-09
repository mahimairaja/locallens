from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from app.models import AskRequest
from app.services.rag import stream_answer
import json

router = APIRouter()


@router.post("/ask")
async def ask(req: AskRequest):
    def event_stream():
        for token, sources in stream_answer(req.question, req.top_k):
            if token is not None:
                yield f"event: token\ndata: {json.dumps({'text': token})}\n\n"
            if sources is not None:
                yield f"event: sources\ndata: {json.dumps({'sources': [s.model_dump() for s in sources]})}\n\n"
        yield f"event: done\ndata: {{}}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
