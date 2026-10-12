---
status: completed
priority: p4
issue_id: "605"
tags: [backend, forum, email, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-11
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

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-11 - Filed from the PR #1050 review (todo sweep run 2026-10-11-2219)

Filed by the closing step of the run from `state.py followups-md g3`.

### 2026-10-11 - Implemented by the todo sweep (run 2026-10-12-0349)

- Finding 1 (fixed): the claim in `backend/packages/wagtail_forum/wagtail_forum/management/commands/send_forum_digest.py` now also requires `email != ""` (still a join-free `user_id__in` subquery). After the claim it re-reads the address and mails that one. When the address is gone, it rolls the claim back. Tests: `test_a_member_who_clears_their_email_mid_run_is_not_claimed_or_mailed`, `test_a_member_who_changes_their_email_mid_run_is_mailed_at_the_new_one`.
- Finding 2 (fixed): the run lock's value is now a per-run token. The `finally` deletes the key only while it still holds that token, so a run that outlived `DIGEST_RUN_LOCK_SECONDS` leaves a later fire's lock alone. Tests: `test_a_run_that_outlives_its_lock_leaves_a_later_fires_lock_alone`, `test_a_run_releases_its_own_lock_by_token`. The MagicMock TTL test now stubs `cache.get` to return the token it added.
- Findings 3 and 4 (the same test, fixed): `test_the_claim_update_stays_on_one_table_with_the_marker_outside` normalises the SQL before checking it (drops quotes, folds case, collapses whitespace), so a quoting or casing change in Django's rendering no longer turns it red. It still fails on a JOIN or on a marker that moved into a subquery.
- Before landing, the three new behaviour tests failed against the pre-change command and passed after it. `backend/packages/wagtail_forum/wagtail_forum/tests/test_digest.py` 41 passed, and `apps/core/tests` 1670 passed.

### 2026-10-11 - Verified by the todo sweep (run 2026-10-12-0349)

- AC 1: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 5 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_digest.py --create-db -v -p no:cacheprovider && grep -n 'Finding' ../todos/archive/605-completed-p4-forum-digest-claim-email-1050.md` — evidence `.sweep-evidence/g5/605-ac0.txt` (not committed), last lines:

  ```text
  ======================= 41 passed, 3 warnings in 19.71s ========================
  17:## Findings
  39:- Finding 1 (fixed): the claim in `backend/packages/wagtail_forum/wagtail_forum/management/commands/send_forum_digest.py` now also requires `email != ""` (still a join-free `user_id__in` subquery). After the claim it re-reads the address and mails that one. When the address is gone, it rolls the claim back. Tests: `test_a_member_who_clears_their_email_mid_run_is_not_claimed_or_mailed`, `test_a_member_who_changes_their_email_mid_run_is_mailed_at_the_new_one`.
  40:- Finding 2 (fixed): the run lock's value is now a per-run token. The `finally` deletes the key only while it still holds that token, so a run that outlived `DIGEST_RUN_LOCK_SECONDS` leaves a later fire's lock alone. Tests: `test_a_run_that_outlives_its_lock_leaves_a_later_fires_lock_alone`, `test_a_run_releases_its_own_lock_by_token`. The MagicMock TTL test now stubs `cache.get` to return the token it added.
  41:- Findings 3 and 4 (the same test, fixed): `test_the_claim_update_stays_on_one_table_with_the_marker_outside` normalises the SQL before checking it (drops quotes, folds case, collapses whitespace), so a quoting or casing change in Django's rendering no longer turns it red. It still fails on a JOIN or on a marker that moved into a subquery.
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-12-0349)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
