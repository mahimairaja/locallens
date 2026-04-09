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
      <div className="space-y-6">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[...Array(4)].map((_, i) => (
            <Card key={i}>
              <CardContent className="p-6">
                <div className="h-16 animate-pulse rounded bg-muted" />
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
    <div className="space-y-6">
      {/* Stats Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {statCards.map((card) => (
          <Card key={card.title}>
            <CardContent className="flex items-center gap-4 p-6">
              <div className="rounded-lg bg-primary/10 p-3">
                <card.icon className="h-5 w-5 text-primary" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">{card.title}</p>
                <p className="text-2xl font-bold">{card.value}</p>
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
            <ul className="space-y-2">
              {stats.top_searches.slice(0, 10).map((q, i) => (
                <li key={i}>
                  <button
                    onClick={() =>
                      navigate(`/search?q=${encodeURIComponent(q)}`)
                    }
                    className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                  >
                    <Search className="h-3.5 w-3.5" />
                    {q}
                  </button>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Quick Actions */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card
          className="cursor-pointer transition-colors hover:border-primary/50"
          onClick={() => navigate("/index")}
        >
          <CardContent className="flex items-center gap-3 p-6">
            <FolderSync className="h-5 w-5 text-primary" />
            <span className="font-medium">Index a Folder</span>
          </CardContent>
        </Card>
        <Card
          className="cursor-pointer transition-colors hover:border-primary/50"
          onClick={() => navigate("/search")}
        >
          <CardContent className="flex items-center gap-3 p-6">
            <Search className="h-5 w-5 text-primary" />
            <span className="font-medium">Search Files</span>
          </CardContent>
        </Card>
        <Card
          className="cursor-pointer transition-colors hover:border-primary/50"
          onClick={() => navigate("/ask")}
        >
          <CardContent className="flex items-center gap-3 p-6">
            <MessageSquare className="h-5 w-5 text-primary" />
            <span className="font-medium">Ask a Question</span>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
