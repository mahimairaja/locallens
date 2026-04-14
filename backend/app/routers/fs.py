"""Local filesystem helpers.

Exposes a native folder picker that pops the OS's own "choose folder"
dialog on the machine running the backend and returns the selected
path. Intended for local-first use — LocalLens assumes the backend and
the browser are on the same machine.
"""

import logging
import os
import platform
import shutil
import subprocess
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from app.auth import require_auth

logger = logging.getLogger(__name__)

router = APIRouter()


def _pick_folder_macos() -> str | None:
    """Open macOS native folder picker via AppleScript. Returns path or None."""
    script = (
        'tell application "System Events" to activate\n'
        'set chosen to POSIX path of (choose folder with prompt "Choose a folder to index")\n'
        'return chosen'
    )
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        return None

    if result.returncode != 0:
        # User cancelled — AppleScript returns non-zero. Treat as "no selection".
        if "User canceled" in result.stderr or "-128" in result.stderr:
            return None
        logger.warning("osascript error: %s", result.stderr.strip())
        return None

    path = result.stdout.strip()
    return path or None


def _pick_folder_linux() -> str | None:
    """Open Linux native folder picker via zenity if available."""
    if shutil.which("zenity") is None:
        return None
    try:
        result = subprocess.run(
            ["zenity", "--file-selection", "--directory", "--title=Choose a folder to index"],
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        return None
    if result.returncode != 0:
        return None
    path = result.stdout.strip()
    return path or None


@router.post("/fs/pick-folder")
async def pick_folder(api_key: str | None = Depends(require_auth)):
    """Open the native OS folder picker and return the chosen absolute path."""
    system = platform.system()

    if system == "Darwin":
        path = _pick_folder_macos()
    elif system == "Linux":
        path = _pick_folder_linux()
    else:
        raise HTTPException(
            status_code=501,
            detail=f"Native folder picker not supported on {system}. Type the path manually.",
        )

    if path is None:
        # User cancelled — return empty payload, not an error, so the frontend
        # can silently ignore without showing a failure state.
        return {"path": None, "cancelled": True}

    p = Path(path)
    if not p.exists() or not p.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a directory: {path}")

    return {"path": str(p.resolve()), "cancelled": False}


@router.get("/fs/home")
async def home_directory(api_key: str | None = Depends(require_auth)):
    """Return the user's home directory — handy for prefilling the text input."""
    return {"path": str(Path(os.path.expanduser("~")).resolve())}
