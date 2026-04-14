"""Namespace management endpoints."""

import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import check_namespace_access, require_auth
from app.config import collection_for_namespace
from app.services import store

router = APIRouter()

_NS_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}$")


class CreateNamespaceRequest(BaseModel):
    namespace: str


@router.get("/namespaces")
async def list_namespaces(api_key: str | None = Depends(require_auth)):
    """List all existing namespaces."""
    return {"namespaces": store.list_namespaces()}


@router.post("/namespaces")
async def create_namespace(
    req: CreateNamespaceRequest,
    api_key: str | None = Depends(require_auth),
):
    """Create a new namespace (Qdrant collection)."""
    ns = req.namespace.lower().strip()
    if not _NS_RE.match(ns):
        raise HTTPException(
            400,
            "Namespace must be 1-63 lowercase alphanumeric characters, hyphens, or underscores.",
        )
    check_namespace_access(api_key, ns)
    col = collection_for_namespace(ns)
    store.ensure_collection(col)
    return {"namespace": ns, "collection": col}
