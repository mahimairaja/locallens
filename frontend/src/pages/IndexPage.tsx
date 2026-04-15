import { useState, useEffect, useRef, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { FolderSync, Trash2, Loader2, FolderOpen, Eye, EyeOff, CheckCircle2 } from "lucide-react";
import { api } from "@/lib/api";
import type { IndexProgress, IndexedFile } from "@/types";
import { motion } from "framer-motion";

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

const PAGE_SIZE = 10;

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

  return (
    <div className="space-y-6">
      {/* Folder Input -- Step 12 */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Index a Folder</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Path input + button group with consistent heights */}
          <div className="flex gap-2">
            <Input
              placeholder="~/Documents/my-project"
              value={folderPath}
              onChange={(e) => setFolderPath(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && startIndexing()}
              className="flex-1"
              style={{
                fontFamily: "var(--font-mono)",
                fontStyle: folderPath ? "normal" : "italic",
                fontSize: "0.9rem",
                height: "42px",
              }}
            />
            <button
              type="button"
              onClick={browseFolder}
              disabled={isIndexing || isPicking}
              title="Browse for a folder"
              aria-label="Browse for a folder"
              className="flex items-center gap-1.5 rounded-[var(--radius-md)] px-3 text-sm transition-all disabled:opacity-50"
              style={{
                background: "var(--bg-card)",
                color: "var(--text-primary)",
                border: "1px solid var(--border)",
                boxShadow: "var(--shadow-xs)",
                fontFamily: "var(--font-sans)",
                fontWeight: 500,
                height: "42px",
              }}
            >
              {isPicking ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <FolderOpen className="h-4 w-4" style={{ color: "var(--text-secondary)" }} />
              )}
              Browse
            </button>
            <Button
              onClick={startIndexing}
              disabled={isIndexing || !folderPath.trim()}
              style={{ height: "42px" }}
            >
              {isIndexing ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <FolderSync className="mr-2 h-4 w-4" />
              )}
              {isIndexing ? "Indexing..." : "Start Indexing"}
            </Button>
          </div>

          {/* Toggle switch instead of checkbox -- Step 12 */}
          <div className="flex items-center gap-3">
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
                  fontSize: "0.875rem",
                  fontWeight: 500,
                }}
              >
                Force re-index
              </span>
              <p
                style={{
                  color: "var(--text-tertiary)",
                  fontFamily: "var(--font-sans)",
                  fontSize: "0.75rem",
                  marginTop: "2px",
                }}
              >
                Re-processes all files, even if unchanged
              </p>
            </div>
          </div>

          {folderPath && (
            <button
              type="button"
              onClick={() => toggleWatch(folderPath)}
              className="flex items-center gap-1.5 text-sm"
              style={{
                color: watchStatus.folders.includes(folderPath) ? "var(--accent)" : "var(--text-tertiary)",
                fontFamily: "var(--font-sans)",
                fontWeight: 500,
              }}
            >
              {watchStatus.folders.includes(folderPath) ? (
                <><Eye className="h-3.5 w-3.5" /> Watching for changes</>
              ) : (
                <><EyeOff className="h-3.5 w-3.5" /> Enable auto-watch</>
              )}
            </button>
          )}
        </CardContent>
      </Card>

      {/* Progress -- Step 14: copper progress bar + live file log */}
      {progress && (progress.status === "scanning" || progress.status === "indexing") && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <Card>
            <CardContent className="space-y-3 p-6">
              <div className="flex items-center justify-between text-sm">
                <span style={{ color: "var(--text-primary)", fontWeight: 500 }}>
                  {progress.status === "scanning" ? "Scanning files..." : "Indexing..."}
                </span>
                <span style={{ color: "var(--text-secondary)", fontFamily: "var(--font-mono)", fontSize: "0.75rem" }}>
                  {progress.files_processed}/{progress.files_total} files &middot; {progress.chunks_created} chunks &middot; {progress.elapsed_seconds.toFixed(1)}s
                </span>
              </div>
              {/* Copper progress bar */}
              <div
                style={{
                  height: "8px",
                  background: "var(--bg-hover)",
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
              {/* Live file log -- Step 14 */}
              {fileLog.length > 0 && (
                <div className="sk-file-log" ref={logRef}>
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
              {progress.current_file && fileLog.length === 0 && (
                <p
                  className="truncate text-xs"
                  style={{ color: "var(--text-tertiary)", fontFamily: "var(--font-mono)" }}
                >
                  {progress.current_file}
                </p>
              )}
            </CardContent>
          </Card>
        </motion.div>
      )}

      {/* Error */}
      {progress?.status === "error" && (
        <Card>
          <CardContent
            className="p-6 text-sm"
            style={{ color: "var(--danger)", fontFamily: "var(--font-sans)" }}
          >
            Error: {progress.error ?? "Unknown error"}
          </CardContent>
        </Card>
      )}

      {/* Done -- Step 14: completion summary card with fade-up */}
      {progress?.status === "done" && (
        <Card className="sk-completion-card">
          <CardContent className="flex items-center gap-3 p-6">
            <CheckCircle2
              style={{ color: "var(--success)", width: "24px", height: "24px", flexShrink: 0 }}
            />
            <div>
              <p style={{ fontFamily: "var(--font-sans)", fontSize: "0.95rem", fontWeight: 600, color: "var(--text-primary)" }}>
                Indexing Complete
              </p>
              <p style={{ fontFamily: "var(--font-sans)", fontSize: "0.8rem", color: "var(--text-secondary)", marginTop: "2px" }}>
                Indexed {progress.files_processed} files, {progress.chunks_created} chunks in {progress.elapsed_seconds.toFixed(1)}s
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Indexed Files -- Step 13 */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Indexed Files</CardTitle>
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
            <p className="sk-empty">No files indexed yet -- enter a folder path above to get started.</p>
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
                        {/* Colored file type pill -- Step 13 */}
                        <Badge className={typePillClass(file.file_type)}>{file.file_type}</Badge>
                      </TableCell>
                      <TableCell style={{ fontFamily: "var(--font-mono)", color: "var(--text-primary)", fontSize: "0.85rem" }}>
                        {file.chunk_count}
                      </TableCell>
                      <TableCell>
                        {/* Relative timestamp with tooltip -- Step 13 */}
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
                        {/* Delete button: muted by default, red on hover -- Step 13 */}
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

              {/* Pagination -- Step 13 */}
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
