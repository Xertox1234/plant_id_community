---
status: pending
priority: p4
issue_id: "504"
tags: [forum, backend, testing]
dependencies: []
---

# Thread publish single recount: non-blocking findings from PR #906 (todo 431)

## Problem

PR #906 (todo 431) merged after two review rounds in todo-sweep run 2026-10-01-0121. The findings below were rated non-blocking, so they were not repaired. Findings at the same file:line are merged; each one says which round reported it. Line numbers are as of the PR head. Re-check each finding against main before acting on it.

## Findings

1. **`backend/packages/wagtail_forum/wagtail_forum/signals.py:327`** (low, round 1). The topic branch reads \_publish\_counterpart returning True as proof that the nested post receiver recounted the board. A revision.publish that schedules (go\_live\_at in the future) sends no published signal, so the board topic\_count recount would be skipped. Not reachable today because there is no PublishingPanel.
   Suggested: After opening.refresh\_from\_db(), set linked\_author\_id only when opening.live is True. Otherwise fall through to the full board and author recount.

2. **`backend/packages/wagtail_forum/wagtail_forum/tests/test_topic_approval.py:343`** (low, round 1). No test pins that exclude\_author\_id only skips the opening-post author. A second author with a live post in the topic must still be recounted. Making the exclusion drop all authors would still pass.
   Suggested: Add a fixture with a second author's live reply, approve the thread, and assert \_refresh\_profile is called for that author too.

3. **`backend/packages/wagtail_forum/wagtail_forum/tests/test_topic_approval.py:364`** (low, round 2). Every new test has a single author, so nothing checks that exclude\_author\_id leaves other authors' profiles in the recount. A regression that skips \_refresh\_topic\_authors entirely after a successful link would pass all the new tests.
   Suggested: Add a topic-first case with a live post by a second author in the never-published topic. Assert that the \_refresh\_profile calls equal [(author.pk,), (other.pk,)] (or check their post\_count) so only the linked author is excluded.

4. **`backend/packages/wagtail_forum/wagtail_forum/tests/test_topic_approval.py:379`** (low, round 1). Only the post-to-topic failure arm is tested. The topic-to-post arm (opening-post publish fails, so linked\_author\_id stays None and the topic must still recount board and author) has no test. Deleting that guard would still pass.
   Suggested: Add a test that patches Post.save\_revision to raise during an admin topic publish and asserts the board recounts once and the author profile is recounted.

5. **`backend/packages/wagtail_forum/wagtail_forum/tests/test_topic_approval.py:381`** (low, round 2). Failed-link coverage exists only for the post-side branch. The topic-side fallback (opening-post publish fails, so the board recount must still run via linked\_author\_id None) has no test; deleting that `if linked_author_id is None` guard would still pass.
   Suggested: Add a test that patches Post.save\_revision to raise during an admin topic publish and asserts \_refresh\_board\_counters is called once and the author is still recounted.

6. **`backend/packages/wagtail_forum/wagtail_forum/tests/test_topic_approval.py:391`** (low, round 1). The new failed-link test covers only the post-to-topic direction. The new topic-branch fallback (linked\_author\_id None leads to a full board recount when the opening-post publish fails) has no test, so a mutation that always skips the board recount there would pass.
   Suggested: Add a topic-direction failure test: patch Post.save\_revision to raise, admin-publish the topic, assert \_refresh\_board\_counters is called once and board.topic\_count == 1.

7. **`backend/packages/wagtail_forum/wagtail_forum/tests/test_topic_approval.py:392`** (low, round 2). The failed-link test never asserts that the link failed. If the Topic.save\_revision patch stopped taking effect, the success path also gives exactly one board recount and one profile call, so the test would still pass without running the fallback recount.
   Suggested: After the publish, add `topic.refresh_from_db(); assert topic.live is False` (as the earlier failed-link test does), so the test proves the `_refresh_board_and_author` fallback is what produced the single recount.

8. **`backend/packages/wagtail_forum/wagtail_forum/tests/test_topic_approval.py:393`** (low, round 1). Only the post-to-topic direction has a failed-link test. If the opening-post publish fails in the topic branch, linked\_author\_id stays None and the full board and author recount runs, but no test covers that. Code is correct today; a regression there would go uncaught.
   Suggested: Add a test that approves the topic with Post.save\_revision patched to raise. Assert that \_refresh\_board\_counters runs once and \_refresh\_profile runs once with author.pk, and that board.topic\_count == 1.

## Acceptance Criteria

- [ ] Each finding above is fixed with a test, or the Work Log records why it was left as is.

## Work Log

- 2026-09-30: Filed from todo-sweep run 2026-10-01-0121, PR #906 review rounds 1-2.
