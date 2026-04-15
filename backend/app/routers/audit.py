"""Audit log endpoint (requires auth when enabled)."""

from fastapi import APIRouter, Depends, Query

from app.auth import require_auth
from app.services import audit

router = APIRouter()


@router.get("/audit")
async def get_audit_log(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    operation: str | None = Query(None),
    namespace: str | None = Query(None),
    api_key: str | None = Depends(require_auth),
):
    """Return paginated audit log entries."""
    return audit.query(
        page=page,
        page_size=page_size,
        operation=operation,
        namespace=namespace,
    )
