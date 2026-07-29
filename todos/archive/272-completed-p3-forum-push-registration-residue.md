---
status: completed
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

## Technical Details

- `plant_community_mobile/ios/Runner/Runner.entitlements` +
  `ios/Runner.xcodeproj/project.pbxproj` (three `CODE_SIGN_ENTITLEMENTS` sites,
  lines 495/678/701) — item 1.
- `backend/apps/forum_host/constants.py` (`DEFAULT_FORUM_RATELIMITS`
  `profile_update`) + `apps/forum_host/api.py` (`MeProfileView`,
  `@_throttled("profile_update", "PATCH")`) — item 2.
- `plant_community_mobile/lib/services/push_registration_service.dart` (class
  docstring) — item 3.
- `backend/apps/users/firebase_auth_views.py::_ensure_firebase_initialized` +
  `backend/apps/garden/firebase_config.py::initialize_firebase` +
  `backend/plant_community_backend/settings.py:820-823` — item 4.
- `backend/apps/core/services/notification_service.py` (`send_forum_*`),
  `backend/apps/forum_host/tasks.py::_notification_content`,
  `web/src/components/layout/NotificationBell.tsx::notificationLabel` — item 5.
- `plant_community_mobile/lib/services/auth_service.dart` +
  `test/services/` (no `auth_service_test.dart`) — item 6.

## Acceptance Criteria

This section was **written during closure** (2026-07-29) — todo 272 shipped
without one. Each criterion restates a disposition already named in this todo's
own Recommended Action; none was chosen to fit the outcome. See the Work Log's
verification note on why decision-type criteria carry no command output.

- [x] #1 (iOS `aps-environment`): promoted to its own todo AND given a durable
      marker somewhere a person cutting an archive will actually read
- [x] #2 (shared `profile_update` throttle): accepted as monitor-only, with the
      three sharing writers and the revisit trigger recorded at the throttle
      definition
- [x] #3 (in-flight PATCH vs logout clear): confirmed already durably
      documented; no further action
- [x] #4 (Firebase init two homes): decision recorded (consolidate / accept),
      with the doc's load-bearing claims re-verified rather than trusted
- [x] #5 (notification copy in 3 homes): consolidation promoted to its own todo,
      and each home cross-references the other two in the meantime
- [x] #6 (AuthService harness): promoted to its own todo, with the specific
      unpinned call sites enumerated

## Work Log

### 2026-07-29 - Started by completing-todos skill (run 2026-07-29-0438)

- Picked up by automated workflow.

### 2026-07-29 - All 6 items dispositioned (promote-all closure)

**Verification note (honest framing):** every criterion here is a
*decision-type* criterion — there is no command whose output proves "a
disposition was recorded". The evidence is the durable artifact, cited by file
below. The test/lint runs at the end prove the edits are **safe**, not that the
decisions are **right**. This todo also shipped with no Acceptance Criteria
section at all; the one above was written during this closure, derived from
this todo's own Recommended Action rather than from what was convenient to
close.

