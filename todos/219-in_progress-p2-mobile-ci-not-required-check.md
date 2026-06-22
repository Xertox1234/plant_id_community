---
status: in_progress
priority: p2
issue_id: "219"
tags: [ci, branch-protection, flutter, mobile, process]
dependencies: []
---

# Mobile CI (Flutter) is not a required status check on `main`

## Problem

A Flutter-only PR can merge into `main` even if `flutter analyze`/`flutter test`
fails. `main`'s branch protection requires only backend/web/harness checks — the
mobile app's own CI (`Mobile Fresh Checkout CI` → job **"Flutter analyze, test,
and debug build"**) is **not** in the required set. Since the mobile app is the
primary platform, broken mobile code reaching `main` is a real risk.

The naive fix (add the job to required checks) is **wrong on its own**: `mobile-ci`
is path-filtered, so making it required would deadlock every non-mobile PR.

## Findings

- `main` required status checks (`gh api repos/Xertox1234/plant_id_community/branches/main/protection/required_status_checks/contexts`, 2026-06-06):

  ```text
  Install dependencies and run Django checks
  Run backend test suite (pytest, postgres + redis)
  Type-check, lint, and unit/component tests
  Hook self-tests and Python inject tests
  ```

  No Flutter/mobile context present.
- `.github/workflows/mobile-ci.yml:9-13` — the `pull_request` trigger is **path-filtered**:

  ```yaml
  pull_request:
    branches: [main, develop]
    paths:
      - 'plant_community_mobile/**'
      - '.github/workflows/mobile-ci.yml'
  ```

  → on a non-mobile PR the job never runs. A required, never-running check
  leaves the PR permanently `BLOCKED` ("waiting for status to be reported").
- Precedent / cautionary note: `.github/workflows/harness-ci.yml:4-8` documents
  exactly this trap and deliberately runs its required job on **every** PR
  (justified because the harness tests are *fast*). Flutter CI is **not** fast
  (~6.5 min: `build_runner` + `analyze` + `test` + debug build), so the
  always-run approach has a real cost.
- Surfaced 2026-06-06 while merging PR #357 (a Flutter-only change): all 4
  required checks went green and the PR became mergeable independently of the
  Flutter job (which happened to pass at 6m36s, but was never a gate).
