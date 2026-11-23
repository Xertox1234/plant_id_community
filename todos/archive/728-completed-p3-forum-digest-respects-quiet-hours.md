---
status: completed
priority: p3
issue_id: "728"
tags: [forum, email, digest, quiet-hours, celery]
dependencies: []
triage: ready
triaged: 2026-11-22
---

# The weekly forum digest respects each member's quiet hours

## Problem

The weekly digest goes out at Monday 09:00 UTC, which is 02:00 or 03:00 in
America/Denver, and it ignores the member's quiet hours. Every other optional
forum email is held until the window ends (`apps/forum_host/pacing.py`). The
owner decided on 2026-11-21 that the digest should be held the same way.

## Findings

- `backend/packages/wagtail_forum/wagtail_forum/digest.py` never calls `quiet_release` or anything else from pacing. The beat entry is `forum-weekly-digest`, `crontab(hour=9, minute=0, day_of_week="monday")`, in UTC (`settings.py:1535-1538`). Source: audit 2026-11-21 L10 (celery-async-reviewer).
- The quiet-hours rule lives in `apps/forum_host/pacing.py` (lines 1-10): optional push and email inside the window are held, and security mail never goes through pacing.

## Recommended Action

1. In the digest command's per-member claim, skip a member whose quiet window covers the current run. Leave them due, so the claim stays intact, and record why they were skipped.
2. Re-run for skipped members after their windows end. Either schedule a follow-up run at the earliest release time (`apply_async(eta=...)`, the same continuation mechanism as the soft-limit path), or run the beat hourly on Mondays and send to whoever is due and outside their window. Pick whichever keeps the existing run lock and the at-most-once-per-period claim intact.
3. Document the rule in `pacing.py`'s module docstring.

## Technical Details

- The digest's claim, rollback and lock, and its soft-limit continuation: `apps/forum_host/tasks.py` (`send_forum_weekly_digest`) and `packages/wagtail_forum/wagtail_forum/management/commands/send_forum_digest.py`.
- The quiet-hours helpers are in `packages/wagtail_forum/wagtail_forum/quiet_hours.py`.

## Acceptance Criteria

- [x] A member whose quiet window covers the run gets no digest during the run, then gets exactly one after the window ends (a test using freeze_time).
- [x] A member with quiet hours off, or outside their window, is unaffected (a test).
- [x] A member is never sent two digests in one period, including across the follow-up run (a test).

## Work Log

### 2026-11-21 - Filed from the forum backend audit

- From `docs/audits/2026-11-21-forum-backend.md` L10.
- Owner decision 2026-11-21 (audit triage): "Respect quiet hours: hold a member's digest until their quiet window ends, like the other optional forum email."

### 2026-11-23 - Implemented by the todo sweep (run 2026-11-22-1957)

- `send_forum_digest` skips a due member whose quiet window covers the run (`quiet_hours.profile_release` on the loaded profile, against the current clock). Nothing is written for them, so they stay due and the claim UPDATE is unchanged. The summary line gains `held=N`, which the recovery logic does not read as a failure.
- Follow-up: two beat entries (`forum-weekly-digest-quiet-release-monday` and `-tuesday` in `backend/plant_community_backend/settings.py`) run the task hourly on the half hour from Monday 09:30 to Tuesday 09:30 UTC with `quiet_only=True`, which passes `--quiet-hours-only` (members with quiet hours on only). Chosen over an `eta` follow-up because a hold can last most of a day and Redis redelivers a message that old; `pacing.py` rejects long countdowns for the same reason.
- The run lock and the `last_digest_sent_at` claim are the same for both runs. A member sent late on Monday is due again the next Monday, because `is_due` allows a day of slack.
- The rule is documented in the `backend/apps/forum_host/pacing.py` module docstring.
- Known and accepted: a recovery run after a follow-up run is a full run, and a member with quiet hours on who opts in to the digest on Monday gets their first one within the hour.

### 2026-11-23 - Verified by the todo sweep (run 2026-11-22-1957)

- AC 1: `python3 scripts/todos/slot_env.py --main-root . 4 -- backend/venv/bin/python -m pytest --rootdir backend -c backend/pytest.ini backend/packages/wagtail_forum/wagtail_forum/tests/test_digest.py::test_a_member_inside_their_quiet_window_gets_the_digest_once_it_ends --create-db -v -p no:cacheprovider` — evidence `.sweep-evidence/g11/728-ac0.txt` (not committed), last lines:

  ```text

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================== 1 passed, 2 warnings in 20.73s ========================

  exit code: 0
  ```

