import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api } from "@/lib/api";
import type { AuditEntry, AuditResponse } from "@/lib/api";
import {
  FileText,
  Search,
  MessageSquare,
  Trash2,
  FolderSync,
  ChevronLeft,
  ChevronRight,
  Loader2,
} from "lucide-react";

const OP_ICONS: Record<string, typeof Search> = {
  search: Search,
  ask: MessageSquare,
  index: FolderSync,
  delete: Trash2,
};

const OP_COLORS: Record<string, string> = {
  search: "var(--accent)",
  ask: "#6366f1",
  index: "#22c55e",
  delete: "#ef4444",
};

function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export default function AuditPage() {
  const [data, setData] = useState<AuditResponse | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const pageSize = 30;

  useEffect(() => {
    setLoading(true);
    setError(null);
    api
      .getAuditLog(page, pageSize)
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load audit log"))
      .finally(() => setLoading(false));
  }, [page]);

  const totalPages = data ? Math.max(1, Math.ceil(data.total / pageSize)) : 1;

  return (
    <div className="space-y-6">
      {error && (
        <Card>
          <CardContent className="p-6">
            <p className="text-sm" style={{ color: "var(--danger)", fontFamily: "var(--font-sans)" }}>
              {error}
            </p>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base">
            {data ? `${data.total} entries` : "Loading..."}
          </CardTitle>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span
              className="text-sm"
              style={{ fontFamily: "var(--font-sans)", color: "var(--text-secondary)" }}
            >
              {page} / {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin" style={{ color: "var(--accent)" }} />
            </div>
          ) : data && data.entries.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead style={{ width: 40 }}></TableHead>
                  <TableHead>Operation</TableHead>
                  <TableHead>Namespace</TableHead>
                  <TableHead>Detail</TableHead>
                  <TableHead>Key</TableHead>
                  <TableHead>Time</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.entries.map((entry: AuditEntry) => {
                  const Icon = OP_ICONS[entry.operation] || FileText;
                  const color = OP_COLORS[entry.operation] || "var(--text-tertiary)";
                  return (
                    <TableRow key={entry.id}>
                      <TableCell>
                        <Icon className="h-4 w-4" style={{ color }} />
                      </TableCell>
                      <TableCell>
                        <span
                          className="text-xs font-medium uppercase"
                          style={{ color, fontFamily: "var(--font-sans)", letterSpacing: "0.05em" }}
                        >
                          {entry.operation}
                        </span>
                      </TableCell>
                      <TableCell>
                        <span
                          className="rounded px-1.5 py-0.5 text-xs"
                          style={{
                            background: "var(--bg-hover)",
                            color: "var(--text-secondary)",
                            fontFamily: "var(--font-mono)",
                          }}
                        >
                          {entry.namespace}
                        </span>
                      </TableCell>
                      <TableCell>
                        <span
                          className="block max-w-[300px] truncate text-sm"
                          style={{ color: "var(--text-primary)", fontFamily: "var(--font-sans)" }}
                          title={entry.detail || ""}
                        >
                          {entry.detail || "--"}
                        </span>
                      </TableCell>
                      <TableCell>
                        <span
                          className="text-xs"
                          style={{ color: "var(--text-tertiary)", fontFamily: "var(--font-mono)" }}
                        >
                          {entry.api_key_hash ? entry.api_key_hash.slice(0, 8) + "..." : "--"}
                        </span>
                      </TableCell>
                      <TableCell>
                        <span
                          className="text-xs whitespace-nowrap"
                          style={{ color: "var(--text-tertiary)", fontFamily: "var(--font-sans)" }}
                        >
                          {formatTimestamp(entry.timestamp)}
                        </span>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          ) : (
            <p className="sk-empty">No audit entries yet.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
