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
- **Commit(s):** `cbb028b` (audit artifacts + todos 126–133), `b20a065` (web-ci
  workflow — F1 fix), `e32c390` (F1 checkoff + todo 126 archive); branch
  `chore/harness-audit-2026-05-30` (PR #307).

### 2026-06-02 — Full Codebase Audit

- **Trigger:** User-invoked `/audit` (full scope) — first full audit since
  2026-05-17. Largest change since: Green Thumb web migration (#323/#324).
- **Manifest:** [2026-06-02-full.md](2026-06-02-full.md)
- **Findings:** 0 critical, 7 high, 13 medium, 16 low (36 total). All
  primary-source verified; 8 library-dependent ones additionally doc-validated
  via Context7 (Phase 2.5) — all confirmed, 2 with cleaner doc-informed fixes.
- **Resolved:** 10 fixed & verified, 26 deferred to todos 204–208, 0 open. Plus
  2 Phase-6 code-review fixes outside the 36 count: C1 (a regression introduced by
  the M9 fix) and C2 (a pre-existing `statistics` 500), both now test-covered.
- **Verdict:** The Green Thumb web migration is, for the audited surfaces, a
  clean mechanical Tailwind-token reskin — it weakened no XSS/CSRF/auth/upload
  control and introduced only low-severity nits. The real new bugs are in
  **backend behavior**, not the migration.
- **Highlights (fixed):** H4 — blog comment writes never invalidated cached
  `comment_count` (added a `BlogComment` signal); M8 — same for `BlogCategory`.
  H6/H7 — N+1 on two public list endpoints (`select_related`). M9/M10 — garden
  analytics/harvest collapsed Python loops + 6 queries into single aggregates
  (now covered by endpoint tests with `assertNumQueries`). H5/M11 — Firestore
  rules let an owner reassign a doc's `user_id` and exposed public docs to anon
  reads (latent — collections unused by clients). M2 — `service_status` returned
  HTTP 200 on error. M5 — Retry-After wrapper adopted in two more modules.
- **Deferred:** H1/M12 Celery autoretry inert — the service swallows all
  exceptions so the task-only fix was reverted; needs service re-raise + on_failure
  → todo 208; H2/H3/L15 wagtail-ai 3.x migration (AI endpoint silently 503-ing,
  rate-limit on no live path) → todo 204; M1/M3/M4/M6/M7/M13 backend medium
  hardening → todo 205; backend + frontend lows → todos 206–207.
- **Meta:** Phase 6 code review earned its keep — it caught a `Count("id")`
  **regression my own M9 fix introduced** (500 on `analytics`, a `uuid`-PK model)
  that the 687-test suite missed because the endpoint had zero coverage; fixed to
  `Count("pk")` and locked with new endpoint tests, which also caught a
  pre-existing `Count("uuid")` 500 in `statistics` (C2). It also showed the
  Celery task-only fix was inert (service swallows exceptions) → reverted, not
  shipped. kimi-review's lone "CRITICAL" (declared model field could
  `AttributeError`) was a verified false positive — a Django field is always an
  instance attribute, and the handler is `try/except`-wrapped. Two 2026-05-17
  "fixed" items (M23 AI cache TTL, M25 Prefetch slice) found still present in
  code — surfaced for reconciliation, not re-audited.
- **Commit(s):** branch `chore/full-audit-2026-06-02` (PR pending).

### 2026-06-03 — Harness Effectiveness Audit (Follow-up)

- **Trigger:** User-invoked `/audit development harness` — follow-up to 2026-05-30
  harness audit; all 8 prior todos (126–133) confirmed archived/completed.
- **Manifest:** [2026-06-03-harness.md](2026-06-03-harness.md)
- **Findings:** 0 critical, 1 high, 1 medium, 1 low (3 total). All primary-source
  verified via direct reads and `gh api` call.
- **Resolved:** 0 fixed (report+todos mode — Auto Mode blocks `.claude/` edits),
  3 deferred to todos 211–213, 0 false-positive, 0 open.
- **Verdict:** The prior harness audit's CI gap is half-closed — 3 workflows were
  added but only `backend-checks` is a required status check (H1). Telemetry writer
  IS wired correctly in `match_triggers.py`; empty log = ephemeral `/tmp` (L1).
  Auto-capture loop machinery exists but has never run end-to-end in production —
  all 8 triggers remain hand-seeded `warn` (M1). LSP integration and cd-to-root
  fix are well-executed additions with no findings.
- **Commit(s):** (report+todos; no fix commit)
