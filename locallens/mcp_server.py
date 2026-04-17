"""LocalLens MCP server — exposes search, ask, index as tools for AI agents.

Start with: ``locallens serve --mcp``
Or directly: ``python -m locallens.mcp_server``
"""

from __future__ import annotations

import os
import sys

_lens = None


def _get_lens():
    global _lens
    if _lens is None:
        from locallens import LocalLens

        _lens = LocalLens(
            data_dir=os.environ.get("LOCALLENS_DATA_DIR", None),
            collection_name=os.environ.get("LOCALLENS_COLLECTION", "locallens"),
            ollama_url=os.environ.get("LOCALLENS_OLLAMA_URL", "http://localhost:11434"),
            ollama_model=os.environ.get("LOCALLENS_OLLAMA_MODEL", "qwen2.5:3b"),
            embedding_model=os.environ.get(
                "LOCALLENS_EMBEDDING_MODEL", "all-MiniLM-L6-v2"
            ),
        )
    return _lens


def create_mcp_app():
    """Create and return a FastMCP server with LocalLens tools."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        print(
            "MCP package not installed. Install with: pip install locallens[mcp]",
            file=sys.stderr,
        )
        sys.exit(1)

    mcp = FastMCP("LocalLens")

    @mcp.tool()
    def locallens_search(
        query: str,
        top_k: int = 5,
        file_type: str | None = None,
        mode: str = "hybrid",
    ) -> list[dict]:
        """Search indexed files by semantic meaning, keywords, or hybrid. Use this to find files and code relevant to a topic or question."""
        lens = _get_lens()
        results = lens.search(query, top_k=top_k, mode=mode, file_type=file_type)
        return [r.to_dict() for r in results]

    @mcp.tool()
    def locallens_ask(question: str, top_k: int = 3) -> dict:  # type: ignore[type-arg]
        """Ask a question about indexed files and get an answer with source citations. Uses RAG with a local LLM. Requires Ollama to be running."""
        lens = _get_lens()
        result = lens.ask(question, top_k=top_k)
        return dict(result.to_dict())

    @mcp.tool()
    def locallens_index(folder_path: str, force: bool = False) -> dict:
        """Index a folder of files for semantic search. Extracts text from PDFs, DOCX, code, CSVs and more. Re-indexes only changed files unless force is true."""
        from locallens import LocalLens

        lens = LocalLens(path=folder_path)
        result = lens.index(force=force)
        return result.to_dict()

    @mcp.tool()
    def locallens_status() -> dict:
        """Get the current status of LocalLens including indexed file count, health of dependencies, and available features."""
        lens = _get_lens()
        stats = lens.stats()
        checks = lens.doctor()
        return {
            "stats": stats.to_dict(),
            "health": [c.to_dict() for c in checks],
        }

    @mcp.tool()
    def locallens_files(file_type: str | None = None) -> list[dict]:
        """List all indexed files with their types, chunk counts, and when they were indexed."""
        lens = _get_lens()
        files = lens.files()
        if file_type:
            files = [f for f in files if f.file_type == file_type]
        return [f.to_dict() for f in files]

    return mcp


def main(port: int = 8811) -> None:
    """Run the MCP server."""
    mcp = create_mcp_app()
    print(
        f"LocalLens MCP server running on http://localhost:{port}/sse\n\n"
        "Add to Claude Desktop config (claude_desktop_config.json):\n"
        '  "locallens": {"command": "locallens", "args": ["serve", "--mcp"]}\n',
        file=sys.stderr,
    )
    mcp.run(transport="sse")


if __name__ == "__main__":
    main()
