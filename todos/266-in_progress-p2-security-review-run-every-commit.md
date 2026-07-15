---
status: in_progress
priority: p2
issue_id: "266"
tags: [ci, security]
dependencies: []
---

# Security-review blocking gate silently skips every commit after a PR's first

## Problem

`anthropics/claude-code-security-review` (vendored in `.github/workflows/security-review.yml`)
only ever runs its actual Claude scan on a PR's **first** commit. A per-PR
`actions/cache` marker (keyed `claudecode-<repo_id>-pr-<PR#>-<sha>`, restored via
a PR-scoped prefix) disables the scan on every subsequent push to the same PR —
by upstream design, to save API cost. While the severity gate was advisory
(pre-todo-249), a skipped re-scan was harmless. Since todo 249 promoted the gate
to blocking + fail-closed-on-unverifiable-results (2026-07-14), every commit
after a PR's first now hits a missing `claudecode-results.json` and fails the
required check unconditionally — merge is permanently blocked unless someone
notices and manually clears the cache.

This is not a new bug introduced by todo 249 — the dedup blind spot (later
commits are never independently scanned) has existed all along. Todo 249 just
made it fail loudly instead of silently.

## Findings

- Live-hit on PR #462 (todo 253 slice 1, 2 commits: `dfac88a`, `4cd631d`):
  second push's "Claude Code Security Review" run failed in 19s with
  `##[error]claudecode-results.json not found — cannot verify severity, failing
  closed.` (run 29339610714, job 87107599261).
- Root cause confirmed from the action's own source at the pinned SHA
  (`anthropics/claude-code-security-review@0c6a49f1fa56a1d472575da86a94dbc1edb78eda`,
  `action.yml`, step "Determine ClaudeCode enablement"):

  ```bash
  if [ "$RUN_EVERY_COMMIT" != "true" ] && [ -f ".claudecode-marker/marker.json" ]; then
    echo "ClaudeCode has already run on PR #$PR_NUMBER (found marker file), forcing disable to avoid false positives"
    ENABLE_CLAUDECODE="false"
  ```

  The restore-keys prefix (`claudecode-<repo_id>-pr-<PR#>-`) matches ANY prior
  commit's marker on the same PR, not just an exact-SHA cache hit.
  `run-every-commit` (action input, default `false`) is the only documented
  escape hatch.
- Neither of the action's exposed outputs (`findings-count`, `results-file`)
  surfaces the enablement state to the calling workflow — our own
  `security-review.yml` has no way to distinguish "skipped by dedup" from "ran
  and errored" without adding an `id:` to the scan step and checking whether
  `steps.<id>.outputs.findings-count` is empty.
- `gh cache list --key "claudecode-"` at the time of discovery showed exactly
  **one** marker per PR across PRs #443–#461 — consistent with most recent PRs
  merging before todo 249's promotion (2026-07-14, PR #460), so #462 is likely
  the first PR to exercise this interaction.
- Immediate unblock applied to #462 (one-off, no workflow file changed):
  `gh cache delete 5735337998` (the stale PR-462 marker) then
  `gh run rerun 29339610714 --failed`. Rerun log confirmed a genuine re-scan:
  `ClaudeCode will run for PR #462 (first run)` / `ClaudeCode is enabled for
  this run`, followed by `At/above-HIGH-severity findings: 0` / `No
  HIGH-or-above severity findings — check passed.` PR merged automatically via
  already-armed auto-merge at `2026-07-14T14:31:03Z` (merge commit `0fb9665`).

## Proposed Solutions

### Option 1: Set `run-every-commit: true` (Recommended)

- **Implementation:** in `.github/workflows/security-review.yml`, add
  `run-every-commit: true` to the `with:` block of the "Run Claude Code
  security review" step.
- **Pros:** every pushed commit is actually scanned — the gate finally
  guarantees what "blocking, required, fail-closed" was assumed to mean since
  todo 249. Closes the pre-existing dedup blind spot entirely, not just the
  new failure mode.
- **Cons:** one Claude API scan per push instead of per PR (real, ongoing
  cost). The action's own docs warn of "more false positives ... as the AI
  analyzes the same code multiple times" — but per this repo's design only
  HIGH/CRITICAL blocks (MEDIUM/LOW stays advisory), so extra false positives
  at those lower severities cost nothing; an extra false HIGH would block a
  later commit until dismissed/re-reviewed, which is arguably the gate working
  as intended, not a defect.
- **Effort:** 5 minutes (one-line workflow change) + re-verification on a
  multi-commit test PR.
- **Risk:** low. Pure config change, no code path changes.

### Option 2: Teach the gate to distinguish "skipped by dedup" from "errored"

- **Implementation:** add `id:` to the scan step; in the gate step, treat an
  empty `steps.<id>.outputs.findings-count` (dedup-skipped) as a pass instead
  of fail-closed, reserving fail-closed for the case where the scan actually
  ran but produced no parseable results.
- **Pros:** keeps the one-scan-per-PR cost profile.
- **Cons:** **rejected** — this makes the required check pass-by-default on
  every commit after a PR's first, i.e. fails open on exactly the commits
  most likely to carry unreviewed changes. That's precisely the failure mode
  todo 249 was written to close ("a blocking gate must not fail open"), and
  this repo has no human-review backstop on AI-authored/AI-reviewed PRs to
  catch what it'd miss. Listed only for completeness — do not implement
  without a strong reason to override todo 249's own reasoning.

## Recommended Action

1. Edit `.github/workflows/security-review.yml`: add `run-every-commit: true`
   to the `with:` block of the "Run Claude Code security review" step, with a
   comment citing this todo and the dedup collision it closes.
