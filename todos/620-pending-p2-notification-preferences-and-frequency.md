---
status: pending
priority: p2
issue_id: "620"
tags: [backend, web, mobile, notifications, preferences, product]
dependencies: []
---

# Make notification choices consistent and reduce avoidable noise

## Problem

Mobile's broad switches and web's event/channel matrix control different fields, so an enabled choice can still be suppressed and a broadly worded email opt-out does not stop every optional email. Users also lack quiet-hour/frequency controls, while important mentions or accepted answers have no immediate email channel.

## Findings

Source: Devin's read-only email/notification audit and backlog comparison, 2026-10-12; source inspection, not a production user study.

- `plant_community_mobile/lib/features/profile/profile_screen.dart:489-525` edits `User.email_notifications`, `plant_id_notifications` and `forum_notifications`. `web/src/pages/SettingsPage.tsx:91-230,234-507` edits `ForumProfile.digest_frequency` and `notification_preferences`; it does not expose the same broad flags.
- `backend/apps/core/services/email_service.py:287-322` consults broad flags, but `backend/packages/wagtail_forum/wagtail_forum/digest.py:117-124` selects by digest opt-in and account state without those flags. Newsletter consent is independently stored in BlogNewsletter. A single ambiguous "Email Notifications" label does not explain these differences.
- `backend/apps/users/email_unsubscribe.py:7-11` and archived todo 408 explicitly note that the web UI cannot re-enable the broad email flag. Archived 343 delivered the web matrix, not mobile parity.
- `backend/apps/forum_host/notifications.py:212-225,264-301` excludes mentioned/quoted members from reply-email recipients. `backend/packages/wagtail_forum/wagtail_forum/preferences.py:33-38` provides email only for replies, leaving important-event email unavailable even to members without push.
- The audited forum dispatch/task paths send per-reply external notifications without quiet hours or recipient/topic coalescing. Digests are a separate opt-in, not an automatic replacement for immediate email.
- `backend/apps/core/services/notification_service.py:326-354` has an identification-result helper, but the audit reference search found only its definition and a test call, not a production caller. Mobile's Plant ID Notifications switch should not imply a verified delivery feature without tracing the live path.

## Recommended Action

1. Agree and record a channel/event policy: required security mail versus optional activity email, independent newsletter consent, digest cadence and legacy master-switch precedence. Preserve existing opt-outs; do not silently subscribe users during migration.
2. Expose consistent effective settings in web and mobile, including digest/per-event choices and an explanation when a master flag or OS permission prevents delivery. Either retire legacy flags safely or expose their real effect in both clients.
3. Make reply/mention/quote/accepted-answer email an explicit product decision. Recommended: optional important-event email with deduplication so a mentioned subscriber receives one appropriate message, not duplicate messages or an accidental loss of the enabled reply channel.
4. Define quiet hours, timezone handling, frequency/coalescing and read-before-send suppression. Keep security mail exempt and the persistent in-app inbox available. Choose concrete defaults with the owner before rollout.
5. Trace Plant ID notification triggers; implement a justified live path or remove/relabel the inert switch with owner approval. Do not build a new channel merely because a legacy helper exists.

## Technical Details

Relevant models: `backend/apps/users/models.py:182-199`, ForumProfile, and BlogNewsletter. Frontends: SettingsPage, mobile profile/settings screens and `plant_community_mobile/lib/services/user_profile_service.dart`.

Read `web/docs/patterns/react-typescript.md`, `web/docs/patterns/testing.md`, and `plant_community_mobile/docs/patterns/riverpod.md`. Existing signed unsubscribe links must keep working. Todo 430 only removes the orphaned subscription model; it does not solve this preference hierarchy. Mobile device permission/registration diagnostics belong to todo 621.

## Acceptance Criteria

- [ ] A recorded policy matrix defines effective opt-in for every live email/push event, security-mail exceptions, newsletter independence and legacy flag precedence; owner decisions on new channels/frequency defaults are recorded before implementation.
- [ ] Web and mobile show and update the same effective forum email/push and digest choices. Tests cover mobile-off/web-on and web-off/mobile-on sequences, failed saves, and persisted state after reload.
- [ ] Tests prove broad opt-outs, digest/newsletter choices and signed unsubscribe actions follow the documented policy; any migration preserves prior opt-outs and requires no manual user repair.
- [ ] Mention/quote/accepted-answer email and mentioned-subscriber behavior are explicitly decided; approved channels are implemented and tested for missing push registration, deduplication and unsubscribe. Any declined channel has a dated reason, not an untracked deferral.
- [ ] Approved quiet-hour/frequency behavior is implemented and tested across timezones/DST, rapid replies, read-before-send, preference changes while waiting, and security-mail exemptions. Any declined option has a dated owner decision.
- [ ] Plant ID notification switch behavior is backed by a live trigger test or is removed/relabelled under a recorded decision; a test-only sender is not evidence of a shipped feature.
- [ ] Relevant backend preference/unsubscribe tests, web settings tests and type-check, and mobile preference tests/analyze pass.

## Work Log

### 2026-10-12 - Created from read-only audit

- Grouped cross-platform settings, optional important-event email and notification-fatigue improvements into one user-policy initiative.
- Archived 343/408 were checked: related mechanisms shipped, but no active todo covers this consistency work. No product defaults or application code changed during filing.

## Notes

P2 because the controls can misrepresent actual delivery. New notification channels and quiet hours are product choices, not claims of existing incidents. Care reminders stay FCM-only and retain the 24-hour lookback unless the owner separately revisits archived 410's decisions. No inferred owner decision has been added to frontmatter.
