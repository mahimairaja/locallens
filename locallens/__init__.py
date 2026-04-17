"""LocalLens — Semantic file search engine for AI agents. 100% offline.

Quick start::

    from locallens import LocalLens

    lens = LocalLens("~/Documents")
    lens.index()
    results = lens.search("quarterly revenue report")
    print(results[0].file_name, results[0].score)
"""

__version__ = "0.2.0"

from locallens.engine import LocalLens
from locallens.models import (
    AskResult,
    AskStreamEvent,
    DoctorCheck,
    FileInfo,
    IndexResult,
    OllamaUnavailableError,
    SearchResult,
    StatsResult,
)

__all__ = [
    "LocalLens",
    "IndexResult",
    "SearchResult",
    "AskResult",
    "AskStreamEvent",
    "StatsResult",
    "FileInfo",
    "DoctorCheck",
    "OllamaUnavailableError",
    "__version__",
]
