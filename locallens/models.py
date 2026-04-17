"""Result dataclasses for the LocalLens Python API.

Every public method on ``LocalLens`` returns one of these dataclasses.
All have a ``to_dict()`` method for JSON serialization.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class IndexResult:
    total_files: int = 0
    new_files: int = 0
    updated_files: int = 0
    skipped_files: int = 0
    total_chunks: int = 0
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SearchResult:
    file_path: str = ""
    file_name: str = ""
    file_type: str = ""
    chunk_text: str = ""
    chunk_index: int = 0
    score: float = 0.0
    extractor: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AskResult:
    answer: str = ""
    sources: list[SearchResult] = field(default_factory=list)
    model: str = ""
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["sources"] = [s.to_dict() for s in self.sources]
        return d


@dataclass
class AskStreamEvent:
    event_type: str = ""  # "token" or "sources"
    data: Any = None

    def to_dict(self) -> dict[str, Any]:
        if self.event_type == "sources" and isinstance(self.data, list):
            return {
                "event_type": self.event_type,
                "data": [
                    s.to_dict() if hasattr(s, "to_dict") else s for s in self.data
                ],
            }
        return {"event_type": self.event_type, "data": self.data}


@dataclass
class StatsResult:
    total_files: int = 0
    total_chunks: int = 0
    file_types: dict[str, int] = field(default_factory=dict)
    collection_name: str = ""
    data_dir: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FileInfo:
    file_path: str = ""
    file_name: str = ""
    file_type: str = ""
    chunk_count: int = 0
    indexed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DoctorCheck:
    name: str = ""
    status: str = ""  # "ok", "fail", "warn"
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class OllamaUnavailableError(Exception):
    """Raised when Ollama is not reachable."""

    def __init__(
        self, message: str = "Ollama is not running. Start it with: ollama serve"
    ):
        super().__init__(message)
