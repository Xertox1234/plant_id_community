---
status: pending
priority: p4
issue_id: "491"
tags: [harness, todo-sweep]
dependencies: []
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

- [ ] The owner has picked a strategy, and it is recorded here.
- [ ] A fixture reproducing the 2026-09-28 shape (hub files, two todos whose dependencies are out
      of the run) schedules the todos that have no dependency. The test fails on the current
      `group.py`.
- [ ] No group in that fixture has more than a stated cap of todos.

## Work Log

### 2026-09-28 - Filed from todo sweep run 2026-09-28-2018 (grouping step)
