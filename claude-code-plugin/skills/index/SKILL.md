---
name: locallens-index
description: Index a folder of files for semantic search. Run this before searching. Supports PDF, DOCX, code, CSV, and 20+ file types.
command: /locallens:index
---

Index a folder for semantic search using LocalLens.

If the user provides a path, use it. Otherwise, index the current working directory.

```bash
locallens index "$ARGUMENTS" --format json
```

If `$ARGUMENTS` is empty, use the current directory:

```bash
locallens index . --format json
```

After indexing, report:
- Total files indexed
- New files added
- Files skipped (unchanged)
- Total chunks created

Suggest the user try searching:

> Your files are indexed. Try: `/locallens:search your query here`
