import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import {
  Archive,
  BarChart3,
  BookOpen,
  Box,
  Check,
  Cpu,
  Database,
  ExternalLink,
  Filter,
  Gauge,
  GitBranch,
  Globe,
  HardDrive,
  Layers,
  Minus,
  Monitor,
  Search,
  Server,
} from "lucide-react";

// ============================================================================
// Source of truth -- one entry per stack component / Edge feature. Rendering
// is a simple .map() below. No markdown, no MDX, no new dependencies.
// ============================================================================

interface StackComponent {
  name: string;
  purpose: string;
  version: string;
  role: string;
  layer: "Storage" | "AI Models" | "Backend" | "Frontend";
}

const STACK: StackComponent[] = [
  {
    name: "Qdrant Edge",
    purpose: "Embedded vector store for the CLI",
    version: "qdrant-edge-py 0.6",
    role: "locallens index writes here, locally, on-device",
    layer: "Storage",
  },
  {
    name: "Qdrant Server",
    purpose: "Shared vector store for the web backend",
    version: "qdrant/qdrant:v1.14.0",
    role: "Receives sync pushes from the CLI, serves the web app",
    layer: "Storage",
  },
  {
    name: "all-MiniLM-L6-v2",
    purpose: "Sentence embeddings",
    version: "384-dim, cosine",
    role: "Encodes text chunks to vectors (via sentence-transformers)",
    layer: "AI Models",
  },
  {
    name: "Ollama + qwen2.5:3b",
    purpose: "Local LLM for RAG answers",
    version: "Q4_K_M quantized",
    role: "Generates grounded answers from retrieved chunks",
    layer: "AI Models",
  },
  {
    name: "Moonshine tiny-en",
    purpose: "On-device speech-to-text",
    version: "bundled assets",
    role: "Transcribes voice input on the /ask page",
    layer: "AI Models",
  },
  {
    name: "Piper TTS (lessac-medium)",
    purpose: "On-device text-to-speech",
    version: "VITS / ONNX, auto-downloaded",
    role: "Plays back assistant answers via inline Listen button",
    layer: "AI Models",
  },
  {
    name: "FastAPI",
    purpose: "HTTP API for the web app",
    version: "Python 3.11+",
    role: "Talks to Qdrant Server, streams RAG responses",
    layer: "Backend",
  },
  {
    name: "React + Vite",
    purpose: "Frontend",
    version: "React 19, Vite 8",
    role: "This UI you're looking at",
    layer: "Frontend",
  },
];

const LAYER_ORDER: StackComponent["layer"][] = ["Storage", "AI Models", "Backend", "Frontend"];

const LAYER_ICONS: Record<string, React.ComponentType<{ className?: string; style?: React.CSSProperties }>> = {
  Storage: Database,
  "AI Models": Cpu,
  Backend: Server,
  Frontend: Globe,
};

interface EdgeFeature {
  icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }>;
  name: string;
  what: string;
  how: string;
  snippet: string;
}

