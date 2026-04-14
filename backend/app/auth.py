"""Simple API key authentication and per-namespace access control.

When ``LOCALLENS_API_KEY`` is set in the environment, all API endpoints
require ``Authorization: Bearer <key>``.  When unset, endpoints are open
(backward compatible).

Per-namespace ACL is driven by ``~/.locallens/access.json``:
  {"key1": ["default", "project-a"], "key2": ["project-b"]}

If the file is absent, any valid key can access every namespace.
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import Depends, HTTPException, Request

from app.config import collection_for_namespace, settings

logger = logging.getLogger(__name__)

_ACCESS_FILE = Path.home() / ".locallens" / "access.json"


def _load_access_map() -> dict[str, list[str]] | None:
    """Load the access map from disk. Returns ``None`` if the file is absent."""
    if not _ACCESS_FILE.exists():
        return None
    try:
        data = json.loads(_ACCESS_FILE.read_text())
        if isinstance(data, dict):
            return data
    except Exception as exc:
        logger.warning("Could not load access.json: %s", exc)
    return None


def hash_key(key: str) -> str:
    """SHA-256 hash of an API key (for audit log storage)."""
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _extract_bearer(request: Request) -> str | None:
    """Pull the bearer token from the Authorization header, or ``None``."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


async def require_auth(request: Request) -> Optional[str]:
    """FastAPI dependency that enforces API key auth when configured.

    Returns the raw API key string (or ``None`` when auth is disabled).
    Raises 401 if the key is missing or invalid.
    """
    if not settings.locallens_api_key:
        return None  # Auth disabled -- allow everything.

    token = _extract_bearer(request)
    if not token:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    if token != settings.locallens_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return token


async def optional_auth(request: Request) -> Optional[str]:
    """Like ``require_auth`` but never raises -- returns ``None`` silently."""
    if not settings.locallens_api_key:
        return None
    token = _extract_bearer(request)
    if token and token == settings.locallens_api_key:
        return token
    return None


def check_namespace_access(api_key: str | None, namespace: str) -> None:
    """Raise 403 if ``api_key`` is not allowed to access ``namespace``.

    No-op when auth is disabled or when ``access.json`` is absent.
    """
    if not settings.locallens_api_key or api_key is None:
        return  # Auth disabled -- unrestricted.
    access_map = _load_access_map()
    if access_map is None:
        return  # No ACL file -- any valid key can access everything.
    allowed = access_map.get(api_key, [])
    if namespace not in allowed:
        raise HTTPException(
            status_code=403,
            detail=f"Access denied to namespace '{namespace}'",
        )
