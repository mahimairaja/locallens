import { Card, CardContent } from "@/components/ui/card";
import {
  Archive,
  BarChart3,
  BookOpen,
  Box,
  Database,
  ExternalLink,
  Filter,
  Gauge,
  GitBranch,
  Layers,
  Search,
} from "lucide-react";

// ============================================================================
// Source of truth — one entry per stack component / Edge feature. Rendering
// is a simple .map() below. No markdown, no MDX, no new dependencies.
// ============================================================================

interface StackComponent {
  name: string;
  purpose: string;
  version: string;
  role: string;
}

const STACK: StackComponent[] = [
  {
    name: "Qdrant Edge",
    purpose: "Embedded vector store for the CLI",
    version: "qdrant-edge-py 0.6",
    role: "locallens index writes here, locally, on-device",
  },
  {
    name: "Qdrant Server",
    purpose: "Shared vector store for the web backend",
    version: "qdrant/qdrant:v1.14.0",
    role: "Receives sync pushes from the CLI, serves the web app",
  },
  {
    name: "all-MiniLM-L6-v2",
    purpose: "Sentence embeddings",
    version: "384-dim, cosine",
    role: "Encodes text chunks to vectors (via sentence-transformers)",
  },
  {
    name: "Ollama + qwen2.5:3b",
    purpose: "Local LLM for RAG answers",
    version: "Q4_K_M quantized",
    role: "Generates grounded answers from retrieved chunks",
  },
  {
    name: "Moonshine tiny-en",
    purpose: "On-device speech-to-text",
    version: "bundled assets",
    role: "Transcribes voice input on the /ask page",
  },
  {
    name: "Piper TTS (lessac-medium)",
    purpose: "On-device text-to-speech",
    version: "VITS / ONNX, auto-downloaded",
    role: "Plays back assistant answers via inline Listen button",
  },
  {
    name: "FastAPI",
    purpose: "HTTP API for the web app",
    version: "Python 3.11+",
    role: "Talks to Qdrant Server, streams RAG responses",
  },
  {
    name: "React + Vite",
    purpose: "Frontend",
    version: "React 19, Vite 8",
    role: "This UI you're looking at",
  },
];

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
    what: "Server-side aggregation over an indexed payload field — distinct values with counts.",
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
    how: "locallens sync pull --incremental calls snapshot_manifest() and applies update_from_snapshot — keeps warm shards warm, only moves the delta.",
    snippet:
      "manifest = shard.snapshot_manifest(); shard.update_from_snapshot(partial_snapshot_path)",
  },
  {
    icon: Gauge,
    name: "Optimizer tuning",
    what: "Per-shard control over deletion thresholds, vacuum cadence, and segment layout.",
    how: "LocalLens ships with a slightly more eager vacuum so deletes don't linger — tuned for personal-corpus re-indexing patterns.",
    snippet:
      "EdgeOptimizersConfig(deleted_threshold=0.2, vacuum_min_vector_number=100, default_segment_number=2)",
  },
];

// ============================================================================

