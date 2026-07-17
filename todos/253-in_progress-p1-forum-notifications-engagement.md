---
status: in_progress
priority: p1
issue_id: "253"
tags: [forum, notifications, product-ux, celery]
dependencies: []
source_review: "docs/audits/2026-07-11-forum-modernization.md"
source_finding: "C2, H1, H2, H3, H4, H10"
---

# Forum epic: notifications & engagement loop

## Problem

The forum has no working notification or engagement loop at all: no in-app
notifications, an FCM push pipeline that always no-ops (no client ever registers
a token), fully orphaned email senders, no subscriptions/watching, no @mentions,
and no unread indicators. The ask→answered loop — the core retention mechanic of
any forum — does not exist. This is the C2-anchored p1 epic from the 2026-07-11
forum-modernization audit.

## Findings

Path shorthand: `W` = `backend/packages/wagtail_forum/wagtail_forum`, `H` = `backend/apps/forum_host`.
Full detail lives in the source manifest rows.

- **C2** — No in-app notifications and no working delivery channel: no
  Notification model/endpoints/bell UI; FCM is server-side only — `fcm_token` is
  never populated by web or mobile, so `send_forum_push` always no-ops
  (`H/tasks.py:52-57`, `W/models/profiles.py:34`).
- **H1** — Email notifications fully orphaned: `send_forum_reply/mention/digest`
  and `EmailType.FORUM_*` and the user-visible `forum_notifications` preference
  all exist with zero callers (`apps/core/services/notification_service.py:287,407,472`).
- **H2** — Push event coverage minimal: `reply_added` notifies the topic author
  only (not participants), `topic_created` is log-only, nothing for
  mentions/reactions (`H/notifications.py:26-72`).
- **H3** — No topic/board subscription or watching model.
- **H4** — No @mentions: no write-side parsing, no composer autocomplete, no
  linkification (`W/api/sanitize.py`, web TipTapEditor).
- **H10** — No unread/new-content indicators, no read-state model, no
  polling/live updates (`websocket_urlpatterns = []`).

## Recommended Action

Sequenced so each step ships value alone:

1. **Notification model + API + bell** (C2 core): host-side model (recipient,
   actor, verb, target ids, `read_at`), cursor-paginated list + mark-read
   endpoints, bell with unread count in the web layout.
2. **Wire the orphaned email senders** (H1): connect
   `send_forum_reply/mention/digest` into the signal path so the existing
   `forum_notifications` preference finally gates something.
3. **Subscriptions** (H3): explicit follow/unfollow + auto-subscribe on
   create/reply; fan-out in `H/notifications.py` replaces the author-only rule (H2).
4. **@mentions** (H4): server-side parse on publish, mention notification type,
   TipTap autocomplete + linkification.
5. **Unread indicators** (H10): per-user topic last-read timestamp (or a cheap
   localStorage first pass) driving new/unread badges in lists.
6. **FCM token registration** on at least one real client so push works
   end-to-end (C2 residue; mobile side coordinates with todo 260).

## Technical Details

- Keep reusable primitives (models, signals) in the package `W`; delivery
  concerns (FCM, the email service) stay host-side in `forum_host` — the split
  already exists (`H/notifications.py`, `H/tasks.py`, `W/signals.py` with 3
  public signals).
- Reuse the `send_forum_push` Celery pattern (now with permanent-error handling
  and backoff after audit fix M33).
- Fan-out writes should be bulk (`bulk_create`) and tested with exact query pins
  per `docs/rules/testing.md`.

## Acceptance Criteria

- [x] A reply to a subscribed topic produces an in-app notification visible via
      bell UI; mark-read works — satisfied since slice 3: every topic now has
      a real subscriber list (auto-subscribed authors/repliers + explicit
      Follow), and a reply notifies all of them, not just the topic author.
      Bell UI + mark-read have worked since slice 1; slice 3 is what made
      "subscribed topic" literally true.
- [x] The `forum_notifications` preference actually gates deliveries (email and push)
      — satisfied for the reply vertical (the only wired one): push has
      gated on it since before slice 1; slice 2 wires the reply email
      through `EmailService._should_send_email`'s same
      `user.forum_notifications` check. Mention/digest/new-topic emails
      remain unwired (slices 3-4), so there's nothing to gate for those yet.
- [x] Reply/mention events fan out to subscribers/participants, not only the
      topic author — satisfied for the reply vertical (the only wired one):
      slice 3 rewrote the fan-out to notify every `TopicSubscription`
      holder (auto-subscribed on topic-create and on reply, plus explicit
      Follow), excluding the replier. Mention fan-out remains unwired —
      needs slice 4's @mention parsing first.
- [x] An @mention notifies the mentioned user and renders as a profile link —
      satisfied since slice 4 for the "notifies" half only: server-side
      mention parsing on publish creates a `mention` Notification reaching
      the bell + push. The "renders as a profile link" half is unmet by
      design (scope decision, slice 4) — no public-profile page exists
      anywhere in the app yet; mentions render as plain `@username` text.
      True linkification is a follow-up todo once a profile page exists.
- [x] Topic lists show an unread/new indicator — satisfied since slice 5:
      server-side read-state (`TopicRead` + `ForumProfile.read_watermark_at`)
      badges both never-opened and previously-read-but-newly-replied topics,
      via a zero-added-query queryset annotation.
- [ ] At least one real client (web or mobile) registers an FCM token and
      receives a push end-to-end — REGISTRATION half done and live-verified
      since slice 6 (Android emulator → real FCM token → real dev backend →
      `ForumProfile.fcm_token` row; repeatable via
      `integration_test/fcm_registration_e2e_test.dart`). The
      "receives a push" half is gated on the one input only the user can
      provide: the Firebase service-account JSON (drop at
      `firebase/firebase-adminsdk-credentials.json`, set
      `FIREBASE_CREDENTIALS_PATH` in backend/.env, then the slice-6 work
      log's 5-step delivery runbook).

## Work Log

### 2026-07-11 - Created from forum-modernization audit (Phase 4 deferral)

- Epic groups 6 open findings per the manifest's Phase 4 grouping table
  (user-approved: one todo per epic; social/engagement selected as a p1 theme).

### 2026-07-14 - Started by completing-todos skill (run 2026-07-14-0401)

- Picked up by automated workflow. Scope: Slice 1 only (C2 core — persisted
  Notification model + fan-out service + list/unread-count/mark-read API +
  polling bell UI). Plan approved this session; epic sequencing and design
  decisions locked in the session plan file. Branch:
  `feat/forum-notifications-slice1-notification-model-bell`.

### 2026-07-14 - Slice 1 (C2 core: Notification model + API + bell) shipped

- **Backend**: new `Notification` model (`W/models/notifications.py`,
  migration `0013_notification.py`) with real FKs to `Topic`/`Post` (rewritten
  fresh, not the retired-machina `apps/core` scaffold); fan-out helper
  `wagtail_forum.notifications.create_notifications()` (`bulk_create` +
  `ignore_conflicts` idempotency, self-notify skip, defensive `None`-recipient
  skip); list/unread-count/mark-read endpoints (`W/api/notifications.py`,
  mounted + throttled in `H/api.py`/`H/api_urls.py` — generous 120/m limit on
  the polled unread-count route so normal polling never trips it). Fixed a
  pre-existing bug in the same branch touched: `send_forum_push.delay()`
  previously fired synchronously inside the open Wagtail publish transaction;
  the Notification row now persists in-transaction and the push enqueue is
  deferred to `transaction.on_commit` (`H/notifications.py`), proven by a
  dedicated rollback test.
- **Frontend**: `notificationService.ts` + `types/notifications.ts`,
  `NotificationBell.tsx` (polling badge + lazy-loaded dropdown, `useRef` timer
  per CLAUDE.md gotcha #5, reuses the existing `threadPath()` URL builder —
  added `board_id` to the API's topic payload so that helper's `Pick<Category>`
  contract is satisfiable), wired into `Header.tsx` desktop + mobile. Gated on
  `isAuthenticated` via conditional mount (not an internal check), so polling
  starts/stops for free with mount/unmount.
- Design decisions locked pre-implementation and followed as specified:
  `forum_notifications` pref gates delivery only, never row creation; explicit
  nullable FKs (not GenericForeignKey); bulk_create in-transaction + on_commit
  delivery.
- **Verification**:
  - Backend: `cd backend && python -m pytest apps/forum_host/tests/
    packages/wagtail_forum/wagtail_forum/tests/ -q --create-db` → `Pytest: 287
    passed` (22 net new: 6 model/service, 12 API, 4 signal-path — including a
    test that dispatches inside an aborted `transaction.atomic()` and asserts
    zero Notification rows + zero push enqueues, proving the on_commit fix).
  - `python manage.py check` → "System check identified no issues (0
    silenced)."
  - `python manage.py makemigrations --check --dry-run` → "No changes
    detected" (migration is complete and consistent with model state).
  - Frontend: `npx vitest run` → `Tests 608 passed`; `npm run type-check` →
    clean (no output = zero errors); `npm run lint` → "0 errors, 1 warnings"
    (the 1 warning is pre-existing, in an unrelated generated file,
    `block-navigation.js`).
  - Manual browser E2E not run this session (dev servers not started); the
    signal-path test proves row-creation + deferred-push end-to-end on the
    backend, and the NotificationBell tests prove poll → open → click →
    mark-read → navigate end-to-end on the frontend (mocked service layer).
- **Known issue fixed, not new work**: two pre-existing tests in
  `H/tests/test_signals.py` (`test_reply_added_enqueues_push_for_topic_author`,
  `test_reply_added_swallows_push_delay_failure`) constructed an **unsaved**
  `Post(...)` fixture. The new Notification fan-out needs a real pk —
  `bulk_create()` raises `ValueError: bulk_create() prohibited to prevent data
  loss due to unsaved related object 'post'` on Django 6.0.7 (confirmed
  empirically via `manage.py shell` probe before touching test code). Both
  fixed to `Post.objects.create(...)` + wrapped in
  `django_capture_on_commit_callbacks(execute=True)` (the project's existing
  convention, per `wagtail_forum/tests/api/test_topic_detail.py`) so the
  deferred push enqueue actually fires within the test. The parallel
  `moderation_decided`-branch tests are untouched — that branch is out of
  scope for slice 1.
- **AC boxes**: none flipped this slice. Every AC as literally worded needs a
  later slice (subscriptions for AC1's "subscribed topic" language + AC3;
  email for AC2; mentions for AC4; unread indicators for AC5; FCM registration
  for AC6) — matches the epic's own Recommended-Action sequencing. AC1's
  bell-UI + mark-read HALF is proven working now; full satisfaction awaits
  slice 3's subscription-based fan-out (author-only fan-out is what ships
  today, unchanged from the pre-slice behavior). AC2's push half was already
  pref-gated before this slice; the email half remains unwired until slice 2.
