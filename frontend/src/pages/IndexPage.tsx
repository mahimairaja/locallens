import { useState, useEffect, useRef, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Trash2, Loader2, FolderOpen, Eye, EyeOff, CheckCircle2, Pause, Square } from "lucide-react";
import { api } from "@/lib/api";
import type { IndexProgress, IndexedFile } from "@/types";
import { motion, AnimatePresence } from "framer-motion";

/** Returns a human-readable relative time string. */
function relativeTime(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffSec = Math.floor((now - then) / 1000);
  if (diffSec < 60) return "just now";
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 30) return `${diffDay}d ago`;
  const diffMon = Math.floor(diffDay / 30);
  if (diffMon < 12) return `${diffMon}mo ago`;
  return `${Math.floor(diffMon / 12)}y ago`;
}

/** Returns the colored pill CSS class for a file type extension. */
function typePillClass(ext: string): string {
  const e = ext.replace(".", "").toLowerCase();
  const map: Record<string, string> = {
    pdf: "sk-pill-pdf", txt: "sk-pill-txt", py: "sk-pill-py", md: "sk-pill-md",
    js: "sk-pill-js", ts: "sk-pill-ts", docx: "sk-pill-docx", csv: "sk-pill-csv",
    html: "sk-pill-html", go: "sk-pill-go", rs: "sk-pill-rs", java: "sk-pill-java",
    rb: "sk-pill-rb", c: "sk-pill-c", cpp: "sk-pill-cpp",
  };
  return map[e] || "sk-tab-default";
}

/** All supported file type extensions (from backend config). */
const ALL_FILE_TYPES = [
  ".pdf", ".md", ".docx", ".xlsx", ".xls", ".csv", ".tsv",
  ".txt", ".html", ".py", ".js", ".ts", ".go", ".rs",
  ".java", ".c", ".cpp", ".rb", ".pptx", ".eml", ".epub",
];

/** Default excluded directories. */
const EXCLUDED_DIRS = "node_modules, .git, __pycache__, .venv";

const PAGE_SIZE = 10;

