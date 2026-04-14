import type {
  SearchResponse,
  IndexedFile,
  StatsResponse,
  TranscribeResponse,
} from "@/types";

const API_BASE = "";

/** Read the API key from localStorage (set on the Settings page). */
function getApiKey(): string | null {
  return localStorage.getItem("locallens_api_key") || null;
}

/** Read the active namespace from localStorage. */
function getNamespace(): string {
  return localStorage.getItem("locallens_namespace") || "default";
}

function authHeaders(): Record<string, string> {
  const key = getApiKey();
  if (key) return { Authorization: `Bearer ${key}` };
  return {};
}

function nsParam(extra?: string): string {
  const ns = getNamespace();
  const base = `namespace=${encodeURIComponent(ns)}`;
  return extra ? `${base}&${extra}` : base;
}

async function get<T>(path: string): Promise<T> {
  const sep = path.includes("?") ? "&" : "?";
  const res = await fetch(`${API_BASE}${path}${sep}${nsParam()}`, {
    headers: { ...authHeaders() },
  });
  if (!res.ok) throw new Error(`GET ${path}: ${res.statusText}`);
  return res.json();
}

async function getNoNs<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { ...authHeaders() },
  });
  if (!res.ok) throw new Error(`GET ${path}: ${res.statusText}`);
  return res.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const sep = path.includes("?") ? "&" : "?";
  const res = await fetch(`${API_BASE}${path}${sep}${nsParam()}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${path}: ${res.statusText}`);
  return res.json();
}

async function postNoNs<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${path}: ${res.statusText}`);
  return res.json();
}

async function del(path: string): Promise<void> {
  const sep = path.includes("?") ? "&" : "?";
  const res = await fetch(`${API_BASE}${path}${sep}${nsParam()}`, {
    method: "DELETE",
    headers: { ...authHeaders() },
  });
  if (!res.ok) throw new Error(`DELETE ${path}: ${res.statusText}`);
}

async function postFormData<T>(path: string, audio: Blob): Promise<T> {
  const form = new FormData();
  form.append("file", audio, "audio.webm");
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { ...authHeaders() },
    body: form,
  });
  if (!res.ok) throw new Error(`POST ${path}: ${res.statusText}`);
  return res.json();
}

async function postAudio(
  path: string,
  body: unknown
): Promise<ArrayBuffer> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${path}: ${res.statusText}`);
  return res.arrayBuffer();
}

export interface AuditEntry {
  id: number;
  timestamp: string;
  operation: string;
  namespace: string;
  api_key_hash: string | null;
  detail: string | null;
}

export interface AuditResponse {
  entries: AuditEntry[];
  total: number;
  page: number;
  page_size: number;
}

export const api = {
  // Index
  startIndex: (path: string, force: boolean) =>
    post<{ task_id: string }>("/api/index", { folder_path: path, force }),
  getFiles: () => get<IndexedFile[]>("/api/files"),
  deleteFile: (path: string) =>
    del(`/api/files/${encodeURIComponent(path)}`),

  // Search
  search: (
    query: string,
    topK: number,
    fileType?: string | null,
    pathPrefix?: string | null,
    mode?: string,
    dateFrom?: string | null,
    dateTo?: string | null,
  ) =>
    post<SearchResponse>("/api/search", {
      query,
      top_k: topK,
      file_type: fileType || null,
      path_prefix: pathPrefix || null,
      mode: mode || "hybrid",
      date_from: dateFrom || null,
      date_to: dateTo || null,
    }),

  // Ask (SSE -- handled in hook)
  askUrl: () => `${API_BASE}/api/ask?${nsParam()}`,
  askHeaders: () => ({ "Content-Type": "application/json", ...authHeaders() }),

  // Voice
  transcribe: (audio: Blob) =>
    postFormData<TranscribeResponse>("/api/voice/transcribe", audio),
  synthesize: (text: string) =>
    postAudio("/api/voice/synthesize", { text }),
  voiceConversation: (audio: Blob) =>
    postFormData<{ transcription: string; intent: string; response_text: string; audio_url?: string; sources?: unknown[] }>(
      "/api/voice/conversation",
      audio
    ),

  // Stats
  getStats: () => get<StatsResponse>("/api/stats"),

  // Filesystem
  pickFolder: () =>
    postNoNs<{ path: string | null; cancelled: boolean }>("/api/fs/pick-folder", {}),

  // Health
  checkHealth: () => getNoNs<{ status: string }>("/api/health"),

  // Namespaces
  getNamespaces: () =>
    getNoNs<{ namespaces: string[] }>("/api/namespaces"),
  createNamespace: (namespace: string) =>
    postNoNs<{ namespace: string; collection: string }>("/api/namespaces", { namespace }),

  // Auth
  getAuthStatus: () =>
    getNoNs<{ auth_enabled: boolean; authenticated: boolean }>("/api/auth/status"),

  // Audit
  getAuditLog: (page = 1, pageSize = 50, operation?: string, namespace?: string) => {
    const params = new URLSearchParams();
    params.set("page", String(page));
    params.set("page_size", String(pageSize));
    if (operation) params.set("operation", operation);
    if (namespace) params.set("namespace", namespace);
    return getNoNs<AuditResponse>(`/api/audit?${params.toString()}`);
  },

  // Helpers
  getNamespace,
  getApiKey,
};
