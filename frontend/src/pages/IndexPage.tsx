import { useState, useEffect, useRef } from "react";
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
import { FolderSync, Trash2, Loader2, FolderOpen } from "lucide-react";
import { api } from "@/lib/api";
import type { IndexProgress, IndexedFile } from "@/types";
import { motion } from "framer-motion";

export default function IndexPage() {
  const [folderPath, setFolderPath] = useState("");
  const [force, setForce] = useState(false);
  const [isIndexing, setIsIndexing] = useState(false);
  const [isPicking, setIsPicking] = useState(false);
  const [progress, setProgress] = useState<IndexProgress | null>(null);
  const [files, setFiles] = useState<IndexedFile[]>([]);
  const [filesLoading, setFilesLoading] = useState(true);
  const wsRef = useRef<WebSocket | null>(null);

  const loadFiles = () => {
    api
      .getFiles()
      .then(setFiles)
      .catch(() => {})
      .finally(() => setFilesLoading(false));
  };

  useEffect(() => {
    loadFiles();
  }, []);

  const startIndexing = async () => {
    if (!folderPath.trim()) return;
    setIsIndexing(true);
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
      // Silently ignore — user can still type the path manually.
    } finally {
      setIsPicking(false);
    }
  };

  const progressPercent =
    progress && progress.files_total > 0
      ? Math.round((progress.files_processed / progress.files_total) * 100)
      : 0;

  const typeTabClass = (ext: string) => {
    const e = ext.replace(".", "").toLowerCase();
    if (e === "pdf") return "sk-tab-pdf";
    if (e === "py") return "sk-tab-py";
    if (e === "md") return "sk-tab-md";
    if (e === "docx") return "sk-tab-docx";
    if (e === "txt") return "sk-tab-txt";
    if (e === "js") return "sk-tab-js";
    if (e === "ts") return "sk-tab-ts";
    return "sk-tab-default";
  };

  return (
    <div className="space-y-6">
      {/* Folder Input */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Index a Folder</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Input
              placeholder="~/Documents/my-project"
              value={folderPath}
              onChange={(e) => setFolderPath(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && startIndexing()}
              className="flex-1"
              style={{ fontFamily: "var(--font-mono)", fontStyle: folderPath ? "normal" : "italic" }}
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
              }}
            >
              {isPicking ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <FolderOpen className="h-4 w-4" style={{ color: "var(--text-secondary)" }} />
              )}
              Browse
            </button>
            <Button onClick={startIndexing} disabled={isIndexing || !folderPath.trim()}>
              {isIndexing ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <FolderSync className="mr-2 h-4 w-4" />
              )}
              {isIndexing ? "Indexing..." : "Start Indexing"}
            </Button>
          </div>
          <label
            className="flex items-center gap-2 text-sm"
            style={{ color: "var(--text-secondary)", fontFamily: "var(--font-sans)" }}
          >
            <input
              type="checkbox"
              checked={force}
              onChange={(e) => setForce(e.target.checked)}
              style={{ accentColor: "var(--accent)" }}
            />
            Force re-index (ignore cache)
          </label>
        </CardContent>
      </Card>

      {/* Progress */}
      {progress && (progress.status === "scanning" || progress.status === "indexing") && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <Card>
            <CardContent className="space-y-3 p-6">
              <div className="flex items-center justify-between text-sm">
                <span style={{ color: "var(--text-primary)", fontWeight: 500 }}>
                  {progress.status === "scanning" ? "Scanning files…" : "Indexing…"}
                </span>
                <span style={{ color: "var(--text-secondary)", fontFamily: "var(--font-mono)", fontSize: "0.75rem" }}>
                  {progress.files_processed}/{progress.files_total} files · {progress.chunks_created} chunks · {progress.elapsed_seconds.toFixed(1)}s
                </span>
              </div>
              <div className="sk-gauge">
                <motion.div
                  className="sk-gauge-fill"
                  initial={{ width: 0 }}
                  animate={{ width: `${progressPercent}%` }}
                  transition={{ duration: 0.3 }}
                />
              </div>
              {progress.current_file && (
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

      {/* Done */}
      {progress?.status === "done" && (
        <Card>
          <CardContent className="flex items-center gap-3 p-6" style={{ color: "var(--success)" }}>
            <span className="sk-led sk-led-green" />
            <span style={{ fontFamily: "var(--font-sans)", fontSize: "0.9rem", fontWeight: 500 }}>
              Indexing complete! {progress.files_processed} files, {progress.chunks_created} chunks in {progress.elapsed_seconds.toFixed(1)}s
            </span>
          </CardContent>
        </Card>
      )}

      {/* Indexed Files */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Indexed Files</CardTitle>
        </CardHeader>
        <CardContent>
          {filesLoading ? (
            <div className="space-y-2">
              {[...Array(5)].map((_, i) => (
                <div
                  key={i}
                  className="h-10 animate-pulse rounded"
                  style={{ background: "var(--bg-hover)" }}
                />
              ))}
            </div>
          ) : files.length === 0 ? (
            <p className="sk-empty">No files indexed yet — enter a folder path above to get started.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>File Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Chunks</TableHead>
                  <TableHead>Indexed At</TableHead>
                  <TableHead className="w-12" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {files.map((file) => (
                  <TableRow key={file.file_path}>
                    <TableCell style={{ color: "var(--text-primary)", fontWeight: 500 }}>
                      {file.file_name}
                    </TableCell>
                    <TableCell>
                      <Badge className={typeTabClass(file.file_type)}>{file.file_type}</Badge>
                    </TableCell>
                    <TableCell style={{ fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>
                      {file.chunk_count}
                    </TableCell>
                    <TableCell style={{ color: "var(--text-tertiary)", fontFamily: "var(--font-mono)", fontSize: "0.75rem" }}>
                      {file.indexed_at
                        ? new Date(file.indexed_at).toLocaleString()
                        : "—"}
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="icon-xs"
                        onClick={() => deleteFile(file.file_path)}
                      >
                        <Trash2 className="h-3.5 w-3.5" style={{ color: "var(--text-tertiary)" }} />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