const EDGE_FEATURES: EdgeFeature[] = [
  {
    icon: Layers,
    name: "Named vectors",
    what: "A collection can store multiple vector fields per point, each keyed by name.",
    how: "Both the CLI shard and the Docker backend use one named vector, \"text\", so points move between them without translation.",
    snippet:
      'EdgeConfig(vectors={"text": EdgeVectorParams(size=384, distance=Distance.Cosine)})',
  },
  {
    icon: Filter,
    name: "Payload indexes",
    what: "Keyword indexes over payload fields turn filter lookups into O(1) server-side operations.",
    how: "We index file_hash, file_path, and file_type. Re-indexing a folder is a single filtered count per file instead of scrolling the whole shard.",
    snippet:
      'shard.update(UpdateOperation.create_field_index("file_hash", PayloadSchemaType.Keyword))',
  },
  {
    icon: Search,
    name: "Filtered search",
    what: "Combine vector similarity with payload constraints in a single query.",
    how: 'The /search page and locallens search --file-type .pdf both thread optional filters through Query.Nearest.',
    snippet:
      'shard.query(QueryRequest(query=Query.Nearest(vec, using="text"), filter=Filter(must=[FieldCondition(key="file_type", match=MatchValue(value=".pdf"))])))',
  },
  {
    icon: BarChart3,
    name: "Facets",
    what: "Server-side aggregation over an indexed payload field -- distinct values with counts.",
    how: "The Dashboard and the CLI stats command both ask the shard for the file-type breakdown instead of aggregating in Python.",
    snippet: 'shard.facet(FacetRequest(key="file_type", exact=True))',
  },
  {
    icon: GitBranch,
    name: "Push sync",
    what: "Dual-write pattern: every local upsert is also sent to a remote Qdrant server as a qdrant-client PointStruct.",
    how: "Set QDRANT_SYNC_URL=http://localhost:6333 before running locallens index and the CLI uploads each batch to the Dockerized backend so the web app sees the same data instantly.",
    snippet:
      'server_client.upsert(collection_name="locallens", points=[PointStruct(id=..., vector={"text": emb}, payload=...)])',
  },
  {
    icon: Archive,
    name: "Pull snapshot",
    what: "Initialize a local shard from a server-side snapshot so multiple devices share the same corpus.",
    how: "locallens sync pull downloads a full snapshot from the configured server and unpacks it into ~/.locallens/qdrant_data.",
    snippet: "EdgeShard.unpack_snapshot(snapshot_path, data_dir)",
  },
  {
    icon: GitBranch,
    name: "Partial snapshot sync",
    what: "Send the local manifest to the server, receive only the segments that changed.",
    how: "locallens sync pull --incremental calls snapshot_manifest() and applies update_from_snapshot -- keeps warm shards warm, only moves the delta.",
    snippet:
      "manifest = shard.snapshot_manifest(); shard.update_from_snapshot(partial_snapshot_path)",
  },
  {
    icon: Gauge,
    name: "Optimizer tuning",
    what: "Per-shard control over deletion thresholds, vacuum cadence, and segment layout.",
    how: "LocalLens ships with a slightly more eager vacuum so deletes don't linger -- tuned for personal-corpus re-indexing patterns.",
    snippet:
      "EdgeOptimizersConfig(deleted_threshold=0.2, vacuum_min_vector_number=100, default_segment_number=2)",
  },
];

interface SystemReq {
  label: string;
  value: string;
  icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }>;
}

const SYSTEM_REQUIREMENTS: SystemReq[] = [
  { label: "RAM", value: "4 GB minimum (8 GB recommended for LLM)", icon: Cpu },
  { label: "Disk", value: "~2 GB for models + index data", icon: HardDrive },
  { label: "OS", value: "macOS 12+, Linux (x86_64 / arm64), Windows 10+ (WSL2)", icon: Monitor },
];

// -- Doctor card definitions --------------------------------------------------

interface DoctorCard {
  id: string;
  name: string;
  description: string;
  statusKey: string; // key in healthState
  optional?: boolean;
}

const DOCTOR_CARDS: DoctorCard[] = [
  {
    id: "qdrant-edge",
    name: "Qdrant Edge",
    description: "Embedded vector shard for the CLI (qdrant-edge-py)",
    statusKey: "qdrantEdge",
  },
  {
    id: "qdrant-server",
    name: "Qdrant Server",
    description: "Docker container on :6333 for the web backend",
    statusKey: "qdrantServer",
  },
  {
    id: "ollama",
    name: "Ollama",
    description: "Local LLM runtime (qwen2.5:3b Q4_K_M)",
    statusKey: "ollama",
  },
  {
    id: "embedder",
    name: "Embedder",
    description: "all-MiniLM-L6-v2, 384-dim cosine",
    statusKey: "embedder",
  },
  {
    id: "stt",
    name: "Moonshine STT",
    description: "On-device speech-to-text (tiny-en)",
    statusKey: "stt",
    optional: true,
  },
  {
    id: "tts",
    name: "Piper TTS",
    description: "On-device text-to-speech (lessac-medium)",
    statusKey: "tts",
    optional: true,
  },
];