- Related: todo 211 (PR #337) added backend-tests / web-checks / harness-tests
  to branch protection required checks — mobile-ci was missed in that pass.

## Proposed Solutions

### Option 1: Always-run gate job that conditionally runs Flutter (Recommended)

- **Implementation:** Add a lightweight job (e.g. `mobile-ci-gate`) that runs on
  **every** PR (no path filter). It uses a path-detection step
  (`dorny/paths-filter` or a `git diff` check): if `plant_community_mobile/**`
  changed, it runs/awaits the Flutter job; otherwise it short-circuits and exits
  0. Make **this gate** the required status check. Keep the heavy Flutter job
  path-filtered as today.
- **Pros:** No deadlock on non-mobile PRs; Flutter cost only paid when mobile
  files change; honest gate for mobile PRs.
- **Cons:** Slightly more workflow plumbing; the "did it actually run Flutter"
  signal is one indirection removed.
- **Effort:** ~1–2 hours.
- **Risk:** Low — additive workflow change, testable on a throwaway PR.

### Option 2: Remove the path filter so Flutter runs on every PR

- **Implementation:** Drop the `paths:` block from `mobile-ci.yml`'s
  `pull_request` trigger (mirror `harness-ci.yml`), then add the job to required
  checks.
- **Pros:** Simplest; matches the harness-ci pattern exactly.
- **Cons:** Every PR — including docs-only and backend-only — pays ~6.5 min of
  Flutter CI. Wasteful and slows unrelated PRs.
- **Effort:** ~30 min.
- **Risk:** Low correctness risk; ongoing CI-time cost.

### Option 3: Accept the gap (status quo)

- Leave mobile-ci non-required; rely on author discipline. Cheapest, but the gap
  remains and will eventually let a broken Flutter PR through.

## Recommended Action

1. Implement **Option 1**: add an always-run `mobile-ci-gate` job to
   `.github/workflows/mobile-ci.yml` that conditionally runs/awaits the Flutter
   job and always reports a status.
2. Verify on a throwaway non-mobile PR that the gate reports **success quickly**
   (does not deadlock) and on a mobile PR that it fails when `flutter test` fails.
3. Add the gate context to branch protection (repo-admin required):

   ```bash
   gh api -X POST \
     repos/Xertox1234/plant_id_community/branches/main/protection/required_status_checks/contexts \
     -f 'contexts[]=mobile-ci-gate'
   ```

   (or Settings → Branches → `main` → Require status checks → add the context)

## Technical Details

- Files: `.github/workflows/mobile-ci.yml` (trigger + new gate job),
  branch-protection settings for `main`.
- Deadlock mechanism: GitHub treats a required check with **no reported status**
  as pending forever; path-filtered workflows report nothing on PRs whose diff
  doesn't match `paths:`. See the inline rationale in
  `.github/workflows/harness-ci.yml:4-8`.
- Applying branch-protection changes requires repo-admin permissions (the API
  call above is not runnable by CI / non-admin).

## Acceptance Criteria

- [ ] A required status check exists that gates `main` on Flutter `analyze`/`test`
      for PRs that touch `plant_community_mobile/**`.
- [ ] A non-mobile PR (e.g. docs-only) is **not** blocked/deadlocked by the new
      required check (it reports success promptly).
- [ ] A mobile PR with a deliberately failing `flutter test` is blocked from
      merging.
- [ ] `main` branch-protection `required_status_checks/contexts` includes the new
      gate context.

## Work Log

### 2026-06-06 - Discovered & filed

- Found while merging PR #357 (Flutter-only): the merge was gated only by
  backend/web/harness checks; the Flutter job was advisory.
- Confirmed `mobile-ci.yml` is path-filtered, so the simple "add to required
  checks" fix would deadlock non-mobile PRs. Captured the safe approaches above.

### 2026-06-22 - Started by completing-todos skill (run 2026-06-22-1542)

- Picked up by automated workflow. Implementing Option 1 (always-run
  `mobile-ci-gate` job + conditional Flutter job via `dorny/paths-filter`).

### 2026-06-22 - Implemented Option 1 (workflow change) — branch-protection step pending

**Done (this PR, branch `todo-219-mobile-ci-required-gate`):**

- Rewrote `.github/workflows/mobile-ci.yml` to the always-run gate pattern:
  - Removed the `paths:` filter from the `pull_request` trigger (workflow now runs
    on every PR); kept the `push` trigger path-filtered.
  - Added a `changes` job (`dorny/paths-filter@v4`, current major — latest is
    v4.0.1) exposing `outputs.mobile`.
  - `flutter-fresh-checkout` now `needs: changes` and runs only when mobile files
    changed (`if: needs.changes.outputs.mobile == 'true' || github.event_name ==
    'workflow_dispatch'`). Job body unchanged.
  - Added `mobile-ci-gate` (job id **is** the branch-protection context — no
    `name:` override): `needs: [changes, flutter-fresh-checkout]`, `if: always()`.
    Fails the gate if change-detection didn't succeed OR the Flutter job result is
    `failure`/`cancelled`; passes otherwise (incl. Flutter `skipped` on non-mobile
    PRs, so non-mobile PRs are never deadlocked).

**Verification (local — proves implementation correctness, NOT the acceptance
criteria, which are GitHub-side):**

- `actionlint .github/workflows/mobile-ci.yml` → `OK (no issues)` (validates the
  `needs`/context refs and the gate's shell).
- `python3 -c "yaml.safe_load(...)"` → parses; jobs = `[changes,
  flutter-fresh-checkout, mobile-ci-gate]`.
- Gate decision logic simulated across all six scenarios — every one matched the
  expected verdict: non-mobile PR → PASS (no deadlock); mobile pass → PASS; mobile
  fail → FAIL; cancelled → FAIL; broken change-detection → FAIL (no silent green);
  workflow_dispatch → PASS.

**Code review:** No specialist reviewer matches a YAML workflow change
(code-review-orchestrator routing → 0 agents). Self-assessment: gate wiring correct
across every scenario; no GitHub Actions expression-injection risk (only the
controlled `needs.*.result` enum is interpolated). 1 HIGH + 3 LOW:

- HIGH — gate is inert until `mobile-ci-gate` is added to `main`'s required
  contexts (verified live: required set is still the 4 backend/web/harness checks).
  This is the tracked admin step below, **not** a code defect; nothing in this PR
  can close it.
- LOW (all accepted, no code change): (1) paths-filter false-negative is the only
  residual slip-through vector — low prob, globs match scope + mirror the `push`
  filter; (2) `dorny/paths-filter@v4` pinned to a major tag not a SHA — matches repo
  convention; (3) `workflow_dispatch` may show a cosmetic red gate (non-gating,
  manual only).

**Remaining (NOT done — why this todo stays `in_progress`):** all four acceptance
criteria are GitHub-side / repo-admin and cannot be verified locally. Required
**ordered** handoff:

1. Merge this PR to `main` (the gate workflow must live on the default branch
   before it can back a required check).
2. Open any PR after the merge and read the **exact** reported check name; confirm
   it is literally `mobile-ci-gate`. (A required context that never matches =
   permanent deadlock — the very failure this todo prevents.)
3. Repo-admin adds it as a required context, only after step 2 confirms the string:

   ```bash
   gh api -X POST \
     repos/Xertox1234/plant_id_community/branches/main/protection/required_status_checks/contexts \
     -f 'contexts[]=mobile-ci-gate'
   ```

   Per the user's choice, Claude runs this with explicit go-ahead once steps 1–2
   are confirmed.
4. Live-verify the criteria: a docs-only PR shows `mobile-ci-gate` green quickly
   (criterion #2); a mobile PR with a deliberately failing `flutter test` shows the
   gate red and is blocked from merge (criterion #3). Then check off the criteria
   and archive the todo.

## Notes

- Priority **p2**: real gap on the primary platform, but no active breakage and
  exploiting it requires a specific scenario (a Flutter-only PR with a failing
  test). The correct fix needs a small design step (Option 1), not a one-liner —
  hence not p1.
- Related: todo 211 (branch-protection required checks) — same class of gap; this
  is the mobile follow-up that pass missed.
