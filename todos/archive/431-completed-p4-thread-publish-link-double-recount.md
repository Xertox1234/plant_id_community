---
status: completed
priority: p4
issue_id: "431"
tags: [forum, backend, performance]
dependencies: []
source_review: "PR #815"
triage: ready
triaged: 2026-09-30
---

# Linked topic/opening-post publishes recount the board and profiles twice

## Problem

Todo 422 made a topic's publish carry its never-published opening post, and
the reverse. The two publishes are nested inside each other's `published`
receiver (`wagtail_forum/signals.py`, `update_counters_on_publish`), so an
approved thread recounts twice:

- topic → post: the topic branch runs `_refresh_board_counters` and
  `_refresh_topic_authors` before the opening post is live (wasted), then the
  nested post publish runs `_refresh_for_post`.
- post → topic: `_refresh_for_post` recounts the board and profile, then the
  nested topic publish recounts the board and every author's profile again.

Each is a locked UPDATE plus COUNT. Correct, just redundant, once per approved
thread.

## Findings

- Raised by the bundled `/code-review` of PR #815 (finding 7, efficiency).

## Recommended Action

Run the counterpart publish before the trigger's own recount in the topic
branch, or skip the trigger's recount when the nested publish will redo it.
Keep the ordering rule from todo 422: the topic's revision must snapshot
fresh counters.

## Acceptance Criteria

- [x] An approved thread (either direction) runs each recount once, pinned by
      an exact `django_assert_num_queries` (or a spy on the refresh helpers).

## Work Log

### 2026-09-24 - Filed from PR #815 review round 1

### 2026-09-30 - Implemented by the todo sweep (run 2026-10-01-0121)

- Topic branch of `update_counters_on_publish` now publishes the linked
  opening post FIRST; when that succeeds, its own receiver has already
  recounted the board and its author with the topic live, so the topic skips
  the board recount and excludes that author from `_refresh_topic_authors`
  (new `exclude_author_id` kwarg). Other authors in the topic still recount.
- Post branch splits `_refresh_for_post` into the topic recount (always, and
  before the topic is read, so its revision snapshots fresh counters — the
  todo 422 rule) and `_refresh_board_and_author`, which it skips when it will
  publish the never-published topic; a failed link still runs it.
- Unpublish/delete keep calling `_refresh_for_post` unchanged.
- Pinned by spies on `_refresh_board_counters`, `_refresh_profile` and
  `_refresh_topic_counters` in `test_topic_approval.py` (one call each, both
  directions, plus the final counter values); a mutation reintroducing either
  double recount fails them at `2 == 1`.

### 2026-09-30 - Verified by the todo sweep (run 2026-10-01-0121)

- AC 1: `cd backend && python3 ../scripts/todos/slot_env.py 3 -- /Users/williamtower/projects/plant_id_community/backend/venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_topic_approval.py --create-db -v -p no:cacheprovider` — evidence `.sweep-evidence/g3/431-ac0.txt`, last lines:

  ```text
    /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_010041ec-ccf-3/backend/packages/wagtail_forum/wagtail_forum/api/image_management.py:32: RemovedInWagtail90Warning: wagtail.images.permissions.permission_policy is deprecated. Use wagtail.permissions.policy_registry.get_by_type(get_image_model()) instead.
      from wagtail.images import permissions as image_permissions

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================= 16 passed, 3 warnings in 18.09s ========================
  ```

### 2026-09-30 - Completed by the todo sweep (run 2026-10-01-0121)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
