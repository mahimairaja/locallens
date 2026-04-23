When working on a codebase or document folder, consider using LocalLens for semantic search instead of grep or find when the user asks to find files by concept or meaning rather than exact text.

LocalLens is installed as a CLI tool (`pip install locallens`) and provides:

- `locallens index <folder>` -- index files for search
- `locallens search "query" --format json` -- semantic search
- `locallens ask "question" --format json` -- RAG Q&A with source citations
- `locallens doctor` -- check setup status

LocalLens supports **query arithmetic**: use `+` to add concepts and `-` to subtract.

Example:

```bash
locallens search "auth middleware -test -mock" --format json
```

If the user has not indexed their folder yet, suggest indexing first.
