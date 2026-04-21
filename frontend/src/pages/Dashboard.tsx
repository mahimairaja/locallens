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
  MessageSquare,
  Mic,
  HardDrive,
  Tags,
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
  const totalChunks = stats?.total_chunks ?? 0;
  const fileTypes = stats?.file_types ?? {};
  const chartData = Object.entries(fileTypes)
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value);

  /* ============================================================
     Empty state: search-first hero
     ============================================================ */
  if (totalFiles === 0) {
    return (
      <div
        className="flex flex-col items-center justify-center"
        style={{ minHeight: "calc(100vh - 12rem)" }}
      >
        {/* Quiet stats band */}
        <p
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "0.7rem",
            fontWeight: 500,
            textTransform: "uppercase",
            letterSpacing: "0.1em",
            color: "var(--text-tertiary)",
            marginBottom: "2.5rem",
          }}
        >
          0 files &middot; 0 chunks
        </p>

        {/* Logo */}
        <img
          src="/logo.png"
          alt="LocalLens"
          style={{ width: 64, height: 64, marginBottom: "1.5rem" }}
        />

        {/* Headline */}
        <h1
          style={{
            fontFamily: "var(--font-sans)",
            fontSize: "2.4rem",
            fontWeight: 700,
            color: "var(--text-primary)",
            letterSpacing: "-0.025em",
            lineHeight: 1.15,
            textAlign: "center",
            marginBottom: "2rem",
          }}
        >
          What do your files{" "}
          <span style={{ color: "var(--accent)" }}>say</span>?
        </h1>

        {/* Big search bar */}
        <div
          style={{
            position: "relative",
            width: "100%",
            maxWidth: "560px",
            marginBottom: "1.25rem",
          }}
        >
          <Search
            className="h-5 w-5"
            style={{
              position: "absolute",
              left: "1rem",
              top: "50%",
              transform: "translateY(-50%)",
              color: "var(--text-tertiary)",
            }}
          />
          <input
            className="sk-input"
            readOnly
            onClick={() => navigate("/ask")}
            placeholder="ask or search..."
            style={{
              width: "100%",
              padding: "0.9rem 1rem 0.9rem 2.75rem",
              fontSize: "1.05rem",
              fontFamily: "var(--font-sans)",
              borderRadius: "var(--radius-lg)",
              border: "1px solid var(--border)",
              background: "var(--bg-card)",
              color: "var(--text-primary)",
              cursor: "pointer",
              boxShadow: "var(--shadow-md)",
            }}
          />
        </div>

        {/* Mode chips */}
        <div style={{ display: "flex", gap: "0.5rem", marginBottom: "3rem" }}>
          {[
            { label: "ask mode", icon: MessageSquare, route: "/ask" },
            { label: "hybrid", icon: Search, route: "/search" },
            { label: "voice", icon: Mic, route: "/ask" },
          ].map((chip) => (
            <button
              key={chip.label}
              onClick={() => navigate(chip.route)}
              className="sk-query-chip"
              style={{ gap: "0.35rem" }}
            >
              <chip.icon
                className="h-3.5 w-3.5"
                style={{ color: "var(--text-tertiary)" }}
              />
              {chip.label}
            </button>
          ))}
        </div>

        {/* Bottom: index CTA */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: "0.75rem",
          }}
        >
          <p
            style={{
              fontFamily: "var(--font-sans)",
              fontSize: "0.85rem",
              color: "var(--text-secondary)",
            }}
          >
            No files indexed yet. Point LocalLens at a folder to get started.
          </p>
          <Button
            className="sk-press"
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
      </div>
    );
  }

  /* ============================================================
     Data state: classic dashboard
     ============================================================ */
  const fileTypeCount = Object.keys(fileTypes).length;

  const statCards = [
    {
      title: "CHUNKS",
      value: String(totalChunks),
      icon: Layers,
      accent: false,
    },
    {
      title: "FILES",
      value: String(totalFiles),
      icon: FileText,
      accent: true,
    },
    {
      title: "FILE TYPES",
      value: String(fileTypeCount),
      icon: Tags,
      accent: false,
    },
    {
      title: "LAST INDEXED",
      value: formatRelativeTime(stats?.last_indexed_at ?? null),
      tooltip: stats?.last_indexed_at
        ? new Date(stats.last_indexed_at).toLocaleString()
        : undefined,
      icon: Clock,
      accent: false,
    },
  ];

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
      {/* 4-column stat cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {statCards.map((card) => (
          <Card
            key={card.title}
            style={
              card.accent
                ? {
                    background: "rgba(198, 123, 60, 0.06)",
                    borderColor: "rgba(198, 123, 60, 0.25)",
                  }
                : undefined
            }
          >
            <CardContent className="p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: "0.55rem",
                      fontWeight: 500,
                      textTransform: "uppercase",
                      letterSpacing: "0.12em",
                      color: card.accent ? "var(--accent)" : "var(--text-tertiary)",
                      marginBottom: "0.25rem",
                    }}
                  >
                    {card.title}
                  </p>
                  <p
                    style={{
                      fontFamily: "var(--font-sans)",
                      fontSize: "1.75rem",
                      fontWeight: 700,
                      color: card.accent ? "var(--accent)" : "var(--text-primary)",
                      letterSpacing: "-0.02em",
                      lineHeight: 1.1,
                    }}
                    title={card.tooltip}
                  >
                    {card.value}
                  </p>
                </div>
                <div
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full"
                  style={{
                    background: card.accent
                      ? "rgba(198, 123, 60, 0.12)"
                      : "rgba(198, 123, 60, 0.06)",
                  }}
                >
                  <card.icon
                    className="h-5 w-5"
                    style={{
                      color: card.accent ? "#C67B3C" : "var(--text-tertiary)",
                    }}
                    strokeWidth={1.8}
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* File type chart + recent activity side-by-side on large screens */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
        {/* File Type Distribution Chart */}
        {chartData.length > 0 && (
          <Card className="lg:col-span-2">
            <CardContent className="p-6">
              <h3
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: "0.6rem",
                  fontWeight: 500,
                  textTransform: "uppercase",
                  letterSpacing: "0.1em",
                  color: "var(--text-tertiary)",
                  marginBottom: "1rem",
                }}
              >
                File Types
              </h3>
              <div className="flex flex-col items-center gap-4">
                <div style={{ width: 180, height: 180 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={chartData}
                        cx="50%"
                        cy="50%"
                        innerRadius={45}
                        outerRadius={80}
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
                <div className="flex flex-wrap justify-center gap-x-4 gap-y-1.5">
                  {chartData.map((entry, index) => (
                    <div key={entry.name} className="flex items-center gap-1.5">
                      <span
                        className="inline-block h-2.5 w-2.5 rounded-sm"
                        style={{
                          background: CHART_COLORS[index % CHART_COLORS.length],
                        }}
                      />
                      <span
                        style={{
                          fontFamily: "var(--font-sans)",
                          fontSize: "0.8rem",
                          color: "var(--text-primary)",
                          fontWeight: 500,
                        }}
                      >
                        {entry.name}
                      </span>
                      <span
                        style={{
                          fontFamily: "var(--font-mono)",
                          fontSize: "0.7rem",
                          color: "var(--text-tertiary)",
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

        {/* Recent Activity */}
        <Card className={chartData.length > 0 ? "lg:col-span-3" : "lg:col-span-5"}>
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

      {/* Action buttons row */}
      <div className="flex flex-wrap items-center gap-3">
        <Button
          className="sk-press"
          onClick={() => navigate("/index")}
          style={{
            background: "var(--accent)",
            color: "var(--text-on-accent)",
            fontFamily: "var(--font-sans)",
            fontWeight: 500,
            padding: "0.6rem 1.25rem",
            fontSize: "0.88rem",
          }}
        >
          <FolderOpen className="mr-2 h-4 w-4" />
          + index a folder
        </Button>
        <Button
          className="sk-press"
          onClick={() => navigate("/ask")}
          style={{
            background: "var(--bg-card)",
            color: "var(--text-primary)",
            fontFamily: "var(--font-sans)",
            fontWeight: 500,
            padding: "0.6rem 1.25rem",
            fontSize: "0.88rem",
            border: "1px solid var(--border)",
            boxShadow: "var(--shadow-xs)",
          }}
        >
          <MessageSquare className="mr-2 h-4 w-4" />
          ask a question
        </Button>
        <Button
          className="sk-press"
          onClick={() => navigate("/search")}
          style={{
            background: "transparent",
            color: "var(--text-secondary)",
            fontFamily: "var(--font-sans)",
            fontWeight: 500,
            padding: "0.6rem 1.25rem",
            fontSize: "0.88rem",
            border: "1px solid var(--border)",
          }}
        >
          <Search className="mr-2 h-4 w-4" />
          browse files
        </Button>
      </div>
    </div>
  );
}
