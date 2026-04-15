import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  FileText,
  Layers,
  Database,
  Clock,
  FolderOpen,
  Search,
} from "lucide-react";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { api } from "@/lib/api";
import type { StatsResponse, IndexedFile } from "@/types";

/* Copper-derived palette for chart slices */
const CHART_COLORS = [
  "#C67B3C", /* copper */
  "#D4915A", /* warm amber */
  "#8B5E3C", /* warm brown */
  "#C9A87C", /* warm tan */
  "#DAA520", /* warm gold */
  "#A0522D", /* sienna */
  "#B8860B", /* dark goldenrod */
  "#CD853F", /* peru */
];

export default function Dashboard() {
  const navigate = useNavigate();
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [files, setFiles] = useState<IndexedFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"files" | "searches">("files");

  useEffect(() => {
    Promise.all([
      api.getStats().catch(() => null),
      api.getFiles().catch(() => [] as IndexedFile[]),
    ]).then(([statsData, filesData]) => {
      setStats(statsData);
      setFiles(filesData);
    }).finally(() => setLoading(false));
  }, []);

  const formatRelativeTime = (dateStr: string | null) => {
    if (!dateStr) return "Never";
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "Just now";
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
  };

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

  /* Loading skeleton */
  if (loading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[...Array(4)].map((_, i) => (
            <Card key={i}>
              <CardContent className="p-6">
                <div className="flex items-start gap-4">
                  <div className="sk-skeleton h-10 w-10 shrink-0" style={{ borderRadius: "9999px" }} />
                  <div className="min-w-0 flex-1 space-y-2">
                    <div className="sk-skeleton h-3 w-16" />
                    <div className="sk-skeleton h-6 w-24" />
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  const totalFiles = stats?.total_files ?? 0;

  /* ============================================================
     Empty state — Step 7
     ============================================================ */
  if (totalFiles === 0) {
    return (
      <div className="flex flex-col items-center justify-center" style={{ minHeight: "calc(100vh - 12rem)" }}>
        <div
          className="flex h-16 w-16 items-center justify-center rounded-full"
          style={{ background: "rgba(198, 123, 60, 0.1)" }}
        >
          <FolderOpen
            className="h-8 w-8"
            style={{ color: "rgba(198, 123, 60, 0.3)" }}
            strokeWidth={1.5}
          />
        </div>
        <h3
          className="mt-5 text-xl"
          style={{
            fontFamily: "var(--font-sans)",
            fontWeight: 600,
            color: "var(--text-primary)",
          }}
        >
          No files indexed yet
        </h3>
        <p
          className="mt-2 text-sm"
          style={{
            color: "var(--text-secondary)",
            fontFamily: "var(--font-sans)",
          }}
        >
          Point LocalLens at a folder to get started
        </p>
        <Button
          className="sk-press mt-6"
          onClick={() => navigate("/index")}
          style={{
            background: "var(--accent)",
            color: "var(--text-on-accent)",
            fontFamily: "var(--font-sans)",
            fontWeight: 500,
            padding: "0.6rem 1.5rem",
          }}
        >
          <FolderOpen className="mr-2 h-4 w-4" />
          Index a Folder
        </Button>
      </div>
    );
  }

  /* ============================================================
     Stat cards data — Step 4
     ============================================================ */
  const statCards = [
    {
      title: "Total Files",
      value: String(stats?.total_files ?? 0),
      icon: FileText,
    },
    {
      title: "Total Chunks",
      value: String(stats?.total_chunks ?? 0),
      icon: Layers,
    },
    {
      title: "Storage Size",
      value: `${(stats?.storage_size_mb ?? 0).toFixed(1)} MB`,
      icon: Database,
    },
    {
      title: "Last Indexed",
      value: formatRelativeTime(stats?.last_indexed_at ?? null),
      tooltip: stats?.last_indexed_at
        ? new Date(stats.last_indexed_at).toLocaleString()
        : undefined,
      icon: Clock,
    },
  ];

  /* ============================================================
     Chart data — Step 5
     ============================================================ */
  const fileTypes = stats?.file_types ?? {};
  const chartData = Object.entries(fileTypes)
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value);

  /* ============================================================
     Recent files — Step 6
     ============================================================ */
  const recentFiles = [...files]
    .sort((a, b) => {
      if (!a.indexed_at) return 1;
      if (!b.indexed_at) return -1;
      return new Date(b.indexed_at).getTime() - new Date(a.indexed_at).getTime();
    })
    .slice(0, 8);

  const topSearches = stats?.top_searches ?? [];
  const hasSearches = topSearches.length > 0;

  return (
    <div className="space-y-6">
      {/* Stat Cards — 2x2 / 4-col grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {statCards.map((card) => (
          <Card key={card.title}>
            <CardContent className="p-6">
              <div className="flex items-start gap-4">
                <div
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full"
                  style={{ background: "rgba(198, 123, 60, 0.1)" }}
                >
                  <card.icon className="h-5 w-5" style={{ color: "#C67B3C" }} strokeWidth={2} />
                </div>
                <div className="min-w-0">
                  <p
                    className="text-[0.68rem] uppercase"
                    style={{
                      color: "var(--text-secondary)",
                      fontFamily: "var(--font-sans)",
                      fontWeight: 500,
                      letterSpacing: "0.08em",
                    }}
                  >
                    {card.title}
                  </p>
                  <p
                    className="mt-0.5 text-2xl leading-tight"
                    style={{
                      fontFamily: "var(--font-sans)",
                      fontWeight: 700,
                      color: "var(--text-primary)",
                      letterSpacing: "-0.02em",
                    }}
                    title={card.tooltip}
                  >
                    {card.value}
                  </p>
                </div>
              </div>
              {/* Accent bottom border */}
              <div
                className="mt-4 h-[2px] rounded-full"
                style={{ background: "rgba(198, 123, 60, 0.2)" }}
              />
            </CardContent>
          </Card>
        ))}
      </div>

      {/* File Type Distribution Chart — Step 5 */}
      {chartData.length > 0 && (
        <Card>
          <CardContent className="p-6">
            <h3
              className="mb-4 text-sm uppercase"
              style={{
                fontFamily: "var(--font-sans)",
                fontWeight: 600,
                color: "var(--text-secondary)",
                letterSpacing: "0.06em",
              }}
            >
              File Types
            </h3>
            <div className="flex flex-col items-center gap-6 sm:flex-row">
              <div style={{ width: 200, height: 200 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={chartData}
                      cx="50%"
                      cy="50%"
                      innerRadius={50}
                      outerRadius={85}
                      paddingAngle={2}
                      dataKey="value"
                      stroke="none"
                    >
                      {chartData.map((_, index) => (
                        <Cell
                          key={`cell-${index}`}
                          fill={CHART_COLORS[index % CHART_COLORS.length]}
                        />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        background: "var(--bg-card)",
                        border: "1px solid var(--border)",
                        borderRadius: "var(--radius-md)",
                        fontFamily: "var(--font-sans)",
                        fontSize: "0.8rem",
                        boxShadow: "var(--shadow-md)",
                      }}
                      formatter={(value, name) => [
                        `${value} file${value !== 1 ? "s" : ""}`,
                        String(name),
                      ]}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="flex flex-wrap gap-x-5 gap-y-2">
                {chartData.map((entry, index) => (
                  <div key={entry.name} className="flex items-center gap-2">
                    <span
                      className="inline-block h-3 w-3 rounded-sm"
                      style={{
                        background: CHART_COLORS[index % CHART_COLORS.length],
                      }}
                    />
                    <span
                      className="text-sm"
                      style={{
                        fontFamily: "var(--font-sans)",
                        color: "var(--text-primary)",
                        fontWeight: 500,
                      }}
                    >
                      {entry.name}
                    </span>
                    <span
                      className="text-xs"
                      style={{
                        color: "var(--text-tertiary)",
                        fontFamily: "var(--font-mono)",
                      }}
                    >
                      {entry.value}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Recent Activity — Step 6 */}
      <Card>
        <CardContent className="p-6">
          {/* Tab switcher */}
          <div className="mb-4 flex items-center gap-1">
            <button
              onClick={() => setActiveTab("files")}
              className="rounded-md px-3 py-1.5 text-sm transition-all"
              style={{
                fontFamily: "var(--font-sans)",
                fontWeight: activeTab === "files" ? 600 : 500,
                color: activeTab === "files" ? "#C67B3C" : "var(--text-secondary)",
                background: activeTab === "files" ? "rgba(198, 123, 60, 0.08)" : "transparent",
              }}
            >
              Recent Files
            </button>
            {hasSearches && (
              <button
                onClick={() => setActiveTab("searches")}
                className="rounded-md px-3 py-1.5 text-sm transition-all"
                style={{
                  fontFamily: "var(--font-sans)",
                  fontWeight: activeTab === "searches" ? 600 : 500,
                  color: activeTab === "searches" ? "#C67B3C" : "var(--text-secondary)",
                  background: activeTab === "searches" ? "rgba(198, 123, 60, 0.08)" : "transparent",
                }}
              >
                Recent Searches
              </button>
            )}
          </div>

          {/* Recent Files tab */}
          {activeTab === "files" && (
            <div className="space-y-1">
              {recentFiles.length > 0 ? (
                recentFiles.map((file) => (
                  <div
                    key={file.file_path}
                    className="flex items-center gap-3 rounded-lg px-3 py-2.5 transition-all"
                    style={{ cursor: "default" }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = "rgba(198, 123, 60, 0.04)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = "transparent";
                    }}
                  >
                    <FileText
                      className="h-4 w-4 shrink-0"
                      style={{ color: "var(--text-tertiary)" }}
                    />
                    <span
                      className="min-w-0 flex-1 truncate text-sm"
                      style={{
                        fontFamily: "var(--font-sans)",
                        fontWeight: 500,
                        color: "var(--text-primary)",
                      }}
                    >
                      {file.file_name}
                    </span>
                    <span
                      className={`shrink-0 rounded-full px-2 py-0.5 text-[0.68rem] font-medium ${typeTabClass(file.file_type)}`}
                    >
                      {file.file_type}
                    </span>
                    <span
                      className="shrink-0 text-xs"
                      style={{
                        fontFamily: "var(--font-mono)",
                        color: "var(--text-tertiary)",
                      }}
                    >
                      {file.chunk_count} chunks
                    </span>
                    <span
                      className="shrink-0 text-xs"
                      style={{
                        fontFamily: "var(--font-sans)",
                        color: "var(--text-tertiary)",
                        minWidth: "4rem",
                        textAlign: "right",
                      }}
                      title={
                        file.indexed_at
                          ? new Date(file.indexed_at).toLocaleString()
                          : undefined
                      }
                    >
                      {formatRelativeTime(file.indexed_at)}
                    </span>
                  </div>
                ))
              ) : (
                <p
                  className="py-6 text-center text-sm"
                  style={{
                    color: "var(--text-tertiary)",
                    fontFamily: "var(--font-sans)",
                    fontStyle: "italic",
                  }}
                >
                  No files indexed yet.
                </p>
              )}
            </div>
          )}

          {/* Recent Searches tab */}
          {activeTab === "searches" && hasSearches && (
            <div className="space-y-1">
              {topSearches.slice(0, 10).map((q, i) => (
                <button
                  key={i}
                  onClick={() =>
                    navigate(`/search?q=${encodeURIComponent(q)}`)
                  }
                  className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition-all"
                  style={{
                    color: "var(--text-primary)",
                    fontFamily: "var(--font-sans)",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = "rgba(198, 123, 60, 0.04)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = "transparent";
                  }}
                >
                  <Search
                    className="h-3.5 w-3.5 shrink-0"
                    style={{ color: "var(--text-tertiary)" }}
                  />
                  <span className="truncate">{q}</span>
                </button>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
