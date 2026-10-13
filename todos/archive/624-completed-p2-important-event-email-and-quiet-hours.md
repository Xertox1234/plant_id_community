---
status: completed
priority: p2
issue_id: "624"
tags: [backend, web, mobile, notifications, preferences, product]
dependencies: []
triage: ready
triaged: 2026-10-12
owner_decision: "Owner: approve optional mention/quote/accepted-answer email, OFF by default (no silent opt-in), and a mentioned subscriber gets ONE merged email (2026-10-12). Owner: quiet hours are opt-in, default window 22:00-07:00 in the client-reported IANA timezone (UTC if unknown); held pushes/emails release at window end; security mail exempt (2026-10-12). Owner: coalesce same-topic replies within a 10-minute window into one email/push, and skip the external send if the user already read the post in-app (2026-10-12). Executes after 620 merges"
---

# Add important-event email and quiet hours for forum notifications

## Problem

Split from todo 620 at triage (run 2026-10-12-1616, owner decision 2026-10-12): 620 ships the policy matrix and web/mobile parity; this todo owns the optional important-event email channel and quiet-hour/frequency behavior that 620's AC4 and AC5 required.

## Findings

- `backend/packages/wagtail_forum/wagtail_forum/preferences.py:33-38` offers email only for replies; mention, quote and accepted-answer events are push-only, so members without push get no immediate signal.
- `backend/apps/forum_host/notifications.py:212-225,264-301` excludes mentioned/quoted members from reply-email recipients.
- No quiet-hour, timezone or coalescing logic exists in the forum dispatch/task paths; each reply sends immediately.

## Recommended Action

1. Build on 620's recorded policy matrix. Get owner defaults for quiet hours (window, timezone source), coalescing window and read-before-send suppression before implementing them.
2. Add optional mention/quote/accepted-answer email, deduplicated with reply email so a mentioned subscriber gets one appropriate message.
3. Implement quiet hours/coalescing with security mail exempt and the in-app inbox unaffected.

## Acceptance Criteria

- [x] Mention/quote/accepted-answer email and mentioned-subscriber behavior are explicitly decided; approved channels are implemented and tested for missing push registration, deduplication and unsubscribe. Any declined channel has a dated reason, not an untracked deferral.
- [x] Approved quiet-hour/frequency behavior is implemented and tested across timezones/DST, rapid replies, read-before-send, preference changes while waiting, and security-mail exemptions. Any declined option has a dated owner decision.
- [x] Web and mobile settings expose the new choices consistently with 620's matrix; relevant backend preference/unsubscribe tests, web settings tests and type-check, and mobile preference tests/analyze pass.

## Work Log

### 2026-10-12 - Split from 620 at triage

- Criteria 620 AC4 and AC5 re-pointed here by owner decision; wording carried over unchanged.

### 2026-10-12 - Implemented by the todo sweep (run 2026-10-12-1746)

- Important-event email: mention, quote and accepted-answer email cells, off by default (package `NOTIFICATION_DEFAULTS`); `send_forum_email_batch` sends them with one merged email for a mentioned or quoted subscriber (their event email if on, else the reply email they follow the topic for). New `forum_mention` / `forum_quote` / `forum_solution` unsubscribe lists each turn off only their own cell; shared `forum_event` template.
- Quiet hours: opt-in `ForumProfile.quiet_hours_*` and `time_zone` (migration 0040), window math in `wagtail_forum/quiet_hours.py` (wall-clock in the reported IANA zone, DST-aware, UTC fallback). Held deliveries sit in the outbox (`delivery.mark_held`, mobile push joins it as `Kind.FORUM_PUSH`, core migration 0008) and reconciliation releases them; a profile change reschedules them. Security mail never passes through `apps/forum_host/pacing.py`.
- Coalescing (implementation reading of the owner decision): first reply goes out at once; replies within 10 minutes of the last message about that topic are held and folded into one "N new replies" message per channel. Read-before-send is a new `already_read` recheck reason.
- Web Settings and mobile Profile show the new email cells, the merged-email note and quiet hours with the zone in effect; `docs/notifications-policy.md` records it all. Mobile reports a zone only when the platform gives an IANA name.

### 2026-10-12 - Verified by the todo sweep (run 2026-10-12-1746)

- AC 1: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest apps/forum_host/tests/test_important_event_email.py apps/users/tests/test_email_unsubscribe.py apps/users/tests/test_email_presentation.py packages/wagtail_forum/wagtail_forum/tests/api/test_notification_preferences.py apps/forum_host/tests/test_signals.py -v --create-db -p no:cacheprovider` — evidence `.sweep-evidence/g1/624-ac0.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================= 145 passed, 3 warnings in 24.69s =======================
  ```

- AC 2: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_quiet_hours.py apps/forum_host/tests/test_quiet_hours_and_coalescing.py apps/forum_host/tests/test_send_time_eligibility.py apps/forum_host/tests/test_delivery_outbox.py apps/core/tests -v --create-db -p no:cacheprovider` — evidence `.sweep-evidence/g1/624-ac1.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======= 1899 passed, 3 warnings, 71 subtests passed in 75.45s (0:01:15) ========
  ```

- AC 3: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_notification_preferences.py packages/wagtail_forum/wagtail_forum/tests/test_quiet_hours.py apps/users/tests/test_email_unsubscribe.py apps/users/tests/test_notification_policy.py apps/forum_host/tests/test_notification_preferences.py -q --create-db -p no:cacheprovider && cd ../web && npx vitest run src/pages/SettingsPage.test.tsx src/services/forumService.test.ts && npm run type-check && cd ../plant_community_mobile && flutter test test/features/profile test/services/user_profile_service_test.dart && flutter analyze` — evidence `.sweep-evidence/g1/624-ac2.txt` (not committed), last lines:

  ```text
  Got dependencies!
  141 packages have newer versions incompatible with dependency constraints.
  Try `flutter pub outdated` for more information.
  Analyzing plant_community_mobile...
  No issues found! (ran in 3.4s)
  ```

### 2026-10-12 - Completed by the todo sweep (run 2026-10-12-1746)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

## Notes

Depends in practice on 620's policy matrix landing first. Care reminders stay FCM-only (archived 410).
