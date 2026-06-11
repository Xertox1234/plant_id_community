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

### 2026-06-09 — Maintainability Audit (all stacks)

- **Trigger:** User-invoked `/audit maintainability` (all three stacks,
  discovery-first). First audit through a **maintainability lens** (complexity,
  duplication, dead code, drift, type-safety escapes, hollow tests) — prior audits
  were security/perf/correctness-focused, so dedup risk was low.
- **Manifest:** [2026-06-09-maintainability.md](2026-06-09-maintainability.md)
- **Findings:** 0 critical, 4 high, 22 medium, 13 low (39 total). All
  primary-source verified; high-impact dead-code claims independently confirmed by
  reference count. Research (Phase 2.5) skipped — every finding is internal-code
  (no external-library dependence). 2 agent-proposed Highs calibrated down to
  Medium (M17, M20).
- **Resolved:** 21 fixed & verified (dead-code sweep + hollow tests — the user's
  chosen scope), 18 deferred to todos 221–223, 0 false-positive, 0 open. Net
  **−4,317 / +57 lines across 24 files** (overwhelmingly dead-code removal).
- **Method note:** mass-deletion discipline — whole-repo (non-`.py`) reference
  sweep before deleting any model method (catches template/panel/settings string
  refs), transitive-deadness chains followed to closure (`log_trust_level_upgrade`,
  `_get_next_step`, `_get_project_for_location`, 4 orphaned constants, 2 orphaned
  imports), and a post-deletion orphan re-sweep (tests can't catch under-deletion).
- **Highlights (fixed):** H1 dead `TrustLevelService` (auth-adjacent, print-based,
  dangerous-if-revived); H2 462-line `_services_deprecated.py` frozen shadow of two
  live services; H3 dead 382-line `formatDate.ts`; H4 + M20 empty rate-limit
  *security* tests (one named the RFC `Retry-After` gotcha but asserted nothing) —
  rewritten/removed; M10 dead `SecurityMonitor` tracking API; M17/M18/M19 dead
  Flutter modules (offline-sync layer + nav helpers removed with user approval).
- **Conservative deferrals:** `validation.ts` tested **security validators**
  (M12) and the drifted PlantNet parser (M1/L1) were NOT blind-deleted — deferred
  to todos 222/221 for a wire-or-remove decision, per deletion-safety guidance.
- **Scope note:** the live backend forum (`packages/wagtail_forum/`,
  `apps/forum_host/`) — new/small, just reviewed in #361/#362 — was a deliberate
  coverage gap; the Phase-1 churn signal pointed at the now-deleted
  `forum_integration/`.
- **Commit(s):** branch `chore/maintainability-audit-2026-06-09` (PR pending).

### 2026-06-10 — Forum Extension Audit (wagtail_forum + forum_host)

- **Trigger:** User-invoked `/audit` on the forum extension ("make sure we did
  everything right") — fills the deliberate coverage gap from the 2026-06-09
  maintainability audit.
- **Manifest:** [2026-06-10-forum.md](2026-06-10-forum.md)
- **Findings:** 0 critical, 5 high, 19 medium, 13 low (37 total) from 6 parallel
  discovery agents (heavy independent convergence) + 2 docs-researchers (13
  doc-dependent claims: all confirmed/better-fix, zero contradicted).
- **Resolved:** 34 fixed & verified, 2 deferred to todo 231 (H4 web-client/read-API
  = documented Spec 2 + L10 URL rationalization), 1 false-positive (L9
  versioning opt-out — removal proven breaking). 0 open.
- **Headlines fixed:** rate limiting dropped between plans 1C→1D (host-side
  throttled wrappers + 429/Retry-After + per-user tests); `board.topic_count`
  undercount on the API publish path; no unpublish/delete reconciliation —
  spammers kept autopublish trust earned from removed posts (trust now re-derived
  both directions, manual grants preserved); topic titles never spam-screened;
  edit-republish duplicate notifications + activity corruption; bootstrap wiping
  Forum Moderators perms each deploy (+ missing `access_admin`); idempotency
  contract (scoped+hashed keys, original-status replay, fingerprint 422, reply +
  reaction support, in-flight 409); board takedown/PageViewRestriction/multi-tree
  slug visibility; dead `ENABLE_FORUM` flag deleted (docs/CI claims fixed).
- **Phase 6 round 2:** orchestrated review of the fix set found 3 HIGH (unsendered
  global `post_delete` killing fast-delete project-wide; NULL `last_post_at`
  breaking the cursor invariant; execution-proven non-str block value 500) — all
  fixed same-session with regression tests. kimi-review CRITICALs ×3 refuted with
  evidence (documented in manifest).
- **Tests:** forum suite 62 → 106 (+44); full backend suite green; spectacular:
  0 forum schema errors.
- **Commit(s):** branch `chore/forum-audit-2026-06-10` (PR pending).
