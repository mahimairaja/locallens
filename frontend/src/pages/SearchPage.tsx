import { useState, useCallback, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Search, Loader2 } from "lucide-react";
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

  const doSearch = useCallback(
    async (q: string) => {
      if (q.trim().length < 2) return;
      setLoading(true);
      setHasSearched(true);
      try {
        const resp: SearchResponse = await api.search(
          q, topK, fileType || null, null, searchMode, dateFrom || null, dateTo || null,
        );
        setResults(resp.results);
        setSearchTime(resp.search_time_ms);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    },
    [topK, fileType, searchMode, dateFrom, dateTo]
  );

  // Auto-search from URL param
  useEffect(() => {
    const q = searchParams.get("q");
    if (q) {
      setQuery(q);
      doSearch(q);
    }
  }, [searchParams, doSearch]);

  // Debounced search-as-you-type — also re-runs when filter state changes.
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
    <div className="space-y-8">
      <h2
        className="text-2xl"
        style={{
          fontFamily: "var(--font-sans)",
          fontWeight: 600,
          color: "var(--text-primary)",
          letterSpacing: "-0.015em",
        }}
      >
        Search
      </h2>

      {/* Search Bar */}
      <div className="space-y-5">
        <div className="relative">
          <Search
            className="pointer-events-none absolute left-5 top-1/2 h-5 w-5 -translate-y-1/2"
            style={{ color: "var(--text-tertiary)" }}
            strokeWidth={2}
          />
          <Input
            placeholder="Search your files..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && doSearch(query)}
            style={{
              paddingLeft: "3.25rem",
              paddingRight: "1.25rem",
              height: "56px",
              fontSize: "1.05rem",
              fontStyle: query ? "normal" : "italic",
              boxShadow: "var(--shadow-sm)",
            }}
          />
        </div>
        <div
          className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm"
          style={{ color: "var(--text-secondary)", fontFamily: "var(--font-sans)" }}
        >
          <label className="flex items-center gap-3">
            <span style={{ fontWeight: 500 }}>Results</span>
            <input
              type="range"
              min={1}
              max={20}
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              className="w-32"
              style={{ accentColor: "var(--accent)" }}
            />
            <span className="sk-meter">{topK}</span>
          </label>
          <label className="flex items-center gap-2">
            <span style={{ fontWeight: 500 }}>File type</span>
            <select
              value={fileType}
              onChange={(e) => setFileType(e.target.value)}
              className="text-sm"
              style={{
                background: "var(--bg-card)",
                color: "var(--text-primary)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-md)",
                padding: "0.35rem 0.65rem",
                fontFamily: "var(--font-sans)",
                cursor: "pointer",
                outline: "none",
                boxShadow: "var(--shadow-xs)",
              }}
            >
              {FILE_TYPE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2">
            <span style={{ fontWeight: 500 }}>Mode</span>
            <select
              value={searchMode}
              onChange={(e) => setSearchMode(e.target.value)}
              className="text-sm"
              style={{
                background: "var(--bg-card)",
                color: "var(--text-primary)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-md)",
                padding: "0.35rem 0.65rem",
                fontFamily: "var(--font-sans)",
                cursor: "pointer",
                outline: "none",
                boxShadow: "var(--shadow-xs)",
              }}
            >
              <option value="hybrid">Hybrid</option>
              <option value="semantic">Semantic</option>
              <option value="keyword">Keyword</option>
            </select>
          </label>
          <label className="flex items-center gap-2">
            <span style={{ fontWeight: 500 }}>From</span>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="text-sm"
              style={{
                background: "var(--bg-card)",
                color: "var(--text-primary)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-md)",
                padding: "0.25rem 0.5rem",
                fontFamily: "var(--font-sans)",
                outline: "none",
                boxShadow: "var(--shadow-xs)",
              }}
            />
          </label>
          <label className="flex items-center gap-2">
            <span style={{ fontWeight: 500 }}>To</span>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="text-sm"
              style={{
                background: "var(--bg-card)",
                color: "var(--text-primary)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-md)",
                padding: "0.25rem 0.5rem",
                fontFamily: "var(--font-sans)",
                outline: "none",
                boxShadow: "var(--shadow-xs)",
              }}
            />
          </label>
          {searchTime !== null && (
            <span className="ml-auto">
              {results.length} results · {searchTime.toFixed(0)}ms
            </span>
          )}
        </div>
      </div>

      {/* Results */}
      {loading ? (
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => (
            <Card key={i}>
              <CardContent className="p-6">
                <div className="space-y-2">
                  <div className="h-4 w-48 animate-pulse rounded" style={{ background: "var(--bg-hover)" }} />
                  <div className="h-3 w-full animate-pulse rounded" style={{ background: "var(--bg-hover)" }} />
                  <div className="h-3 w-3/4 animate-pulse rounded" style={{ background: "var(--bg-hover)" }} />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : results.length > 0 ? (
        <div className="space-y-4">
          {results.map((r) => (
            <Card
              key={`${r.file_path}-${r.chunk_index}`}
              className="cursor-pointer"
              onClick={() => setSelectedResult(r)}
            >
              <CardContent className="p-6">
                <div className="mb-3 flex items-center gap-3">
                  <span
                    className="flex h-6 min-w-6 items-center justify-center rounded-full px-2 text-xs"
                    style={{ background: "var(--accent-soft)", color: "var(--accent-hover)", fontWeight: 600 }}
                  >
                    {r.rank}
                  </span>
                  <span
                    className="text-base"
                    style={{ color: "var(--text-primary)", fontWeight: 600 }}
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
                  <span className="ml-auto sk-meter">{(r.score * 100).toFixed(1)}%</span>
                </div>
                <p
                  className="line-clamp-3 text-sm"
                  style={{ color: "var(--text-secondary)", lineHeight: 1.6 }}
                >
                  {highlightQuery(r.chunk_text.slice(0, 300))}
                </p>
                <div
                  className="mt-3 h-[3px] rounded-full"
                  style={{
                    background: `linear-gradient(90deg, var(--accent) 0%, var(--accent) ${Math.max(
                      2,
                      Math.round(r.score * 100)
                    )}%, var(--bg-hover) ${Math.round(r.score * 100)}%, var(--bg-hover) 100%)`,
                  }}
                />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : hasSearched ? (
        <Card>
          <CardContent className="sk-empty">
            No matches in your files — try another phrase.
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="sk-empty">
            Enter a search query to find relevant content in your indexed files.
          </CardContent>
        </Card>
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