- AC 2: `python3 scripts/todos/slot_env.py --main-root . 4 -- backend/venv/bin/python -m pytest --rootdir backend -c backend/pytest.ini backend/packages/wagtail_forum/wagtail_forum/tests/test_digest.py::test_members_with_quiet_hours_off_or_outside_their_window_are_unaffected --create-db -v -p no:cacheprovider` — evidence `.sweep-evidence/g11/728-ac1.txt` (not committed), last lines:

  ```text

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================== 1 passed, 2 warnings in 20.52s ========================

  exit code: 0
  ```

- AC 3: `python3 scripts/todos/slot_env.py --main-root . 4 -- backend/venv/bin/python -m pytest --rootdir backend -c backend/pytest.ini backend/packages/wagtail_forum/wagtail_forum/tests/test_digest.py::test_no_member_gets_two_digests_in_one_period_across_the_follow_up_runs --create-db -v -p no:cacheprovider` — evidence `.sweep-evidence/g11/728-ac2.txt` (not committed), last lines:

  ```text

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================== 1 passed, 2 warnings in 21.34s ========================

  exit code: 0
  ```

### 2026-11-23 - Completed by the todo sweep (run 2026-11-22-1957)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-11-23 - Repaired by the todo sweep (run 2026-11-22-1957)

- Round-1 review (medium, regression): the hourly quiet-hours runs share the digest run lock, and a recovery run (about 30 and 90 minutes after the main run) could fire while one was mid-send. The command then exits on "another run holds the lock" with no summary line, the task read that as nothing failed, and the retry chain ended.
- Fix in `backend/apps/forum_host/tasks.py`: a recovery run turned away by the lock re-enqueues itself with the same `recovery` count (`lock_wait` counts the waits: every 5 minutes, at most 8 times, which outlasts the 35-minute lock TTL; an ERROR log when the bound runs out). A scheduled run turned away is left alone, as before. The beat times are unchanged: a recovery run fires relative to when its run ended, so no fixed minute avoids it.
- Tests in `backend/apps/forum_host/tests/test_tasks.py` run the real command against a held lock: the recovery run tries again with its count, stops at the bound, and a scheduled or quiet-hours run does not re-enqueue.
- Not changed (outside the finding): a soft-limit continuation of the main run (recovery 0) that meets an hourly run's lock still exits, as any overlap did before; only recovery runs wait for the lock.

### 2026-11-23 - Review round 1: non-blocking findings

- **Fixed: the follow-up run mailed members the main run never held (medium, two reviewers).**
  `--quiet-hours-only` took every due member with quiet hours on, so one outside their window
  with nothing new at 09:00 got a "weekly" digest from the first hourly run after an item
  appeared. The task now passes `--held-at` (the main run's time, read from its beat entry) and
  the command considers only members whose quiet window covered it. New tests; removing the
  filter fails `test_the_follow_up_run_skips_a_member_the_main_run_did_not_hold`. Known gap,
  accepted: no hold is stored, so a member whose window opened in the minutes between 09:00 and
  the run reaching them is judged "not held" and waits for next week.
- **Declined: a member who turns quiet hours off while held gets no digest that week (low).**
  The same root as above (no stored hold). The next weekly run sends as usual.
- **Declined: a quiet-only run with failures schedules full-scope recovery runs (low).** A full
  run reads only members still due; every member without quiet hours was stamped at 09:00, so
  the extra runs send nothing new. Bounded at two per failing run.
- **Declined: a quiet window that leaves a gap under an hour holding no :30 mark is never
  released (low).** It needs a window of more than 23 hours. Not handled.

### 2026-11-23 - Review round 2: non-blocking findings

These changes were made after round 2, on the owner's decision of 2026-11-23 ("Fix it, then
merge"), and were not seen by a reviewer. `pytest packages/wagtail_forum apps/forum_host` plus the
two Firebase test files: 2905 passed.

- **Fixed: a member held by a late, continuation or recovery run was never mailed that week
  (medium, plus a low marked a regression).** Round 1's `--held-at` filter kept only members whose
  quiet window covered the main run's time, so a hold made later by another run was lost. Each
  hold now leaves a cache marker for 26 hours and the follow-up runs send to members with a
  marker; the window test at `--held-at` stays as the fallback for a lost marker. A dry run
  writes no marker. Two new tests; writing no marker, or writing one on a dry run, fails them.
  This replaces the "known gap" recorded under round 1.
- **Fixed: a follow-up run with a failed send scheduled full, unscoped recovery runs (low, two
  reviewers).** A follow-up run now schedules none; the next hourly run is its retry. The last
  run (Tuesday 09:30) has no retry, so a send that fails there waits for next week. Corrects
  the round-1 answer, which wrongly said every other member was already stamped. New test.
- **Declined: a soft-limit continuation of the main run that meets a follow-up run's lock is not
  retried (low).** Documented in the task's docstring; its remaining members wait a week.
- **Declined: the lock-held marker is a substring of the command's output (low, two
  reviewers).** Tests in `test_tasks.py` and `test_digest.py` pin the wording.
