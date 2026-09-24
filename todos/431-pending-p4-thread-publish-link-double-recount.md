---
status: pending
priority: p4
issue_id: "431"
tags: [forum, backend, performance]
dependencies: []
source_review: "PR #815"
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

- [ ] An approved thread (either direction) runs each recount once, pinned by
      an exact `django_assert_num_queries` (or a spy on the refresh helpers).

## Work Log

### 2026-09-24 - Filed from PR #815 review round 1
