---
name: locallens-search
description: Semantically search indexed files and code by meaning. Use when the user wants to find files related to a concept, feature, or topic. Supports query arithmetic with +/- operators.
command: /locallens:search
---

Search indexed files using LocalLens semantic search.

Run the following command with the user's query:

```bash
locallens search "$ARGUMENTS" --format json --top-k 10
```

If no results are found, suggest the user index their folder first:

```bash
locallens index /path/to/folder
```

Query arithmetic is supported:
- `"auth -test"` finds auth-related files excluding test files
- `"pricing +recent"` finds pricing docs biased toward recent content
- `'payment +"last quarter" -draft'` uses quoted multi-word terms

Parse the JSON results and present them as:
1. File name and path
2. Relevant chunk preview (first 200 chars)
3. Relevance score

If the user wants more detail about a specific result, show the full chunk text.