2. Open a small standalone PR (not bundled with unrelated work).
3. Verify on that PR itself: push a second commit after the first CI run
   completes, confirm the second run's log shows `ClaudeCode is enabled for
   this run` (not the disabled/marker-found branch) and produces a fresh
   `claudecode-results.json`.
4. Update the workflow file's header comment (currently documents the
   fail-closed rationale from todo 249) to note every commit is now
   independently scanned.

## Technical Details

- `.github/workflows/security-review.yml` — the "Run Claude Code security
  review" step (`uses: anthropics/claude-code-security-review@...`) and the
  "Enforce severity gate (blocking, todo 249)" step immediately after it.
- Vendored action pinned at
  `anthropics/claude-code-security-review@0c6a49f1fa56a1d472575da86a94dbc1edb78eda`
  — `action.yml` steps "Check ClaudeCode run history" (cache restore) and
  "Determine ClaudeCode enablement" (the dedup logic itself) are not
  something we can edit directly (vendored by SHA); `run-every-commit` is the
  only supported input for this.
- Related: `docs/LEARNINGS.md` and `docs/rules/` don't yet have an entry for
  this — worth a short note when this todo is completed, since "a blocking CI
  gate can silently stop verifying anything after the first commit" is a
  reusable lesson beyond this one action.

## Acceptance Criteria

- [x] `run-every-commit: true` set on the security-review action in
      `.github/workflows/security-review.yml`.
- [ ] A test PR with 2+ commits shows a fresh, non-dedup-skipped scan log
      (`ClaudeCode is enabled for this run`) on the second commit's run.
- [x] Workflow file's header/step comments updated to reflect the new
      per-commit scan behavior and reference this todo.

## Work Log

### 2026-07-14 - Discovered live on PR #462, filed as a follow-up todo

- Hit while completing todo 253 slice 1: PR #462's second push failed the
  required "Claude Code Security Review" check via the new todo-249 blocking
  gate, not because of a real finding but because the action's own per-PR
  dedup cache had disabled the scan for that commit. Diagnosed from the live
  run log + the action's `action.yml` source at the pinned SHA (see Findings).
  Unblocked #462 with a one-off `gh cache delete` + `gh run rerun --failed`
  (no workflow file changes on that branch) — rerun log confirmed a genuine
  scan ran, 0 HIGH/CRITICAL findings, gate passed for real, PR merged via
  already-armed auto-merge (`0fb9665`, 2026-07-14T14:31:03Z). User chose to
  file this todo now rather than implement the durable fix immediately.

### 2026-07-15 - Started by completing-todos skill (run 2026-07-15-0310)

- Picked up by automated workflow.

### 2026-07-15 - Option 1 implemented on standalone branch `fix/security-review-run-every-commit`

- Branched off `origin/main` (HEAD `2dedc46`) into an isolated worktree, per
  Recommended Action step 2 ("not bundled with unrelated work") — the current
  session's active branch (`feat/forum-notifications-slice4-mentions`) is
  unrelated to this fix.
- Edited `.github/workflows/security-review.yml`: added `run-every-commit:
  true` to the scan step's `with:` block, plus a header-comment paragraph and
  an inline step comment, both citing this todo. `python3 -c "import yaml;
  yaml.safe_load(...)"` confirmed the file parses. `git diff --stat` showed
  "1 file changed, 10 insertions(+)".
- AC1 verified: `grep -n "run-every-commit" .github/workflows/security-review.yml`
  →

  ```
  17:# scanned. `run-every-commit: true` on the scan step below closes that gap.
  78:          run-every-commit: true
  ```

- AC3 verified: `grep -n "todo 266" .github/workflows/security-review.yml`
  →

  ```
  13:# Every commit is scanned, not just the PR's first (todo 266, 2026-07-15): the
  75:          # todo 266: without this, the action's per-PR dedup cache skips the
  ```

- Also added a `docs/LEARNINGS.md` entry (Tooling / Agents, 2026-07-15
  additions) per this todo's own Technical Details note — not an acceptance
  criterion, included as a bonus per the todo's explicit ask.
- AC2 (live 2-commit PR showing a fresh, non-dedup-skipped scan) intentionally
  NOT attempted yet: it requires committing, pushing, and opening a real PR —
  actions the completing-todos skill's safety rails explicitly forbid running
  autonomously ("never commit"), and which affect shared state (GitHub) per
  the broader executing-actions-with-care guidance. Paused here to get the
  user's explicit go-ahead before pushing anything.

### 2026-07-15 - PR #466 opened, first CI run observed

- User approved pushing the branch and opening a standalone PR, with the
  explicit constraint that merge stays a separate confirmation.
- Pushed `fix/security-review-run-every-commit` (commit `59028af`), opened
  <https://github.com/Xertox1234/plant_id_community/pull/466> against `main`.
- First run (29386701402) completed: job "Claude Code Security Review"
  passed in 54s. `gh run view 29386701402 --log` confirmed the baseline
  path (expected for any PR's first commit, fix or no fix):

  ```
  ClaudeCode will run for PR #466 (first run)
  ClaudeCode is enabled for this run
  ```

  This alone doesn't prove the fix works — a first run always scans. The
  real test is the next commit.

## Notes

- Priority p2: not urgent (the one-off unblock is done and #462 is merged),
  but every future multi-commit PR will hit this exact failure until fixed —
  should not sit indefinitely.
- Do not implement Option 2 without revisiting this decision explicitly —
  advisor guidance during discovery was explicit that it reopens the gap
  todo 249 closed.
