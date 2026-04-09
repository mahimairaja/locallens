import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  FolderSync,
  Search,
  MessageSquare,
  Mic,
  Database,
  Cpu,
  Loader2,
} from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const navItems = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/index", icon: FolderSync, label: "Index" },
  { to: "/search", icon: Search, label: "Search" },
  { to: "/ask", icon: MessageSquare, label: "Ask" },
  { to: "/voice", icon: Mic, label: "Voice" },
];

interface ServiceStatus {
  qdrant: "checking" | "online" | "offline";
  ollama: "checking" | "online" | "offline";
}

export function Sidebar() {
  const [status, setStatus] = useState<ServiceStatus>({
    qdrant: "checking",
    ollama: "checking",
  });

  useEffect(() => {
    async function checkServices() {
      // Check backend health (which implies Qdrant connectivity)
      try {
        await api.checkHealth();
        setStatus((s) => ({ ...s, qdrant: "online" }));
      } catch {
        setStatus((s) => ({ ...s, qdrant: "offline" }));
      }

      // Check Ollama
      try {
        const res = await fetch("/api/health");
        if (res.ok) {
          setStatus((s) => ({ ...s, ollama: "online" }));
        } else {
          setStatus((s) => ({ ...s, ollama: "offline" }));
        }
      } catch {
        setStatus((s) => ({ ...s, ollama: "offline" }));
      }
    }

    checkServices();
    const interval = setInterval(checkServices, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <aside className="fixed left-0 top-0 z-40 flex h-screen w-60 flex-col border-r border-border bg-sidebar">
      {/* Logo */}
      <div className="flex h-14 items-center gap-2 border-b border-border px-5">
        <Search className="h-5 w-5 text-primary" />
        <span className="text-lg font-semibold text-foreground">
          LocalLens
        </span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 px-3 py-4">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                isActive
                  ? "bg-sidebar-accent text-primary"
                  : "text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-foreground"
              }`
            }
          >
            <item.icon className="h-4 w-4" />
            {item.label}
          </NavLink>
        ))}
      </nav>

      {/* Connection Status */}
      <div className="border-t border-border p-4 space-y-2">
        <StatusIndicator
          icon={Database}
          label="Qdrant"
          status={status.qdrant}
        />
        <StatusIndicator
          icon={Cpu}
          label="Ollama"
          status={status.ollama}
        />
      </div>
    </aside>
  );
}

function StatusIndicator({
  icon: Icon,
  label,
  status,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  status: "checking" | "online" | "offline";
}) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <Icon className="h-3.5 w-3.5 text-muted-foreground" />
      <span className="text-muted-foreground">{label}</span>
      <span className="ml-auto">
        {status === "checking" && (
          <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
        )}
        {status === "online" && (
          <span className="inline-block h-2 w-2 rounded-full bg-emerald-500" />
        )}
        {status === "offline" && (
          <span className="inline-block h-2 w-2 rounded-full bg-red-500" />
        )}
      </span>
    </div>
  );
}