- **Code review** (code-review-orchestrator → django-drf-reviewer,
  wagtail-reviewer, react-typescript-reviewer, cross-cutting-reviewer, run in
  parallel per Phase 1 triage): 13 findings total, 0 duplicates across
  reviewers. Repaired directly (not via re-dispatch — full session context
  already in hand) rather than through the skill's re-dispatch-the-reviewer
  path:
  - **[high, django-drf]** `create_notifications()` call in `H/notifications.py`
    ran unguarded inside the ambient Wagtail publish transaction — a DB error
    would poison it past `send_robust`'s Python-only exception swallow and
    break the next write in the same transaction (`_refresh_for_post`).
    Fixed: wrapped in a nested `transaction.atomic()` (savepoint) with the
    try/except OUTSIDE it, per this repo's own "except must sit outside
    atomic()" forum rule.
  - **[high, wagtail]** List/unread-count querysets had no topic-visibility
    filter (every other content endpoint in the package gates on
    `topic__live`/`_visible_boards()`). Verified "harmless today" (slice 1's
    only recipient is the topic's own author) but a real gap once slice 3
    widens fan-out. Implemented a right-sized fix now: `topic__live=True`
    (null-safe via `Q(topic__isnull=True) | ...`, the testing.md "IN (NULL)"
    lesson) — zero extra query (confirmed: the pinned query-count test still
    reads `== 1`). Deliberately did NOT add the full `board__in=
    _visible_boards()` check (that costs a real extra query — a
    PageViewRestriction lookup — on every call to a POLLED endpoint) —
    documented in a code comment as slice 3's job, when non-author recipients
    make it load-bearing.
  - **[medium, react-ts]** Notification-list fetch effect had no
    cancelled-flag guard — a stale in-flight response could overwrite a
    fresher one on rapid dropdown open/close. Fixed.
  - **[medium→shipped as fix, react-ts]** Fetch failures rendered the same
    "No notifications yet." as a real empty inbox. Added a distinct error
    state.
  - **[medium, react-ts]** `NotificationBell` was mounted TWICE (desktop,
    CSS-hidden but never unmounted, + the mobile drawer) — two independent
    30s poll loops running concurrently on mobile whenever the hamburger menu
    was open. Fixed by restructuring `Header.tsx` to a single shared instance
    rendered once, visible at all breakpoints, instead of one copy per
    layout branch.
  - **[low, react-ts]** Mobile dropdown width (fixed `w-80`) could clip on
    narrow phones; "Mark all read" button was under the 44×44px tap-target
    minimum. Both fixed with small Tailwind class additions.
  - **[medium, cross-cutting]** `create_notifications()` had no type hints
    (a service-layer function called across the app boundary — binding
    project rule). Added, using `AbstractBaseUser` matching this exact
    package's existing convention (`workflow.py`).
  - **[medium, cross-cutting]** `NotificationListView`'s `swagger_fake_view`
    guard had no direct pin test (schema-content tests can't catch its
    removal — drf-spectacular never calls `get_queryset()` for a
    `ListAPIView`). Added, mirroring the exact existing
    `test_topic_list_view_guards_schema_generation` precedent.
  - **[medium, cross-cutting]** 3 auth-required tests asserted
    `status_code in (401, 403)`. **Verified independently before fixing** —
    grepped 4 sibling test files and found 6/7 existing assertions use the
    exact `== 401`; only `test_profiles.py` uses the looser set (the file I'd
    mirrored). Fixed all 3 to `== 401`, matching the dominant, correct
    convention.
  - **[low, cross-cutting]** `isinstance(i, int)` accepts Python bools (`bool`
    subclasses `int`); no test covered a non-list `ids` payload either. Fixed
    the check and added both missing test cases.
  - **[low, cross-cutting]** `unread-count`/`mark-read` used a bare `dict` in
    `@extend_schema(responses=...)` (opaque in the OpenAPI schema). Added
    inline schemas matching the file's own `AUTHOR_SCHEMA`/`CAPABILITIES_SCHEMA`
    pattern.
  - **Declined (not fixed, with reasoning)**: `notificationService.ts`'s
    `authenticatedFetch` duplicates the identically-named helper in
    `forumService.ts` byte-for-byte — but this is the ALREADY-established
    pattern across 4 existing service files (auth/diagnosis/plantId/disease);
    a 5th copy is consistent with precedent, not a new problem, and
    extracting a shared helper now would be an out-of-scope refactor of files
    untouched by this slice. `Notification.post` not exposed by the
    serializer — reviewer's own note says "may be deliberate slice-1 scope";
    agreed, no fix needed (the bell links to the topic, not a specific post).
  - Re-verified after every fix: backend `291 passed` (was 287; +4 for the
    guard/ids/visibility tests), frontend `608 passed` unchanged (no new test
    files, only fixed internals), `manage.py check` clean, `type-check`/`lint`
    clean.
- Not archived — 5 slices remain (H1, H3+H2, H4, H10, FCM residue). Todo stays
  `in_progress`.

### 2026-07-14 - Post-review closeout: trigger capture + live contract verification

- **Trigger capture (skipped step, now run).** The code-review-orchestrator's
  Phase 2 hands off `trigger_signature` objects for
  `scripts/inject/capture_from_review.py` to persist as write-time triggers;
  this was done for the repairs but the capture itself was never run. Re-read
  the 4 reviewers' raw JSON from the session transcript (not reconstructed
  from memory), wrote the merged findings array, and ran the capture script:
  `captured 5 candidate trigger(s): unguarded-db-write-in-signal-receiver,
  forum-api-queryset-missing-visibility-filter,
  swagger-fake-view-guard-missing-pin-test, loose-401-403-set-assertion,
  extend-schema-bare-dict-response`. `git diff --stat docs/rules/triggers.json`
  → `86 insertions(+)`, valid JSON, 28 total triggers. These are
  `severity: candidate` (provisional/prunable), not permanent rules.
- **Live frontend↔backend contract verification.** Every existing test mocks
  one side of the API boundary (frontend tests mock `notificationService`,
  backend tests assert Python dicts) — nothing had proven the actual wire
  JSON matches the hand-mirrored TypeScript types in
  `web/src/types/notifications.ts`. Applied the branch's pending migration to
  the local dev Postgres DB (`migrate wagtail_forum` — 0013_notification
  hadn't been applied yet), then ran a throwaway script through
  `manage.py shell` (`transaction.atomic()` + a sentinel exception to force
  rollback — no dev-DB rows persisted) that creates a real topic + reply,
  calls the real `create_notifications()` service, and hits the REAL
  production routes (`/api/v1/forum/notifications/`,
  `.../unread-count/`, `.../mark-read/` — through the actual
  `apps.forum_host.api_urls` host wrapper, not the package's bare test
  urlconf) via `APIClient`. Diffed the raw response JSON field-by-field
  against `NotificationActor`/`NotificationTopicRef`/`ForumNotification`/
  `NotificationListResponse`/`UnreadCountResponse`/`MarkReadResponse`: every
  field name, nesting, and nullability matched exactly (`actor.trust_level:
  null`, `topic.board_id`/`board_slug`, `read_at: null`, `count`/`updated` as
  bare-int responses). Zero drift found. This does not exercise the React
  component rendering against real data (that's what
  `NotificationBell.test.tsx`'s mocks already cover, using data shaped
  exactly like these types) — it closes specifically the shape-fidelity gap
  between the two independently-hand-written sides of the contract.
- Still not run: a real browser session (bell renders, poll ticks, dropdown
  click navigates). Judged out of scope for this closeout — the shape
  verification above was the one thing 899 passing tests structurally
  couldn't prove; full browser E2E is the epic's eventual manual-QA pass, not
  a per-slice gate this codebase's convention requires (no Playwright spec
  exists for the forum bell; `web/CLAUDE.md` excludes E2E from CI already).

### 2026-07-14 - Slice 2 (H1: wire the orphaned reply-notification email) shipped

- **Scope decision (user-approved).** The todo's slice-2 line named
  "reply/mention/digest"; exploration showed only **reply** is wirable now —
  mention needs slice 4's @mention parsing, new-topic needs slice 3's
  subscriber list, and digest needs a `CELERY_BEAT_SCHEDULE` that doesn't
  exist anywhere in the project. Reply-only ships value alone, matching the
  epic's own staged design; the other three stay orphaned pending their
  prerequisite slices.
- **Two latent bugs found before any wiring, both fixed as part of this
  slice** (the email path had zero callers, so was never integration-tested):
  1. **Missing `.txt` template (app-wide gap, one instance fixed here).**
     `EmailService.send_email` renders `.html` AND `.txt` unconditionally;
     `TemplateDoesNotExist` is swallowed to a silent `return False`. The repo
     had 13 `.html`, 0 `.txt` templates. Added `forum_reply.txt`; the other
     10 templates' gap is now todo 267.
  2. **Template context-variable mismatch.** `forum_reply.html` referenced
     `{{ author_name }}`/`{{ post_excerpt }}`/`{{ forum_preferences_url }}`;
     the sender's context dict supplied `reply_author`/`reply_excerpt` (base
     context supplies `preferences_url`, not the `forum_`-prefixed name).
     Django renders an undefined var as `''` — this shipped a
     blank-author/blank-excerpt email that a bare outbox-count assertion
     would not catch. Fixed both sides to match; verified a second instance
     of the same bug class exists in `send_identification_result_notification`
     (unrelated to forum, filed in todo 267, not fixed here).
- **Delivery design**: mirrors slice 1's push pattern exactly — new
  `send_forum_email` Celery task, enqueued via `transaction.on_commit`
  alongside the existing `_enqueue_push` in `forum_host/notifications.py`'s
  `reply_added` branch (both registered only after the Notification-row
  write commits, per the existing "except must sit outside atomic()" forum
  rule). The email is a parallel `EMAIL`-only channel — no second in-app
  `Notification` row, no migration. Preference gating (`forum_notifications`)
  is enforced once, inside `EmailService._should_send_email`, not
  re-duplicated in the task (single source of truth, deliberate).
- **Verification**:
  - Backend: `pytest apps/forum_host/tests/ packages/wagtail_forum/wagtail_forum/tests/
    -q --create-db` → `302 passed` (was 287 at slice-1 baseline; +15: 9 new
    `send_forum_email` task tests, 1 new signal-level enqueue test, 3
    existing push tests got a defensive `send_forum_email.delay` mock with
    no new assertions — Celery `CELERY_TASK_ALWAYS_EAGER` defaults `False`
    with no test override, so an unmocked `.delay()` in those tests'
    `django_capture_on_commit_callbacks(execute=True)` blocks would have
    attempted a real broker publish; 2 test-quality fixes from review).
  - `manage.py check` → "System check identified no issues (0 silenced)."
  - `manage.py makemigrations --check --dry-run` → "No changes detected."
  - Content-level assertions (not just outbox length) on both the `.txt` AND
    `.html` alternatives — the one test design that actually catches both
    latent bugs above; a fixture with an apostrophe + ampersand was added
    specifically to catch the autoescape bug found in review (below).