// -- Component choice table ---------------------------------------------------

const COMPONENT_TABLE: { component: string; choice: string }[] = [
  { component: "Embeddings", choice: "all-MiniLM-L6-v2 (sentence-transformers)" },
  { component: "Keyword", choice: "Qdrant payload indexes (file_hash, file_path, file_type)" },
  { component: "LLM", choice: "Ollama + qwen2.5:3b (Q4_K_M, streamed)" },
  { component: "STT/TTS", choice: "Moonshine tiny-en / Piper lessac-medium (optional)" },
  { component: "Backend", choice: "FastAPI + qdrant-client + httpx" },
];

// -- Supported file types -----------------------------------------------------

const FILE_TYPE_CHIPS = [
  ".txt", ".md", ".pdf", ".docx", ".py", ".ts", ".js",
  ".rs", ".go", ".java", ".rb", ".c", ".cpp", ".csv", ".html",
];

// ============================================================================

type HealthState = Record<string, "ok" | "opt" | "unreachable" | "loading">;

export default function StackPage() {
  const [health, setHealth] = useState<HealthState>({
    qdrantEdge: "ok", // Edge is always present (it is bundled)
    qdrantServer: "loading",
    ollama: "loading",
    embedder: "ok", // sentence-transformers is a hard dep
    stt: "loading",
    tts: "loading",
  });

  useEffect(() => {
    let cancelled = false;

    async function probe() {
      const next: HealthState = { ...health };

      // /api/health gives us qdrant + ollama
      try {
        const res = await fetch("/api/health");
        if (res.ok) {
          const data = await res.json();
          next.qdrantServer = data.qdrant === "ok" ? "ok" : "unreachable";
          next.ollama = data.ollama === "ok" ? "ok" : "unreachable";
        } else {
          next.qdrantServer = "unreachable";
          next.ollama = "unreachable";
        }
      } catch {
        next.qdrantServer = "unreachable";
        next.ollama = "unreachable";
      }

      // /api/voice/status gives us stt + tts
      try {
        const res = await fetch("/api/voice/status");
        if (res.ok) {
          const data = await res.json();
          next.stt = data.stt_available ? "ok" : "opt";
          next.tts = data.tts_available ? "ok" : "opt";
        } else {
          next.stt = "opt";
          next.tts = "opt";
        }
      } catch {
        next.stt = "opt";
        next.tts = "opt";
      }

      if (!cancelled) setHealth(next);
    }

    probe();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // -- Status rendering helpers -----------------------------------------------

  function StatusIndicator({ status }: { status: "ok" | "opt" | "unreachable" | "loading" }) {
    if (status === "loading") {
      return (
        <span
          className="inline-block h-2 w-2 rounded-full"
          style={{ background: "var(--text-tertiary)" }}
        />
      );
    }
    if (status === "ok") {
      return <Check className="h-3.5 w-3.5" style={{ color: "var(--success)" }} />;
    }
    if (status === "opt") {
      return <Minus className="h-3.5 w-3.5" style={{ color: "var(--warning)" }} />;
    }
    return <Minus className="h-3.5 w-3.5" style={{ color: "var(--danger)" }} />;
  }

  function statusLabel(status: string, optional?: boolean): string {
    if (status === "loading") return "checking...";
    if (status === "ok") return "ok";
    if (status === "opt") return "opt";
    if (optional) return "not installed";
    return "unreachable";
  }

  // -- How many are healthy? --------------------------------------------------
  const okCount = Object.values(health).filter((v) => v === "ok").length;
  const totalCount = Object.keys(health).length;

  return (
    <div className="space-y-10 pb-12">
      {/* Page header */}
      <div>
        <h2
          className="text-2xl"
          style={{
            fontFamily: "var(--font-sans)",
            fontWeight: 600,
            color: "var(--text-primary)",
            letterSpacing: "-0.015em",
          }}
        >
          Stack
        </h2>
        <p
          className="mt-2 max-w-2xl text-sm"
          style={{ color: "var(--text-secondary)", fontFamily: "var(--font-sans)", lineHeight: 1.6 }}
        >
          Live doctor check, component matrix, and Qdrant Edge feature map.
          Everything runs on your machine: no servers you don't own, no telemetry.
        </p>
      </div>

      {/* ================================================================
          Section 1: Doctor cards (2x3 grid)
          ================================================================ */}
      <section className="space-y-4">
        <h3
          className="text-sm uppercase"
          style={{
            fontFamily: "var(--font-sans)",
            fontWeight: 600,
            color: "var(--text-secondary)",
            letterSpacing: "0.08em",
          }}
        >
          Component status
        </h3>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {DOCTOR_CARDS.map((card) => {
            const st = health[card.statusKey] || "loading";
            return (
              <Card key={card.id} className="sk-lift">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <span
                      style={{
                        fontFamily: "var(--font-sans)",
                        fontWeight: 600,
                        color: "var(--text-primary)",
                        fontSize: "0.9rem",
                      }}
                    >
                      {card.name}
                    </span>
                    <div className="flex items-center gap-1.5">
                      <StatusIndicator status={st} />
                      <span
                        className="text-[0.7rem]"
                        style={{
                          fontFamily: "var(--font-mono)",
                          color:
                            st === "ok"
                              ? "var(--success)"
                              : st === "opt"
                                ? "var(--warning)"
                                : st === "unreachable"
                                  ? "var(--danger)"
                                  : "var(--text-tertiary)",
                        }}
                      >
                        {statusLabel(st, card.optional)}
                      </span>
                    </div>
                  </div>
                  <p
                    className="mt-1.5 text-[0.72rem]"
                    style={{
                      fontFamily: "var(--font-mono)",
                      color: "var(--text-tertiary)",
                      lineHeight: 1.45,
                    }}
                  >
                    {card.description}
                  </p>
                </CardContent>
              </Card>
            );
          })}
        </div>

        {/* Accent summary bar */}
        <div
          className="flex items-center gap-4 rounded-lg px-4 py-3"
          style={{
            background: "var(--accent-soft)",
            border: "1px solid var(--accent)",
          }}
        >
          <span
            className="text-xs"
            style={{
              fontFamily: "var(--font-sans)",
              fontWeight: 600,
              color: "var(--accent-hover)",
            }}
          >
            {okCount}/{totalCount} components healthy
          </span>
          <div className="flex-1">
            <div
              className="h-1.5 overflow-hidden rounded-full"
              style={{ background: "rgba(198,123,60,0.15)" }}
            >
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{
                  width: `${Math.round((okCount / totalCount) * 100)}%`,
                  background: "var(--accent)",
                }}
              />
            </div>
          </div>
          <span
            className="text-[0.7rem]"
            style={{
              fontFamily: "var(--font-mono)",
              color: "var(--accent-hover)",
            }}
          >
            ~2 GB models + index
          </span>
        </div>
      </section>

      {/* ================================================================
          Section 2: Component choice table
          ================================================================ */}
      <section className="space-y-4">
        <h3
          className="text-sm uppercase"
          style={{
            fontFamily: "var(--font-sans)",
            fontWeight: 600,
            color: "var(--text-secondary)",
            letterSpacing: "0.08em",
          }}
        >
          Component choices
        </h3>
        <div
          className="overflow-hidden rounded-lg"
          style={{
            border: "1px solid var(--border)",
            fontFamily: "var(--font-mono)",
            fontSize: "0.78rem",
          }}
        >
          {/* Header row */}
          <div
            className="grid grid-cols-[140px_1fr] gap-0"
            style={{
              background: "var(--bg-sidebar)",
              borderBottom: "1px solid var(--border)",
            }}
          >
            <div
              className="px-4 py-2.5"
              style={{
                fontWeight: 600,
                color: "var(--text-secondary)",
                letterSpacing: "0.06em",
                textTransform: "uppercase",
                fontSize: "0.68rem",
              }}
            >
              Component
            </div>
            <div
              className="px-4 py-2.5"
              style={{
                fontWeight: 600,
                color: "var(--text-secondary)",
                letterSpacing: "0.06em",
                textTransform: "uppercase",
                fontSize: "0.68rem",
                borderLeft: "1px solid var(--border)",
              }}
            >
              Choice
            </div>
          </div>
          {/* Data rows */}
          {COMPONENT_TABLE.map((row, i) => (
            <div
              key={row.component}
              className="grid grid-cols-[140px_1fr] gap-0"
              style={{
                borderBottom:
                  i < COMPONENT_TABLE.length - 1
                    ? "1px dashed var(--border)"
                    : "none",
                background: i % 2 === 0 ? "var(--bg-card)" : "var(--bg-page)",
              }}
            >
              <div
                className="px-4 py-2.5"
                style={{
                  fontWeight: 500,
                  color: "var(--text-primary)",
                }}
              >
                {row.component}
              </div>
              <div
                className="px-4 py-2.5"
                style={{
                  color: "var(--text-secondary)",
                  borderLeft: "1px solid var(--border)",
                }}
              >
                {row.choice}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ================================================================
          Section 3: Qdrant Edge feature cards (compact)
          ================================================================ */}
      <section className="space-y-4">
        <div>
          <h3
            className="text-sm uppercase"
            style={{
              fontFamily: "var(--font-sans)",
              fontWeight: 600,
              color: "var(--text-secondary)",
              letterSpacing: "0.08em",
            }}
          >
            Qdrant Edge features we leverage
          </h3>
          <p
            className="mt-1 text-xs"
            style={{ color: "var(--text-tertiary)", fontFamily: "var(--font-sans)" }}
          >
            Snippets from the real call sites in
            <span className="sk-source-tag mx-1">locallens/store.py</span> and{" "}
            <span className="sk-source-tag mx-1">locallens/sync.py</span>.
          </p>
        </div>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {EDGE_FEATURES.map((feature) => (
            <Card key={feature.name} className="sk-lift">
              <CardContent className="p-4">
                <div className="flex items-start gap-3">
                  <div
                    className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full"
                    style={{ background: "var(--accent-soft)" }}
                  >
                    <feature.icon
                      className="h-3.5 w-3.5"
                      style={{ color: "var(--accent)" }}
                    />
                  </div>
                  <div className="min-w-0 flex-1 space-y-1.5">
                    <p
                      style={{
                        fontFamily: "var(--font-sans)",
                        fontWeight: 600,
                        color: "var(--text-primary)",
                        fontSize: "0.85rem",
                      }}
                    >
                      {feature.name}
                    </p>
                    <p
                      className="text-xs"
                      style={{ color: "var(--text-secondary)", lineHeight: 1.5, fontFamily: "var(--font-sans)" }}
                    >
                      {feature.what}
                    </p>
                    <p
                      className="text-xs"
                      style={{ color: "var(--text-secondary)", lineHeight: 1.5, fontFamily: "var(--font-sans)" }}
                    >
                      <span
                        style={{
                          color: "var(--accent-hover)",
                          fontWeight: 600,
                          textTransform: "uppercase",
                          letterSpacing: "0.06em",
                          fontSize: "0.65rem",
                          marginRight: "0.35rem",
                        }}
                      >
                        How
                      </span>
                      {feature.how}
                    </p>
                    <pre
                      className="overflow-x-auto rounded-md px-2.5 py-1.5 text-[0.68rem]"
                      style={{
                        background: "var(--bg-page)",
                        color: "var(--text-primary)",
                        fontFamily: "var(--font-mono)",
                        border: "1px solid var(--border)",
                        lineHeight: 1.5,
                        borderRadius: "6px",
                      }}
                    >
                      {feature.snippet}
                    </pre>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {/* ================================================================
          Section 4: Supported file types (chip row)
          ================================================================ */}
      <section className="space-y-4">
        <h3
          className="text-sm uppercase"
          style={{
            fontFamily: "var(--font-sans)",
            fontWeight: 600,
            color: "var(--text-secondary)",
            letterSpacing: "0.08em",
          }}
        >
          Supported file types
        </h3>
        <div className="flex flex-wrap gap-2">
          {FILE_TYPE_CHIPS.map((ext) => {
            // Derive pill class from extension
            const cls = `sk-pill-${ext.replace(".", "")}`;
            return (
              <span
                key={ext}
                className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[0.72rem] font-medium ${cls}`}
                style={{ fontFamily: "var(--font-mono)" }}
              >
                {ext}
              </span>
            );
          })}
          <span
            className="inline-flex items-center rounded-full px-2.5 py-0.5 text-[0.72rem] font-medium"
            style={{
              fontFamily: "var(--font-mono)",
              background: "var(--accent-soft)",
              color: "var(--accent-hover)",
              border: "1px dashed var(--accent)",
            }}
          >
            + plugin
          </span>
        </div>
      </section>

      {/* ================================================================
          Section 5: The full stack (grouped by layer -- existing)
          ================================================================ */}
      <section className="space-y-6">
        <h3
          className="text-sm uppercase"
          style={{
            fontFamily: "var(--font-sans)",
            fontWeight: 600,
            color: "var(--text-secondary)",
            letterSpacing: "0.08em",
          }}
        >
          The stack
        </h3>
        {LAYER_ORDER.map((layer) => {
          const items = STACK.filter((s) => s.layer === layer);
          if (items.length === 0) return null;
          const LayerIcon = LAYER_ICONS[layer] || Box;
          return (
            <div key={layer} className="space-y-3">
              <div className="flex items-center gap-2">
                <LayerIcon className="h-4 w-4" style={{ color: "var(--accent)" }} />
                <span
                  className="text-xs uppercase"
                  style={{
                    fontFamily: "var(--font-sans)",
                    fontWeight: 600,
                    color: "var(--text-secondary)",
                    letterSpacing: "0.08em",
                  }}
                >
                  {layer}
                </span>
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {items.map((item) => (
                  <Card key={item.name} className="sk-lift">
                    <CardContent className="p-4">
                      <div className="flex items-center gap-2">
                        <Box className="h-3.5 w-3.5" style={{ color: "var(--accent)" }} />
                        <span
                          style={{
                            fontFamily: "var(--font-sans)",
                            fontWeight: 600,
                            color: "var(--text-primary)",
                            fontSize: "0.88rem",
                          }}
                        >
                          {item.name}
                        </span>
                      </div>
                      <p
                        className="mt-1.5 text-xs"
                        style={{ color: "var(--text-secondary)", lineHeight: 1.5, fontFamily: "var(--font-sans)" }}
                      >
                        {item.purpose}
                      </p>
                      <p
                        className="mt-1.5 text-[0.68rem]"
                        style={{
                          color: "var(--text-tertiary)",
                          fontFamily: "var(--font-mono)",
                        }}
                      >
                        {item.version}
                      </p>
                      <p
                        className="mt-2 text-xs"
                        style={{ color: "var(--text-secondary)", lineHeight: 1.5, fontFamily: "var(--font-sans)" }}
                      >
                        {item.role}
                      </p>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          );
        })}
      </section>

      {/* ================================================================
          Section 6: System Requirements
          ================================================================ */}
      <section className="space-y-4">
        <h3
          className="text-sm uppercase"
          style={{
            fontFamily: "var(--font-sans)",
            fontWeight: 600,
            color: "var(--text-secondary)",
            letterSpacing: "0.08em",
          }}
        >
          System Requirements
        </h3>
        <Card>
          <CardContent className="p-5">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              {SYSTEM_REQUIREMENTS.map((req) => (
                <div key={req.label} className="flex items-start gap-3">
                  <div
                    className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full"
                    style={{ background: "var(--accent-soft)" }}
                  >
                    <req.icon className="h-4 w-4" style={{ color: "var(--accent)" }} />
                  </div>
                  <div>
                    <p
                      className="text-sm"
                      style={{
                        fontFamily: "var(--font-sans)",
                        fontWeight: 600,
                        color: "var(--text-primary)",
                      }}
                    >
                      {req.label}
                    </p>
                    <p
                      className="mt-0.5 text-xs"
                      style={{
                        color: "var(--text-secondary)",
                        fontFamily: "var(--font-sans)",
                        lineHeight: 1.5,
                      }}
                    >
                      {req.value}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </section>

      {/* ================================================================
          Section 7: Try it yourself
          ================================================================ */}
      <section className="space-y-4">
        <h3
          className="text-sm uppercase"
          style={{
            fontFamily: "var(--font-sans)",
            fontWeight: 600,
            color: "var(--text-secondary)",
            letterSpacing: "0.08em",
          }}
        >
          Try it yourself
        </h3>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <Card className="sk-lift">
            <CardContent className="p-5">
              <div className="flex items-center gap-2">
                <Database className="h-4 w-4" style={{ color: "var(--accent)" }} />
                <span
                  style={{
                    fontFamily: "var(--font-sans)",
                    fontWeight: 600,
                    color: "var(--text-primary)",
                  }}
                >
                  Install
                </span>
              </div>
              <p
                className="mt-2 text-xs"
                style={{ color: "var(--text-secondary)", fontFamily: "var(--font-sans)" }}
              >
                Add Qdrant Edge to any Python project:
              </p>
              <pre
                className="mt-3 overflow-x-auto rounded-md px-3 py-2 text-[0.8rem]"
                style={{
                  background: "var(--bg-page)",
                  color: "var(--text-primary)",
                  fontFamily: "var(--font-mono)",
                  border: "1px solid var(--border)",
                  borderRadius: "8px",
                }}
              >
                pip install qdrant-edge-py
              </pre>
            </CardContent>
          </Card>
          <Card className="sk-lift">
            <CardContent className="p-5">
              <div className="flex items-center gap-2">
                <BookOpen className="h-4 w-4" style={{ color: "var(--accent)" }} />
                <span
                  style={{
                    fontFamily: "var(--font-sans)",
                    fontWeight: 600,
                    color: "var(--text-primary)",
                  }}
                >
                  Read the docs
                </span>
              </div>
              <p
                className="mt-2 text-xs"
                style={{ color: "var(--text-secondary)", fontFamily: "var(--font-sans)" }}
              >
                The quickstart walks through shard setup, filtered queries,
                facets, and snapshot sync.
              </p>
              <a
                href="https://qdrant.tech/documentation/edge/"
                target="_blank"
                rel="noopener noreferrer"
                className="mt-3 inline-flex items-center gap-1.5 text-sm"
                style={{ color: "var(--accent)", fontWeight: 500 }}
              >
                qdrant.tech/documentation/edge
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            </CardContent>
          </Card>
          <Card className="sk-lift">
            <CardContent className="p-5">
              <div className="flex items-center gap-2">
                <GitBranch className="h-4 w-4" style={{ color: "var(--accent)" }} />
                <span
                  style={{
                    fontFamily: "var(--font-sans)",
                    fontWeight: 600,
                    color: "var(--text-primary)",
                  }}
                >
                  See examples
                </span>
              </div>
              <p
                className="mt-2 text-xs"
                style={{ color: "var(--text-secondary)", fontFamily: "var(--font-sans)" }}
              >
                Reference Python and Rust implementations in the Qdrant
                repository.
              </p>
              <a
                href="https://github.com/qdrant/qdrant/tree/dev/lib/edge"
                target="_blank"
                rel="noopener noreferrer"
                className="mt-3 inline-flex items-center gap-1.5 text-sm"
                style={{ color: "var(--accent)", fontWeight: 500 }}
              >
                github.com/qdrant/qdrant
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            </CardContent>
          </Card>
        </div>
      </section>

      <p
        className="text-center text-xs"
        style={{ color: "var(--text-tertiary)", fontFamily: "var(--font-sans)" }}
      >
        LocalLens is MIT-licensed. Fork it, strip it, rebuild it.
      </p>
    </div>
  );
}
