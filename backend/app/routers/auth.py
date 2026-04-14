"""Auth status endpoint."""

from fastapi import APIRouter, Depends

from app.auth import optional_auth
from app.config import settings

router = APIRouter()


@router.get("/auth/status")
async def auth_status(api_key: str | None = Depends(optional_auth)):
    """Return whether auth is enabled and whether the caller is authenticated."""
    enabled = bool(settings.locallens_api_key)
    return {
        "auth_enabled": enabled,
        "authenticated": api_key is not None if enabled else True,
    }
