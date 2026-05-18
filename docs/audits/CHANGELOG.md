# Audit Changelog

Append-only history of all code audits performed on this project. Each entry
links to the full audit manifest with detailed findings and resolutions.

## Format

```text
### YYYY-MM-DD — Audit Title
- **Trigger:** Why the audit was run
- **Manifest:** [link to manifest file]
- **Findings:** X critical, Y high, Z medium, W low
- **Resolved:** N fixed, M deferred, P false-positive
- **Commit(s):** git SHA(s) of fix commits
```

---

### 2026-05-17 — Full Codebase Audit

- **Trigger:** User-invoked `/audit` (full scope) — first recorded audit.
- **Manifest:** [2026-05-17-full.md](2026-05-17-full.md)
- **Findings:** 9 critical, 38 high, 46 medium, 31 low (124 total).
- **Resolved:** 12 fixed & verified (C1–C8, H1, H5, H6, H11), 110 deferred to
  todos 079–085, 2 false-positive.
- **Highlights:** C1 unblocked the entire backend test suite (stub `tests.py` vs
  `tests/` package collision); C4–C6/C8 closed security gaps (DB transaction held
  across an external API call, missing PIL upload-validation layer, client-supplied
  identity fields in Firebase token exchange); H1 closed a GitHub-OAuth
  account-takeover path. Discovery surfaced that `apps/forum/` is not installed
  under `ENABLE_FORUM=True` (Machina is the active forum).
- **Commit(s):** (pending — fix commit on branch `audit/full-2026-05-17`)
