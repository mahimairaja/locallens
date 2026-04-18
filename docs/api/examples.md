# Examples

## Index and search a project

```python
from locallens import LocalLens

lens = LocalLens("~/my-project")
result = lens.index()
print(f"Indexed {result.total_files} files")

# Find authentication-related code
results = lens.search("user authentication login", file_type=".py")
for r in results:
    print(f"{r.file_name}:{r.chunk_index} — {r.score:.2f}")
    print(f"  {r.chunk_text[:100]}")
```

## Stream a RAG answer

```python
from locallens import LocalLens

lens = LocalLens("~/Documents")

for event in lens.ask_stream("Summarize the Q3 report"):
    if event.event_type == "token":
        print(event.data, end="", flush=True)
    elif event.event_type == "sources":
        print(f"\n\nSources:")
        for s in event.data:
            print(f"  - {s.file_name}")
```

## Search with different modes

```python
from locallens import LocalLens

lens = LocalLens("~/Documents")

# Semantic: finds conceptually similar content
results = lens.search("financial performance", mode="semantic")

# Keyword: finds exact term matches (BM25)
results = lens.search("EBITDA margin", mode="keyword")

# Hybrid: combines both with RRF (default, usually best)
results = lens.search("quarterly earnings", mode="hybrid")
```

## Export results as JSON

```python
import json
from locallens import LocalLens

lens = LocalLens("~/Documents")
results = lens.search("meeting notes")

# Serialize to JSON
data = [r.to_dict() for r in results]
print(json.dumps(data, indent=2))
```

## Health check script

```python
from locallens import LocalLens

lens = LocalLens()
checks = lens.doctor()

all_ok = all(c.status != "fail" for c in checks)

for c in checks:
    icon = {"ok": "✓", "warn": "!", "fail": "✗"}[c.status]
    print(f"  {icon} {c.name}: {c.message}")

if not all_ok:
    print("\nSome checks failed. Run 'locallens doctor' for details.")
    exit(1)
```

## Build a simple search API

```python
from locallens import LocalLens
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

lens = LocalLens("~/Documents")

class SearchHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = self.path.split("q=")[-1] if "q=" in self.path else ""
        if not query:
            self.send_response(400)
            self.end_headers()
            return

        results = lens.search(query, top_k=5)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps([r.to_dict() for r in results]).encode())

HTTPServer(("localhost", 8080), SearchHandler).serve_forever()
```
