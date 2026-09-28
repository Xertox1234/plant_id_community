---
status: completed
priority: p4
issue_id: "470"
tags: [web, typescript, docs]
dependencies: []
source_review: "PR #863"
triage: ready
triaged: 2026-09-28
---

# Stale JSDoc above `DashboardForumStats` contradicts replies-only counts

## Problem

PR #863 (todo 439) made the dashboard's post counts replies-only and added a new
JSDoc block above `DashboardForumStats` in `web/src/types/auth.ts` (~line 50).
The old block is still there, directly above it, and says "Posts include each
topic's opening post." That is now false.

## Findings

- Raised as `low` by both review rounds of #863 (todo sweep pilot, run
  `2026-09-28-0839`).

## Recommended Action

Delete the old JSDoc block and keep the new one.

## Acceptance Criteria

- [x] `web/src/types/auth.ts` has one JSDoc block above `DashboardForumStats`, and it says replies only.

## Work Log

### 2026-09-28 - Filed from PR #863 review

### 2026-09-28 - Implemented by the todo sweep (run 2026-09-28-2018)

- Merged the two JSDoc blocks above `DashboardForumStats` in
  `web/src/types/auth.ts` into one.
- Dropped the false "Posts include each topic's opening post" sentence. Kept
  the endpoint, the "last 30 days" meaning of "this month", and the todo 439
  replies-only note.
- Comment-only change: eslint, tsc and prettier are clean on the file.

### 2026-09-28 - Verified by the todo sweep (run 2026-09-28-2018)

- AC 1: `sed -n '/^export type ProfileUpdate/,/^export interface DashboardForumStats/p' web/src/types/auth.ts` — evidence `.sweep-evidence/g9/470-ac0.txt`, last lines:

  ```text
   * "This month" is the last 30 days. `total_posts` / `posts_this_month` count
   * REPLIES only (todo 439): an opening post is already one of the topics. The
   * wire names predate that decision.
   */
  export interface DashboardForumStats {
  ```

### 2026-09-28 - Completed by the todo sweep (run 2026-09-28-2018)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
