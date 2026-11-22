---
status: pending
priority: p3
issue_id: "728"
tags: [forum, email, digest, quiet-hours, celery]
dependencies: []
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

- [ ] A member whose quiet window covers the run gets no digest during the run, then gets exactly one after the window ends (a test using freeze_time).
- [ ] A member with quiet hours off, or outside their window, is unaffected (a test).
- [ ] A member is never sent two digests in one period, including across the follow-up run (a test).

## Work Log

### 2026-11-21 - Filed from the forum backend audit

- From `docs/audits/2026-11-21-forum-backend.md` L10.
- Owner decision 2026-11-21 (audit triage): "Respect quiet hours: hold a member's digest until their quiet window ends, like the other optional forum email."
