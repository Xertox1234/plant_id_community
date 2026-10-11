---
status: pending
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

- [ ] Its finding is fixed with a test, or the Work Log records why it was left as is.

## Work Log

### 2026-10-10 - Promoted out of todo 527

- Split from the consolidated follow-up todo 527 (owner decision 2026-10-10: one todo per source PR).
