---
status: pending
priority: p4
issue_id: "517"
tags: [forum, backend, testing]
dependencies: []
triage: ready
triaged: 2026-10-02
---

# Topic recount multi-author tests: non-blocking findings from PR #929 (todo 504)

## Problem

PR #929 (todo 504) merged after two review rounds in todo-sweep run 2026-10-02-0118. The findings below were rated non-blocking, so they were not repaired. Findings at the same file:line are merged; each one says which round reported it. Line numbers are as of the PR head. Re-check each finding against main before acting on it.

## Findings

1. **`backend/packages/wagtail_forum/wagtail_forum/tests/test_topic_approval.py:492`** (low, round 1). Failed opening-post link test has no live post by the opening author, so \_refresh\_topic\_authors walks nothing. A regression passing exclude\_author\_id=opening.author\_id even on a failed link (board guard intact) still passes.
   Suggested: Give the opening author a second live reply in the topic before approval, then assert \_refresh\_profile is called with (author.pk,) and that author's post\_count == 1 after the failed link.

2. **`backend/packages/wagtail_forum/wagtail_forum/tests/test_topic_approval.py:510`** (low, round 2). The scheduled-opening-post test passes on unchanged code. It pins Wagtail 8's behavior of sending `published` for a scheduled first publish, not a repo change. The assertions are not hollow, but the docstring should state which Wagtail change turns it red.
   Suggested: Add a one-line note in the test comment naming the Wagtail behavior that would make it fail.

3. **`backend/packages/wagtail_forum/wagtail_forum/tests/test_topic_approval.py:512`** (low, round 1). Scheduled-post test and its comment pin Wagtail 8.0 behavior (published signal sent for scheduled first publish). The reviewer brief says 7.4; requirements.txt actually pins 8.0, so no mismatch, but the test is version-coupled and will fail on a Wagtail bump.
   Suggested: Keep; the comment already names the behaviour. Optionally cite the Wagtail version in the test docstring so a future bump failure is easy to diagnose.

4. **`todos/archive/504-completed-p4-thread-publish-single-recount-906-followups.md:55`** (low, round 1, round 2). Work Log headings are dated 2026-10-01 but cite sweep run 2026-10-02-0118, and the AC evidence points to a gitignored `.sweep-evidence/` path, so a reader can't re-check it. Evidence is only quoted inline.
   Suggested: Make the heading dates match the run id, or note that the evidence file is not committed.
   Also reported: Work Log headings are dated 2026-10-01 but cite sweep run 2026-10-02-0118; the date and run id disagree, and the evidence is a quoted paste only (the .sweep-evidence file is not in the diff).

## Acceptance Criteria

- [ ] Each finding above is fixed with a test, or the Work Log records why it was left as is.

## Work Log

- 2026-10-01: Filed from todo-sweep run 2026-10-02-0118, PR #929 review rounds 1-2.
