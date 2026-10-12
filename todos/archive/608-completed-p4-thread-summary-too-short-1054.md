---
status: completed
priority: p4
issue_id: "608"
tags: [web, forum, follow-ups]
dependencies: []
owner_decision: "Agree with the refuter: record the finding as declined (Outcome is only ready|too_short, types/forum.ts:441-444) and archive; verify-only, no code (2026-10-11)"
triage: ready
triaged: 2026-10-11
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

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-11 - Filed from the PR #1054 review (todo sweep run 2026-10-11-2219)

Filed by the closing step of the run from `state.py followups-md g6`.

### 2026-10-11 - Owner decision: close, agreeing with the refuter

The owner agrees with the refuter. `Outcome = Exclude<TopicSummary, pending>` is only `'ready'` or `'too_short'`
(`web/src/types/forum.ts:441-444`), so the condition cannot show the line next to an error or a disabled state.
Record the finding as declined with that evidence and archive. No code change.

### 2026-10-11 - Implemented by the todo sweep (run 2026-10-12-0349)

- Finding (`ThreadSummaryPanel.tsx`, `outcome?.status !== 'ready'` "broader than the comment"): declined, per
  the owner decision. No code change.
- Reason: `type Outcome = Exclude<TopicSummary, { status: 'pending' }>`
  (`web/src/components/forum/ThreadSummaryPanel.tsx:57`), and `TopicSummary` is `ready | pending | too_short`
  (`web/src/types/forum.ts:441-444`), so `outcome` is only `null`, `ready` or `too_short`.
- Errors, 403/404/429 and the still-writing case call `setMessage(...)` (lines 153-190), never `setOutcome`,
  so the too-short line (line 225) can show only for `null` or `too_short`, which is what the comment at
  lines 219-224 says.

### 2026-10-11 - Verified by the todo sweep (run 2026-10-12-0349)

- AC 1: `grep -n -E "type Outcome = Exclude<TopicSummary|status: 'ready'; summary|status: 'pending' \}|status: 'too_short'; post_count|setOutcome\(|Implemented by the todo sweep \(run 2026-10-12-0349\)|declined, per" web/src/components/forum/ThreadSummaryPanel.tsx web/src/types/forum.ts todos/archive/608-completed-p4-thread-summary-too-short-1054.md` — evidence `.sweep-evidence/g4/608-ac0.txt` (not committed), last lines:

  ```text
  web/src/types/forum.ts:443:  | { status: 'pending' }
  web/src/types/forum.ts:444:  | { status: 'too_short'; post_count: number };
  todos/608-pending-p4-thread-summary-too-short-1054.md:45:### 2026-10-11 - Implemented by the todo sweep (run 2026-10-12-0349)
  todos/608-pending-p4-thread-summary-too-short-1054.md:47:- Finding (`ThreadSummaryPanel.tsx`, `outcome?.status !== 'ready'` "broader than the comment"): declined, per
  todos/608-pending-p4-thread-summary-too-short-1054.md:49:- Reason: `type Outcome = Exclude<TopicSummary, { status: 'pending' }>`
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-12-0349)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