**Why promote-all rather than re-defer.** This todo's Recommended Action
conditioned items 4/5/6 on "if the area is touched again (todo 260's mobile
forum client is the likely trigger)". That trigger **has fired** — todo 260
shipped and merged (PR #498), with todo 279 already open as its follow-up. So
"re-defer, untriggered" was not available. Combined with `CLAUDE.md` → Review
Doc Tracking ("re-deferring keeps it open forever, so promote-all is the only
terminal state" for a parking todo, per the todo 263 precedent), the closure is:
promote the real work, record a durable decision for the accept-as-is items.

**#1 iOS `aps-environment` — PROMOTED → todo 286, plus two durable markers.**

- Re-verified before promoting: one entitlements file
  (`find ios -name "*.entitlements"` → exactly one), and **three**
  `CODE_SIGN_ENTITLEMENTS = Runner/Runner.entitlements;` sites in
  `project.pbxproj` (lines 495, 678, 701) — Debug, Profile AND Release, exactly
  as this todo claimed.
- Deliberately **not** "fixed" by flipping the string to `production`: that one
  file is wired into Debug too, so flipping it breaks the development push loop
  and buys nothing while no archive is being cut. Todo 286 recommends
  per-config entitlements instead, done together with real APNs provisioning.
- Primary marker: a checklist line in `docs/DEPLOYMENT_SECURITY_CHECKLIST.md` →
  `### Mobile (Flutter)`, placed immediately **before** the existing
  `flutter build ios --release` step — chosen over a code comment alone because
  that is a document someone actually reads at archive time.
- Secondary marker: an XML comment in `Runner.entitlements` itself. Validated
  that it did not break the file: `plutil -lint` → `OK`, and
  `plutil -extract aps-environment raw` → `development` (still parses). Noted
  in todo 286 that Xcode may strip this comment if the file is edited via the
  UI — which is why the checklist is the primary marker, not this.

**#2 shared `profile_update` throttle — ACCEPTED, monitor-only.** Recorded at
the throttle definition itself (`apps/forum_host/constants.py`,
`DEFAULT_FORUM_RATELIMITS`), naming the three writers that share the one 10/h
budget (FCM registration on login, the logout clear, human profile edits), the
starvation mechanism in both directions, and an explicit revisit trigger
(`profile_update` 429s in logs). Placed there rather than in this todo because
the todo is being archived and the next person to touch that rate needs the
context at the line they are editing.

**#3 in-flight PATCH vs logout clear — ALREADY DOCUMENTED, verified.** Read
`push_registration_service.dart`'s class docstring rather than assuming: it
carries a "Known residual race (accepted, ms-scale)" paragraph stating the race,
why it cannot be recalled, and both bounds (the serializer's cross-profile
token release, and self-correction on the next login/logout cycle). Nothing to
add; no edit made.

**#4 Firebase init two homes — ACCEPTED as-is.** Recorded in
`apps/users/firebase_auth_views.py::_ensure_firebase_initialized`'s docstring.
Both load-bearing claims re-verified against source rather than trusted:

- `settings.py:820-823` really does absorb `GOOGLE_APPLICATION_CREDENTIALS`
  into `FIREBASE_CREDENTIALS_PATH` (with a deliberate `or None` so an empty
  string falls through to the env var).
- Tier 2 really does delegate — `_ensure_firebase_initialized` imports and calls
  `apps.garden.firebase_config.initialize_firebase` rather than building its own
  `credentials.Certificate`, so there is exactly one certificate-init site.
- Therefore the *dangerous* part of the split (two paths → different
  credentials → divergent project identity) is already closed. What remains
  split is only tier 3, the projectId-only fallback, which exists solely for the
  auth-emulator/ADC dev loop and which the garden side has no use for. A shared
  bootstrap module would move code without removing a failure mode. Revisit
  trigger recorded: a third caller, or tier 3 growing a non-dev-loop use.

**#5 notification copy in 3 homes — PROMOTED → todo 287, plus a stopgap.**

- Re-verified all three homes and their *current strings*. Confirmed divergence
  on a single `reply_added` event: `New reply in: {title}` (email),
  `New reply in "{title}"` + `{actor} replied` (push tray),
  `{actor} replied to "{title}"` (web bell).
- Two facts this todo did not record, found by re-grepping. First, the homes
  differ in **event coverage**, not just wording — the tray deliberately renders
  only `reply_added` and `mention` and returns `None` for everything else, so a
  naive consolidation would flatten the tray-silence whitelist and start popping
  "your post was published" at users.
- Second, and materially: **three of the four `send_forum_*` methods are dead
  code.** `send_forum_reply_notification` is the only live email path (called
  from `apps/forum_host/tasks.py:364`); `send_forum_mention_notification`,
  `send_new_topic_notification` and `send_forum_digest_email` have **zero call
  sites repo-wide** (verified by grepping for callers rather than definitions,
  and confirming no `getattr`-style dynamic dispatch). This shrinks todo 287's
  real scope a lot — the email side is one method, not four — and it means the
  emoji-bearing copy and the whole "mention email" arm are not shipped behavior.
  Caught *late*, while reading `docs/LEARNINGS.md` to write the codification:
  its 2026-07-29 / todo 270 entry documents this exact method as dead code, and
  a first draft of this closure had already cited the siblings as a live copy
  home in both todo 287 and the code comment. Both corrected; the code comment
  now states the deadness explicitly so the next reader does not re-cite them.
- Stopgap shipped now: a mutual cross-reference comment in all three homes, each
  naming the other two and pointing at todo 287. That directly addresses the
  stated failure mode ("any copy change must find all three") without waiting
  for the refactor.

**#6 AuthService harness — PROMOTED → todo 288, plus a pointer comment.**

- Verified the gap is real: `test/services/` has five service tests and **no**
  `auth_service_test.dart`. Verified a seam already exists
  (`@visibleForTesting FirebaseAuth get firebaseAuth`), and that
  `push_registration_service_test.dart` already proves that harness shape
  in-repo — so todo 288 is a bounded task, not a testability refactor.
- Given its own todo rather than appended to todo 279, deliberately: 279 is a
  forum-*feature* tracking list whose single AC is "prioritize the above into
  concrete slices", so test infrastructure filed there would be invisible.
- **Correction to this todo's own item 6 text.** It named "the `_signingOut`
  session-expiry suppression". There is no `_signingOut` identifier anywhere in
  `lib/` (grep, 2026-07-29). The suppression is not a notifier-side boolean at
  all: `signOut()`'s own FCM-clear PATCH is exempted **request-side** via
  `ApiService.skipSessionExpiryKey`, and `_handleSessionExpired`'s docstring
  records why a flag was rejected — it "couldn't cover a 401 arriving after the
  clear's timeout abandoned the request" (which is the standing Flutter rule
  against suppressing an interceptor side effect with a boolean around an
  awaited call). Todo 288's criterion pins the request-side exemption instead.
  Caught because the class-head comment was being written from this todo's
  wording; it would have shipped a criterion for a symbol that does not exist.

**Line-number hygiene:** todo 288's call-site line numbers were first written
from a grep taken *before* the class-head comment was added to
`auth_service.dart`, which shifted every one of them. Re-grepped and corrected
after the edit (detach `:131`, clearOnLogout `:255`, syncAfterLogin `:354`,
epoch capture `:279`, `_isCurrentExchange` `:404` with five call sites, seam
`:92`). This happened **four times** across the session in total — the last one
after this todo was already archived and the codification written: a follow-up
commit added one net line to a `tasks.py` docstring above the
`send_forum_reply_notification` caller, invalidating the `:363` cited in three
files (including the LEARNINGS entry about this exact failure). Corrected to
`:364`; the LEARNINGS entry now carries that instance as its worked example.

**Source-review tracking — deliberately skipped, not silently no-opped.** This
todo's `source_review` frontmatter is `"todo 253 slice 6 code review
(2026-07-16)"`, which is a *description, not a file path* — there is no review
document to open and no `## Finding Status` section to check off. The
completing-todos archival step that would edit one is therefore inapplicable
here, recorded explicitly rather than left to look like it ran.

**Evidence (safety of the edits, not correctness of the decisions):**

- `python manage.py check` → `System check identified no issues (0 silenced).`
- `python manage.py makemigrations --check --dry-run` → `No changes detected`
  (confirms the constants.py / firebase_auth_views.py edits are comment-only).
- `python -m pytest apps/forum_host apps/core apps/users packages/wagtail_forum
  --create-db` → `765 passed, 2 warnings in 56.25s` (single serial invocation,
  `--create-db` per the page-creating-suite rule).
- `flake8` on all four edited Python files → exit 0.
- `flutter analyze` → `No issues found!`; `flutter test` → `All tests passed!`
  (220 passed, 3 skipped).
- `flutter pub run build_runner build` → `git diff --stat -- '*.g.dart'` empty,
  so the `@riverpod` source edit left the generated hash unchanged and CI's
  "generated code is committed" gate is satisfied.
- `npx tsc --noEmit` → clean; `npx eslint NotificationBell.tsx` → exit 0.
- `plutil -lint Runner.entitlements` → `OK`.
- `markdownlint` on every changed/added Markdown file → clean after fixing one
  table-separator style error in todo 287.

**Review:** `code-review-orchestrator`, run with documentation-accuracy as the
explicit primary dimension (correct for a diff where no executable line
changed). 42 factual claims checked against primary source, 40 accurate, **0
critical / 0 high**. Two info-level line-number findings, both verified
independently before acting rather than taken at face value — both real, and
both repaired:

- todo 287's table cited the email subject at `notification_service.py:307`.
  Stale for the same reason todo 288's numbers were: the docstring **this diff
  added** to `send_forum_reply_notification` shifted the subject to `:318`, and
  `:307` now lands inside that new docstring. Corrected to `:318` (function
  defined `:287`). Second instance of the same self-inflicted shift in one
  session — see the codification note below.
- todo 288 cited `:405` as where the epoch guard re-checks. Literally true (the
  comparison is on that line) but not useful: the comparison lives in the
  `_isCurrentExchange` helper (`:404`), which the exchange path calls at **five**
  points (`:299`, `:322`, `:337`, `:360`, `:383`) — one after each await.
  Rewritten to name the helper and all five call sites, since a harness pinning
  only one of them would miss the point of the guard.

No findings were accepted-unaddressed. The reviewer independently confirmed the
substantive claims: the three throttle writers, the tier-2 delegation and the
`settings.py:822` absorb, all three notification copy strings, the three
`CODE_SIGN_ENTITLEMENTS` configs, the absent `auth_service_test.dart`, and the
`_signingOut`-does-not-exist correction.

**Codified** → `docs/LEARNINGS.md`, new section "Self-invalidating citations:
your own edit moves the line you just cited (todo 272, docs)". Two lessons, both
earned the hard way in this diff:

1. A line number cited for a file the *same diff* edits must be re-derived after
   the final edit to that file. This produced three stale citations here, and no
   gate catches it — flake8, `flutter analyze`, `tsc` and 765 tests all pass,
   because no executable line changed. The `notification_service.py` case broke
   twice: the review-driven repair from `:307`→`:318` was itself invalidated
   (→`:326`) by the very next docstring edit. Rule recorded: code edits first,
   citations last, re-grep before commit, and prefer symbol-anchored pointers.
2. The todo-270 dead-code trap fired again, on the same method it documents.
   Recorded that reading `docs/LEARNINGS.md` only at codification time is too
   late — read it for the area *before* writing, and when a doc enumerates
   "where X lives", grep for **callers**, not definitions, and state liveness.

**Re-verified after the post-review edits** (the dead-code correction touched
`notification_service.py` again, after the first test run):

- `flake8` on all four edited Python files → exit 0.
- `python -m pytest apps/forum_host apps/core apps/users packages/wagtail_forum
  --create-db` → `765 passed`.
- `python manage.py check` → no issues; `makemigrations --check --dry-run` →
  `No changes detected`.
- `markdownlint` on all changed Markdown → clean.

### 2026-07-29 - Completed by completing-todos skill (run 2026-07-29-0438)

- Verification: all 6 acceptance criteria satisfied. Every one is a
  decision-type criterion, so the evidence is the durable artifact cited per
  item above, not command output — no command can prove a disposition was
  recorded. Supporting safety evidence (re-run after the post-review edits):
  `manage.py check` clean, `makemigrations --check` "No changes detected",
  `765 passed`, `flake8` exit 0, `flutter analyze` clean, `flutter test`
  220 passed, codegen diff empty, `tsc`/`eslint` clean, `plutil -lint` OK,
  `markdownlint` clean.
- Review: `code-review-orchestrator`, 42 claims checked, 0 critical / 0 high,
  2 info-level line-number findings — both independently verified as real and
  both repaired; 0 accepted-unaddressed.
- Closure shape: promote-all (the re-defer trigger in this todo's own
  Recommended Action had already fired via todo 260 / PR #498). Items 1, 5, 6
  promoted to todos 286, 287, 288; items 2 and 4 accepted with durable
  decisions recorded at the code they govern; item 3 confirmed already
  documented.
- Two corrections to this todo's own text, both caught by re-verifying rather
  than trusting it: `_signingOut` does not exist (item 6), and three of the four
  `send_forum_*` methods are dead code, shrinking item 5's real scope (item 5).
- Codified → `docs/LEARNINGS.md` (self-invalidating citations; the todo-270
  dead-code trap re-firing).
- `source_review` frontmatter is a description, not a file path — no review doc
  exists to check off, so that archival step is deliberately skipped, not
  silently no-opped.

## Notes

Spun out of todo 253 slice 6 (2026-07-16). Related: todo 260 (mobile forum
client — will reuse the E2E scaffolding and could add the AuthService
harness), todo 268 (fan-out batching), todo 267 (EmailService systemic).
