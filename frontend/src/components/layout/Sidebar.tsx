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
  Settings,
  Lock,
  LockOpen,
  ScrollText,
  ChevronDown,
  Plus,
} from "lucide-react";
import { useEffect, useState, useRef } from "react";
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
  overall: "checking" | "connected" | "degraded" | "offline";
}

export function Sidebar() {
  const [status, setStatus] = useState<ServiceStatus>({
    qdrant: "checking",
    ollama: "checking",
    overall: "checking",
  });
  const [authStatus, setAuthStatus] = useState<{
    auth_enabled: boolean;
    authenticated: boolean;
  } | null>(null);
  const [namespaces, setNamespaces] = useState<string[]>(["default"]);
  const [activeNs, setActiveNs] = useState<string>(
    localStorage.getItem("locallens_namespace") || "default"
  );
  const [nsOpen, setNsOpen] = useState(false);
  const [newNs, setNewNs] = useState("");
  const [creatingNs, setCreatingNs] = useState(false);
  const nsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    async function checkServices() {
      try {
        const data = await api.checkHealth() as {
          qdrant: string;
          ollama: string;
          search_available: boolean;
          ask_available: boolean;
        };
        const qdrant = data.qdrant === "ok" ? "online" : "offline";
        const ollama = data.ollama === "ok" ? "online" : "offline";
        let overall: ServiceStatus["overall"];
        if (qdrant === "online" && ollama === "online") {
          overall = "connected";
        } else if (qdrant === "online" && ollama === "offline") {
          overall = "degraded";
        } else {
          overall = "offline";
        }
        setStatus({ qdrant, ollama, overall });
      } catch {
        setStatus({ qdrant: "offline", ollama: "offline", overall: "offline" });
      }
    }

    checkServices();
    const interval = setInterval(checkServices, 30000);
    return () => clearInterval(interval);
  }, []);

  // Load auth status and namespaces
  useEffect(() => {
    api.getAuthStatus().then(setAuthStatus).catch(() => {});
    api
      .getNamespaces()
      .then((data) => {
        setNamespaces(data.namespaces);
      })
      .catch(() => {});
  }, []);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (nsRef.current && !nsRef.current.contains(e.target as Node)) {
        setNsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const switchNamespace = (ns: string) => {
    setActiveNs(ns);
    localStorage.setItem("locallens_namespace", ns);
    setNsOpen(false);
    // Force reload data on the current page
    window.dispatchEvent(new Event("locallens-ns-change"));
  };

  const createNamespace = async () => {
    const name = newNs.trim().toLowerCase();
    if (!name) return;
    setCreatingNs(true);
    try {
      await api.createNamespace(name);
      setNamespaces((prev) => (prev.includes(name) ? prev : [...prev, name].sort()));
      switchNamespace(name);
      setNewNs("");
    } catch {
      // Silently ignore
    } finally {
      setCreatingNs(false);
    }
  };

  const authEnabled = authStatus?.auth_enabled ?? false;
  const authenticated = authStatus?.authenticated ?? true;

  return (
    <aside
      className="fixed left-0 top-0 z-40 flex h-screen flex-col border-r"
      style={{
        width: "240px",
        background: "var(--bg-sidebar)",
        borderColor: "var(--border)",
      }}
    >
      {/* Logo */}
      <div
        className="flex h-16 items-center gap-3 px-5"
        style={{ borderBottom: "1px solid var(--border)" }}
      >
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

      {/* Namespace Selector */}
      <div className="mx-3 mt-3 mb-2" ref={nsRef}>
        <button
          onClick={() => setNsOpen(!nsOpen)}
          className="flex w-full items-center justify-between rounded-lg border px-3 py-2 text-sm transition-colors"
          style={{
            background: "var(--bg-card)",
            borderColor: "var(--border)",
            color: "var(--text-primary)",
            fontFamily: "var(--font-sans)",
          }}
        >
          <span className="flex items-center gap-2">
            <Database className="h-3.5 w-3.5" style={{ color: "var(--accent)" }} />
            <span className="truncate">{activeNs}</span>
          </span>
          <ChevronDown
            className="h-3.5 w-3.5 transition-transform"
            style={{
              color: "var(--text-tertiary)",
              transform: nsOpen ? "rotate(180deg)" : "rotate(0deg)",
            }}
          />
        </button>
        {nsOpen && (
          <div
            className="absolute left-3 right-3 z-50 mt-1 rounded-lg border shadow-md"
            style={{ background: "var(--bg-card)", borderColor: "var(--border)" }}
          >
            <div className="max-h-48 overflow-y-auto py-1">
              {namespaces.map((ns) => (
                <button
                  key={ns}
                  onClick={() => switchNamespace(ns)}
                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition-colors"
                  style={{
                    fontFamily: "var(--font-sans)",
                    color: ns === activeNs ? "var(--accent)" : "var(--text-primary)",
                    background: ns === activeNs ? "var(--accent-soft)" : "transparent",
                  }}
                  onMouseEnter={(e) => {
                    if (ns !== activeNs)
                      e.currentTarget.style.background = "var(--bg-hover)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background =
                      ns === activeNs ? "var(--accent-soft)" : "transparent";
                  }}
                >
                  <Database className="h-3 w-3" style={{ color: "var(--text-tertiary)" }} />
                  {ns}
                </button>
              ))}
            </div>
            <div
              className="flex items-center gap-1 border-t px-2 py-2"
              style={{ borderColor: "var(--border)" }}
            >
              <input
                type="text"
                placeholder="New namespace..."
                value={newNs}
                onChange={(e) => setNewNs(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") createNamespace();
                }}
                className="flex-1 rounded border px-2 py-1 text-xs outline-none"
                style={{
                  borderColor: "var(--border)",
                  background: "var(--bg-page)",
                  color: "var(--text-primary)",
                  fontFamily: "var(--font-sans)",
                }}
              />
              <button
                onClick={createNamespace}
                disabled={creatingNs || !newNs.trim()}
                className="flex items-center justify-center rounded p-1 transition-colors disabled:opacity-50"
                style={{ color: "var(--accent)" }}
              >
                {creatingNs ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Plus className="h-3.5 w-3.5" />
                )}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Section divider */}
      <div className="mx-3 my-2" style={{ borderTop: "1px solid var(--border)" }} />

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

        {/* Separator */}
        <div className="!my-3" style={{ borderTop: "1px solid var(--border)" }} />

        {/* Settings */}
        <NavLink
          to="/settings"
          className={({ isActive }) =>
            `sk-nav-item ${isActive ? "active" : ""}`
          }
        >
          <Settings className="h-4 w-4 sk-nav-icon" />
          <span>Settings</span>
          {/* Lock icon showing auth state */}
          <span className="ml-auto">
            {authEnabled ? (
              authenticated ? (
                <Lock className="h-3.5 w-3.5" style={{ color: "#22c55e" }} />
              ) : (
                <LockOpen className="h-3.5 w-3.5" style={{ color: "#ef4444" }} />
              )
            ) : null}
          </span>
        </NavLink>

        {/* Audit Log -- only visible when auth is active */}
        {authEnabled && (
          <NavLink
            to="/audit"
            className={({ isActive }) =>
              `sk-nav-item ${isActive ? "active" : ""}`
            }
          >
            <ScrollText className="h-4 w-4 sk-nav-icon" />
            <span>Audit Log</span>
          </NavLink>
        )}
      </nav>

      {/* Connection Status */}
      <div
        className="mx-3 mb-3 rounded-lg border px-4 py-3 space-y-2.5"
        style={{ background: "var(--bg-card)", borderColor: "var(--border)" }}
      >
        <StatusIndicator
          icon={Database}
          label="Qdrant"
          status={status.qdrant}
          tooltip="Qdrant: Vector search engine"
        />
        <StatusIndicator
          icon={Cpu}
          label="Ollama"
          status={status.ollama}
          degraded={status.overall === "degraded"}
          tooltip="Ollama: Local LLM for Q&A"
        />
        <div
          className="flex items-center gap-2 pt-2 mt-1"
          style={{ borderTop: "1px solid var(--border)" }}
        >
          <span
            className="inline-block h-2.5 w-2.5 rounded-full"
            style={{
              background: status.overall === "connected"
                ? "#22c55e"
                : status.overall === "degraded"
                  ? "#f59e0b"
                  : status.overall === "offline"
                    ? "#ef4444"
                    : "var(--text-tertiary)",
            }}
          />
          <span
            className="text-[0.72rem]"
            style={{
              fontFamily: "var(--font-sans)",
              color: status.overall === "connected"
                ? "#22c55e"
                : status.overall === "degraded"
                  ? "#f59e0b"
                  : status.overall === "offline"
                    ? "#ef4444"
                    : "var(--text-tertiary)",
              fontWeight: 500,
            }}
            title={
              status.overall === "connected"
                ? "All services are running"
                : status.overall === "degraded"
                  ? "Search works but Ask requires Ollama"
                  : status.overall === "offline"
                    ? "Backend or Qdrant is unreachable"
                    : "Checking services..."
            }
          >
            {status.overall === "connected"
              ? "Connected"
              : status.overall === "degraded"
                ? "Degraded"
                : status.overall === "offline"
                  ? "Offline"
                  : "Checking..."}
          </span>
        </div>
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
  degraded,
  tooltip,
}: {
  icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }>;
  label: string;
  status: "checking" | "online" | "offline";
  degraded?: boolean;
  tooltip?: string;
}) {
  const statusColor =
    status === "online"
      ? degraded
        ? "#f59e0b"
        : "#22c55e"
      : status === "offline"
        ? "#ef4444"
        : "var(--text-tertiary)";

  const statusLabel =
    status === "online"
      ? degraded
        ? "Degraded"
        : "Connected"
      : status === "offline"
        ? "Offline"
        : "Checking...";

  return (
    <div className="flex items-center gap-2 text-xs" title={tooltip}>
      <Icon className="h-3.5 w-3.5" style={{ color: "var(--text-tertiary)" }} />
      <span style={{ fontFamily: "var(--font-sans)", color: "var(--text-secondary)", fontSize: "0.75rem", fontWeight: 500 }}>
        {label}
      </span>
      <span className="ml-auto flex items-center gap-1.5">
        {status === "checking" ? (
          <Loader2 className="h-3 w-3 animate-spin" style={{ color: "var(--text-tertiary)" }} />
        ) : (
          <>
            <span
              className="inline-block rounded-full"
              style={{
                width: "10px",
                height: "10px",
                background: statusColor,
              }}
            />
            <span
              style={{
                fontSize: "0.68rem",
                fontFamily: "var(--font-sans)",
                fontWeight: 500,
                color: statusColor,
              }}
            >
              {statusLabel}
            </span>
          </>
        )}
      </span>
    </div>
  );
}
