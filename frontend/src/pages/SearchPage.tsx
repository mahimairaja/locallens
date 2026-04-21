import { useState, useCallback, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Search, FileSearch, Plus, Minus, X } from "lucide-react";
import { api } from "@/lib/api";
import type { SearchResult, SearchResponse } from "@/types";

const FILE_TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: "",      label: "All types" },
  { value: ".txt",  label: ".txt"  },
  { value: ".md",   label: ".md"   },
  { value: ".pdf",  label: ".pdf"  },
  { value: ".docx", label: ".docx" },
  { value: ".pptx", label: ".pptx" },
  { value: ".xlsx", label: ".xlsx" },
  { value: ".xls",  label: ".xls"  },
  { value: ".csv",  label: ".csv"  },
  { value: ".tsv",  label: ".tsv"  },
  { value: ".html", label: ".html" },
  { value: ".py",   label: ".py"   },
  { value: ".js",   label: ".js"   },
  { value: ".ts",   label: ".ts"   },
  { value: ".go",   label: ".go"   },
  { value: ".rs",   label: ".rs"   },
  { value: ".java", label: ".java" },
  { value: ".c",    label: ".c"    },
  { value: ".cpp",  label: ".cpp"  },
  { value: ".rb",   label: ".rb"   },
];

const RESULT_COUNT_OPTIONS = [5, 10, 20];

const SEARCH_MODES = [
  { value: "hybrid",   label: "Hybrid" },
  { value: "semantic",  label: "Semantic" },
  { value: "keyword",   label: "Keyword" },
];

const EXAMPLE_QUERIES = [
  "How does authentication work?",
  "Database connection setup",
  "Error handling patterns",
  "API endpoint definitions",
  "Configuration files",
];

