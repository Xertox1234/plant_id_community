---
status: pending
priority: p4
issue_id: "605"
tags: [backend, forum, email, follow-ups]
dependencies: []
---

# Follow-ups from PR #1050 (todo 585, forum digest lock follow-ups)

## Problem

Todo-sweep run 2026-10-11-2219 merged PR #1050 (todo 585, forum digest lock follow-ups). The non-blocking review findings are below. The curator merged duplicates and checked each item against main, and the refuter dismissed what is listed as dropped. An item the curator did not return was kept as stored, unchecked. Line numbers are as of the PR head, so re-check each against main before acting on it.

## Findings

PR #1050 (todo sweep run 2026-10-11-2219, group g3, todos 585); follow-ups: verified; 1 item(s) the curator did not return were kept as stored.

1. **low** `backend/packages/wagtail_forum/wagtail_forum/management/commands/send_forum_digest.py:186` The per-member claim rechecks digest_frequency and is_active but not digest_recipients' third condition, user__email != ''. send_digest then mails the stale digest.user.email read with the chunk. A member who clears or changes their email mid-run is still claimed and mailed at the old address. | also: The claim rechecks digest_frequency and user__is_active, but not the third digest_recipients filter, exclude(user__email=""). send_digest also mails digest.user.email as read in the chunk, so a member who clears or changes their address mid-run gets mailed at the old one. | The recheck covers opt-in and is_active, but not the recipient filter's `user__email != ''`. The digest still goes to the address loaded with the chunk, so a member who changes or clears their email mid-run is mailed at the old address. | The claim rechecks digest_frequency and user.is_active, but digest_recipients also excludes user__email=''. A member who clears their email after the chunk read is still claimed and mailed. send_digest probably guards this, so the impact is small. | The claim rechecks digest_frequency and is_active but not digest_recipients' third condition (user email != ''). send_digest also mails the stale in-memory digest.user.email, so a member who changes or clears their address after the chunk was read is mailed at the old address. | The new claim rechecks opt-in and is_active, but send_digest still mails digest.user.email from the chunk read up to 200 rows earlier. A member who changed their email in that window, for example moving off a compromised address, gets the digest at the old address. | The claim rechecks opt-in and is_active, but not the third recipient condition in digest_recipients (`user.email != ""`). A member who clears their email after their chunk was read is still claimed, and send_digest gets the stale in-memory address.
2. **low** `backend/packages/wagtail_forum/wagtail_forum/management/commands/send_forum_digest.py:100` The comment says 'Release only a lock this run took', but holds_lock is set once at add() time. If the run outlives DIGEST_RUN_LOCK_SECONDS and another fire takes the expired key, this run's finally still deletes that fire's lock. This predates the change.
3. **low** `backend/packages/wagtail_forum/wagtail_forum/tests/test_digest.py:985` The one-table claim test asserts on Django's exact rendered SQL text (quoted "table"."col" IS NULL, ' WHERE ' and '(SELECT' splits). A Django or backend formatting change could turn it red with no real regression, though it does pin the join-free invariant. | also: The one-table claim test asserts on Django's exact quoted SQL text (`"table"."col" IS NULL`, `(SELECT` split). A Django or backend formatting change could turn it red with no real regression. It does fail on the intended `user__is_active` join. (reported at test_digest.py:962)
4. **low** `backend/packages/wagtail_forum/wagtail_forum/tests/test_digest.py:962` The one-table claim test asserts on Django's exact quoted SQL text (`"table"."col" IS NULL`, `(SELECT` split). A Django or backend formatting change could turn it red with no real regression. It does fail on the intended `user__is_active` join.

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-11 - Filed from the PR #1050 review (todo sweep run 2026-10-11-2219)

Filed by the closing step of the run from `state.py followups-md g3`.
