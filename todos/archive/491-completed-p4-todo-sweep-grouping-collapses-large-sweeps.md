---
status: completed
priority: p4
issue_id: "491"
tags: [harness, todo-sweep]
dependencies: []
triage: blocked-owner
triaged: 2026-10-02
blocked_on: "Owner picks a strategy: drop LANE_FILES from the union, cap/split components, or hold only along dependency edges"
owner_decision: "Drop LANE_FILES from the union-find (they stay lanes) and propagate a hold along dependency edges only; no component size cap (2026-10-02)"
---

# Todo sweep: transitive file-overlap grouping plus a whole-component hold collapses a large sweep

## Problem

In sweep run 2026-09-28-2018, `state.py group` made **23 of the 52 selected todos
unschedulable**, including the p2 target 462. None of them was blocked on its own.
`_components` (`scripts/todos/group.py`) unions todos on every shared predicted file, and a few
hub files chained 23 todos into one component. `_held` then holds the whole component because
two members depend on todos in flight elsewhere: 448 → 428 and 457 → 410.

Hub files seen in the run: `backend/plant_community_backend/settings.py`,
`plant_community_mobile/lib/services/api_service.dart`, `backend/apps/users/views.py`,
`backend/apps/forum_host/tasks.py`,
`backend/packages/wagtail_forum/wagtail_forum/signals.py` and
`web/src/components/StreamFieldRenderer.tsx`.

Skipping 448 and 457 would not have helped: the rest still formed an 18-todo group, one worker
and one PR. 462 had to be deferred to a separate `finish todo 462`.

## Candidate fixes (owner picks)

1. Leave `LANE_FILES` (settings.py, `.secrets.baseline`) out of the union-find. They already
   serialise through lanes.
2. Cap or split a component: by top-level module, or by a size limit that serialises the
   overflow through waves.
3. Propagate a hold along dependency edges only, not along shared files. A file-sharing
   neighbour can still run in a later wave.

## Acceptance Criteria

- [x] The owner has picked a strategy, and it is recorded here.
- [x] A fixture reproducing the 2026-09-28 shape (hub files, two todos whose dependencies are out
      of the run) schedules the todos that have no dependency. The test fails on the current
      `group.py`.
- [x] No group in that fixture has more than a stated cap of todos.

## Work Log

### 2026-09-28 - Filed from todo sweep run 2026-09-28-2018 (grouping step)

### 2026-10-02 - Implemented by the todo sweep (run 2026-10-02-2343)

- Strategy (the owner's decision in the frontmatter): candidate fixes 1 and 3, no size cap.
  `_components` skips `LANE_FILES` (settings.py, `.secrets.baseline`), which stay lanes. A todo that
  depends on an open todo outside the plan is refused before grouping, and `_refuse` holds every todo
  that depends on it. It never joins a group, so the todos it shares a file with plan without it.
- The cycle check still unions on lane files (`_components(..., lane_files=True)`). A cycle between two
  todos that share only settings.py is still refused for those two (todo 474), not raised for the plan.
- `test_group.py` has a 23-todo fixture of the 2026-09-28 shape: the six hub files, with 448 -> 428
  and 457 -> 410 out of the run. On the merge-base `group.py` all 23 are unschedulable, as in the
  run. Now only 448 and 457 are: the other 21 are in 9 groups, and 462 is in the first wave. AC3's
  stated cap is 4 todos per group, the largest cluster that shares a real hub file.
- Two existing checks now assert the opposite, as the decision requires: "a shared hot file merges
  its todos into one group" (settings.py), and I4's "a todo sharing a real file with an unschedulable
  one is still blocked with it". Spec §7.1 now describes both rules.
- Trade-off: todos that overlap only on settings.py are now separate PRs, two waves apart. The
  fixture's eight settings.py groups take waves 0, 2, ..., 14.

### 2026-10-02 - Verified by the todo sweep (run 2026-10-02-2343)

- AC 1: `grep -n -e "^owner_decision:" -e "^- Strategy" todos/archive/491-completed-p4-todo-sweep-grouping-collapses-large-sweeps.md` — evidence `.sweep-evidence/g1/491-ac0.txt` (not committed), last lines:

  ```text
  10:owner_decision: "Drop LANE_FILES from the union-find (they stay lanes) and propagate a hold along dependency edges only; no component size cap (2026-10-02)"
  55:- Strategy (the owner's decision in the frontmatter): candidate fixes 1 and 3, no size cap.
  ```

- AC 2: `python3 .sweep-evidence/g1/491_fails_on_merge_base.py` — evidence `.sweep-evidence/g1/491-ac1.txt` (not committed), last lines:

  ```text
    FAIL  491 AC2: only the two todos whose dependencies are out of the run are unschedulable
    FAIL  491 AC2: every todo with no dependency is grouped and placed in a wave
    FAIL  491 AC2: the p2 target 462 is in the first wave
  branch group.py: exit 0, all checks passed
  RESULT: PASS -- the fixture checks pass with this branch's group.py, and the same test fails with the merge-base group.py
  ```

- AC 3: `python3 scripts/todos/test_group.py` — evidence `.sweep-evidence/g1/491-ac2.txt` (not committed), last lines:

  ```text
    PASS  491: a todo that depends on a held one is held too, naming it; a file-sharing one is not
    PASS  491: a cycle between todos that share only a lane file is refused for them, not the whole plan
    PASS  planning is deterministic

  All checks passed.
  ```

### 2026-10-02 - Completed by the todo sweep (run 2026-10-02-2343)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