export default function SearchPage() {
  const [searchParams] = useSearchParams();
  const [query, setQuery] = useState(searchParams.get("q") ?? "");
  const [topK, setTopK] = useState(10);
  const [fileType, setFileType] = useState<string>("");
  const [searchMode, setSearchMode] = useState<string>("hybrid");
  const [dateFrom, setDateFrom] = useState<string>("");
  const [dateTo, setDateTo] = useState<string>("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searchTime, setSearchTime] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [selectedResult, setSelectedResult] = useState<SearchResult | null>(null);
  const [addTexts, setAddTexts] = useState<string[]>([]);
  const [subtractTexts, setSubtractTexts] = useState<string[]>([]);

  const hasRefinements = addTexts.length > 0 || subtractTexts.length > 0;

  const doSearch = useCallback(
    async (q: string, boosts?: string[], suppressions?: string[]) => {
      if (q.trim().length < 2) return;
      setLoading(true);
      setHasSearched(true);
      const curBoosts = boosts ?? addTexts;
      const curSuppress = suppressions ?? subtractTexts;
      try {
        let resp: SearchResponse;
        if (curBoosts.length > 0 || curSuppress.length > 0) {
          resp = await api.refineSearch(
            q, curBoosts, curSuppress, topK, fileType || null, searchMode,
          );
        } else {
          resp = await api.search(
            q, topK, fileType || null, null, searchMode, dateFrom || null, dateTo || null,
          );
        }
        setResults(resp.results);
        setSearchTime(resp.search_time_ms);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    },
    [topK, fileType, searchMode, dateFrom, dateTo, addTexts, subtractTexts]
  );

  // Auto-search from URL param
  useEffect(() => {
    const q = searchParams.get("q");
    if (q) {
      setQuery(q);
      doSearch(q);
    }
  }, [searchParams, doSearch]);

  // Debounced search-as-you-type -- also re-runs when filter state changes.
  useEffect(() => {
    if (query.trim().length < 3) return;
    const timer = setTimeout(() => doSearch(query), 300);
    return () => clearTimeout(timer);
  }, [query, doSearch]);

  const highlightQuery = (text: string) => {
    if (!query.trim()) return text;
    const words = query.trim().split(/\s+/).filter(Boolean);
    const regex = new RegExp(`(${words.map(w => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join("|")})`, "gi");
    const parts = text.split(regex);
    return parts.map((part, i) =>
      regex.test(part) ? (
        <mark
          key={i}
          style={{
            background: "var(--accent-soft)",
            color: "var(--text-primary)",
            borderRadius: "3px",
            padding: "0 3px",
          }}
        >
          {part}
        </mark>
      ) : (
        part
      )
    );
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

  return (
    <div className="space-y-6">
      {/* Search Bar -- Step 8: full width, 18px, search icon left, copper bottom border */}
      <div className="space-y-4">
        <div className="relative">
          <Search
            className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2"
            style={{ color: "var(--text-tertiary)" }}
            strokeWidth={2}
          />
          <input
            type="text"
            placeholder="Search your files..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && doSearch(query)}
            className="sk-search-input"
            style={{
              width: "100%",
              paddingLeft: "3rem",
              paddingRight: "1.25rem",
              height: "56px",
              fontSize: "18px",
              fontFamily: "var(--font-sans)",
              fontStyle: query ? "normal" : "italic",
              background: "var(--bg-card)",
              color: "var(--text-primary)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-md)",
              boxShadow: "var(--shadow-sm)",
              transition: "border-color 150ms ease, box-shadow 150ms ease",
            }}
          />
        </div>

        {/* Query arithmetic hint */}
        {!hasSearched && (
          <p className="text-xs" style={{ color: "var(--text-tertiary)", fontStyle: "italic" }}>
            Use + to add concepts, - to subtract. Example: pricing +recent -draft
          </p>
        )}

        {/* Refinement pills */}
        {hasRefinements && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Refinements:</span>
            {addTexts.map((t, i) => (
              <span key={`add-${i}`} className="sk-query-tag-positive">
                <Plus className="inline w-3 h-3 mr-1" />
                {t.slice(0, 40)}{t.length > 40 ? "..." : ""}
                <button
                  className="ml-1 opacity-60 hover:opacity-100"
                  onClick={() => {
                    const next = addTexts.filter((_, j) => j !== i);
                    setAddTexts(next);
                    doSearch(query, next, subtractTexts);
                  }}
                >
                  <X className="w-3 h-3" />
                </button>
              </span>
            ))}
            {subtractTexts.map((t, i) => (
              <span key={`sub-${i}`} className="sk-query-tag-negative">
                <Minus className="inline w-3 h-3 mr-1" />
                {t.slice(0, 40)}{t.length > 40 ? "..." : ""}
                <button
                  className="ml-1 opacity-60 hover:opacity-100"
                  onClick={() => {
                    const next = subtractTexts.filter((_, j) => j !== i);
                    setSubtractTexts(next);
                    doSearch(query, addTexts, next);
                  }}
                >
                  <X className="w-3 h-3" />
                </button>
              </span>
            ))}
            <button
              className="text-xs underline"
              style={{ color: "var(--text-tertiary)" }}
              onClick={() => { setAddTexts([]); setSubtractTexts([]); doSearch(query, [], []); }}
            >
              Clear all
            </button>
          </div>
        )}

        {/* Filters row -- Step 8 & 9 */}
        <div
          className="flex flex-wrap items-center gap-x-4 gap-y-3"
          style={{ color: "var(--text-secondary)", fontFamily: "var(--font-sans)" }}
        >
          {/* Search mode segmented control -- Step 9 */}
          <div className="sk-segmented">
            {SEARCH_MODES.map((mode) => (
              <button
                key={mode.value}
                type="button"
                className={`sk-segmented-btn ${searchMode === mode.value ? "active" : ""}`}
                onClick={() => setSearchMode(mode.value)}
              >
                {mode.label}
              </button>
            ))}
          </div>

          {/* File type dropdown */}
          <label className="flex items-center gap-2">
            <span style={{ fontWeight: 500, fontSize: "0.8rem" }}>Type</span>
            <select
              value={fileType}
              onChange={(e) => setFileType(e.target.value)}
              className="sk-select"
            >
              {FILE_TYPE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>

          {/* Result count dropdown -- replaces slider */}
          <label className="flex items-center gap-2">
            <span style={{ fontWeight: 500, fontSize: "0.8rem" }}>Results</span>
            <select
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              className="sk-select"
            >
              {RESULT_COUNT_OPTIONS.map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
          </label>

          {/* Date filters */}
          <label className="flex items-center gap-2">
            <span style={{ fontWeight: 500, fontSize: "0.8rem" }}>From</span>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="sk-select"
            />
          </label>
          <label className="flex items-center gap-2">
            <span style={{ fontWeight: 500, fontSize: "0.8rem" }}>To</span>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="sk-select"
            />
          </label>

          {/* Search timing */}
          {searchTime !== null && (
            <span className="ml-auto text-xs" style={{ color: "var(--text-tertiary)" }}>
              {results.length} results in {searchTime.toFixed(0)}ms
            </span>
          )}
        </div>
      </div>

      {/* Results -- Step 10, 11 */}
      {loading ? (
        /* Loading state: 3 skeleton cards with shimmer -- Step 11 */
        <div className="space-y-4">
          {[0, 1, 2].map((i) => (
            <Card key={i}>
              <CardContent className="p-6 space-y-3">
                <div className="flex items-center gap-3">
                  <div className="sk-skeleton" style={{ width: "180px", height: "18px" }} />
                  <div className="sk-skeleton" style={{ width: "48px", height: "22px", borderRadius: "9999px" }} />
                </div>
                <div className="sk-skeleton" style={{ width: "60%", height: "14px" }} />
                <div className="space-y-2">
                  <div className="sk-skeleton" style={{ width: "100%", height: "14px" }} />
                  <div className="sk-skeleton" style={{ width: "90%", height: "14px" }} />
                  <div className="sk-skeleton" style={{ width: "70%", height: "14px" }} />
                </div>
                <div className="sk-skeleton" style={{ width: "100%", height: "4px", borderRadius: "9999px" }} />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : results.length > 0 ? (
        /* Results cards -- Step 10 */
        <div className="space-y-4">
          {results.map((r, idx) => (
            <Card
              key={`${r.file_path}-${r.chunk_index}`}
              className="sk-result-card sk-fade-up cursor-pointer"
              style={{ animationDelay: `${idx * 30}ms` }}
              onClick={() => setSelectedResult(r)}
            >
              <CardContent className="p-6">
                {/* Title row: bold file name + type badge */}
                <div className="flex items-center gap-3 mb-1">
                  <span
                    style={{
                      color: "var(--text-primary)",
                      fontWeight: 600,
                      fontSize: "16px",
                      fontFamily: "var(--font-sans)",
                    }}
                  >
                    {r.file_name}
                  </span>
                  <Badge className={typeTabClass(r.file_type)}>{r.file_type}</Badge>
                  {r.extractor && (
                    <span
                      className="rounded px-1.5 py-0.5 text-[0.65rem]"
                      style={{
                        background: "var(--bg-hover)",
                        color: "var(--text-tertiary)",
                        fontFamily: "var(--font-mono)",
                      }}
                    >
                      {r.extractor}
                    </span>
                  )}
                  {r.page_number != null && (
                    <span
                      className="text-[0.7rem]"
                      style={{ color: "var(--text-tertiary)", fontFamily: "var(--font-sans)" }}
                    >
                      p.{r.page_number}
                    </span>
                  )}
                </div>

                {/* Muted file path */}
                <p
                  className="truncate mb-3"
                  style={{
                    color: "var(--text-tertiary)",
                    fontSize: "0.75rem",
                    fontFamily: "var(--font-mono)",
                  }}
                >
                  {r.file_path}
                </p>

                {/* 3-line preview with ellipsis */}
                <p
                  className="line-clamp-3 text-sm mb-3"
                  style={{ color: "var(--text-secondary)", lineHeight: 1.6 }}
                >
                  {highlightQuery(r.chunk_text.slice(0, 300))}
                </p>

                {/* Bottom row: relevance bar + chunk info */}
                <div className="flex items-center gap-4">
                  <div className="sk-relevance-track flex-1">
                    <div
                      className="sk-relevance-fill"
                      style={{ width: `${Math.max(2, Math.round(r.score * 100))}%` }}
                    />
                  </div>
                  <span
                    className="sk-meter"
                    style={{ fontSize: "0.7rem" }}
                  >
                    {(r.score * 100).toFixed(1)}%
                  </span>
                  <span
                    style={{
                      color: "var(--text-tertiary)",
                      fontSize: "0.72rem",
                      fontFamily: "var(--font-sans)",
                      whiteSpace: "nowrap",
                    }}
                  >
                    Chunk {r.chunk_index + 1}
                  </span>
                  <span className="flex items-center gap-1 ml-auto">
                    <button
                      className="sk-refine-btn sk-refine-boost"
                      title="More like this"
                      onClick={(e) => {
                        e.stopPropagation();
                        const next = [...addTexts, r.chunk_text];
                        setAddTexts(next);
                        doSearch(query, next, subtractTexts);
                      }}
                    >
                      <Plus className="w-3.5 h-3.5" />
                    </button>
                    <button
                      className="sk-refine-btn sk-refine-suppress"
                      title="Less like this"
                      onClick={(e) => {
                        e.stopPropagation();
                        const next = [...subtractTexts, r.chunk_text];
                        setSubtractTexts(next);
                        doSearch(query, addTexts, next);
                      }}
                    >
                      <Minus className="w-3.5 h-3.5" />
                    </button>
                  </span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : hasSearched ? (
        /* No results state -- Step 11 */
        <div
          className="flex flex-col items-center justify-center py-16"
          style={{ color: "var(--text-tertiary)" }}
        >
          <FileSearch
            className="mb-4"
            style={{ width: "48px", height: "48px", color: "var(--text-tertiary)", opacity: 0.5 }}
            strokeWidth={1.5}
          />
          <p
            style={{
              fontFamily: "var(--font-sans)",
              fontSize: "1rem",
              fontWeight: 500,
              color: "var(--text-secondary)",
              marginBottom: "0.5rem",
            }}
          >
            No results found
          </p>
          <p
            style={{
              fontFamily: "var(--font-sans)",
              fontSize: "0.85rem",
              color: "var(--text-tertiary)",
            }}
          >
            Try broader terms or check your file type filter
          </p>
        </div>
      ) : (
        /* Empty state before search -- Step 11 */
        <div
          className="flex flex-col items-center justify-center py-16"
          style={{ color: "var(--text-tertiary)" }}
        >
          <Search
            className="mb-4"
            style={{ width: "56px", height: "56px", color: "var(--accent)", opacity: 0.3 }}
            strokeWidth={1.5}
          />
          <p
            style={{
              fontFamily: "var(--font-sans)",
              fontSize: "1.05rem",
              fontWeight: 500,
              color: "var(--text-secondary)",
              marginBottom: "1rem",
            }}
          >
            Search your files
          </p>
          <div className="flex flex-wrap justify-center gap-2 max-w-lg">
            {EXAMPLE_QUERIES.map((eq) => (
              <button
                key={eq}
                type="button"
                className="sk-query-chip"
                onClick={() => {
                  setQuery(eq);
                  doSearch(eq);
                }}
              >
                {eq}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* File Preview Modal */}
      <Dialog
        open={selectedResult !== null}
        onOpenChange={(open) => !open && setSelectedResult(null)}
      >
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle
              className="flex items-center gap-3"
              style={{ color: "var(--text-primary)", fontSize: "1.15rem", fontWeight: 600 }}
            >
              {selectedResult?.file_name}
              {selectedResult && (
                <Badge className={typeTabClass(selectedResult.file_type)}>
                  {selectedResult.file_type}
                </Badge>
              )}
            </DialogTitle>
          </DialogHeader>
          <div className="flex items-center gap-2 text-xs" style={{ color: "var(--text-tertiary)", fontFamily: "var(--font-mono)" }}>
            <span>{selectedResult?.file_path}</span>
            {selectedResult?.extractor && (
              <span className="rounded px-1.5 py-0.5" style={{ background: "var(--bg-hover)" }}>
                {selectedResult.extractor}
              </span>
            )}
            {selectedResult?.page_number != null && (
              <span>p.{selectedResult.page_number}</span>
            )}
          </div>
          <div className="sk-brass-rule" />
          <ScrollArea className="max-h-96">
            <pre
              className="whitespace-pre-wrap text-sm"
              style={{ color: "var(--text-primary)", fontFamily: "var(--font-mono)", lineHeight: 1.55 }}
            >
              {selectedResult?.chunk_text}
            </pre>
          </ScrollArea>
        </DialogContent>
      </Dialog>
    </div>
  );
}
