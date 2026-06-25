---
status: completed
priority: p2
issue_id: "234"
tags: [web, testing, vitest, ci, flaky]
dependencies: []
---

# Flaky Web CI: an unhandled async rejection fails Vitest despite all tests passing

## Problem

The "Web CI → Type-check, lint, and unit/component tests (Vitest)" job fails
intermittently with **all test files passing** but **1 unhandled error**, which
makes the runner exit 1. Because it is non-deterministic and unrelated to the
diff under test, it blocks unrelated PRs until the job is re-run by hand —
a recurring tax on every merge.

## Findings

- Observed on run `27482300767` (PR #372, a docs/config-only change with **zero**
  `web/` files): Vitest summary `Test Files 34 passed (34)` and `Errors 1 error`
  → `Process completed with exit code 1`.
- Same branch (`chore/commit-gate-friction`) ran "Web CI" twice with no web code
  change — once **pass**, once **fail** — confirming a flake, not a real failure.
- The leaked error stacks in that run were forum-service error paths:
  `Error: Thread not found`, `Error: Search failed`, `Error: Category not found`.
  These are the error-path branches of forum service/component tests — the likely
  source is a promise rejection that isn't awaited/caught inside a test (or a
  fire-and-forget call in the component under test) that surfaces *after* the test
  resolves, so Vitest counts it as an unhandled error rather than a failed assertion.
