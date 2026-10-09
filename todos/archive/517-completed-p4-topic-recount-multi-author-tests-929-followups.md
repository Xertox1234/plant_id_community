---
status: completed
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

- [x] Each finding above is fixed with a test, or the Work Log records why it was left as is.

## Work Log

- 2026-10-01: Filed from todo-sweep run 2026-10-02-0118, PR #929 review rounds 1-2.

### 2026-10-02 - Implemented by the todo sweep (run 2026-10-02-0335)

- Finding 1: added `test_a_failed_opening_post_link_still_recounts_the_authors_live_reply`. The opening author also has a live reply in the never-published topic, the opening post's publish is failed at `Revision.publish`, and the topic's own recount must then reach the author: `_refresh_profile` is called with exactly `[(author.pk,)]`, the author's `post_count` is 1, the board is recounted once and reads `(topic_count, post_count) == (1, 1)`. The existing failed-link test is untouched: its empty `_refresh_profile` list is a real pin (no live post, nothing owed), just not of the exclusion. Mutation check: passing `exclude_author_id=opening.author_id` regardless of the link failed only the new test (`assert [] == [(author.pk,)]`); the four other recount tests stayed green.
- Findings 2/3: comment only, no new test, since the existing assertions already pin the behaviour. The scheduled-post test's comment now cites Wagtail 8.0's `PublishRevisionAction._publish_revision` (`wagtail/actions/publish_revision.py`): a future `go_live_at` returns before `_after_publish()`, the `published` send, only when `object.live_revision_id` is set, so a never-published object is saved `live=False` and still gets the signal. It names what turns the test red (a bump that moves `_after_publish()` under `if object.live:` or widens that early return) and that the `linked_author_id` gate in signals.py, not the test, must change then.
- Finding 4: an amendment entry appended to todo 504's Work Log rather than a rewrite of its headings. Run ids are `date -u +%Y-%m-%d-%H%M` (UTC; `.claude/skills/completing-todos/SKILL.md`) while Work Log dates are local: run 2026-10-02-0118 began at 19:18 MDT on 2026-10-01 and PR #929 merged at 02:05 UTC (20:05 MDT), so both are right in their own clock and redating the headings would postdate the merge. `.sweep-evidence/` is gitignored (`.gitignore:228`), so the quoted pytest tail is the only committed record; the entry names the command that regenerates it. The same UTC-vs-local shape is in every Land-written entry and is not changed here.

### 2026-10-02 - Verified by the todo sweep (run 2026-10-02-0335)

- AC 1: `python3 scripts/todos/slot_env.py 1 -- backend/venv/bin/python -m pytest backend/packages/wagtail_forum/wagtail_forum/tests/test_topic_approval.py --create-db -v -p no:cacheprovider` — evidence `.sweep-evidence/g7/517-ac0.txt` (not committed), last lines:

  ```text
    backend/packages/wagtail_forum/wagtail_forum/api/image_management.py:32: RemovedInWagtail90Warning: wagtail.images.permissions.permission_policy is deprecated. Use wagtail.permissions.policy_registry.get_by_type(get_image_model()) instead.
      from wagtail.images import permissions as image_permissions

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================= 20 passed, 3 warnings in 32.34s ========================
  ```

### 2026-10-02 - Completed by the todo sweep (run 2026-10-02-0335)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
