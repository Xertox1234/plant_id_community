---
status: pending
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

- [ ] `web/src/types/auth.ts` has one JSDoc block above `DashboardForumStats`, and it says replies only.

## Work Log

### 2026-09-28 - Filed from PR #863 review
