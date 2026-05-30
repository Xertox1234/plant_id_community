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
- **Commit(s):** `aa42902` (branch `audit/full-2026-05-17`)

### 2026-05-30 — Harness Effectiveness Audit

- **Trigger:** User-invoked `/audit the harness to see how effective it is`
  (primary lens: produce higher-quality code). Report + create-todos mode; scope
  = full quality-enforcement surface (`.claude/`, `docs/rules/`, `kimi-*` tools,
  `scripts/inject/`, CI/pre-commit gates).
- **Manifest:** [2026-05-30-harness.md](2026-05-30-harness.md)
- **Findings:** 0 critical, 2 high, 3 medium, 3 low (8 total, all corroborated by
  direct file reads). **+4 false findings reversed** (fabricated tool output), and
  1 over-correction self-corrected back into a real finding (F2).
- **Resolved:** 0 fixed (report-only), 8 deferred to todos 126–133, 0 remaining
  open.
- **Verdict:** The agent-facing harness is well-built and working — JIT
  mistake-injection fires correctly end-to-end; the codify loop demonstrably
  captured the forum rate-limit recurrence (todos 104–109) into the
  `drf-action-no-ratelimit` trigger; all harness self-tests pass; agents/rules
  consistent. The real quality gaps are in **CI coverage**, not the harness.
- **Highlights:** CI runs functional tests for the **mobile stack only**. F1
  (HIGH) no `web-ci.yml` — web `tsc`/vitest/lint gated nowhere in CI (only `npm
  audit`). F2 (HIGH) backend test suite runs in no CI workflow. F3 (MED) the
  harness's own (passing) tests aren't run by any CI. F4 (MED) kimi-review is
  pre-authorized to be skipped + fail-open locally. F5–F7 (LOW) wrong forum path
  in CLAUDE.md, stale `.proposed` handoff artifacts, stale locked worktrees.
- **Meta:** several early tool results were internally inconsistent with isolated
  re-runs (incl. a phantom "230 tests, 3 FAILED" and "rate-limiting.md missing");
  4 would have become published findings (2 HIGH). The affected results all came
  from oversized single-message batches (20+ calls, duplicate/dependent calls);
  every claim re-checked in a small file-backed invocation was correct. Likely
  cross-wiring/misattribution, not infrastructure fabrication. Lessons: keep
  verification batches small + independent, prefer direct primary-source reads,
  route results through files. A correction built on another single unreliable
  read nearly buried real finding F2.
- **Commit(s):** _pending — report-only, no fix commit; todos 126–132 filed._