- Exact originating test file was not pinned: re-running the failed job (to unblock
  #372's auto-merge) cleared the failed-attempt logs.
- Discovery source: self-review of PR #372 (2026-06-14), issue #3.

## Recommended Action

1. Reproduce: re-run the Web CI job (or run the suite locally with
   `cd web && npm run test -- --run`) repeatedly until it fails; capture the
   `⎯⎯ Unhandled Errors ⎯⎯` / "This error originated in …" section to identify the
   exact test file and call site. Candidates: forum thread / category / search
   service or component tests exercising the error path.
2. Fix the leak at the source — `await` (or `.catch`) the rejecting call in the
   test, or in the component make the fire-and-forget call awaited / its rejection
   handled. Prefer fixing the leak over suppressing it.
3. Only if the leak is genuinely benign and unfixable, scope a narrow
   `test.fails`/`expect(...).rejects` or a targeted vitest config — do NOT globally
   set `dangerouslyIgnoreUnhandledErrors` (that would mask real future leaks).
4. Add an assertion so the error-path test actually awaits and asserts the
   rejection, converting the leaked rejection into a checked expectation.

## Technical Details

- Job: `.github/workflows/` Web CI → step "Unit and component tests (Vitest)".
- Likely areas: `web/src/**/forum/**` service/component tests and their
  `*.test.tsx?` error-path cases (`Thread not found`, `Search failed`,
  `Category not found`).
- Vitest treats a post-test unhandled rejection as a run-level error (exit 1) even
  when every test file passes — see the `Errors: 1 error` line in the summary.

## Acceptance Criteria

> **Resolution (2026-06-25): not-reproducible + mitigated.** AC1/AC2 are **not satisfiable** —
> there is no observable leak to pin or fix (unreproducible in ~346 runs across macOS/Linux/CI,
> cold + warm; no orphan promise by static analysis; likely already fixed by PRs #406/#407).
> Rather than fabricate a fix, the leak class is **mitigated** so any recurrence self-diagnoses.

- [ ] ~~Originating test file + call site identified~~ — **not satisfiable**: unreproducible;
      documented why instead (2026-06-25 work log + static analysis).
- [ ] ~~Fixed at the source~~ — **n/a**: no observable leak; likely already fixed by the
      forum-test rewrite. **Mitigated** via a non-suppressing reporter (explicitly *not* suppressed).
- [x] The Web CI Vitest job passes across multiple consecutive runs — **verified**: 24 cold
      separate CI jobs + 40 warm in-job runs all green (2026-06-25).

## Work Log

### 2026-06-25 — Exhaustively investigated; UNREPRODUCIBLE on every platform → mitigated + resolved

**Outcome: resolved as not-reproducible + mitigated.** The flake did not surface in
**~346 full-suite runs** across every platform/config; static analysis shows no orphan
promise; the three tests that create the leaked error strings were materially rewritten by
PRs #406/#407 (forum spec-2 PR-3) *after* this was filed (2026-06-14), so it was almost
certainly fixed incidentally. Shipped a permanent, non-suppressing `unhandledRejection`
reporter so any recurrence is instantly self-diagnosing — closing the exact gap that left
this stuck (run #372's logs were cleared before the stack could be read). Did **not**
fabricate a source fix for a leak that cannot be observed (would dishonestly "satisfy"
AC#1/AC#2). PR #410.

**Reproduction attempts (all clean — 0 trips):**

- **macOS** (darwin-arm64, Node 24.9): default `vitest run` 100×; `--maxWorkers=1` 6×;
  `--no-file-parallelism` 1×; 25× under full CPU saturation (12 `yes` hogs on 10 cores);
  30× with `--sequence.shuffle`. = 162 runs.
- **Linux** (Docker `node:24-bookworm`, Node 24.18): 100× shuffled, fresh `npm ci`. *This is
  the lever the 2026-06-21 attempt lacked* — unhandled-rejection timing (when V8 fires the
  event vs microtask drain/GC/libuv) is platform-specific, so macOS could never reproduce a
  CI-Linux flake.
- **CI** (ubuntu-latest): 40× warm loop in one job; then **24 independent COLD separate jobs**
  (temporary `flake-hunt` matrix, `fail-fast:false`) to replicate the original cold-job
  failure condition. All green.

**Why no static fix exists (root-cause analysis — read all 4 forum page tests + service test
+ components):**

- Every forum component attaches its rejection handler **synchronously**, so no orphan can
  form: `ThreadDetailPage` `Promise.all([fetchThread, fetchPosts])` attaches to both inputs in
  one tick (both rejections consumed); `ThreadListPage` awaits `fetchCategory`→`fetchThreads`
  sequentially (2nd never called on the error path, and `mockRejectedValue` is **lazy** → not
  an orphan); `SearchPage` awaits each call in try/catch.
- Every error-path test awaits & asserts its rejection (`waitFor` / `await expect().rejects`);
  `forumService.test.ts` uses `await expect(fetchCategory(999)).rejects.toThrow('Category not found')`.
- The logger's Sentry path is dead in tests (`import.meta.env.DEV` → `console.log` only), so
  the "CategoryListPage mocks logger / doesn't leak" correlation is a red herring (its real
  difference is a single async call vs the others' multi-call patterns).
- Vitest 4.1.5 **removed** `poolOptions.forks.singleFork`; its replacement `isolate:false`
  breaks 100+ tests via state-bleed, so the pure single-process amplifier is unavailable.

**Delivered:** `web/src/tests/setup.ts` — non-suppressing `process.on('unhandledRejection')`
reporter (prints the originating stack; Vitest still exits 1, so it diagnoses without masking).
**If it ever recurs**, the CI log will contain `[UNHANDLED REJECTION] <stack>` → the exact
call site is pinned immediately and can be fixed at source per the original AC.

### 2026-06-21 - Investigated; could NOT reproduce locally → blocked on a real stack (run 2026-06-21-1412)

Picked up by completing-todos. **Outcome: not completable this run** — the flake
did not reproduce locally, so the exact originating call site can't be pinned and a
fix can't be verified. Left `in_progress`. Findings below to give the next attempt
a head start.

**Reproduction attempts (all clean):**

- Forum page tests alone (`ThreadDetailPage` + `SearchPage` + `ThreadListPage` +
  `CategoryListPage`), 3× → 66 passed, 0 unhandled. Confirms the leak is **cross-file**,
  surfacing only in the full 34-file run.
- Full suite `npx vitest run`, **20 runs** with precise detection (true process exit
  code + the `Errors  N` summary line) → **all exit 0, 623 passed**. The flake is
  CI-specific or <5% locally.
- Caution for the next person: the three components legitimately `logger.error(...)`
  in their catch blocks, so `Error: Thread not found` / `Search failed` /
  `Category not found` print on EVERY run as expected logs. Grepping for `Error:`
  or `fail` gives FALSE reproductions — gate only on exit code / the `Errors N`
  summary / the `⎯ Unhandled Errors ⎯` section.

**Theories ruled out (by code inspection):**

- `ThreadDetailPage` uses `Promise.all([fetchThread, fetchPosts])` in try/catch. The
  obvious "Promise.all leaks the 2nd rejection" theory is WRONG: per spec `Promise.all`
  attaches a rejection handler to each input promise, so both rejections are consumed.
  (Confirmed: forum-only runs with both mocks rejecting are clean.)
- `ThreadListPage` awaits `fetchCategory` then `fetchThreads` **sequentially** — the
  first rejection throws before the 2nd call is made, so no orphan promise.
- `SearchPage` calls `performSearch()` fire-and-forget (`:149`) but that fn is fully
  try/catch/finally-wrapped, so it RESOLVES (never rejects) → no unhandled rejection.
- All three components catch their rejections (try/catch → setError). No component has
  an un-awaited, un-caught promise in normal flow.

**Where this leaves it / recommended next step:**

- The leak is a rare cross-file timing artifact, not an obvious un-caught promise.
  Pinning it needs the **real stack** from a failing run: re-run Web CI until it fails
  and capture the `⎯⎯ Unhandled Errors ⎯⎯` → "This error originated in …" line (the CI
  logs that had it were cleared when #372's job was re-run). Or reproduce locally with
  a much longer loop / CI-like pool settings (`--pool=forks`, slower machine/load).
- Likely class once pinned: a test triggers an async path (e.g. an event handler or a
  debounced 300ms search timer in `SearchPage` that fires after teardown) whose
  rejected promise loses its handler across the test-file boundary. Fix at the source
  per the todo (await/clear the timer in the test, or guard the effect), NOT via
  `dangerouslyIgnoreUnhandledErrors`.
- Sibling risk noted in passing: `BlogListPage.tsx:68` also uses `Promise.all` (not
  forum, not in the reported messages) — harmless per the spec analysis above, but
  worth a glance if the leak ever traces to a `Promise.all` site.

### 2026-06-14 - Filed

- Created from self-review of PR #372 (issue #3). Flake pre-exists on `main` and is
  independent of the commit-gate work; re-running the job cleared #372 to merge.

## Notes

- p2: not a product bug, but it intermittently blocks every PR's path to a green
  merge (including #373), so it has real ongoing cost.
- Related: PR #372 / #373; the flake is on `main`, not introduced by either.
