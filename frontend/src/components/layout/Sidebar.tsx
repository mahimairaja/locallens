import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  FolderSync,
  Search,
  MessageSquare,
  BookOpen,
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
  { to: "/stack", icon: BookOpen, label: "Stack" },
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
    <aside
      className="fixed left-0 top-0 z-40 flex h-screen w-60 flex-col border-r"
      style={{ background: "var(--bg-sidebar)", borderColor: "var(--border)" }}
    >
      {/* Logo */}
      <div className="flex h-16 items-center gap-3 px-5">
        <Search className="h-5 w-5" style={{ color: "var(--accent)" }} strokeWidth={2.2} />
        <span
          className="text-lg"
          style={{
            fontFamily: "var(--font-sans)",
            fontWeight: 600,
            color: "var(--text-primary)",
            letterSpacing: "-0.01em",
          }}
        >
          LocalLens
        </span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 px-3">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              `sk-nav-item ${isActive ? "active" : ""}`
            }
          >
            <item.icon className="h-4 w-4 sk-nav-icon" />
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Connection Status */}
      <div
        className="mx-3 mb-3 rounded-lg border px-4 py-3 space-y-2"
        style={{ background: "var(--bg-card)", borderColor: "var(--border)" }}
      >
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

      {/* Version */}
      <div className="mb-4 text-center">
        <span
          className="text-[0.7rem]"
          style={{ color: "var(--text-tertiary)", fontFamily: "var(--font-sans)", letterSpacing: "0.05em" }}
        >
          LocalLens · v0.1
        </span>
      </div>
    </aside>
  );
}

function StatusIndicator({
  icon: Icon,
  label,
  status,
}: {
  icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }>;
  label: string;
  status: "checking" | "online" | "offline";
}) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <Icon className="h-3.5 w-3.5" style={{ color: "var(--text-tertiary)" }} />
      <span style={{ fontFamily: "var(--font-sans)", color: "var(--text-tertiary)", fontSize: "0.72rem" }}>
        {label}
      </span>
      <span className="ml-auto">
        {status === "checking" && (
          <Loader2 className="h-3 w-3 animate-spin" style={{ color: "var(--text-tertiary)" }} />
        )}
        {status === "online" && <span className="sk-led sk-led-green" />}
        {status === "offline" && <span className="sk-led sk-led-red" />}
      </span>
    </div>
  );
}
