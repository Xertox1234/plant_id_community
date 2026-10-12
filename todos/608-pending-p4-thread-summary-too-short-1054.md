---
status: pending
priority: p4
issue_id: "608"
tags: [web, forum, follow-ups]
dependencies: []
---

# Follow-ups from PR #1054 (todo 588, thread summary too-short line)

## Problem

Todo-sweep run 2026-10-11-2219 merged PR #1054 (todo 588, thread summary too-short line). The non-blocking review findings are below. The curator merged duplicates and checked each item against main, and the refuter dismissed what is listed as dropped. An item the curator did not return was kept as stored, unchecked. Line numbers are as of the PR head, so re-check each against main before acting on it.

Nothing was kept: the one finding was refuted. It is listed below so the owner can re-judge it; close this todo if you agree with the refuter.

## Findings

PR #1054 (todo sweep run 2026-10-11-2219, group g6, todos 588); follow-ups: verified.

Dropped by curation (fixed on main, refuted, or not a reported location):

- low: web/src/components/forum/ThreadSummaryPanel.tsx:225 The condition `outcome?.status !== 'ready'` also shows the too-short line next to other outcomes such as errors or disabled, when postCount < MIN_POSTS. This is harmless but broader than the comment says. No test covers it. (refuted: Outcome = Exclude<TopicSummary,pending> is only 'ready' or 'too_short' (types/forum.ts:441-444); errors/403/404/429 set `message`, never `outcome`. So the condition shows the line for null or too_short, which is what the comment at 219-224 says: shown below MIN_POSTS, except beside a summary.)

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-11 - Filed from the PR #1054 review (todo sweep run 2026-10-11-2219)

Filed by the closing step of the run from `state.py followups-md g6`.
