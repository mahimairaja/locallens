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

export default function SearchPage() {
  const [searchParams] = useSearchParams();
  const [query, setQuery] = useState(searchParams.get("q") ?? "");
  const [topK, setTopK] = useState(10);
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
        const resp: SearchResponse = await api.search(q, topK);
        setResults(resp.results);
        setSearchTime(resp.search_time_ms);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    },
    [topK]
  );

  // Auto-search from URL param
  useEffect(() => {
    const q = searchParams.get("q");
    if (q) {
      setQuery(q);
      doSearch(q);
    }
  }, [searchParams, doSearch]);

  // Debounced search-as-you-type
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
        <mark key={i} className="bg-primary/30 text-foreground rounded px-0.5">
          {part}
        </mark>
      ) : (
        part
      )
    );
  };

  return (
    <div className="space-y-6">
      {/* Search Bar */}
      <div className="space-y-3">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search your files..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && doSearch(query)}
            className="pl-10 text-base"
          />
        </div>
        <div className="flex items-center gap-3 text-sm text-muted-foreground">
          <label className="flex items-center gap-2">
            Results:
            <input
              type="range"
              min={1}
              max={20}
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              className="w-24"
            />
            <span className="w-6 text-foreground">{topK}</span>
          </label>
          {searchTime !== null && (
            <span className="ml-auto">
              Found {results.length} results in {searchTime.toFixed(0)}ms
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
                  <div className="h-4 w-48 animate-pulse rounded bg-muted" />
                  <div className="h-3 w-full animate-pulse rounded bg-muted" />
                  <div className="h-3 w-3/4 animate-pulse rounded bg-muted" />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : results.length > 0 ? (
        <div className="space-y-3">
          {results.map((r) => (
            <Card
              key={`${r.file_path}-${r.chunk_index}`}
              className="cursor-pointer transition-colors hover:border-primary/50"
              onClick={() => setSelectedResult(r)}
            >
              <CardContent className="p-5">
                <div className="mb-2 flex items-center gap-3">
                  <Badge variant="outline" className="text-xs">
                    #{r.rank}
                  </Badge>
                  <span className="font-medium">{r.file_name}</span>
                  <Badge variant="secondary" className="text-xs">
                    {r.file_type}
                  </Badge>
                  <span className="ml-auto text-sm text-muted-foreground">
                    {(r.score * 100).toFixed(1)}%
                  </span>
                </div>
                <p className="line-clamp-3 text-sm text-muted-foreground">
                  {highlightQuery(r.chunk_text.slice(0, 300))}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : hasSearched ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            No results. Try a different query or index more files.
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
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
            <DialogTitle className="flex items-center gap-2">
              {selectedResult?.file_name}
              <Badge variant="secondary">{selectedResult?.file_type}</Badge>
            </DialogTitle>
          </DialogHeader>
          <p className="text-xs text-muted-foreground">
            {selectedResult?.file_path}
          </p>
          <ScrollArea className="max-h-96">
            <pre className="whitespace-pre-wrap text-sm">
              {selectedResult?.chunk_text}
            </pre>
          </ScrollArea>
        </DialogContent>
      </Dialog>
    </div>
  );
}
