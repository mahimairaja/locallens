from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class IndexRequest(BaseModel):
    folder_path: str
    force: bool = False


class IndexProgress(BaseModel):
    status: str  # "scanning" | "indexing" | "done" | "error"
    current_file: Optional[str] = None
    files_processed: int = 0
    files_total: int = 0
    chunks_created: int = 0
    elapsed_seconds: float = 0
    error: Optional[str] = None


class SearchRequest(BaseModel):
    query: str
    top_k: int = 10


class SearchResult(BaseModel):
    rank: int
    score: float
    file_name: str
    file_path: str
    file_type: str
    chunk_text: str
    chunk_index: int


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    search_time_ms: float


class AskRequest(BaseModel):
    question: str
    top_k: int = 3


class AskSource(BaseModel):
    file_name: str
    file_path: str
    chunk_preview: str


class IndexedFile(BaseModel):
    file_path: str
    file_name: str
    file_type: str
    chunk_count: int
    indexed_at: Optional[datetime] = None


class StatsResponse(BaseModel):
    total_files: int
    total_chunks: int
    file_types: dict[str, int]
    storage_size_mb: float
    last_indexed_at: Optional[datetime] = None
    top_searches: list[str]


class TranscribeResponse(BaseModel):
    text: str
    duration_ms: float


class SynthesizeRequest(BaseModel):
    text: str