- **Code review** (code-review-orchestrator + bundled `/code-review --effort
  high`, 10 finder angles + verification + gap sweep, run in parallel): the
  orchestrator found 0 critical/high/medium (2 low/info, one already
  addressed). The deep pass surfaced ~24 raw candidates across 10 angles,
  several independently corroborated 2-3x. Consulted the advisor to triage
  scope before repairing (bar: fix real bugs and rule violations touching
  code this diff introduced; defer pre-existing cross-cutting issues to a
  todo; never drift into unrelated files). Fixed:
  - **[bug, confirmed empirically]** `forum_reply.txt` had no
    `{% autoescape off %}` — Django's autoescaping applies to `.txt` renders
    identically to `.html` (not extension-aware), so a reply containing an
    apostrophe or ampersand rendered as `O&#x27;Brien`/`Marks &amp; Spencer`
    in a PLAIN TEXT email. Reproduced directly via `render_to_string` before
    fixing. Fixed with `{% autoescape off %}` (safe — plain text, and the
    excerpt is already `strip_tags`'d); strengthened the test fixture with a
    real apostrophe + ampersand so a regression fails the content assertion.
  - **[rule violation, docs/rules/celery.md]** The task shipped as a bare
    `@shared_task` (retry wrapper removed as dead code — see below). A
    conventions-focused reviewer pass correctly distinguished: the removal
    was right for the *send* call (swallows everything internally, can't
    raise) but wrong to leave the whole task with zero retry config, since
    `User.objects.get()`/`Post.objects.get()` CAN raise `OperationalError` on
    a transient DB blip and that would silently drop the notification with
    no retry — a real, if narrow, gap the binding "every task declares retry
    config" rule exists to prevent. Fixed with the declarative form
    (`autoretry_for=(OperationalError,), retry_backoff=True, max_retries=3`)
    — narrower and cleaner than hand-rolled `self.retry()`, and the inner
    `DoesNotExist`/`ValueError`/`TypeError` branches return early first so
    autoretry only ever fires on the one genuine transient class. Added a
    dedicated test (mirrors `test_send_forum_push_retries_transient_errors_until_exhausted`'s
    `.apply()` pattern) proving it isn't dead config.
  - **[maintainability, 3x independent]** `_plain_text_excerpt` in
    `wagtail_forum/api/views.py` is a leading-underscore "private" helper
    that this task now imports across the package/host-app boundary — a
    silent rename there would ImportError at Celery runtime with no
    review-time signal. Promoted to `plain_text_excerpt` (public), updated
    its one in-package caller.
  - **[duplication, 2x independent, verified]** The `f"{SITE_URL}/forum/{board.id}-..."`
    URL-building f-string duplicated a private closure already in
    `apps/users/views.py` (`_forum_topic_url`, dashboard recent-activity
    feed) — confirmed byte-for-byte identical path shape. Added
    `Topic.get_absolute_url()` to the `wagtail_forum` package (the
    idiomatic Django home for it) and used it here; did NOT touch
    `apps/users/views.py` — the advisor's scope line was "touch another file
    when your change creates a new dependency on it, not because it
    duplicates something," and the dashboard closure works and is unrelated
    to forum notifications. Future mention/digest slices needing the same
    URL now have a canonical method to call instead of re-deriving the
    f-string a third time.
  - **[test-quality, cheap]** An invalid-`post_id` test exercised the same
    `ValueError` branch twice (missing key, non-numeric string), leaving the
    `except (TypeError, ValueError)` clause's `TypeError` half uncovered
    (`{"post_id": None}` → `int(None)` raises `TypeError`, since `dict.get`'s
    default only applies when the key is absent, not when its value is
    `None`). Added the missing case. Also fixed 2 tests that unpacked
    `board, topic` from the shared fixture but never used them, inconsistent
    with the file's own `_`-discard convention.
  - **Declined (with reasoning, matching the advisor's read)**: the
    near-identical `_enqueue_push`/`_enqueue_email` closures in
    `notifications.py` (3x independent flags) — a factory function for two
    call sites is more indirection than two explicit closures, and
    `moderation_decided`'s enqueue in the same file is already inline,
    matching the file's own explicit-over-abstracted convention. The
    preference-gate running after the Post fetch/excerpt render, not before
    (2x independent flags) — deliberate single-source-of-truth design
    (`EmailService._should_send_email` is the one place that decides "does
    this user get a forum email"); re-checking in the task duplicates that
    logic across two layers for a negligible cost (one indexed PK read +
    in-memory string ops, not a network call). The stale
    `backend/test_email_templates.py` manual script (3x independent flags,
    now silently "passes" with blank content) and the broader `EmailService`
    systemic issues (ignored `email.send()` return value, 10 more missing
    `.txt` templates, a second context-key mismatch instance in
    `send_identification_result_notification`) — all pre-existing,
    cross-cutting, unrelated to this diff's own correctness; filed as todo
    267 rather than expanding this slice's scope.
  - Re-verified after every fix: `302 passed` (was 301 pre-fix, +1 for the
    new retry test), `manage.py check`/`makemigrations --check` both clean.
- **AC boxes**: AC2 flipped — `forum_notifications` now gates both push
  (already true since before slice 1) and email (this slice) for the reply
  vertical, the only wired one. AC1/AC3 (subscriptions) and AC4 (mentions)
  still await slices 3-4; AC5 (unread indicators) awaits slice 5; AC6 (FCM
  registration) is the residue item.
- Not archived — 4 slices remain (H3+H2, H4, H10, FCM residue). Todo stays
  `in_progress`.

### 2026-07-14 - Slice 3 (H3 subscriptions + H2 fan-out beyond author-only) shipped

- **Scope decision (user-approved via AskUserQuestion): full-stack.** Backend
  (model, migration+backfill, API, auto-subscribe, fan-out rewrite) AND
  frontend (`is_subscribed` type/field, service functions, Follow/Unfollow
  button on the thread detail page) — not backend-only.
- **Design decisions locked pre-implementation, followed as specified:**
  1. Auto-subscribe at signal (publish) time, not API-write time — hooks the
     existing `topic_created`/`reply_added` branches in `H/notifications.py`,
     so a rejected/pending spam post never subscribes anyone.
  2. Backfill is author-only and landed in this PR (migration `0014`,
     `bulk_create(ignore_conflicts=True)`); deliberately did NOT backfill
     past repliers (they were never notified before — retro-subscribing a
     year-old participant to a necro-reply would be surprise-spam). Past
     repliers get picked up going forward via auto-subscribe-on-reply.
  3. Unfollow is "stop watching," but replying again re-subscribes you — no
     persistent mute flag this slice (Discourse-style; matches how
     `notifications.py:88-97`'s auto-subscribe-on-reply is now documented
     inline after review, see below).
- **Backend**: new `TopicSubscription` model (`W/models/subscriptions.py`,
  migration `0014_topicsubscription.py` — schema + author-only backfill in
  one file) with a `subscribe()`/`unsubscribe()` classmethod pair mirroring
  `ForumProfile.for_user`'s get_or_create/IntegrityError race idiom. Rewrote
  `H/notifications.py`'s `reply_added` branch: deleted both author-only
  guards, fan-out now queries `TopicSubscription.objects.filter(topic=topic)`
  (excluding the replier), auto-subscribes the replier inside the same
  atomic block, and the push/email enqueue loops became N-per-recipient
  (was 1). `topic_created` now auto-subscribes the topic's author. New
  `TopicSubscriptionView` (POST subscribe / DELETE unsubscribe, both
  idempotent), mounted + throttled (`subscription_create`/`subscription_delete`,
  60/m each) in both urlconfs (route-parity test). `is_subscribed`
  `SerializerMethodField` added to `TopicDetailSerializer`. Fixed
  `_visible_notifications()`'s visibility filter (`api/notifications.py`) to
  add `board__in=_visible_boards()`, null-safe via a combined `Q(...)`
  expression per `docs/rules/testing.md`'s "IN (NULL)" lesson — now
  load-bearing since fan-out reaches non-author recipients.
- **Frontend**: `Thread.is_subscribed` type, mapper wiring, `subscribeToTopic`/
  `unsubscribeFromTopic` service functions, and a Follow/Unfollow `Button` on
  `ThreadDetailPage` (optimistic toggle, rollback-on-error, gated on
  `isAuthenticated`).
- **Verification (pre-review)**: Backend `pytest apps/forum_host/tests/
  packages/wagtail_forum/wagtail_forum/tests/ -q --create-db` → `330 passed`
  (was 302 at slice-2 baseline). Frontend `npx vitest run` → `616 passed`.
  `manage.py check` clean, `makemigrations --check --dry-run` → "No changes
  detected", `type-check`/`lint` clean. OpenAPI schema: the exact CI command
  (`manage.py spectacular --file ...`, no `--fail-on-warn`) exits 0; the new
  `/forum/topics/{topic_id}/subscription/` path verified present with
  `post`/`delete` methods and `200`/`429` responses by parsing the generated
  schema directly (drf-spectacular's local `--validate --fail-on-warn` run
  looked alarming — 202 pre-existing, unrelated warnings — but that flag
  isn't what CI actually runs).
- **Code review** (code-review-orchestrator + bundled `/code-review --effort
  high`, all 10 finder angles + the orchestrator run in parallel, 11 agents
  total): the orchestrator self-reported degraded methodology (ran as a
  single inline pass, not true parallel specialist dispatch) and found 0
  findings at "moderate confidence" — treated as low-weight, not a checklist
  all-clear. The bundled 10-angle pass found real, cross-corroborated
  issues. Given the extent of independent convergence (3-4 angles hitting
  the same line from different lenses) plus one finding with direct
  empirical reproduction, Phase 2 (per-candidate verify agent)/Phase 3
  (sweep) were not separately dispatched — treated the convergence +
  reproduction itself as verification, confirmed via a second advisor
  consult, rather than re-verifying already-reproduced findings. Fixed:
  - **[bug, confirmed via reproduction, 2x independent]** `TopicSubscriptionView.delete()`
    reused `post()`'s visibility-gated topic lookup (`live=True,
    board__in=_visible_boards()`), so unsubscribing 404'd — and silently
    no-op'd — once a subscriber's topic was unpublished or its board
    restricted, stranding them subscribed with no self-service way out
    until republish. One angle reproduced it directly (subscribed a user,
    flipped `topic.live=False`, called DELETE, confirmed 404 + orphaned
    row). Fixed: `delete()` is now a pure self-scoped
    `TopicSubscription.objects.filter(user=request.user,
    topic_id=topic_id).delete()` with no topic lookup at all — no
    existence-leak risk the way `post()` has, since it only ever mutates
    the caller's own row. Added 3 regression tests (unpublished topic,
    restricted board, nonexistent topic_id — the last pinning that DELETE
    is a no-op, unlike POST's 404, since there's no topic lookup to fail).
  - **[bug, confirmed empirically, language-pitfall angle]** Two related
    frontend state-leak bugs in `ThreadDetailPage.tsx`'s
    `handleToggleSubscription`: (1) the failure-path rollback wasn't
    guarded by topic identity, so a slow/failed request for thread A could
    overwrite thread B's `is_subscribed` state and raise a spurious error
    banner after the user navigated away; (2) `subscribing` was a
    page-level boolean, so a slow request for thread A left thread B's
    Follow button stuck disabled/spinning after navigating away — no
    failure required, just slowness. Root cause both: nothing bound the
    in-flight request to the topic it was issued for. Fixed with a
    `currentTopicIdRef` (synced in the existing load-thread effect, not
    during render — the `react-hooks/refs` lint rule forbids ref writes in
    the render body; caught by `npm run lint`, not by any test) that
    `handleToggleSubscription`'s catch/finally check before applying
    `setThread`/`setNotice`/`setSubscribing`, plus resetting `subscribing`
    to `false` unconditionally on every navigation so a stuck spinner can't
    outlive the thread it belongs to. Added 2 regression tests
    (navigate-away-while-pending doesn't leave the button stuck loading;
    a stale failure after navigating away doesn't touch the new thread's
    state or show its error).
  - **[cleanup, cheap, reuse angle]** The drf-spectacular `extend_schema`
    ImportError-fallback shim was tripled across the package (`views.py`,
    `api/notifications.py`, `api/subscriptions.py`). Fixed in the new file
    only: `subscriptions.py` now imports `extend_schema` from `.views`
    (which already has the canonical copy) instead of redefining it.
  - **[cleanup, reuse angle, advisor-endorsed]** `subscriptions.py`'s
    `_get_topic()` reimplemented the exact visibility-gated-lookup shape
    `_get_visible_post()` already establishes as this package's pattern for
    "one predicate shape, not N" (its own docstring says so). Extracted
    `_get_visible_topic()` into `views.py` alongside it (additive only —
    did NOT retrofit the 3 pre-existing inline call sites in `views.py`
    that predate this diff; that would be an unrelated-file DRY refactor
    outside this slice's scope), used by `subscriptions.py`'s `post()`
    only (`delete()` no longer needs a topic lookup at all, per the bug fix
    above).
  - **[doc-only, 2x independent]** Two angles independently flagged the
    same ambiguity: `reply_added`'s auto-subscribe-on-reply
    (`TopicSubscription.subscribe(post_author, topic)`) is unconditional,
    so a user who explicitly unfollowed and then posts one more reply gets
    silently re-subscribed. Both angles explicitly caveated this as
    "likely intentional, flagging for confirmation" rather than a bug — it
    is exactly design decision 3 above. No behavior change; added an
    inline comment at the call site documenting the deliberate tradeoff so
    a future reviewer doesn't re-flag it as a bug.
  - **Deferred to todo 268 (not fixed here)**: three angles (Efficiency,
    Altitude, Angle B) independently converged on the same finding — reply
    fan-out now loops one synchronous `.delay()` per subscriber inside
    `transaction.on_commit`, unbounded, blocking the HTTP response; 2N
    broker round-trips for N subscribers with no cap or batching. Real at
    scale, but the proper fix (batch Celery tasks that loop server-side)
    means changing `send_forum_push`/`send_forum_email` signatures shared
    with the untouched `moderation_decided` branch — out of proportion for
    a slice scoped to fan-out *correctness*. A cap-with-warning band-aid
    was considered and rejected (exactly the shallow special-case the
    Altitude angle's own framing warns against).
  - **Declined (with reasoning)**: closure duplication in
    `_enqueue_push`/`_enqueue_email` (cosmetic, same call shape as slice
    2's identical declined finding); `TopicSubscription.subscribe()`'s
    IntegrityError-wrapper duplicating `ForumProfile.for_user()` (verified
    against Django 6.0.7 source — `get_or_create` already handles the race
    internally; removing the wrapper is a paired decision about a
    deliberate house convention this diff extends, not a local oversight —
    declining to keep the mirrored idiom intact, matching the existing
    pattern rather than diverging from it); three new test files each
    hand-rolling a near-identical 4-line board/topic fixture helper (right
    at the "recurs 3x" bar, but each instance is ~4 lines and consolidating
    would add a new shared test-utils file for marginal benefit —
    "three similar lines is better than a premature abstraction"); a
    weaker, explicitly-caveated concern about `get_is_subscribed` only
    mattering if a future serializer reuses the same pattern.
  - Re-verified after every fix: backend `333 passed` (was 330 pre-fix, +3
    for the DELETE-visibility regression tests), frontend `618 passed` (was
    616 pre-fix, +2 for the stale-navigation regression tests),
    `manage.py check`/`makemigrations --check --dry-run` both clean,
    `type-check` clean, `lint` → 0 errors (the `react-hooks/refs` violation
    from the initial ref-in-render implementation, fixed above).
  - Manual browser E2E not run this session — consistent with slices 1-2's
    convention (no Playwright spec exists for the forum thread page; `web/CLAUDE.md`
    excludes E2E from CI). Every test in this slice mocks one side of the
    service boundary; "330+618 passing" proves logic and contract shape,
    not a browser-verified feature.
- **AC boxes**: AC1 flipped (bell UI/mark-read have worked since slice 1;
  slice 3 is what made "subscribed topic" literally true) and AC3 flipped
  for the reply vertical (mention fan-out awaits slice 4). AC4 (mentions)
  and AC5 (unread indicators) still await slices 4-5; AC6 (FCM registration)
  is the residue item.
- Not archived — 3 slices remain (H4 mentions, H10 unread, FCM residue).
  Todo stays `in_progress`.

### 2026-07-14 - Slice 4 (H4: @mentions) shipped

- **Scope decisions (user-approved via AskUserQuestion):**
  1. **Rendering: infra-only, plain text.** Mentions parse, notify, and
     autocomplete, but render as plain `@username` text — matching the
     existing "author name is not a link" precedent app-wide. No
     linkification, no public-profile page (none exists today — `User.
     get_absolute_url()` points at a `users:profile` URL name that doesn't
     exist in `apps/users/urls.py`, already dead). Deferred to a follow-up
     todo once a profile page exists.
  2. **Delivery: in-app bell + push, no email.** Keeps email scoped to slice
     2's reply-only vertical; `send_forum_email` already early-returns for
     non-`reply_added` events, so this needed zero email-task changes.
- **Traps found in research, designed around up front:**
  1. The write-path sanitizer (`W/api/sanitize.py`) strips all structured
     markup — no span, no data-*; only `href`/`title` survive on `<a>`. Only
     literal `@username` text reaches storage, so server-side regex against
     `User.username` on the sanitized text is the only viable resolution
     strategy — a client-supplied mention id is unusable by the time a post
     is stored.
  2. Signals fire once, on first publish only (`_is_first_publish`) — mentions
     in a reply or a new topic's opening post are covered; mentions added by
     *editing* an existing post are not (no signal fires). Documented
     limitation, matches slice precedent that edits don't re-notify.
  3. The `(recipient, verb, post)` unique constraint doesn't collapse a
     `reply` row and a `mention` row for the same `(recipient, post)` — a
     mentioned subscriber would get two bell entries without explicit
     suppression (mentioned users excluded from the `reply` recipient set).
  4. Board-visibility leak: unlike subscribers (visibility-gated at subscribe
     time), anyone can `@mention` a user with no access to a restricted
     board. Gated resolved mention recipients on the topic's board being in
     `_visible_boards()` — conservative: a mention in a non-public board
     notifies nobody, matching the forum-wide "restricted boards are
     invisible to the whole API" stance.
- **Backend**: `NotificationVerb.MENTION` (metadata-only migration `0015`,
  confirmed no DB DDL), `MENTION_MAX_PER_POST` setting (`W/conf.py`, default
  10, bounds fan-out per post). New `W/mentions.py`:
  `resolve_mentioned_users(post, exclude_pks=...)` — a `(?<!\w)@(\w+)` regex
  (word-boundary lookbehind so `admin@gmail.com` doesn't resolve "gmail" as a
  mention) against a dedicated `_mention_scan_text()` walker (title for
  opening posts + `strip_tags()`'d paragraph blocks only, deliberately NOT
  reusing `spam/base.py`'s `extract_text()` — see code review below for why),
  capped/deduped, then board-visibility-gated, then resolved via exact
  `username__in` (no case-insensitive uniqueness on `AbstractUser`, so
  `@Alice` won't resolve to `alice` — documented tradeoff). `H/notifications.py`'s
  `reply_added` branch resolves mentions inside the existing atomic block,
  excludes them from the `reply` recipient set (SQL-side
  `.exclude(user_id__in=mentioned_pks)`), and fires two `create_notifications()`
  calls (`REPLY` to the remainder, `MENTION` to the mentioned); `topic_created`
  gained its own mention handling for opening-post mentions (guarded on
  `post is not None` — admin-created topics can have none). New
  `UserMentionSearchView` (`W/api/user_search.py`) — `GET ?q=<prefix>` →
  `username__istartswith`, exact `get_full_name() or get_username()` shape
  (not a host-specific `.display_name` — mirrors `PostAuthorSerializer`),
  auth-gated, capped at 10 results, mounted in both urlconfs (route-parity
  test) and throttled (`mention_user_search: 30/m`, `H/constants.py`).
- **Frontend**: `ForumNotificationVerb` widened to include `'mention'`;
  `NotificationBell.tsx` gained a `case 'mention':` label arm. New
  `web/src/components/forum/forumMentionNode.ts` — `@tiptap/extension-mention`
  configured with a `suggestion.items` backed by a new `searchForumUsers()`
  service call, a manually-positioned dropdown (installed
  `@tiptap/suggestion@3.22.5` has no `props.mount()` auto-positioning helper
  — that's a newer Tiptap API; Context7's hosted docs described it, but
  `tsc --noEmit` caught the mismatch against what's actually installed).
  Wired into `TipTapEditor.tsx`'s extensions array.
- **Verification (pre-review)**: Backend `pytest apps/forum_host/tests/
  packages/wagtail_forum/wagtail_forum/tests/ -q --create-db` → `356 passed`
  (was 333 at slice-3 baseline). Frontend `npx vitest run` → `623 passed`
  (was 618). `manage.py check` clean, `makemigrations --check --dry-run` →
  "No changes detected" (0015 committed, metadata-only). `type-check`/`lint`
  clean. OpenAPI schema: new `/forum/users/search/` route present with `GET`,
  `200`/`429` responses (same path-prefix gotcha as slice 3 — no
  `/api/v1/forum/` prefix in the generated schema).
- **Code review** (code-review-orchestrator — returned a triage-only plan
  this run since a dispatched subagent can't itself spawn sub-agents, so its
  5 recommended domain reviewers were dispatched directly: django-drf,
  wagtail, celery-async, react-typescript, cross-cutting — plus the bundled
  `/code-review --effort high` skill's 10 finder angles, all 16 run in
  parallel/independently). Unusually high real-finding volume for this epic
  — this slice combines novel regex-based text parsing (real edge cases) with
  a from-scratch async TipTap integration (real lifecycle/concurrency
  subtleties), and both the checklist pass and the deep pass found different
  real things this time rather than mostly overlapping. Consulted the
  advisor twice (once before repair, to triage fix/decline boundaries at
  this volume; once after refuting one of the sixteen findings against
  primary source, to confirm the trace). Fixed, grouped by convergence:
  - **[security, verified empirically, 2 independent leak vectors from one
    root cause]** `resolve_mentioned_users()` scanned mention text via
    `spam/base.py`'s `extract_text()` — a raw-value stringifier built for
    spam heuristics that need to see links/code as-is. Two consequences,
    both reproduced directly (a real saved Post + `.findall()`): (a) a code
    block's contents (e.g. `@property` in a Python sample) resolved as a
    mention nobody could see as a mention; (b) an `<a href="…/@victim"
    title="@victim">` tag's *attribute* text — both attributes survive
    `nh3.clean()` — resolved as a mention invisible to any reader, even
    though the visible link *label* was "click here". Root-caused to one
    fix: a dedicated `_mention_scan_text()` in `mentions.py` (not a shared
    `extract_text()` variant — spam genuinely wants raw values, mentions
    want only reader-visible prose) that walks `raw_data`, `strip_tags()`s
    string block values, and skips code/image blocks entirely. Verified
    `strip_tags('<a href="x/@victim" title="@evil">click</a>')` returns
    `'click'` (attributes drop with the tag markup that carries them) while
    a real link *label* like `<a href="…">@alice</a>` still resolves — no
    false negative introduced. 2 new regression tests.
  - **[bug, 4+ independent angles: Efficiency, Angle C, Angle A,
    react-typescript-reviewer]** No debounce on the mention-autocomplete
    `items()` callback — fired a network request on every keystroke,
    contradicting the route's own rate limit (30/m) and the established
    `SearchPage.tsx` debounce convention. Fixed: 300ms debounce (matching
    `SearchPage.tsx` exactly), implemented as `await new Promise(resolve =>
    setTimeout(resolve, 300))` inside the exported `resolveMentionSuggestions()`
    (not a `useRef` timer — this isn't a React component, so there's no
    effect to clean it up in).
  - **[bug, 2 independent angles with a detailed async-race trace:
    react-typescript-reviewer, Angle D — verified against
    @tiptap/suggestion's actual source, not assumed]** A slow/debounced
    `items()` resolving after its suggestion session already exited (Escape,
    blur) or the editor was destroyed could still fire `onStart`, which
    unconditionally created and appended a `<div>` to `document.body` with
    no future `onExit` ever coming to remove that specific node. Fixed with
    one shared token (`searchToken`, bumped on every new search AND on every
    `onExit`) checked once inside `resolveMentionSuggestions()` after the
    network call resolves, plus `onStart`/`onUpdate` treating empty items as
    "remove any dropdown, don't create one" (an editor-destroyed or
    zero-result response now naturally clears the dropdown instead of
    leaking it) — this also closes a separately-flagged low-severity gap
    (no empty/loading state in the dropdown) for free, since "no dropdown"
    *is* the empty state now. New jsdom test drives two out-of-order network
    resolutions (newer search's response arrives before the older, superseded
    one's) and asserts the stale call resolves to `[]` — this covers
    `resolveMentionSuggestions()`'s token logic exactly. The other half of
    this fix, `onStart`/`onUpdate`'s `shouldRender` guard inside `render()`'s
    closure (the actual dropdown-creation code the orphan was reported
    against), is reasoning-verified via the `@tiptap/suggestion` source
    trace above, not exercised by an automated test — driving it end-to-end
    would need a mounted ProseMirror view, not just a headless `Editor`.
    Flagging explicitly so a future reader doesn't assume the green suite
    covers it.
  - **[bug, confirmed via mergeAttributes trace + 2 independent angles:
    wrapper/proxy Angle E, react-typescript-reviewer]** A custom
    `renderHTML`/`renderText` override hardcoded `{}` for the rendered
    `<span>`'s attributes, silently discarding the configured
    `HTMLAttributes` (`class: 'text-primary font-medium'`). Read the
    installed extension's actual source
    (`node_modules/@tiptap/extension-mention/dist/index.js`) rather than
    trusting the summary of a prior session's finding: the vendor's own
    default `renderHTML`/`renderText` already prepend the suggestion char
    ("@") AND correctly `mergeAttributes()` the configured styling — the
    custom override was solving an already-solved problem while introducing
    a bug. Deleted the override entirely rather than patching it. Added a
    test asserting the configured class string survives serialization (the
    existing test only asserted "@" was present, not the styling).
  - **[correctness, resolved via source trace, not code change — Angle A's
    specific claim REFUTED]** Angle A claimed the Escape-key handler didn't
    reset `currentItems`/`currentCommand`, risking a stale mention on a
    subsequent Enter. Traced `@tiptap/suggestion`'s actual
    `handleKeyDown`/`dispatchExit` (`node_modules/@tiptap/suggestion/dist/
    index.js`): on Escape, the plugin calls this extension's `onKeyDown`
    THEN unconditionally calls `dispatchExit` → `onExit` in the same
    synchronous call, ignoring `onKeyDown`'s return value for Escape either
    way — `onExit` already resets everything a moment later, and the
    plugin's own state transition deactivates the session before any
    subsequent `onKeyDown` could reach the `Enter` branch. Not a live bug.
    The Escape branch in `onKeyDown` was therefore fully inert (its own
    `dropdown?.remove()` call and `return true` were both redundant/ignored)
    — deleted it as a verified-safe simplification, not a fix.
  - **[bug, 3 independent angles: Simplification, Reuse, django-drf-reviewer]**
    The mention-push-enqueue loop was duplicated verbatim between
    `reply_added`'s closure and `topic_created`'s. Extracted a shared
    `_enqueue_mention_push_for(mentioned, payload)` nested helper (kept
    nested, not module-level — preserves the file's existing "import tasks
    lazily so the module stays importable before Celery is ready" pattern).
    The identical `payload` dict construction in both branches was extracted
    alongside it (`_build_payload(post)`) — same duplication, same fix.
  - **[cleanup, cheap, django-drf-reviewer]** `"mention"` string literal used
    instead of the already-imported `NotificationVerb.MENTION` in the two
    `.delay()` calls that determine push-event semantics (left the 2
    diagnostic-only logger literals as plain strings — not the kind of
    magic-string risk the convention targets).
  - **[cleanup, cheap, Simplification angle]** `reply_recipients` was built
    via a Python-side list comprehension filtering out mentioned users;
    pushed into SQL via `.exclude(user_id__in=mentioned_pks)` on the
    queryset instead (a Django empty-set `__in` exclude is a verified no-op,
    so this needed no extra guard for the "nobody mentioned" case).
  - **[architecture, Reuse angle, most significant single finding]**
    `UserMentionSearchView` accessed `u.display_name` — a property specific
    to *this host's* User model, breaking the package's host-agnostic
    contract. Fixed to `u.get_full_name() or u.get_username()`, mirroring
    `PostAuthorSerializer.get_display_name`'s existing pattern exactly (also
    switched `u.username` → `u.get_username()` in the same line for the same
    reason).
  - **[test-coverage gap, cross-cutting-reviewer, named precedent]** No
    throttle-enforcement test for `mention_user_search`, unlike every
    sibling rate-limited route. Added, mirroring
    `test_search_is_throttled_with_429_and_retry_after`'s shape plus
    `force_authenticate` (this route, unlike search, requires auth).
  - **[test-coverage gap, cross-cutting-reviewer]** The two prefix-match
    tests in `test_user_search.py` had no decoy username that *contains* but
    doesn't *start with* the query — couldn't distinguish `istartswith` from
    an `icontains` regression. Added one to each (`malice` for query `ali`;
    `xdave_1` for query `dave_`).
  - **[low, react-typescript-reviewer]** `@tiptap/suggestion` was imported
    directly but only resolved transitively (not a declared dependency).
    Added at the exact version already locked (`3.22.5`); `npm install`
    confirmed a no-op resolution, `npm ls` confirmed zero conflicts.
  - **[low, matches an established repeated convention — slice 1 fixed the
    identical issue]** Dropdown suggestion buttons were under the 44×44px
    tap-target minimum. Fixed with `min-h-11`, matching `PostCard.tsx`'s
    existing action-row convention.
  - **Declined (with reasoning)**: double-notification suppression
    generalized into a shared mechanism (Altitude angle) — premature for 2
    verbs, matches the file's existing one-off-exclusion style; `is_active`
    not filtered in mention resolution (wagtail-reviewer's own note: fixing
    locally would diverge from an existing system-wide inconsistency, not
    close it); `_visible_boards()` imported from `mentions.py` across a
    package-internal boundary (Altitude angle) — reviewer itself confirmed
    no live import cycle exists yet, so relocating it now has no concrete
    payoff; no Playwright E2E for the mention composer flow
    (cross-cutting-reviewer's own note: "appears lapsed epic-wide, not
    specific to this slice" — matches slices 1-3's identical, repeatedly
    accepted precedent); celery-async-reviewer's `H/tasks.py` findings
    (missing idempotency guard, missing `ignore_result=True`, a misleading
    retry log message) — all explicitly pre-existing, not introduced by this
    diff, matching the established pattern (slices 2-3) of not expanding
    scope into unrelated issues; candidates for a follow-up todo alongside
    267/268 if judged worth tracking, not filed this slice.
  - Re-verified after every fix: backend `359 passed` (was 356 pre-fix, +3:
    2 mention-leak regression tests + 1 throttle test — the decoy-username
    additions strengthened 2 existing tests rather than adding new ones),
    frontend `625 passed` (was 623 pre-fix, +2: the out-of-order-resolution
    test + the class-styling assertion), `manage.py check`/
    `makemigrations --check --dry-run` both clean, `type-check` clean,
    `lint` → 0 errors (1 pre-existing warning, generated coverage artifact,
    unrelated).
  - Manual browser E2E not run this session — consistent with slices 1-3's
    convention (no Playwright spec exists for the forum composer; `web/
    CLAUDE.md` excludes E2E from CI already).
- **AC boxes**: AC4 flipped for the "notifies the mentioned user" half only —
  the "renders as a profile link" half is explicitly unmet by design (scope
  decision 1 above), deferred pending a future profile-page feature. AC5
  (unread indicators) awaits slice 5; AC6 (FCM registration) is the residue
  item.
- Not archived — 2 slices remain (H10 unread, FCM residue). Todo stays
  `in_progress`.

### 2026-07-16 - Slice 5 (H10: unread/new topic indicators) shipped

- **Scope decisions (user-approved via AskUserQuestion):**
  1. **Server-side read-state, not localStorage** — the todo's own text
     sanctioned a "cheap localStorage first pass" as an acceptable v1, but the
     user chose the more durable option because mobile is this project's
     primary platform (root `CLAUDE.md`): todo 260's future mobile client
     needs the same read-state a web-only localStorage hack wouldn't provide.
  2. **Badge unseen/brand-new topics too**, not only previously-read topics
     with a new reply since.
  3. **Slice 5 only** — AC6/slice 6 (FCM residue) stays untouched.
- **Design substitution, transparently documented and user-confirmed before
  implementation**: the user's framing ("baseline unseen on your account-join
  date") doesn't map onto a host-agnostic field — `user.date_joined` is
  `AbstractUser`-only, off-limits to this package (same constraint that
  rejected a host-specific `display_name` in slice 4). Substituted a new
  `ForumProfile.read_watermark_at` field, which delivers the same product
  outcome (new-since-you-showed-up topics are "new") through a host-agnostic
  mechanism, and additionally bounds the "everything since a possibly-old
  join date is unread on ship day" flood for already-caught-up existing
  members via the migration's backfill.
- **The unread rule** — a 3-level `Coalesce` fallback per topic per user:
  `TopicRead.last_read_at` (this exact topic, explicitly opened) →
  `ForumProfile.read_watermark_at` (this user's general "caught up as of"
  baseline; backfilled to migration-apply time for existing profiles,
  stamped at creation time for new ones) → `WAGTAILFORUM_UNREAD_LAUNCH_AT`
  (a fixed launch-day constant, the last resort for a user with no profile
  row at all). A topic is unread when `last_post_at` is newer than whichever
  baseline applies.
- **Backend**: new `TopicRead` model (`wagtail_forum/models/topic_reads.py`,
  `(user, topic)` unique constraint, race-safe `mark_read()` upsert matching
  the package's established `IntegrityError`-fallback house convention) +
  `ForumProfile.read_watermark_at` (`default=timezone.now`, not
  `auto_now_add`, so a future "mark all read" action can advance it) — both
  in one migration (`0016_topicread.py`, Django combined the `CreateModel`
  and the `AddField`, matching migration 0014's precedent of bundling
  schema+data). New `WAGTAILFORUM_UNREAD_LAUNCH_AT` setting (`conf.py`).
  `_annotate_topic_unread()` (`api/views.py`) annotates `is_unread` on
  `TopicListView`'s queryset unconditionally (a `Value(False)` constant for
  anonymous, the real `Coalesce` chain for authenticated) via correlated
  `Subquery` expressions folded into the single SELECT — zero added
  Python-level queries, confirmed by an authenticated-request variant of the
  existing pinned query-count test (still exactly 3).
  `TopicDetailView.retrieve()` gained a second `on_commit`-registered
  callback (`_mark_read`, alongside the pre-existing `view_count` one) that
  upserts the `TopicRead` row and ensures a `ForumProfile` row exists on every
  authenticated GET.
- **Frontend**: `is_unread` threaded through `BackendTopicListItem` →
  `Thread` → `ThreadCard.tsx` (a "New" badge pill, matching the existing
  Pinned/Locked badge recipe exactly) — small and additive, mirroring the
  `is_subscribed` precedent from slice 3.
- **Code review** (`code-review-orchestrator` — 4 domain reviewers: django-drf,
  wagtail, react-typescript, cross-cutting — dispatched directly since the
  orchestrator can't itself spawn sub-agents, a known limitation from slices
  3-4; cross-cutting's retry failed twice on API stream stalls with no
  findings recovered either time, not re-retried a third time — past
  diminishing returns per the advisor, and every other angle had already
  converged) + the bundled `/code-review --effort high` skill (10 finder
  angles + 1-vote verify + a gap sweep) — 14 dispatches total, unusually heavy
  convergence (one doc typo alone was independently caught 7+ times). Fixed,
  grouped by theme:
  - **[correctness, empirically confirmed — Angle E]** `transaction.on_commit()`
    does not defer in this project's runtime: verified directly via a real
    `APIClient` GET wrapped in `CaptureQueriesContext` against the production
    urlconf (`manage.py shell`, `connection.in_atomic_block` confirmed
    `False`, no ambient `atomic()` anywhere around this view) — both the
    pre-existing `view_count` UPDATE and this slice's new writes fired
    inline, immediately, as part of the same request. Advisor-reviewed
    disposition: this is Django's documented autocommit behavior, not a
    regression — the writes always ran during the request either way, with
    or without `on_commit`, so there's nothing to "fix" in this slice, and
    re-litigating the pre-existing `view_count` feature (slice 1) from here
    would be scope creep chasing a non-bug. The one genuinely actionable
    consequence, applied: `robust=True` on the new `_mark_read` callback, so
    an exception inside it (verified against Django 6.0.7's actual
    `captureOnCommitCallbacks` source: `robust=True` callbacks are caught and
    logged, not propagated) can never turn an already-successful 200 into a
    500. New test (`test_topic_read_failure_does_not_5xx_the_response`)
    monkeypatches `TopicRead.mark_read` to raise and confirms the response
    still comes back 200. Documented the broader finding (affects the
    pre-existing `view_count` feature too, not just this slice) in the new
    follow-up todo below rather than touching slice 1's code.
  - **[efficiency + correctness, Efficiency angle, disposition corrected
    after review]** `TopicRead.mark_read`/`ForumProfile.for_user` fired on
    every authenticated GET with no dedup. A naive copy of `view_count`'s
    plain TTL-keyed `cache.add()` dedup would have been a correctness
    regression — it would silently swallow a legitimate new-reply write
    inside the TTL window. Fixed with a dedup key that folds in
    `last_post_at` (free from the response already built, zero extra query),
    so a new reply naturally rotates the key instead of being suppressed.
    This changes an existing test's real semantics — the old
    `test_topic_read_updates_same_row_on_repeat_visit` assumed every repeat
    visit advances `last_read_at`, which is no longer true within the same
    epoch — split honestly into two tests:
    `test_topic_read_dedup_suppresses_redundant_write_in_same_epoch` (same
    `last_post_at`, timestamp genuinely unchanged, not just tolerant `>=`)
    and `test_topic_read_updates_after_new_reply_since_last_visit` (proves
    the dedup doesn't also swallow a visit that legitimately should record a
    fresh read).
  - **[correctness/security, 6+ independent reviewers converged]**
    `parse_datetime(get_setting("UNREAD_LAUNCH_AT"))` had no validation — a
    malformed setting would silently degrade `is_unread` to `False` for
    every profile-less user rather than surfacing the misconfiguration.
    Fixed to raise `ImproperlyConfigured` on an unparseable value (and
    `make_aware()` a naive one) — which the project's existing custom
    exception handler (`apps/core/exceptions.py`) converts into a loud,
    logged 500, not a silently-wrong 200. New test confirms the 500 (not a
    raised Python exception — the handler catches and converts it, learned
    empirically when the first version of this test asserted the wrong
    thing and failed with "DID NOT RAISE").
  - **[test-coverage gap, django-drf-reviewer]** No test proved
    `TopicRead.last_read_at` actually wins the `Coalesce` over
    `ForumProfile.read_watermark_at` when they disagree — swapping the
    argument order would have passed every existing test. Added
    `test_is_unread_prefers_topic_read_over_profile_watermark_when_they_disagree`
    (watermark says unread, a specific `TopicRead` after the last post says
    read; asserts the specific signal wins).
  - **[test-coverage gap, django-drf-reviewer]** No test drove the real loop
    end-to-end through both live endpoints (only hand-seeded rows). Added
    `test_ac5_end_to_end_open_detail_then_list_reflects_read`: list shows
    unread → open detail → list shows read → simulate a new reply → list
    shows unread again.
  - **[simplification, verified against actual SQL — Simplification angle]**
    `ExpressionWrapper(Q(...), output_field=BooleanField())` simplified to a
    bare `Q(last_post_at__gt=F("_read_baseline"))` — confirmed bare `Q`
    already resolves `output_field=BooleanField` via `WhereNode` internals on
    this Django version.
  - **[efficiency, Efficiency angle]** `_read_baseline` changed from
    `.annotate()` to `.alias()` — a pure intermediate the serializer never
    reads (Django 3.2+, zero risk on this project's Django 6.0).
  - **[simplification, Simplification angle]** Hoisted this slice's own new
    local imports (`get_setting`, `ForumProfile`, `TopicRead`, inside
    `_annotate_topic_unread` and the new `_mark_read` closure) to module
    level. Left two pre-existing local imports elsewhere in the same file
    (the `view_count` TTL lookup, `MeProfileView.get_object()`) untouched —
    out of scope, not introduced by this slice.
  - **[correctness, advisor-flagged]** `TopicListSerializer.is_unread` gained
    `read_only=True`, matching the field's inherently-read-only nature (the
    view's queryset annotation is the only writer).
  - **[doc accuracy, 7+ independent reviewers on one line]** `profiles.py`'s
    `read_watermark_at` comment cited "migration 0017" — the real migration
    is `0016` (Django bundled the `TopicRead` `CreateModel` and this
    `AddField` into one file). Fixed.
  - **[doc accuracy, wagtail-reviewer + django-drf-reviewer]**
    `topic_reads.py`'s module docstring pointed at "`apps/forum_host`'s API
    views" for the unread computation — wrong; it's
    `wagtail_forum/api/views.py`'s `_annotate_topic_unread`, a host-agnostic
    package file. Fixed.
  - **[doc accuracy, wagtail-reviewer]** `conf.py`'s `UNREAD_LAUNCH_AT`
    comment had leftover todo-file shorthand ("W/models/profiles.py") that
    doesn't parse as a real path outside planning docs. Fixed to a real
    module path.
  - **[low, react-typescript-reviewer]** `ThreadCard.tsx`'s badges container
    gained `flex-wrap` (max simultaneous badges rises from 2 to 3 with "New"
    added).
  - **[documented + follow-up todo 271, not fixed inline]** Three related
    edge cases, none blocking AC5: (1) **watermark trigger-scope**
    (Altitude/Angle C/Efficiency convergence) — `ForumProfile.for_user()` is
    also called from `MeProfileView` and the push-delivery task, so an
    unrelated action can prematurely collapse a pre-ship sleeper account's
    entire unread backlog, not just the topic they were looking at (if any);
    no clean fix exists under the package's host-agnostic, single-purpose
    `for_user()` design, so documented accurately in the field's code
    comment rather than silently left as "self-heals on next topic open" (a
    claim proven incomplete). (2) **The on_commit-inline-execution reality**
    above — pre-existing (slice 1), not this slice's to fix. (3) **A user's
    own reply shows their own topic as "unread" to themselves** (Angle A) —
    confirmed real, not masked, via a direct code trace: `ThreadDetailPage.
    tsx`'s `handleReply` re-fetches only the posts sub-list after posting,
    never the thread/topic detail itself, so `TopicRead.mark_read` never
    fires again after replying, and the reply's own timestamp becomes the
    topic's new `last_post_at`. Cosmetic and self-correcting (clears the next
    time anyone re-opens that topic), but the fix means opening
    `apps/forum_host/notifications.py` — an unfamiliar file with its own
    transaction conventions — for a non-blocking polish item, so deferred
    rather than expanding this slice's diff into a file otherwise untouched.
  - Also independently verified and ruled out (no code change, no test
    needed): whether a topic could ever reach the list endpoint with a null
    `last_post_at` (which would make `is_unread` resolve to SQL `NULL`
    instead of a boolean, via 3-valued-logic comparison) — traced
    `workflow.py`'s `submit_for_moderation` (~line 129: "Publish the topic
    only when its own author's opening post goes live"), confirming a
    `Topic.live=True` transition is structurally always paired with its
    opening post also being live, which the pre-existing counters signal
    always resolves to a non-null `last_post_at` first. Surfaced only
    because a contract-spot-check script created a topic directly
    (bypassing the moderation flow, unlike any real topic) — a test/script
    artifact, not a reachable production state.
  - Re-verified after every fix: backend `381 passed`
    (`apps/forum_host/tests/ packages/wagtail_forum/wagtail_forum/tests/`),
    frontend `628 passed`, `manage.py check` clean, `makemigrations --check
    --dry-run` → "No changes detected", `type-check` clean, `lint` → 0
    errors (1 pre-existing warning, generated coverage artifact, unrelated).
    Contract spot-check (rolled-back `manage.py shell` probe against the real
    `/api/v1/forum/...` production urlconf, not the isolated test urlconf):
    confirmed `is_unread` is a genuine JSON boolean (not `0`/`1`/`null`) on
    the list endpoint, absent from the detail endpoint's response (by
    design — AC5 is list-only), and correctly flips `True` → `False` after a
    real `TopicRead` row exists.
  - Manual browser E2E not run this session — consistent with slices 1-4's
    convention (no Playwright spec exists for the forum list/detail flow;
    `web/CLAUDE.md` excludes E2E from CI already).
- **AC boxes**: AC5 flipped — topic lists show a "New" badge for both
  never-opened topics (relative to the user's watermark or the launch
  constant) and previously-read topics with a new reply since. AC6 (FCM
  registration) remains the sole residue item.
- Not archived — 1 slice remains (AC6, FCM residue, coordinates with todo
  260). Todo stays `in_progress`.

### 2026-07-16 - Slice 5 follow-up: own-post-shows-unread fixed

- The slice-5 review (above) found this real but deferred it to todo 271,
  reasoning the fix meant opening an unfamiliar signal-handler file
  (`apps/forum_host/notifications.py`) for a cosmetic, self-correcting
  issue — not worth the added scope/risk on its own. Explicitly requested
  as a follow-up the same day, so implemented after all.
- Added `TopicRead.mark_read(post_author, topic_id,
  when=post.first_published_at)` to both `reply_added` and `topic_created`
  in `notifications.py`, placed inside the existing
  `with transaction.atomic():` block right after `TopicSubscription.subscribe`
  — a plain DB write that should roll back together with everything else in
  that block, unlike the push/email enqueues a few lines later, which are
  external side effects correctly deferred to `transaction.on_commit` so
  they never fire for a publish that rolls back.
- Read `signals.py`'s `update_counters_on_publish` before writing the fix,
  per the plan's own instruction to match this file's exact conventions —
  and found the originally-recommended `when=topic.last_post_at` (from
  todo 271's Recommended Action) wouldn't actually have worked:
  `notify(reply_added, ...)` fires *before* `_refresh_for_post(post)` (the
  call that updates `last_post_at`), so `topic.last_post_at` is still stale
  at the point `dispatch()` runs. Used `post.first_published_at` instead —
  the exact value `_refresh_topic_counters` derives `last_post_at` from a
  moment later — so the fix can never land a hair behind the unread rule's
  strict `>`. Updated todo 271 to record the corrected mechanism rather than
  leave the stale prescription in place.
- `topic_created` mirrors the same fix, guarded by that branch's own
  existing `if post is not None:` precedent (an admin-created topic can
  have no opening post to derive a timestamp from).
- 3 new tests in `apps/forum_host/tests/test_signals.py`, mirroring the
  file's existing `test_reply_added_auto_subscribes_the_replier`/
  `test_topic_created_auto_subscribes_the_author` shapes exactly.
- `kimi-review`'s commit-gate found a real gap in those 3: all use the
  file's own `Post.objects.create()`-then-`dispatch()`-directly shortcut,
  which leaves `first_published_at` `None` (bypasses the real publish
  action) — `mark_read`'s `when = when or timezone.now()` fallback makes
  them pass regardless of whether `when=post.first_published_at` is even
  present, so they'd stay green through a regression that silently deleted
  that argument. One more test added,
  `test_reply_added_read_marker_keeps_pace_with_real_publish_timing`, using
  the real `.save_revision().publish()` chain end-to-end and asserting
  `TopicRead.last_read_at >= topic.last_post_at` — the actual property the
  fix (and the unread rule's strict `>`) depends on. (kimi's other 2
  findings were false positives: `topic_id` is defined at module scope in
  `dispatch()`, pre-existing, just outside the diff's visible context.)
- Re-verified: backend full suite passes (`385 passed`, was 381), frontend
  unaffected (`628 passed`, `type-check`/`lint` clean — this follow-up is
  backend-only), `manage.py check` clean, `makemigrations --check --dry-run`
  → "No changes detected" (notifications.py and its tests only — no model
  changes this follow-up).
- Contract spot-check (rolled-back `manage.py shell` probe, real Wagtail
  publish chain + the production `/api/v1/forum/...` urlconf, not the
  isolated test urlconf): author of a brand-new topic sees it as read
  (`is_unread: False`); a different user who replies to it also sees it as
  read afterward; an uninvolved bystander who never opened or posted still
  correctly sees it as unread (`True`) — confirms the fix is scoped to the
  actor, not a global side effect. First attempt at this script produced a
  misleading `None` from an unrelated script-methodology bug (a stale
  in-memory `topic` object across two `.publish()` calls clobbering the
  counter refresh, not a product bug — see `docs/LEARNINGS.md` 2026-07-16,
  Testing) before the corrected version confirmed all three outcomes above.
- Todo 271's Acceptance Criteria: #3 flipped to done; #1 and #2 remain open
  and deliberately deferred.

### 2026-07-16 - Slice 5 follow-up: self-review (`/review` on PR #468) fix batch

A `/review` pass against the live PR #468 diff (not local `git diff`) surfaced
4 items; user asked for all of them addressed, including the ones framed as
low-priority "considerations," not just the top-billed suggestions.

- **Untested naive-datetime branch**: `_annotate_topic_unread`'s
  `timezone.is_naive(launch_at)` coercion had zero coverage — every existing
  `WAGTAILFORUM_UNREAD_LAUNCH_AT` override was either already-aware
  (`...Z`) or deliberately malformed. Added
  `test_is_unread_uses_launch_constant_when_naive_datetime_configured`
  (`test_topics_list.py`), mirroring the existing aware-constant test with an
  offset-less setting value — confirmed `parse_datetime` returns a naive
  `datetime` for that input before writing the test.
- **Read-dedup TTL reused `VIEW_COUNT_DEDUP_SECONDS`**: conflated two
  unrelated concerns (view-count throttling vs. read-marking dedup) under one
  setting. Added a dedicated `TOPIC_READ_DEDUP_SECONDS` (`conf.py`, same
  default, own comment explaining why it's separate), wired into
  `TopicDetailView.retrieve()` as its own `read_ttl` read. Added
  `test_topic_read_dedup_ttl_is_independent_of_view_count_dedup_ttl` proving
  the two are now independently tunable (view_count deduped at TTL=900 while
  the read-mark isn't, at TTL=0, in the same two-request exchange).
- **`mark_read`'s `IntegrityError` fallback conflated two failure modes** —
  planned as "add a nested `except DoesNotExist: raise`," but investigating
  it properly (reading Django 6.0.7's actual `get_or_create`/
  `update_or_create` source, then confirming empirically via a real Postgres
  probe) found the opposite fix was correct: Django's `get_or_create` already
  retries its own `.get()` internally after a failed `create()` and only
  re-raises the *original* `IntegrityError` when that retry also comes up
  empty — this package's own outer `except IntegrityError: obj = cls.objects.get(...)`
  wrapper could therefore only ever fire in the already-unrecoverable case,
  where it then converted a clean `IntegrityError` into a confusing masked
  `TopicRead.DoesNotExist`. Removed the wrapper; `mark_read` now calls
  `get_or_create` directly and lets a genuine failure surface uncorrupted.
  Full empirical trail (including a first attempt that gave a false negative
  by wrapping the probe in its own rollback-only savepoint, which suppressed
  this project's `DEFERRABLE INITIALLY DEFERRED` FK constraints from ever
  checking) is in `docs/LEARNINGS.md` (Testing, 2026-07-16, second entry).
- **`mark_read` non-monotonic**: no guard against `last_read_at` moving
  backward if its two callers (the immediate on_commit write from a
  detail-view visit, and the signal-time write from
  `notifications.py`, stamped from `post.first_published_at`) land out of
  chronological order. Fixed in the same edit as the `IntegrityError` change
  above (both touch the same method). First cut used `get_or_create`'s
  `created` flag to drive a conditional `if not created and obj.last_read_at
  < when:` read-then-write in Python — this repo's own `kimi-review` commit
  gate (WARNING tier) caught a real TOCTOU gap in that: two genuinely
  concurrent callers can both read the same stale value and both decide to
  write, and whichever commits last wins even if its own `when` is the
  earlier of the two. Upgraded to a single atomic
  `UPDATE ... SET last_read_at = GREATEST(last_read_at, %s)` instead
  (`django.db.models.functions.Greatest`) — the row's UPDATE lock serializes
  concurrent writers, so the stored value is always the true max of every
  `when` ever passed in, not just non-regressing relative to what one caller
  happened to read. Added
  `test_mark_read_is_monotonic_and_never_moves_last_read_at_backward` and
  `test_mark_read_lets_integrity_error_propagate_uncorrupted` (the latter
  replaces `test_mark_read_falls_back_on_integrity_error`, whose own premise
  — that `mark_read` needs to recover from a race itself — no longer holds
  now that Django's own internals own that recovery).
- kimi-review's other 3 findings on this batch (`assertNumQueries` missing
  on the 3 new tests) were evaluated and dismissed: each new test mirrors an
  existing test in the same file that also doesn't pin query counts (this
  package centralizes the query-count pin in one dedicated test per
  endpoint, not every behavioral variant), and none of the 3 new code paths
  (naive-datetime coercion, a swapped TTL setting value, the monotonic
  guard) can plausibly change a query count — they're pure-Python or
  cache-key operations, not new DB access.
- Re-verified: backend full suite `388 passed` (was 385; net +3 across the
  4 items — item 3's fix replaced 1 test with 2). `manage.py check` clean,
  `makemigrations --check --dry-run` → "No changes detected" (no model
  changes this batch, only a new conf.py setting). Frontend untouched by any
  of these 4 items — not re-run.

### 2026-07-16 - Slice 6 (AC6: FCM registration + push end-to-end) shipped

- **Scope decisions (user-approved via AskUserQuestion):** full slice here
  (todo 260's FCM item now satisfied by cross-reference); server-side
  `notification` block on FCM sends (tray display with zero client display
  code); iOS groundwork landed explicitly unverified (no APNs provisioning);
  credentials handled conditionally — the user pointed at existing docs/mock
  setup; discovery confirmed the instructions exist (`firebase/README.md` →
  drop key at `firebase/firebase-adminsdk-credentials.json`, gitignored), the
  key itself is on no machine path, and the "mock firebase setup" is the
  Emulator Suite (auth 9099/firestore 8080) which has NO FCM emulator —
  delivery always goes through real FCM.
- **Key discovery (planning):** the registration endpoint already existed —
  `PATCH /forum/me/profile/` with write-only `fcm_token`, throttled
  `profile_update: 10/h`. Actually missing: server credentials wiring
  (`FIREBASE_CREDENTIALS_PATH` read by garden's `firebase_config.py`, never
  defined anywhere), any client registering a token, and a visible payload
  (data-only messages show nothing in a backgrounded app's tray).
- **Backend:** `settings.py` gains `FIREBASE_CREDENTIALS_PATH` (canonical —
  absorbs `GOOGLE_APPLICATION_CREDENTIALS` env so ADC-only deploys get push
  too; review fix) + `FIREBASE_PROJECT_ID`; DEBUG-gated `ALLOWED_HOSTS`
  append of `10.0.2.2` (the README's documented Android-emulator dev loop was
  never actually servable). `firebase_auth_views._ensure_firebase_initialized`
  rewritten: registry-as-truth (module flag removed), certificate init
  delegated to garden's `initialize_firebase()` (one home), projectId-only
  fallback honestly scoped to the Auth-emulator dev loop (live-verified:
  firebase_admin 7.4.0 resolves credentials eagerly, so key-less PROD verify
  still 401s), never-raises guard (a typo'd key path degraded to 500-every-
  login before), ValueError race adoption. Garden `initialize_firebase()`:
  get_app() reuse (logs project id), init-race adoption, `reset_firebase()`
  list() iteration fix. `send_forum_push`: notification+data hybrid VIA
  `_notification_content()` — tray copy ONLY for reply_added/mention;
  moderation_decided stays data-only by design (fires on every routine
  autopublish — a visible block would tray-spam users for their own posts;
  review, 3× convergence) — plus a stable collapse key
  (AndroidConfig/APNSConfig) so a retried send replaces, not stacks, the
  tray entry. `_build_payload` gains `actor_name` via the host User's
  `display_name` (same policy as the email channel).
  `MeProfileSerializer.update`: registering a token RELEASES it from any
  other profile (an FCM token identifies a device — closes the shared-device
  stale-push leak the client's best-effort logout clear can't).
- **Mobile:** new `lib/services/push_registration_service.dart` — epoch-
  guarded (`detach()` bumps; every await re-checks: an in-flight sync parked
  on the permission dialog/getToken can't re-register after sign-out —
  review-confirmed race), rotation listener attached BEFORE the token fetch
  (null token on iOS APNS warm-up or a failed first PATCH heals on the next
  rotation event instead of silencing the session), `onError` on the stream,
  `registerToken` swallows internally + skips unchanged tokens (FCM emits an
  onTokenRefresh for the FIRST generation too — observed live), in-memory
  `_lastSyncedToken` dedupe (deliberately NOT persisted: a persisted marker
  would re-introduce the cross-user skip hazard on shared devices),
  `clearOnLogout` (3s-bounded, never throws, skipped when the session never
  registered), `detach()` = full local reset incl. the marker (session-
  expiry path: a different user on the same device must not be dedupe-
  skipped). Manual `Provider` (the `apiServiceProvider`/riverpod.md DI
  precedent). `auth_service.dart`: `_authGeneration++` moved to signOut()'s
  first line (kills in-flight exchanges before the clear window), fire-and-
  forget `syncAfterLogin()` after exchange success, `clearOnLogout()` before
  `firebaseAuth.signOut()` (needs the still-valid JWT), `detach()` in the
  signed-out listener branch, and a `_signingOut` flag so the clear PATCH
  401ing on an expired JWT can't reentrantly fire the session-expired
  handler and stamp a spurious error on an intentional sign-out. Platform:
  Android `POST_NOTIFICATIONS`; debug-only `network_security_config`
  (Dart/dio bypasses Android's cleartext policy but the Firebase SDK's
  native stack enforces it — see LEARNINGS 2026-07-16); iOS
  `Runner.entitlements` (aps-environment=development) + `UIBackgroundModes`
  - `CODE_SIGN_ENTITLEMENTS` in all 3 configs (plutil-linted; MUST flip to
  production before any distribution archive — todo 272 item 1). `minSdk`:
  the flutter tool auto-migrated 23→`flutter.minSdkVersion` (=24 on 3.41.9)
  and RE-APPLIES it every build — pinning back is futile (tried, reverted by
  the next build); documented in-file + LEARNINGS; Android 6 floor cut is
  now a toolchain fact to revisit deliberately.
- **Registration E2E — VERIFIED live, repeatable.** New define-gated
  `integration_test/fcm_registration_e2e_test.dart` (mirrors the firestore-
  emulator test's gating): pumps the REAL app widget, signs in via
  FirebaseAuth against the local Auth emulator (`E2E_AUTH_EMULATOR_HOST`,
  emulator admin API flips `emailVerified` — the backend correctly fails
  closed on unverified emails), and the production chain does the rest
  untouched; polls the service's `lastSyncedToken` (no blind waits). Proof:
  `[PUSH] FCM token registered (142 chars)` app-side, `PATCH
  /api/v1/forum/me/profile/ 200` server-side, `ForumProfile.fcm_token`
  len=142 in the dev DB — re-proven after every repair round. Four real
  gaps found en route, each fixed: ALLOWED_HOSTS (DisallowedHost 400),
  firebase_admin's eager credential resolution (→ projectId tier +
  emulator mode), Android cleartext ban on the native SDK leg, unverified-
  email 403 (by design → emulator flip). Runbook detail: `flutter test`
  reinstalls the APK and wipes `pm grant` — pre-grant POST_NOTIFICATIONS
  with a granter loop racing the install.
- **Delivery E2E — GATED on the service-account key** (searched repo +
  documented locations + common dirs; not present). Everything else is in
  place; the 5-step runbook: (1) drop the key at
  `firebase/firebase-adminsdk-credentials.json`, (2) backend/.env
  `FIREBASE_CREDENTIALS_PATH=<abs path>`, (3) restart backend + `celery -A
  plant_community_backend worker -l info` (or CELERY_TASK_ALWAYS_EAGER=True),
  (4) subscribe the E2E user (`fcm-e2e-slice6`, token already registered) to
  a topic and reply as another user through the real publish chain, (5) tray
  notification on the emulator + `[FCM] forum.reply_added sent` in the
  worker log.
- **Verification (final):** backend `pytest apps/forum_host packages/
  wagtail_forum apps/garden/tests/test_firebase_config.py apps/users
  --create-db` → `520 passed` (388 slice-start baseline; new: content/
  collapse-key/tray-silence tests, fcm_token write-only roundtrip, token
  device-uniqueness, firebase-init reuse/race/failure tests incl. the
  bad-path→401-not-500 pin, actor_name payload pin). `manage.py check` +
  `makemigrations --check` clean (NO model changes — the serializer rule is
  an UPDATE over existing columns). Mobile: `flutter analyze` clean,
  `flutter test` → `190 passed` (epoch/race/heal/dedupe/logout-skip tests),
  codegen regenerated. On-device E2E green post-repair.
- **Code review** (epic convention, heaviest yet: 5 domain reviewers +
  bundled /code-review at high effort = 10 finder angles, all 15 in
  parallel, + 1 post-repair sweep agent): ~35 raw candidates → ~24 distinct,
  most cross-corroborated 2-4×, several live-verified by the finders
  themselves (firebase_admin probe, workflow.py trace, FlutterExtension.kt
  read, scratch-test reproductions of both service races). All repaired
  items above trace to findings. Notable **declines/deferrals with
  reasoning**: google.oauth2.id_token rewrite of the verify path (real
  alternative for credential-less PROD verify, but auth-code churn out of
  slice scope — tier honestly re-scoped instead); persisted dedupe marker
  (correctness-over-throttle tradeoff, documented); signOut concurrency
  (race surface for marginal latency); shared ApiService test fake at 3rd
  occurrence (slice-3 precedent; todo 260 is the natural extraction
  trigger); `_splitHostPort` copy at 2 occurrences (repo convention; both
  angles concurred); emulator-provisioning-via-REST test simplification
  (verified-working choreography kept over re-verification cost); full
  init-bootstrap single-homing + notification-copy consolidation +
  AuthService harness + throttle-sharing → todo 272 (6 items, each with
  disposition). Trigger capture: 3 new candidate write-time triggers
  (initialize_app ValueError adoption, unscoped FCM notification blocks,
  eager Certificate parse) → docs/rules/triggers.json (34 total). 2 new
  LEARNINGS entries (flutter tool re-applies gradle migrations; Dart HTTP
  bypasses Android cleartext policy).
- **Post-repair sweep round** (1 fresh agent over the repairs themselves —
  the one part of the diff no reviewer had seen): 6 findings, all fixed.
  (1) The `_signingOut` boolean couldn't cover a clear-PATCH 401 arriving
  AFTER its 3s timeout abandoned the request (Future.timeout abandons, Dio
  keeps going ~27s) → replaced with a REQUEST-scoped exemption
  (`ApiService.skipSessionExpiryKey` in request extra, checked by the 401
  interceptor) — the flag rides the request, so timing can't outflank it.
  (2) `await _refreshSubscription?.cancel()` is an async gap the epoch guard
  skipped → re-check added. (3) Serializer token-release reordered to
  release-then-save inside `transaction.atomic()` — save-then-release could
  blank the token on BOTH profiles under a concurrent same-token
  registration; release-then-save converges on last-writer-holds. (4) The
  settings `or`-fallback normalized: set-but-EMPTY `FIREBASE_CREDENTIALS_PATH`
  now explicitly disables (and doesn't fall through to
  GOOGLE_APPLICATION_CREDENTIALS); empty never leaks into
  `is_firebase_available()`'s `is not None` gate. (5) The projectId-only
  tier now REFUSES to run when a credentials path IS configured but failed —
  a credential-less default app would be adopted by the FCM sender's reuse
  branch and burn send+3 retries per push with the reuse log masking the
  root cause. (6) Collapse keys made per-EVENT-TYPE, not per-post — FCM
  retains at most 4 distinct collapse keys per offline device, so unique
  keys would silently drop all but 4 notifications accumulated offline.
  Re-verified after the sweep round: backend `520 passed`, mobile `190
  passed`, analyze clean, on-device E2E green.
- **Residue for the user:** (1) the delivery-E2E key (runbook above — with
  it, AC6 flips fully); (2) run 1 of the E2E (before the emulator switch)
  created a throwaway `fcm-e2e-slice6@example.com` user in PROD Firebase
  Auth — inert, deletable in the console (the local Django user of the same
  name is useful for the delivery run); (3) the minSdk 23→24 toolchain
  floor cut, flagged for a deliberate product decision.
- Not archived — AC6's delivery half stays gated on the credentials only
  the user can provide. Todo stays `in_progress` with that single residue.

## Notes

p1 by user triage decision. C2 (one of only two Critical findings) anchors this
epic. Related: todo 260 (mobile client) owns the Flutter FCM registration half.
Related: todo 267 (filed 2026-07-14 from slice 2's code review) tracks the
`EmailService` systemic silent-failure modes found but out of scope here.
Related: todo 268 (filed 2026-07-14 from slice 3's code review) tracks the
reply fan-out's N-sequential-Celery-enqueue scaling gap, deferred rather than
fixed inline.
Related: todo 271 (filed 2026-07-16 from slice 5's code review) tracks
unread/read-state edge cases, none blocking AC5: watermark trigger-scope and
on_commit-inline reality remain deliberately deferred; the third
(own-post-shows-unread) was fixed same-day as a follow-up once requested —
see the "Slice 5 follow-up" Work Log entry above for that fix.
