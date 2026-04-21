import { useState, useCallback, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Search, FileSearch, Plus, Minus, X, Calendar } from "lucide-react";
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

/* ---- Shared inline-style constants matching the wireframe spec ---- */
const CHIP_BASE: React.CSSProperties = {
  fontFamily: "'JetBrains Mono', var(--font-mono)",
  fontSize: "9px",
  padding: "3px 7px",
  border: "1px solid var(--border)",
  borderRadius: "10px",
  cursor: "pointer",
  display: "inline-flex",
  alignItems: "center",
  gap: "4px",
  whiteSpace: "nowrap",
  transition: "all 120ms ease",
  lineHeight: 1.4,
};

const CHIP_ACTIVE: React.CSSProperties = {
  ...CHIP_BASE,
  background: "var(--text-primary)",
  color: "var(--bg-card)",
  borderColor: "var(--text-primary)",
};

const CHIP_ADD: React.CSSProperties = {
  ...CHIP_BASE,
  background: "transparent",
  color: "var(--text-tertiary)",
  borderStyle: "dashed",
};

const CHIP_MODE: React.CSSProperties = {
  ...CHIP_BASE,
  background: "transparent",
  color: "var(--text-secondary)",
  borderColor: "var(--border)",
};

const CHIP_MODE_ACTIVE: React.CSSProperties = {
  ...CHIP_BASE,
  background: "var(--accent)",
  color: "var(--text-on-accent)",
  borderColor: "var(--accent)",
};

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

  /* Popover state for add-filter chips */
  const [showTypeMenu, setShowTypeMenu] = useState(false);
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [showCountMenu, setShowCountMenu] = useState(false);

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
        <span
          key={i}
          style={{
            fontWeight: 700,
            color: "var(--accent)",
          }}
        >
          {part}
        </span>
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

  /* Determine if any filters are active for display */
  const hasActiveFilters = fileType !== "" || dateFrom !== "" || dateTo !== "" || topK !== 10;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      {/* ============================================================
          PILL-SHAPED SEARCH BAR with mode chips inside
          ============================================================ */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          background: "var(--bg-card)",
          border: "1px solid var(--border)",
          borderRadius: "20px",
          padding: "6px 8px 6px 16px",
          boxShadow: "var(--shadow-sm)",
          transition: "border-color 150ms ease, box-shadow 150ms ease",
        }}
      >
        <Search
          style={{ color: "var(--text-tertiary)", flexShrink: 0, width: 18, height: 18 }}
          strokeWidth={2}
        />
        <input
          type="text"
          placeholder="Search your files..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && doSearch(query)}
          style={{
            flex: 1,
            border: "none",
            outline: "none",
            background: "transparent",
            fontSize: "15px",
            fontFamily: "var(--font-sans)",
            fontStyle: query ? "normal" : "italic",
            color: "var(--text-primary)",
            minWidth: 0,
          }}
        />
        {/* Mode chips INSIDE the search bar on the right */}
        <div style={{ display: "flex", gap: "4px", flexShrink: 0 }}>
          {SEARCH_MODES.map((mode) => (
            <button
              key={mode.value}
              type="button"
              style={searchMode === mode.value ? CHIP_MODE_ACTIVE : CHIP_MODE}
              onClick={() => setSearchMode(mode.value)}
            >
              {mode.label}
            </button>
          ))}
        </div>
      </div>

      {/* ============================================================
          FILTER CHIPS ROW
          ============================================================ */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          gap: "6px",
          minHeight: "28px",
        }}
      >
        {/* Active filter: file type */}
        {fileType && (
          <span style={CHIP_ACTIVE}>
            type: {fileType}
            <button
              onClick={() => setFileType("")}
              style={{ background: "none", border: "none", color: "inherit", cursor: "pointer", padding: 0, display: "flex" }}
            >
              <X style={{ width: 10, height: 10 }} />
            </button>
          </span>
        )}

        {/* Active filter: date from */}
        {dateFrom && (
          <span style={CHIP_ACTIVE}>
            from: {dateFrom}
            <button
              onClick={() => setDateFrom("")}
              style={{ background: "none", border: "none", color: "inherit", cursor: "pointer", padding: 0, display: "flex" }}
            >
              <X style={{ width: 10, height: 10 }} />
            </button>
          </span>
        )}

        {/* Active filter: date to */}
        {dateTo && (
          <span style={CHIP_ACTIVE}>
            to: {dateTo}
            <button
              onClick={() => setDateTo("")}
              style={{ background: "none", border: "none", color: "inherit", cursor: "pointer", padding: 0, display: "flex" }}
            >
              <X style={{ width: 10, height: 10 }} />
            </button>
          </span>
        )}

        {/* Active filter: result count (only if non-default) */}
        {topK !== 10 && (
          <span style={CHIP_ACTIVE}>
            top: {topK}
            <button
              onClick={() => setTopK(10)}
              style={{ background: "none", border: "none", color: "inherit", cursor: "pointer", padding: 0, display: "flex" }}
            >
              <X style={{ width: 10, height: 10 }} />
            </button>
          </span>
        )}

        {/* Add-filter chips */}
        <div style={{ position: "relative" }}>
          <button
            style={CHIP_ADD}
            onClick={() => { setShowTypeMenu(!showTypeMenu); setShowDatePicker(false); setShowCountMenu(false); }}
          >
            + type
          </button>
          {showTypeMenu && (
            <div
              style={{
                position: "absolute",
                top: "calc(100% + 4px)",
                left: 0,
                zIndex: 50,
                background: "var(--bg-card)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-md)",
                boxShadow: "var(--shadow-md)",
                padding: "4px",
                display: "flex",
                flexWrap: "wrap",
                gap: "3px",
                maxWidth: "280px",
              }}
            >
              {FILE_TYPE_OPTIONS.filter(o => o.value !== "").map((opt) => (
                <button
                  key={opt.value}
                  style={{
                    ...CHIP_BASE,
                    background: fileType === opt.value ? "var(--accent-soft)" : "transparent",
                    color: fileType === opt.value ? "var(--accent)" : "var(--text-secondary)",
                    borderColor: fileType === opt.value ? "var(--accent)" : "var(--border)",
                  }}
                  onClick={() => { setFileType(opt.value); setShowTypeMenu(false); }}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          )}
        </div>

        <div style={{ position: "relative" }}>
          <button
            style={CHIP_ADD}
            onClick={() => { setShowDatePicker(!showDatePicker); setShowTypeMenu(false); setShowCountMenu(false); }}
          >
            <Calendar style={{ width: 9, height: 9 }} />
            + date
          </button>
          {showDatePicker && (
            <div
              style={{
                position: "absolute",
                top: "calc(100% + 4px)",
                left: 0,
                zIndex: 50,
                background: "var(--bg-card)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-md)",
                boxShadow: "var(--shadow-md)",
                padding: "8px",
                display: "flex",
                flexDirection: "column",
                gap: "6px",
              }}
            >
              <label style={{ display: "flex", alignItems: "center", gap: "6px", fontFamily: "var(--font-mono)", fontSize: "9px", color: "var(--text-secondary)" }}>
                From
                <input
                  type="date"
                  value={dateFrom}
                  onChange={(e) => setDateFrom(e.target.value)}
                  style={{ fontFamily: "var(--font-mono)", fontSize: "10px", border: "1px solid var(--border)", borderRadius: "6px", padding: "2px 6px", outline: "none" }}
                />
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: "6px", fontFamily: "var(--font-mono)", fontSize: "9px", color: "var(--text-secondary)" }}>
                To
                <input
                  type="date"
                  value={dateTo}
                  onChange={(e) => setDateTo(e.target.value)}
                  style={{ fontFamily: "var(--font-mono)", fontSize: "10px", border: "1px solid var(--border)", borderRadius: "6px", padding: "2px 6px", outline: "none" }}
                />
              </label>
              <button
                style={{ ...CHIP_BASE, justifyContent: "center", background: "var(--accent-soft)", color: "var(--accent)", borderColor: "var(--accent)" }}
                onClick={() => setShowDatePicker(false)}
              >
                apply
              </button>
            </div>
          )}
        </div>

        <div style={{ position: "relative" }}>
          <button
            style={CHIP_ADD}
            onClick={() => { setShowCountMenu(!showCountMenu); setShowTypeMenu(false); setShowDatePicker(false); }}
          >
            + count
          </button>
          {showCountMenu && (
            <div
              style={{
                position: "absolute",
                top: "calc(100% + 4px)",
                left: 0,
                zIndex: 50,
                background: "var(--bg-card)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-md)",
                boxShadow: "var(--shadow-md)",
                padding: "4px",
                display: "flex",
                gap: "3px",
              }}
            >
              {RESULT_COUNT_OPTIONS.map((n) => (
                <button
                  key={n}
                  style={{
                    ...CHIP_BASE,
                    background: topK === n ? "var(--accent-soft)" : "transparent",
                    color: topK === n ? "var(--accent)" : "var(--text-secondary)",
                    borderColor: topK === n ? "var(--accent)" : "var(--border)",
                  }}
                  onClick={() => { setTopK(n); setShowCountMenu(false); }}
                >
                  {n}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Clear all filters */}
        {hasActiveFilters && (
          <button
            style={{ ...CHIP_ADD, color: "var(--danger)", borderColor: "rgba(220,38,38,0.3)" }}
            onClick={() => { setFileType(""); setDateFrom(""); setDateTo(""); setTopK(10); }}
          >
            clear filters
          </button>
        )}

        {/* Results count + timing -- pushed to the right */}
        {searchTime !== null && (
          <span
            style={{
              marginLeft: "auto",
              fontFamily: "'JetBrains Mono', var(--font-mono)",
              fontSize: "9px",
              color: "var(--text-tertiary)",
              whiteSpace: "nowrap",
            }}
          >
            {results.length} hits &middot; {searchTime.toFixed(0)}ms
          </span>
        )}
      </div>

      {/* ============================================================
          QUERY ARITHMETIC: hint + refinement pills
          ============================================================ */}
      {!hasSearched && (
        <p style={{ fontFamily: "var(--font-mono)", fontSize: "9px", color: "var(--text-tertiary)", fontStyle: "italic", margin: 0 }}>
          Use + to add concepts, - to subtract. Example: pricing +recent -draft
        </p>
      )}

      {hasRefinements && (
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "6px" }}>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: "9px", fontWeight: 500, color: "var(--text-secondary)" }}>refinements:</span>
          {addTexts.map((t, i) => (
            <span key={`add-${i}`} className="sk-query-tag-positive" style={{ fontSize: "9px", fontFamily: "var(--font-mono)" }}>
              <Plus style={{ width: 9, height: 9 }} />
              {t.slice(0, 40)}{t.length > 40 ? "..." : ""}
              <button
                style={{ background: "none", border: "none", color: "inherit", cursor: "pointer", padding: 0, marginLeft: 2, display: "flex", opacity: 0.6 }}
                onClick={() => {
                  const next = addTexts.filter((_, j) => j !== i);
                  setAddTexts(next);
                  doSearch(query, next, subtractTexts);
                }}
              >
                <X style={{ width: 9, height: 9 }} />
              </button>
            </span>
          ))}
          {subtractTexts.map((t, i) => (
            <span key={`sub-${i}`} className="sk-query-tag-negative" style={{ fontSize: "9px", fontFamily: "var(--font-mono)" }}>
              <Minus style={{ width: 9, height: 9 }} />
              {t.slice(0, 40)}{t.length > 40 ? "..." : ""}
              <button
                style={{ background: "none", border: "none", color: "inherit", cursor: "pointer", padding: 0, marginLeft: 2, display: "flex", opacity: 0.6 }}
                onClick={() => {
                  const next = subtractTexts.filter((_, j) => j !== i);
                  setSubtractTexts(next);
                  doSearch(query, addTexts, next);
                }}
              >
                <X style={{ width: 9, height: 9 }} />
              </button>
            </span>
          ))}
          <button
            style={{ ...CHIP_ADD, color: "var(--text-tertiary)" }}
            onClick={() => { setAddTexts([]); setSubtractTexts([]); doSearch(query, [], []); }}
          >
            clear all
          </button>
        </div>
      )}

      {/* ============================================================
          RESULTS: dense table / list
          ============================================================ */}
      {loading ? (
        /* Loading skeletons styled as table rows */
        <div style={{ border: "1px solid var(--border)", borderRadius: "var(--radius-md)", overflow: "hidden" }}>
          {/* Table header skeleton */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "2fr 4fr 0.7fr 1.2fr 60px",
              gap: "0",
              padding: "8px 12px",
              background: "var(--bg-sidebar)",
              borderBottom: "2px solid var(--text-primary)",
            }}
          >
            {["FILE", "SNIPPET", "SCORE", "DATE", ""].map((h) => (
              <span
                key={h}
                style={{
                  fontFamily: "'JetBrains Mono', var(--font-mono)",
                  fontSize: "9px",
                  fontWeight: 700,
                  textTransform: "uppercase",
                  letterSpacing: "0.08em",
                  color: "var(--text-secondary)",
                }}
              >
                {h}
              </span>
            ))}
          </div>
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              style={{
                display: "grid",
                gridTemplateColumns: "2fr 4fr 0.7fr 1.2fr 60px",
                gap: "8px",
                padding: "10px 12px",
                borderBottom: "1px dashed var(--border)",
              }}
            >
              <div className="sk-skeleton" style={{ width: "80%", height: "12px" }} />
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <div className="sk-skeleton" style={{ width: "100%", height: "10px" }} />
                <div className="sk-skeleton" style={{ width: "70%", height: "10px" }} />
              </div>
              <div className="sk-skeleton" style={{ width: "40px", height: "12px" }} />
              <div className="sk-skeleton" style={{ width: "60px", height: "12px" }} />
              <div className="sk-skeleton" style={{ width: "40px", height: "12px" }} />
            </div>
          ))}
        </div>
      ) : results.length > 0 ? (
        <div style={{ border: "1px solid var(--border)", borderRadius: "var(--radius-md)", overflow: "hidden", background: "var(--bg-card)" }}>
          {/* Column headers */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "2fr 4fr 0.7fr 1.2fr 60px",
              gap: "0",
              padding: "8px 12px",
              background: "var(--bg-sidebar)",
              borderBottom: "2px solid var(--text-primary)",
            }}
          >
            {["FILE", "SNIPPET", "SCORE", "DATE", ""].map((h) => (
              <span
                key={h}
                style={{
                  fontFamily: "'JetBrains Mono', var(--font-mono)",
                  fontSize: "9px",
                  fontWeight: 700,
                  textTransform: "uppercase",
                  letterSpacing: "0.08em",
                  color: "var(--text-secondary)",
                }}
              >
                {h}
              </span>
            ))}
          </div>

          {/* Result rows */}
          {results.map((r, idx) => {
            const isTop = idx === 0;
            return (
              <div
                key={`${r.file_path}-${r.chunk_index}`}
                className="sk-fade-up"
                onClick={() => setSelectedResult(r)}
                style={{
                  display: "grid",
                  gridTemplateColumns: "2fr 4fr 0.7fr 1.2fr 60px",
                  gap: "0",
                  padding: "8px 12px",
                  alignItems: "start",
                  cursor: "pointer",
                  borderBottom: idx < results.length - 1 ? "1px dashed var(--border)" : "none",
                  background: isTop ? "var(--bg-accent-light)" : "transparent",
                  transition: "background 100ms ease",
                  animationDelay: `${idx * 30}ms`,
                }}
                onMouseEnter={(e) => { if (!isTop) e.currentTarget.style.background = "var(--bg-hover)"; }}
                onMouseLeave={(e) => { if (!isTop) e.currentTarget.style.background = "transparent"; }}
              >
                {/* FILE column: name + chunk index */}
                <div style={{ display: "flex", flexDirection: "column", gap: "2px", minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "5px", minWidth: 0 }}>
                    <span
                      style={{
                        fontFamily: "'JetBrains Mono', var(--font-mono)",
                        fontSize: "10.5px",
                        fontWeight: 600,
                        color: "var(--text-primary)",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {r.file_name}
                    </span>
                    <Badge className={typeTabClass(r.file_type)} style={{ fontSize: "8px", padding: "1px 5px", flexShrink: 0 }}>
                      {r.file_type}
                    </Badge>
                  </div>
                  <span
                    style={{
                      fontFamily: "'JetBrains Mono', var(--font-mono)",
                      fontSize: "8.5px",
                      color: "var(--text-tertiary)",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    chunk {r.chunk_index + 1}
                    {r.extractor ? ` \u00b7 ${r.extractor}` : ""}
                    {r.page_number != null ? ` \u00b7 p.${r.page_number}` : ""}
                  </span>
                </div>

                {/* SNIPPET column with highlighted query terms */}
                <p
                  style={{
                    fontFamily: "'JetBrains Mono', var(--font-mono)",
                    fontSize: "10px",
                    lineHeight: 1.55,
                    color: "var(--text-secondary)",
                    margin: 0,
                    overflow: "hidden",
                    display: "-webkit-box",
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: "vertical",
                  }}
                >
                  {highlightQuery(r.chunk_text.slice(0, 200))}
                </p>

                {/* SCORE column */}
                <span
                  style={{
                    fontFamily: "'JetBrains Mono', var(--font-mono)",
                    fontSize: "10px",
                    fontWeight: 500,
                    color: isTop ? "var(--accent)" : "var(--text-secondary)",
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  {r.score.toFixed(2)}
                </span>

                {/* DATE column */}
                <span
                  style={{
                    fontFamily: "'JetBrains Mono', var(--font-mono)",
                    fontSize: "9px",
                    color: "var(--text-tertiary)",
                    whiteSpace: "nowrap",
                  }}
                >
                  --
                </span>

                {/* +/- refinement buttons */}
                <span style={{ display: "flex", alignItems: "center", gap: "3px", justifyContent: "flex-end" }}>
                  <button
                    className="sk-refine-btn sk-refine-boost"
                    title="More like this"
                    onClick={(e) => {
                      e.stopPropagation();
                      const next = [...addTexts, r.chunk_text];
                      setAddTexts(next);
                      doSearch(query, next, subtractTexts);
                    }}
                    style={{ width: 20, height: 20, borderRadius: 5 }}
                  >
                    <Plus style={{ width: 11, height: 11 }} />
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
                    style={{ width: 20, height: 20, borderRadius: 5 }}
                  >
                    <Minus style={{ width: 11, height: 11 }} />
                  </button>
                </span>
              </div>
            );
          })}
        </div>
      ) : hasSearched ? (
        /* No results state */
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: "64px 0",
            color: "var(--text-tertiary)",
          }}
        >
          <FileSearch
            style={{ width: 48, height: 48, color: "var(--text-tertiary)", opacity: 0.5, marginBottom: 16 }}
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
        /* Empty state before search */
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: "64px 0",
            color: "var(--text-tertiary)",
          }}
        >
          <Search
            style={{ width: 56, height: 56, color: "var(--accent)", opacity: 0.3, marginBottom: 16 }}
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
          <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", gap: "8px", maxWidth: "480px" }}>
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

      {/* ============================================================
          FILE PREVIEW MODAL (unchanged logic)
          ============================================================ */}
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
