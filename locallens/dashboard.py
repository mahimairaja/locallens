"""Optional web dashboard — started with ``locallens serve --ui`` or ``--api``."""

from __future__ import annotations

import sys
from pathlib import Path


def start_dashboard(port: int = 8000, with_ui: bool = False) -> None:
    """Start the FastAPI backend, optionally serving the React frontend.

    Args:
        port: HTTP port (default 8000).
        with_ui: If True, mount the built React frontend at ``/``.
    """
    try:
        import uvicorn
    except ImportError:
        print(
            "Server dependencies not installed.\n"
            "Install with: pip install locallens[server]",
            file=sys.stderr,
        )
        sys.exit(1)

    if with_ui:
        frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
        if not frontend_dist.is_dir():
            print(
                f"Frontend not built. Run: cd frontend && npm run build\n"
                f"Expected at: {frontend_dist}",
                file=sys.stderr,
            )
            sys.exit(1)

        # Mount static files on the FastAPI app before starting
        from fastapi.staticfiles import StaticFiles

        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
        from app.main import app

        app.mount(
            "/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend"
        )
    else:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
        from app.main import app  # noqa: F811

    print(
        f"LocalLens {'dashboard' if with_ui else 'API'} running on http://localhost:{port}",
        file=sys.stderr,
    )
    uvicorn.run(app, host="0.0.0.0", port=port)


def start_api(port: int = 8000) -> None:
    """Start headless API server (no frontend)."""
    start_dashboard(port=port, with_ui=False)
