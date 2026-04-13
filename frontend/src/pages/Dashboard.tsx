import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  FileText,
  Layers,
  Database,
  Clock,
  FolderSync,
  Search,
  MessageSquare,
} from "lucide-react";
import { api } from "@/lib/api";
import type { StatsResponse } from "@/types";

export default function Dashboard() {
  const navigate = useNavigate();
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .getStats()
      .then(setStats)
      .catch(() => {})
      .finally(() => setLoading(false));
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

  if (loading) {
    return (
      <div className="space-y-8">
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {[...Array(4)].map((_, i) => (
            <Card key={i}>
              <CardContent className="p-6">
                <div
                  className="h-16 animate-pulse rounded"
                  style={{ background: "var(--bg-hover)" }}
                />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  const statCards = [
    {
      title: "Total Files",
      value: stats?.total_files ?? 0,
      icon: FileText,
    },
    {
      title: "Total Chunks",
      value: stats?.total_chunks ?? 0,
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
      icon: Clock,
    },
  ];

  return (
    <div className="space-y-8">
      <h2
        className="text-2xl"
        style={{ fontFamily: "var(--font-sans)", fontWeight: 600, color: "var(--text-primary)", letterSpacing: "-0.015em" }}
      >
        Dashboard
      </h2>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {statCards.map((card) => (
          <Card key={card.title}>
            <CardContent className="flex items-center gap-4 p-6">
              <div
                className="flex h-10 w-10 items-center justify-center rounded-full"
                style={{ background: "var(--accent-soft)" }}
              >
                <card.icon className="h-5 w-5" style={{ color: "var(--accent)" }} strokeWidth={2} />
              </div>
              <div>
                <p
                  className="text-[0.7rem] uppercase"
                  style={{ color: "var(--text-secondary)", fontFamily: "var(--font-sans)", fontWeight: 500, letterSpacing: "0.08em" }}
                >
                  {card.title}
                </p>
                <p
                  className="text-[1.75rem] leading-tight"
                  style={{ fontFamily: "var(--font-sans)", fontWeight: 700, color: "var(--text-primary)", letterSpacing: "-0.02em" }}
                >
                  {card.value}
                </p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Recent Searches */}
      {stats?.top_searches && stats.top_searches.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Recent Searches</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-1">
              {stats.top_searches.slice(0, 10).map((q, i) => (
                <li key={i}>
                  <button
                    onClick={() =>
                      navigate(`/search?q=${encodeURIComponent(q)}`)
                    }
                    className="flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors"
                    style={{ color: "var(--text-secondary)", fontFamily: "var(--font-sans)" }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-hover)")}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                  >
                    <Search className="h-3.5 w-3.5" style={{ color: "var(--text-tertiary)" }} />
                    {q}
                  </button>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Quick Actions */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">
        {[
          { icon: FolderSync, label: "Index a Folder", to: "/index" },
          { icon: Search,     label: "Search Files",   to: "/search" },
          { icon: MessageSquare, label: "Ask a Question", to: "/ask" },
        ].map((action) => (
          <Card
            key={action.to}
            className="cursor-pointer"
            onClick={() => navigate(action.to)}
          >
            <CardContent className="flex items-center gap-4 p-6">
              <div
                className="flex h-10 w-10 items-center justify-center rounded-full"
                style={{ background: "var(--accent-soft)" }}
              >
                <action.icon className="h-5 w-5" style={{ color: "var(--accent)" }} strokeWidth={2} />
              </div>
              <span
                className="text-base"
                style={{ fontFamily: "var(--font-sans)", color: "var(--text-primary)", fontWeight: 500 }}
              >
                {action.label}
              </span>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Empty state when no files yet */}
      {(stats?.total_files ?? 0) === 0 && (
        <p className="sk-empty">No files indexed yet — head to Index to get started.</p>
      )}
    </div>
  );
}
