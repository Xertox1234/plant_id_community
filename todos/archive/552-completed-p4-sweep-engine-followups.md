---
status: completed
priority: p4
issue_id: "552"
tags: [todo-sweep, follow-ups, scripts]
dependencies: []
triage: ready
triaged: 2026-10-10
owner_decision: "Keep the leading cd <sub> and rewrite later paths relative to it (e.g. ../scripts/...), resolving chained cds; leave already-archived lines alone (2026-10-10)"
---

# Sweep engine follow-up, run 2026-10-02-0335

## Problem

Promoted out of todo 527 on 2026-10-10 (owner decision: slice it per PR). Todo-sweep run 2026-10-02-0335
merged 11 PRs (#941–#954); their review rounds reported the non-blocking findings below, which a curation pass
checked against main and a refuter failed to refute. Line numbers are as of 2026-10-02, so re-check each
finding against main before acting on it.

## Findings

### Sweep engine

1. **`scripts/todos/land.py` `_relativize`** (low, defect). Archived evidence commands keep a leading `cd <sub>` while their paths become repo-root-relative. `_relativize` (todo 524) strips the worktree and main-checkout roots from the quoted acceptance-criterion command but keeps a leading `cd backend &&` / `cd web &&`, so the later repo-root paths (`scripts/todos/slot_env.py`, `backend/venv/bin/python`, `todos/archive/...`) resolve under the subdirectory and the recorded command no longer re-runs. A chained `cd web && ... && cd plant_community_mobile` breaks the same way. Reported by reviewers on #949, #950, #953 and #954; it also affects the archives of 418, 435, 443, 451, 518, 521 and 523 from this run.
   Suggested: Belongs with todo 525 (same function): rewrite paths after a leading `cd <root>/<sub> &&` relative to that subdirectory (or drop the cd and keep repo-root paths), resolve each chained cd against the previous one, and add `test_land.py` cases for both. Leave the already-archived lines alone (owner's todo 524 no-backfill decision).

## Acceptance Criteria

- [x] Its finding is fixed with a test, or the Work Log records why it was left as is.

## Work Log

### 2026-10-10 - Promoted out of todo 527

- Split from the consolidated follow-up todo 527 (owner decision 2026-10-10: one todo per source PR).

### 2026-10-10 - Implemented by the todo sweep (run 2026-10-11-0401)

- `scripts/todos/land.py`: new `_relativize_command`, used for the quoted acceptance-criterion command only. `_relativize` marks each path it took off the repo, a worktree or main_root; the command is cut at `&&`, `||` and `;` outside quotes, and each marked path is rewritten relative to the directory the command has changed into by then (`cd backend && python3 ../scripts/todos/slot_env.py ... -- venv/bin/python`).
- A chained `cd` into another rooted directory resolves against the previous one (`cd web && ... && cd ../plant_community_mobile`). A path the command already wrote relative is left alone. A `cd` to an unrelated place (`~`, `/opt`, `$X`, bare) leaves the directory unknown, so later paths stay repo-root-relative, as before.
- The leading `cd` is kept (owner decision). Evidence tails and `_relativize` itself are unchanged, and already-archived lines are not rewritten.
- `scripts/todos/test_land.py`: 13 `_relativize_command` cases (subdirectory, chained, nested, `;`/`||`, quoted, `:`-joined, the todo's own path, already-relative, unknown cwd, NUL marker forgery) and one `flip_acs` case on the Verified entry.

### 2026-10-10 - Verified by the todo sweep (run 2026-10-11-0401)

- AC 1: `python3 scripts/todos/test_land.py` — evidence `.sweep-evidence/g6/552-ac0.txt` (not committed), last lines:

  ```text
    PASS  m9: the verify-only heading is 'Checked by'
    PASS  m9: no worker Work Log heading satisfies Land's Verified-note check
    PASS  m9: flip_acs's own heading still does

  All checks passed.
  ```

### 2026-10-10 - Completed by the todo sweep (run 2026-10-11-0401)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
