---
status: completed
priority: p4
issue_id: "439"
tags: [web, backend, profile, docs]
dependencies: []
source_review: "PR #821"
triage: ready
triaged: 2026-09-28
owner_decision: "Posts card counts replies only, relabeled \"Replies\" (2026-09-28)"
---

# Profile dashboard stats: non-blocking review findings (todo 411)

## Problem

The bundled `/code-review` of PR #821 raised these as non-blocking.

## Findings

- **Posts double-counts topics.** The "Posts" card counts every post,
  opening posts included, next to a separate "Topics" card, while "Recent
  activity" lists replies only. Count replies only (and label it), or say
  the Posts total includes opening posts.
- **Two sources of truth for a user's post count.** The view re-aggregates
  what `ForumProfile.post_count` already maintains (recounted under a lock
  in `wagtail_forum/signals.py`). Reuse it and drop a COUNT query.
- **Stale pattern docs.** `backend/docs/patterns/performance/query-optimization.md`
  (~line 324) and `backend/docs/performance/n-plus-one-elimination.md`
  (~79/113) still cite `dashboard_stats`' removed plant aggregation and
  "3-4 queries".
- **Field-by-field copy in `fetchDashboardStats`.** After the type guards it
  re-copies every field; adding a payload field now needs four edits.
- **No retry on the error state.** A transient 502 leaves the alert until a
  full reload (losing unsaved form edits), and a 401 shows DRF's raw detail.

## Acceptance Criteria

- [x] Each finding is fixed with a test, or declined with a reason.

## Work Log

### 2026-09-24 - Filed from PR #821 review round 1

### 2026-09-28 - Implemented by the todo sweep (run 2026-09-28-0839)

- **Posts double-counts topics: fixed.** Per the owner decision, `dashboard_stats`
  counts replies only (`is_opening_post=False` on the base queryset, which the
  recent-replies list now reuses) and the web card says "Replies". Wire names
  `total_posts`/`posts_this_month` are kept so no deployed client breaks; the
  view docstring and `DashboardForumStats` say what they mean. Test:
  `test_an_opening_post_counts_as_a_topic_not_a_reply`; two older assertions
  moved from 2 to 1 for the new semantics. Still 5 queries.
- **Reuse `ForumProfile.post_count`: declined.** That counter includes opening
  posts and posts on unpublished or restricted boards (`_refresh_profile` counts
  `live=True, topic__live=True` only) and has no 30-day window. Reusing it would
  bring back the double count and break `test_content_on_an_unpublished_board_is_hidden`,
  and `posts_this_month` would still need its own query. A view comment and the
  pattern doc say so, so the finding is not raised again.
- **Stale pattern docs: fixed.** `query-optimization.md` now shows the live
  forum-only aggregation (5 queries, pinned by `test_query_count_is_constant`)
  and marks the plant example as removed by todo 411. The dashboard rows in
  `n-plus-one-elimination.md`, `PERFORMANCE_PATTERNS_CODIFIED.md` and
  `backend/docs/README.md` now say 5 queries today.
- **Field-by-field copy: fixed.** `fetchDashboardStats` picks by
  `FORUM_STAT_KEYS`/`ACTIVITY_KEYS`, the same lists the guard checks. A new
  field is now one type edit plus one list entry. Test: stray keys inside
  `forum_stats` and inside an activity item are dropped.
- **No retry, raw 401: fixed.** The error state has "Try again", which refetches
  in place. The ProfilePage test types into the form, fails, retries and keeps
  the edit. A 401 now reads "Your session has ended. Sign in again…". A 403 and
  a 5xx keep the server's detail.

### 2026-09-28 - Verified by the todo sweep (run 2026-09-28-0839)

- AC 1: `cd /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_6b13b590-b1b-2/backend && python3 /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_6b13b590-b1b-2/scripts/todos/slot_env.py 2 -- /Users/williamtower/projects/plant_id_community/backend/venv/bin/python -m pytest apps/users/tests/test_dashboard_stats.py --create-db -v && cd /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_6b13b590-b1b-2/web && ./node_modules/.bin/vitest run src/components/profile/ProfileStats.test.tsx src/services/profileService.test.ts src/pages/ProfilePage.test.tsx && ! grep -nE 'PASSING \(3-4|→ 3-4 queries\)|from dashboard_stats endpoint' /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_6b13b590-b1b-2/backend/docs/patterns/performance/query-optimization.md /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_6b13b590-b1b-2/backend/docs/performance/n-plus-one-elimination.md /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_6b13b590-b1b-2/backend/docs/development/PERFORMANCE_PATTERNS_CODIFIED.md /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_6b13b590-b1b-2/backend/docs/README.md && grep -n '5 queries' /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_6b13b590-b1b-2/backend/docs/patterns/performance/query-optimization.md /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_6b13b590-b1b-2/backend/docs/performance/n-plus-one-elimination.md /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_6b13b590-b1b-2/backend/docs/development/PERFORMANCE_PATTERNS_CODIFIED.md /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_6b13b590-b1b-2/backend/docs/README.md && grep -n 'declined' /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_6b13b590-b1b-2/todos/439-pending-p4-profile-dashboard-stats-followups.md` — evidence `.sweep-evidence/g2/439-ac0.txt`, last lines:

  ```text
  /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_6b13b590-b1b-2/backend/docs/patterns/performance/query-optimization.md:1214:| dashboard_stats | ≤5 | <50ms | ✅ PASSING (5 queries, pinned by `test_query_count_is_constant`; todo 439) |
  /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_6b13b590-b1b-2/backend/docs/development/PERFORMANCE_PATTERNS_CODIFIED.md:555:            f"Dashboard should use ≤5 queries, got {query_count}"
  /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_6b13b590-b1b-2/backend/docs/development/PERFORMANCE_PATTERNS_CODIFIED.md:633:| dashboard_stats | ≤5 | <50ms | ✅ PASSING (5 queries, pinned by `test_query_count_is_constant`; todo 439) |
  39:- [ ] Each finding is fixed with a test, or declined with a reason.
  54:- **Reuse `ForumProfile.post_count`: declined.** That counter includes opening
  ```

### 2026-09-28 - Completed by the todo sweep (run 2026-09-28-0839)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
