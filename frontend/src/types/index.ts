// Index
export interface IndexRequest {
  folder_path: string;
  force: boolean;
}

export interface IndexProgress {
  status: "scanning" | "indexing" | "done" | "error";
  current_file: string | null;
  files_processed: number;
  files_total: number;
  chunks_created: number;
  elapsed_seconds: number;
  error?: string | null;
}

// Search
export interface SearchRequest {
  query: string;
  top_k: number;
  file_type?: string | null;
  path_prefix?: string | null;
}

export interface SearchResult {
  rank: number;
  score: number;
  file_name: string;
  file_path: string;
  file_type: string;
  chunk_text: string;
  chunk_index: number;
}

export interface SearchResponse {
  query: string;
  results: SearchResult[];
  search_time_ms: number;
}

// Ask (RAG)
export interface AskRequest {
  question: string;
  top_k: number;
}

export interface AskSource {
  file_name: string;
  file_path: string;
  chunk_preview: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: AskSource[];
  timestamp: Date;
}

// Files
export interface IndexedFile {
  file_path: string;
  file_name: string;
  file_type: string;
  chunk_count: number;
  indexed_at: string | null;
}

// Stats
export interface StatsResponse {
  total_files: number;
  total_chunks: number;
  file_types: Record<string, number>;
  storage_size_mb: number;
  last_indexed_at: string | null;
  top_searches: string[];
}

// Voice
export interface TranscribeResponse {
  text: string;
  duration_ms: number;
}

export interface SynthesizeRequest {
  text: string;
}
