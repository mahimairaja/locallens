---
name: locallens-doctor
description: Check LocalLens setup and dependencies. Shows what is working and what is missing.
command: /locallens:doctor
disable-model-invocation: true
---

Run the LocalLens health check:

```bash
locallens doctor --format json
```

Present the results as a status table showing each component and whether it is OK, warning, or failed.

If LocalLens is not installed, tell the user:

> Install LocalLens: `pip install locallens`