/** Formats seconds into "Xm Ys" or "Ys". */
function formatEta(seconds: number): string {
  if (seconds <= 0) return "--";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

export default function IndexPage() {
  const [folderPath, setFolderPath] = useState("");
  const [force, setForce] = useState(false);
  const [isIndexing, setIsIndexing] = useState(false);
  const [isPicking, setIsPicking] = useState(false);
  const [progress, setProgress] = useState<IndexProgress | null>(null);
  const [files, setFiles] = useState<IndexedFile[]>([]);
  const [filesLoading, setFilesLoading] = useState(true);
  const [watchStatus, setWatchStatus] = useState<{ running: boolean; folders: string[] }>({ running: false, folders: [] });
  const [fileLog, setFileLog] = useState<string[]>([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [enabledTypes, setEnabledTypes] = useState<Set<string>>(new Set(ALL_FILE_TYPES));
  const wsRef = useRef<WebSocket | null>(null);
  const logRef = useRef<HTMLDivElement | null>(null);

  const loadFiles = () => {
    api
      .getFiles()
      .then(setFiles)
      .catch(() => {})
      .finally(() => setFilesLoading(false));
  };

  const loadWatchStatus = () => {
    fetch("/api/watcher/status")
      .then((r) => r.json())
      .then(setWatchStatus)
      .catch(() => {});
  };

  const toggleWatch = async (folder: string) => {
    const isWatched = watchStatus.folders.includes(folder);
    const endpoint = isWatched ? "/api/watcher/unwatch" : "/api/watcher/watch";
    await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ folder }),
    });
    loadWatchStatus();
  };

  useEffect(() => {
    loadFiles();
    loadWatchStatus();
  }, []);

  const startIndexing = async () => {
    if (!folderPath.trim()) return;
    setIsIndexing(true);
    setFileLog([]);
    setProgress({ status: "scanning", current_file: null, files_processed: 0, files_total: 0, chunks_created: 0, elapsed_seconds: 0 });

    try {
      const { task_id } = await api.startIndex(folderPath, force);

      // Connect WebSocket for progress
      const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const ws = new WebSocket(
        `${wsProtocol}//${window.location.host}/api/index/progress/${task_id}`
      );
      wsRef.current = ws;

      ws.onmessage = (event) => {
        const data: IndexProgress = JSON.parse(event.data);
        setProgress(data);
        // Append to file log
        if (data.current_file) {
          setFileLog((prev) => {
            const last = prev[prev.length - 1];
            if (last === data.current_file) return prev;
            return [...prev, data.current_file!];
          });
        }
        if (data.status === "done" || data.status === "error") {
          setIsIndexing(false);
          ws.close();
          loadFiles();
        }
      };

      ws.onerror = () => {
        setIsIndexing(false);
        setProgress((p) =>
          p ? { ...p, status: "error", error: "WebSocket connection failed" } : null
        );
      };
    } catch {
      setIsIndexing(false);
      setProgress({
        status: "error",
        current_file: null,
        files_processed: 0,
        files_total: 0,
        chunks_created: 0,
        elapsed_seconds: 0,
        error: "Failed to start indexing",
      });
    }
  };

  const stopIndexing = () => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsIndexing(false);
    setProgress((p) => p ? { ...p, status: "done" } : null);
    loadFiles();
  };

  // Auto-scroll file log
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [fileLog]);

  const deleteFile = async (filePath: string) => {
    await api.deleteFile(filePath);
    loadFiles();
  };

  const browseFolder = async () => {
    if (isIndexing || isPicking) return;
    setIsPicking(true);
    try {
      const result = await api.pickFolder();
      if (!result.cancelled && result.path) {
        setFolderPath(result.path);
      }
    } catch {
      // Silently ignore -- user can still type the path manually.
    } finally {
      setIsPicking(false);
    }
  };

  const progressPercent =
    progress && progress.files_total > 0
      ? Math.round((progress.files_processed / progress.files_total) * 100)
      : 0;

  // ETA estimation based on elapsed time and progress
  const etaSeconds = useMemo(() => {
    if (!progress || progress.files_total === 0 || progress.files_processed === 0) return 0;
    const rate = progress.elapsed_seconds / progress.files_processed;
    const remaining = progress.files_total - progress.files_processed;
    return rate * remaining;
  }, [progress]);

  // Pagination
  const totalPages = Math.max(1, Math.ceil(files.length / PAGE_SIZE));
  const paginatedFiles = useMemo(() => {
    const start = (currentPage - 1) * PAGE_SIZE;
    return files.slice(start, start + PAGE_SIZE);
  }, [files, currentPage]);

  // Reset to page 1 when files change
  useEffect(() => {
    setCurrentPage(1);
  }, [files.length]);

  // Toggle a file type filter chip
  const toggleFileType = (ext: string) => {
    setEnabledTypes((prev) => {
      const next = new Set(prev);
      if (next.has(ext)) next.delete(ext);
      else next.add(ext);
      return next;
    });
  };

  // File type summary from indexed files
  const fileTypeCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    files.forEach((f) => {
      const ext = f.file_type;
      counts[ext] = (counts[ext] || 0) + 1;
    });
    return Object.entries(counts).sort((a, b) => b[1] - a[1]);
  }, [files]);

  const isActive = isIndexing && progress && (progress.status === "scanning" || progress.status === "indexing");
  const isDone = progress?.status === "done";
  const isError = progress?.status === "error";
  const isWatched = folderPath ? watchStatus.folders.includes(folderPath) : false;
  const namespace = localStorage.getItem("locallens_namespace") || "default";

  return (
    <div className="space-y-6">
      {/* ============================================================
          Two-column grid: controls (left 55%) + progress (right 45%)
          ============================================================ */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "55fr 45fr",
          gap: "1.5rem",
          alignItems: "start",
        }}
      >
        {/* ── LEFT COLUMN: Controls ─────────────────────────────── */}
        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>

          {/* Folder box */}
          <Card>
            <CardContent className="p-5">
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: "0.75rem",
                }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <label
                    style={{
                      fontFamily: "var(--font-sans)",
                      fontSize: "0.7rem",
                      fontWeight: 600,
                      textTransform: "uppercase",
                      letterSpacing: "0.08em",
                      color: "var(--text-tertiary)",
                      marginBottom: "0.35rem",
                      display: "block",
                    }}
                  >
                    Folder
                  </label>
                  {folderPath ? (
                    <p
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: "0.88rem",
                        color: "var(--text-primary)",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {folderPath}
                    </p>
                  ) : (
                    <p
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: "0.88rem",
                        color: "var(--text-tertiary)",
                        fontStyle: "italic",
                      }}
                    >
                      ~/Documents/my-project
                    </p>
                  )}
                </div>
                <button
                  type="button"
                  onClick={browseFolder}
                  disabled={isIndexing || isPicking}
                  style={{
                    fontFamily: "var(--font-sans)",
                    fontSize: "0.8rem",
                    fontWeight: 500,
                    color: "var(--text-secondary)",
                    background: "none",
                    border: "none",
                    cursor: isIndexing || isPicking ? "default" : "pointer",
                    opacity: isIndexing || isPicking ? 0.5 : 1,
                    padding: "0.25rem 0.5rem",
                    borderRadius: "var(--radius-sm)",
                    transition: "color 150ms ease",
                    display: "flex",
                    alignItems: "center",
                    gap: "0.35rem",
                    flexShrink: 0,
                  }}
                  onMouseEnter={(e) => { if (!isIndexing && !isPicking) (e.currentTarget.style.color = "var(--accent)"); }}
                  onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-secondary)"; }}
                >
                  {isPicking ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <FolderOpen className="h-3.5 w-3.5" />
                  )}
                  change
                </button>
              </div>
              {/* Hidden input for keyboard entry */}
              <input
                type="text"
                value={folderPath}
                onChange={(e) => setFolderPath(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && startIndexing()}
                placeholder="type a path..."
                style={{
                  width: "100%",
                  marginTop: "0.5rem",
                  fontFamily: "var(--font-mono)",
                  fontSize: "0.8rem",
                  color: "var(--text-primary)",
                  background: "var(--bg-page)",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius-sm)",
                  padding: "0.4rem 0.6rem",
                  outline: "none",
                  transition: "border-color 150ms ease",
                }}
                onFocus={(e) => { e.currentTarget.style.borderColor = "var(--accent)"; }}
                onBlur={(e) => { e.currentTarget.style.borderColor = "var(--border)"; }}
              />
            </CardContent>
          </Card>

          {/* Watch mode box */}
          <Card>
            <CardContent className="p-5">
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: "1rem",
                }}
              >
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.25rem" }}>
                    <label
                      style={{
                        fontFamily: "var(--font-sans)",
                        fontSize: "0.7rem",
                        fontWeight: 600,
                        textTransform: "uppercase",
                        letterSpacing: "0.08em",
                        color: "var(--text-tertiary)",
                      }}
                    >
                      Watch mode
                    </label>
                    <span
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: "0.65rem",
                        fontWeight: 600,
                        padding: "0.1rem 0.45rem",
                        borderRadius: "9999px",
                        background: isWatched ? "var(--accent)" : "var(--bg-hover)",
                        color: isWatched ? "var(--text-on-accent)" : "var(--text-tertiary)",
                        letterSpacing: "0.04em",
                      }}
                    >
                      {isWatched ? "ON" : "OFF"}
                    </span>
                  </div>
                  <p
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: "0.72rem",
                      color: "var(--text-tertiary)",
                    }}
                  >
                    re-indexes on save . debounced 2s
                  </p>
                </div>
                <button
                  type="button"
                  className={`sk-toggle ${isWatched ? "active" : ""}`}
                  onClick={() => folderPath && toggleWatch(folderPath)}
                  disabled={!folderPath}
                  aria-label="Toggle watch mode"
                  style={{ opacity: folderPath ? 1 : 0.4 }}
                />
              </div>
            </CardContent>
          </Card>

          {/* Filters box */}
          <Card>
            <CardContent className="p-5">
              <label
                style={{
                  fontFamily: "var(--font-sans)",
                  fontSize: "0.7rem",
                  fontWeight: 600,
                  textTransform: "uppercase",
                  letterSpacing: "0.08em",
                  color: "var(--text-tertiary)",
                  marginBottom: "0.6rem",
                  display: "block",
                }}
              >
                File types
              </label>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem", marginBottom: "0.75rem" }}>
                {ALL_FILE_TYPES.map((ext) => {
                  const active = enabledTypes.has(ext);
                  return (
                    <button
                      key={ext}
                      type="button"
                      onClick={() => toggleFileType(ext)}
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: "0.72rem",
                        fontWeight: 500,
                        padding: "0.2rem 0.55rem",
                        borderRadius: "9999px",
                        border: `1px solid ${active ? "var(--accent)" : "var(--border)"}`,
                        background: active ? "rgba(198, 123, 60, 0.1)" : "var(--bg-card)",
                        color: active ? "var(--accent)" : "var(--text-tertiary)",
                        cursor: "pointer",
                        transition: "all 120ms ease",
                      }}
                    >
                      {ext}
                    </button>
                  );
                })}
              </div>
              <p
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: "0.68rem",
                  color: "var(--text-tertiary)",
                }}
              >
                exclude: {EXCLUDED_DIRS}
              </p>
            </CardContent>
          </Card>

          {/* Force re-index toggle */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.75rem",
              padding: "0 0.25rem",
            }}
          >
            <button
              type="button"
              className={`sk-toggle ${force ? "active" : ""}`}
              onClick={() => setForce(!force)}
              aria-label="Force re-index"
            />
            <div>
              <span
                style={{
                  color: "var(--text-secondary)",
                  fontFamily: "var(--font-sans)",
                  fontSize: "0.82rem",
                  fontWeight: 500,
                }}
              >
                Force re-index
              </span>
              <p
                style={{
                  color: "var(--text-tertiary)",
                  fontFamily: "var(--font-sans)",
                  fontSize: "0.7rem",
                  marginTop: "1px",
                }}
              >
                Re-processes all files, even if unchanged
              </p>
            </div>
          </div>
        </div>

        {/* ── RIGHT COLUMN: Progress / Idle ─────────────────────── */}
        <div>
          <AnimatePresence mode="wait">
            {isActive ? (
              /* ──── Active indexing state ──── */
              <motion.div
                key="active"
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 8 }}
                style={{
                  background: "var(--bg-accent-light)",
                  border: "1px solid var(--accent-soft)",
                  borderRadius: "var(--radius-lg)",
                  padding: "2rem 1.75rem",
                  minHeight: "360px",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between",
                }}
              >
                {/* Big number display */}
                <div>
                  <div
                    style={{
                      fontFamily: "'Caveat', cursive",
                      fontSize: "4rem",
                      fontWeight: 700,
                      lineHeight: 1,
                      color: "var(--accent-hover)",
                      letterSpacing: "-0.02em",
                    }}
                  >
                    {progress!.files_processed}
                    <span style={{ fontSize: "2.2rem", color: "var(--text-tertiary)", fontWeight: 400 }}>
                      /{progress!.files_total}
                    </span>
                  </div>
                  <p
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: "0.75rem",
                      color: "var(--text-secondary)",
                      marginTop: "0.25rem",
                    }}
                  >
                    files . {progressPercent}%
                  </p>
                </div>

                {/* Progress bar */}
                <div
                  style={{
                    margin: "1.25rem 0",
                  }}
                >
                  <div
                    style={{
                      height: "8px",
                      background: "rgba(255,255,255,0.7)",
                      border: "1px solid var(--accent-soft)",
                      borderRadius: "9999px",
                      overflow: "hidden",
                    }}
                  >
                    <motion.div
                      style={{
                        height: "100%",
                        background: "var(--accent)",
                        borderRadius: "9999px",
                      }}
                      initial={{ width: 0 }}
                      animate={{ width: `${progressPercent}%` }}
                      transition={{ duration: 0.3 }}
                    />
                  </div>
                </div>

                {/* Current file + ETA */}
                <div style={{ marginBottom: "1rem" }}>
                  {progress!.current_file && (
                    <p
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: "0.72rem",
                        color: "var(--text-secondary)",
                        marginBottom: "0.35rem",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      current . {progress!.current_file}
                    </p>
                  )}
                  <p
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: "0.72rem",
                      color: "var(--text-secondary)",
                      marginBottom: "0.35rem",
                    }}
                  >
                    eta . {formatEta(etaSeconds)}
                  </p>
                  <p
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: "0.72rem",
                      color: "var(--text-tertiary)",
                    }}
                  >
                    {progress!.chunks_created} chunks . {progress!.elapsed_seconds.toFixed(1)}s elapsed
                  </p>
                </div>

                {/* File log */}
                {fileLog.length > 0 && (
                  <div className="sk-file-log" ref={logRef} style={{ maxHeight: "120px", marginBottom: "1rem" }}>
                    {fileLog.map((f, i) => (
                      <div key={i} className="sk-file-log-entry">
                        <span style={{ color: "var(--accent)", marginRight: "0.5rem" }}>
                          {i < fileLog.length - 1 ? "\u2713" : "\u2026"}
                        </span>
                        {f}
                      </div>
                    ))}
                  </div>
                )}

                {/* Stop button */}
                <div style={{ display: "flex", gap: "0.5rem" }}>
                  <button
                    type="button"
                    onClick={stopIndexing}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "0.4rem",
                      fontFamily: "var(--font-sans)",
                      fontSize: "0.8rem",
                      fontWeight: 500,
                      padding: "0.45rem 1rem",
                      borderRadius: "var(--radius-md)",
                      border: "1px solid var(--border-strong)",
                      background: "var(--bg-card)",
                      color: "var(--text-secondary)",
                      cursor: "pointer",
                      transition: "all 150ms ease",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.borderColor = "var(--danger)";
                      e.currentTarget.style.color = "var(--danger)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.borderColor = "var(--border-strong)";
                      e.currentTarget.style.color = "var(--text-secondary)";
                    }}
                  >
                    <Square className="h-3.5 w-3.5" />
                    Stop
                  </button>
                </div>
              </motion.div>
            ) : isDone ? (
              /* ──── Completion state ──── */
              <motion.div
                key="done"
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 8 }}
              >
                <Card className="sk-completion-card">
                  <CardContent className="p-6" style={{ minHeight: "200px", display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", textAlign: "center" }}>
                    <CheckCircle2
                      style={{ color: "var(--success)", width: "36px", height: "36px", marginBottom: "1rem" }}
                    />
                    <p style={{
                      fontFamily: "'Caveat', cursive",
                      fontSize: "2.4rem",
                      fontWeight: 700,
                      color: "var(--text-primary)",
                      lineHeight: 1.1,
                    }}>
                      Done
                    </p>
                    <p style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: "0.75rem",
                      color: "var(--text-secondary)",
                      marginTop: "0.5rem",
                    }}>
                      {progress!.files_processed} files . {progress!.chunks_created} chunks . {progress!.elapsed_seconds.toFixed(1)}s
                    </p>
                    <Button
                      onClick={() => setProgress(null)}
                      style={{ marginTop: "1.25rem" }}
                    >
                      Index another folder
                    </Button>
                  </CardContent>
                </Card>
              </motion.div>
            ) : isError ? (
              /* ──── Error state ──── */
              <motion.div
                key="error"
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 8 }}
              >
                <Card>
                  <CardContent className="p-6" style={{ minHeight: "200px", display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", textAlign: "center" }}>
                    <p style={{
                      fontFamily: "var(--font-sans)",
                      fontSize: "0.9rem",
                      fontWeight: 600,
                      color: "var(--danger)",
                      marginBottom: "0.5rem",
                    }}>
                      Indexing failed
                    </p>
                    <p style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: "0.75rem",
                      color: "var(--text-secondary)",
                    }}>
                      {progress?.error ?? "Unknown error"}
                    </p>
                    <Button
                      onClick={() => { setProgress(null); }}
                      style={{ marginTop: "1rem" }}
                    >
                      Try again
                    </Button>
                  </CardContent>
                </Card>
              </motion.div>
            ) : (
              /* ──── Idle state: CTA + file preview ──── */
              <motion.div
                key="idle"
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 8 }}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "1rem",
                }}
              >
                {/* Drop zone / CTA */}
                <div
                  style={{
                    border: "2px dashed var(--border-strong)",
                    borderRadius: "var(--radius-lg)",
                    padding: "2.5rem 1.5rem",
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    justifyContent: "center",
                    textAlign: "center",
                    minHeight: "220px",
                    background: "var(--bg-card)",
                    transition: "border-color 150ms ease",
                  }}
                >
                  <p
                    style={{
                      fontFamily: "'Caveat', cursive",
                      fontSize: "2rem",
                      fontWeight: 600,
                      color: "var(--text-primary)",
                      lineHeight: 1.2,
                      marginBottom: "0.5rem",
                    }}
                  >
                    Index a folder
                  </p>
                  <p
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: "0.75rem",
                      color: "var(--text-tertiary)",
                      marginBottom: "1.25rem",
                    }}
                  >
                    drop a folder here or choose one
                  </p>
                  <Button
                    onClick={folderPath.trim() ? startIndexing : browseFolder}
                    disabled={isPicking}
                    style={{ minWidth: "160px" }}
                  >
                    {isPicking ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <FolderOpen className="mr-2 h-4 w-4" />
                    )}
                    {folderPath.trim() ? "Start indexing" : "Choose folder"}
                  </Button>
                </div>

                {/* File type preview from existing index */}
                {fileTypeCounts.length > 0 && (
                  <Card>
                    <CardContent className="p-4">
                      <label
                        style={{
                          fontFamily: "var(--font-sans)",
                          fontSize: "0.7rem",
                          fontWeight: 600,
                          textTransform: "uppercase",
                          letterSpacing: "0.08em",
                          color: "var(--text-tertiary)",
                          marginBottom: "0.5rem",
                          display: "block",
                        }}
                      >
                        Indexed files by type
                      </label>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
                        {fileTypeCounts.map(([ext, count]) => (
                          <span
                            key={ext}
                            style={{
                              fontFamily: "var(--font-mono)",
                              fontSize: "0.75rem",
                              color: "var(--text-secondary)",
                            }}
                          >
                            <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>{ext}</span>
                            {" "}
                            <span style={{ color: "var(--accent)" }}>x{count}</span>
                          </span>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* ============================================================
          Indexed Files table (full width below the two columns)
          ============================================================ */}
      <Card>
        <CardHeader>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <CardTitle className="text-base">Indexed Files</CardTitle>
            <span
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: "0.7rem",
                color: "var(--text-tertiary)",
              }}
            >
              {files.length} files
            </span>
          </div>
        </CardHeader>
        <CardContent>
          {filesLoading ? (
            /* Skeleton rows with shimmer */
            <div className="space-y-2">
              {[0, 1, 2].map((i) => (
                <div
                  key={i}
                  className="sk-skeleton"
                  style={{ height: "44px", width: "100%" }}
                />
              ))}
            </div>
          ) : files.length === 0 ? (
            <p className="sk-empty">No files indexed yet -- choose a folder above to get started.</p>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>File Name</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Chunks</TableHead>
                    <TableHead>Indexed</TableHead>
                    <TableHead className="w-12" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {paginatedFiles.map((file, idx) => (
                    <TableRow
                      key={file.file_path}
                      style={{
                        backgroundColor: idx % 2 === 1
                          ? "rgba(198, 123, 60, 0.02)"
                          : "var(--bg-card)",
                        transition: "background-color 150ms ease",
                      }}
                      onMouseEnter={(e) => {
                        (e.currentTarget as HTMLElement).style.backgroundColor = "rgba(198, 123, 60, 0.06)";
                      }}
                      onMouseLeave={(e) => {
                        (e.currentTarget as HTMLElement).style.backgroundColor =
                          idx % 2 === 1 ? "rgba(198, 123, 60, 0.02)" : "var(--bg-card)";
                      }}
                    >
                      <TableCell
                        style={{
                          color: "var(--text-primary)",
                          fontWeight: 500,
                          fontFamily: "var(--font-sans)",
                          fontSize: "0.875rem",
                        }}
                      >
                        {file.file_name}
                      </TableCell>
                      <TableCell>
                        <Badge className={typePillClass(file.file_type)}>{file.file_type}</Badge>
                      </TableCell>
                      <TableCell style={{ fontFamily: "var(--font-mono)", color: "var(--text-primary)", fontSize: "0.85rem" }}>
                        {file.chunk_count}
                      </TableCell>
                      <TableCell>
                        {file.indexed_at ? (
                          <span className="sk-timestamp">
                            <span style={{ color: "var(--text-tertiary)", fontFamily: "var(--font-mono)", fontSize: "0.75rem" }}>
                              {relativeTime(file.indexed_at)}
                            </span>
                            <span className="sk-timestamp-tooltip">
                              {new Date(file.indexed_at).toLocaleString()}
                            </span>
                          </span>
                        ) : (
                          <span style={{ color: "var(--text-tertiary)" }}>&mdash;</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="icon-xs"
                          className="sk-delete-btn"
                          onClick={() => deleteFile(file.file_path)}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              {/* Pagination */}
              {totalPages > 1 && (
                <div
                  className="flex items-center justify-center gap-2 pt-4"
                  style={{ fontFamily: "var(--font-sans)", fontSize: "0.8rem" }}
                >
                  <button
                    type="button"
                    disabled={currentPage <= 1}
                    onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                    style={{
                      padding: "0.3rem 0.6rem",
                      borderRadius: "var(--radius-sm)",
                      border: "1px solid var(--border)",
                      background: "var(--bg-card)",
                      color: currentPage <= 1 ? "var(--text-tertiary)" : "var(--text-primary)",
                      cursor: currentPage <= 1 ? "default" : "pointer",
                      opacity: currentPage <= 1 ? 0.5 : 1,
                    }}
                  >
                    Prev
                  </button>
                  <span style={{ color: "var(--text-secondary)" }}>
                    Page {currentPage} of {totalPages}
                  </span>
                  <button
                    type="button"
                    disabled={currentPage >= totalPages}
                    onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                    style={{
                      padding: "0.3rem 0.6rem",
                      borderRadius: "var(--radius-sm)",
                      border: "1px solid var(--border)",
                      background: "var(--bg-card)",
                      color: currentPage >= totalPages ? "var(--text-tertiary)" : "var(--text-primary)",
                      cursor: currentPage >= totalPages ? "default" : "pointer",
                      opacity: currentPage >= totalPages ? 0.5 : 1,
                    }}
                  >
                    Next
                  </button>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
