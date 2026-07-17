---
status: pending
priority: p3
issue_id: "272"
tags: [forum, notifications, flutter, firebase, celery]
dependencies: []
source_review: "todo 253 slice 6 code review (2026-07-16)"
---

# Forum push registration: deferred residue from the slice-6 review

## Problem

Todo 253 slice 6 (FCM registration + push notification block) went through a
15-agent review; every confirmed defect was repaired in-slice. Six items were
real but deliberately deferred — none blocks AC6, each needs its own decision
or a bigger seam than the slice justified. This todo keeps them visible.

## Findings (deferred, with dispositions)

1. **iOS `aps-environment` is `development` in ALL build configs** —
   `ios/Runner/Runner.entitlements` is wired via `CODE_SIGN_ENTITLEMENTS`
   into Debug, Profile AND Release. A Distribution-signed archive carries a
   development APNs entitlement, which App Store Connect validation rejects.
   Fine until real APNs provisioning exists (the slice shipped iOS groundwork
   explicitly unverified); MUST be switched to `production` (or split
   per-config entitlements) before the first TestFlight/App Store archive.
2. **`profile_update` 10/h throttle is shared** by FCM registration (login),
   the logout clear, and human profile edits. Normal usage is ≪10/h (dedupe
   keeps it to ~1 PATCH per login), but a bio-editing spree can starve the
   logout clear (swallowed 429 → stale token until the next device claims it
   via the serializer's device-uniqueness rule) and vice versa. Revisit only
   if 429s show up in logs: options are a dedicated throttle scope for the
   token write or a modest rate bump.
3. **In-flight rotation PATCH vs logout clear — residual ms-race.** The epoch
   guard kills every guarded step, but a PATCH already on the wire when
   sign-out starts cannot be recalled and may land after the blank clear.
   Documented in `push_registration_service.dart`'s class docstring; bounded
   by the serializer's cross-profile token release + next login/logout cycle.
   No further client-side fix is worth the complexity.
4. **Firebase init arbitration still has two homes** —
   `apps/users/firebase_auth_views._ensure_firebase_initialized` (registry
   reuse → delegate to garden → projectId-only) and
   `apps/garden/firebase_config.initialize_firebase` (path gate → registry
   reuse → Certificate). The slice canonicalized the credential SETTING
   (`FIREBASE_CREDENTIALS_PATH` absorbs `GOOGLE_APPLICATION_CREDENTIALS` in
   settings.py) and single-homed certificate init via delegation, which
   killed the divergent-identity scenarios; a full shared bootstrap module
   (absorbing the projectId-only tier too) is the remaining, low-value step.
5. **Forum notification copy lives in 3 homes**: email
   (`apps/core/services/notification_service.py` subjects/bodies), web bell
   (`web/src/components/layout/NotificationBell.tsx` label arms), push tray
   (`apps/forum_host/tasks._notification_content`). Same event already ships
   three phrasings; any copy change or future i18n pass must find all three.
   Consolidating the two backend homes into one copy table is the natural
   first step — touches `apps/core` email code, so it needs its own slice.
6. **AuthService has no unit-test harness** (pre-existing): the three push
   wiring call sites (post-exchange `syncAfterLogin`, `signOut`'s
   `clearOnLogout`, the listener's `detach`) are pinned only via
   `PushRegistrationService`'s own tests plus the on-device E2E. A
   lightweight AuthService notifier harness would let the wiring (and the
   `_signingOut` session-expiry suppression) be pinned directly.

## Recommended Action

Nothing is urgent. Item 1 becomes MANDATORY at the first iOS distribution
archive — do it together with real APNs provisioning. Items 2/3 are
monitor-only. Items 4/5/6 are candidates for a small hardening slice if the
area is touched again (todo 260's mobile forum client is the likely trigger).

## Notes

Spun out of todo 253 slice 6 (2026-07-16). Related: todo 260 (mobile forum
client — will reuse the E2E scaffolding and could add the AuthService
harness), todo 268 (fan-out batching), todo 267 (EmailService systemic).
