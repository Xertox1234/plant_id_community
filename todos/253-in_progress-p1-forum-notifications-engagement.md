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

- [ ] A reply to a subscribed topic produces an in-app notification visible via
      bell UI; mark-read works
- [x] The `forum_notifications` preference actually gates deliveries (email and push)
      — satisfied for the reply vertical (the only wired one): push has
      gated on it since before slice 1; slice 2 wires the reply email
      through `EmailService._should_send_email`'s same
      `user.forum_notifications` check. Mention/digest/new-topic emails
      remain unwired (slices 3-4), so there's nothing to gate for those yet.
- [ ] Reply/mention events fan out to subscribers/participants, not only the topic author
- [ ] An @mention notifies the mentioned user and renders as a profile link
- [ ] Topic lists show an unread/new indicator
- [ ] At least one real client (web or mobile) registers an FCM token and
      receives a push end-to-end

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

## Notes

p1 by user triage decision. C2 (one of only two Critical findings) anchors this
epic. Related: todo 260 (mobile client) owns the Flutter FCM registration half.
Related: todo 267 (filed 2026-07-14 from this slice's code review) tracks the
`EmailService` systemic silent-failure modes found but out of scope here.