export default function StackPage() {
  return (
    <div className="space-y-10 pb-12">
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
          Under the Hood
        </h2>
        <p
          className="mt-2 max-w-2xl text-sm"
          style={{ color: "var(--text-secondary)", fontFamily: "var(--font-sans)", lineHeight: 1.6 }}
        >
          LocalLens is an offline semantic file search built on Qdrant Edge,
          sentence-transformers, Ollama, Moonshine STT, and Piper TTS.
          Everything runs on your machine — no servers you don't own, no
          telemetry. This page walks through what's inside and how you can
          build with the same pieces.
        </p>
      </div>

      {/* Section 1 — Stack components */}
      <section className="space-y-4">
        <h3
          className="text-base"
          style={{
            fontFamily: "var(--font-sans)",
            fontWeight: 600,
            color: "var(--text-primary)",
            letterSpacing: "-0.005em",
          }}
        >
          The stack
        </h3>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {STACK.map((item) => (
            <Card key={item.name}>
              <CardContent className="p-5">
                <div className="flex items-center gap-2">
                  <Box className="h-4 w-4" style={{ color: "var(--accent)" }} />
                  <span
                    style={{
                      fontFamily: "var(--font-sans)",
                      fontWeight: 600,
                      color: "var(--text-primary)",
                      fontSize: "0.95rem",
                    }}
                  >
                    {item.name}
                  </span>
                </div>
                <p
                  className="mt-2 text-xs"
                  style={{ color: "var(--text-secondary)", lineHeight: 1.5 }}
                >
                  {item.purpose}
                </p>
                <p
                  className="mt-2 text-[0.7rem]"
                  style={{
                    color: "var(--text-tertiary)",
                    fontFamily: "var(--font-mono)",
                  }}
                >
                  {item.version}
                </p>
                <p
                  className="mt-3 text-xs"
                  style={{ color: "var(--text-secondary)", lineHeight: 1.5 }}
                >
                  {item.role}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {/* Section 2 — Qdrant Edge features we leverage */}
      <section className="space-y-4">
        <div>
          <h3
            className="text-base"
            style={{
              fontFamily: "var(--font-sans)",
              fontWeight: 600,
              color: "var(--text-primary)",
              letterSpacing: "-0.005em",
            }}
          >
            Qdrant Edge features we leverage
          </h3>
          <p
            className="mt-1 text-xs"
            style={{ color: "var(--text-tertiary)", fontFamily: "var(--font-sans)" }}
          >
            Each snippet is taken from the real call site in
            <span className="sk-source-tag mx-1">locallens/store.py</span> or{" "}
            <span className="sk-source-tag mx-1">locallens/sync.py</span>.
          </p>
        </div>
        <div className="space-y-3">
          {EDGE_FEATURES.map((feature) => (
            <Card key={feature.name}>
              <CardContent className="p-5">
                <div className="flex items-start gap-4">
                  <div
                    className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full"
                    style={{ background: "var(--accent-soft)" }}
                  >
                    <feature.icon
                      className="h-4 w-4"
                      style={{ color: "var(--accent)" }}
                    />
                  </div>
                  <div className="min-w-0 flex-1 space-y-2">
                    <p
                      style={{
                        fontFamily: "var(--font-sans)",
                        fontWeight: 600,
                        color: "var(--text-primary)",
                        fontSize: "0.95rem",
                      }}
                    >
                      {feature.name}
                    </p>
                    <p
                      className="text-sm"
                      style={{ color: "var(--text-secondary)", lineHeight: 1.55 }}
                    >
                      {feature.what}
                    </p>
                    <p
                      className="text-sm"
                      style={{ color: "var(--text-secondary)", lineHeight: 1.55 }}
                    >
                      <span
                        style={{
                          color: "var(--accent-hover)",
                          fontWeight: 600,
                          textTransform: "uppercase",
                          letterSpacing: "0.06em",
                          fontSize: "0.7rem",
                          marginRight: "0.4rem",
                        }}
                      >
                        How
                      </span>
                      {feature.how}
                    </p>
                    <pre
                      className="mt-1 overflow-x-auto rounded-md px-3 py-2 text-[0.75rem]"
                      style={{
                        background: "var(--bg-page)",
                        color: "var(--text-primary)",
                        fontFamily: "var(--font-mono)",
                        border: "1px solid var(--border)",
                        lineHeight: 1.55,
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

      {/* Section 3 — Try it yourself */}
      <section className="space-y-4">
        <h3
          className="text-base"
          style={{
            fontFamily: "var(--font-sans)",
            fontWeight: 600,
            color: "var(--text-primary)",
            letterSpacing: "-0.005em",
          }}
        >
          Try it yourself
        </h3>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <Card>
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
                style={{ color: "var(--text-secondary)" }}
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
                }}
              >
                pip install qdrant-edge-py
              </pre>
            </CardContent>
          </Card>
          <Card>
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
                style={{ color: "var(--text-secondary)" }}
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
          <Card>
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
                style={{ color: "var(--text-secondary)" }}
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
