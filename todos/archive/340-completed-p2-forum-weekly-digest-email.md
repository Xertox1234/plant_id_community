---
status: completed
priority: p2
issue_id: "340"
tags: [forum, email, celery, package]
dependencies: []
---

# Weekly forum digest email (opt-in package feature, host-scheduled)

## Problem

The forum has per-reply email (`send_forum_email_batch`) but **no digest**.
Discourse's digest is its strongest retention mechanic for members who don't
visit daily; every modern forum product sends one. Without a pull-back
channel, watched-topic notifications are the only re-engagement path, and
they only fire for topics a user already interacts with.

## Findings

- `apps/forum_host/tasks.py:279-362` — `send_forum_email_batch` sends
  reply-added emails only; mention/moderation emails are unwired (2026-09-04
  backend catalog).
- `apps/forum_host/tasks.py` + Celery beat already exist, so scheduling is
  infrastructure we have.
- Visibility rules the digest must respect are already centralized:
  `_visible_boards()` (live + public) and blocked-author exclusion
  (`wagtail_forum/api/views.py:111-119`).
- Source of engagement data exists: `TopicSubscription` (watched topics),
  `Notification` (unread replies/mentions), `Topic.reply_count` /
  `last_post_at` (trending).

## Recommended Action

Design it as a **`wagtail_forum` package feature, opt-in**, host provides
only scheduling and templates overrides — same split as the spam backends:

1. **Package (`wagtail_forum`):**
   - `ForumProfile.digest_frequency` (choices: `off`/`weekly`; default per
     `get_setting("DIGEST_DEFAULT_FREQUENCY", "off")` — opt-in, not opt-out,
     following the package's existing `get_setting()` pattern in
     `wagtail_forum/conf.py`).
   - A `digest.py` service: build the digest payload for a user from
     **unread notifications on watched topics** + **top N active topics in
     public boards they haven't seen**, all filtered through the same
     visibility rules as the API (hidden/restricted topics, blocked authors).
   - A Django management command `send_forum_digest --frequency=weekly
     [--dry-run]` that enqueues/sends via Django's `send_mail` with
     package templates under `templates/wagtail_forum/email/`
     (`digest.txt` + `digest.html`) — **overridable by hosts via normal
     Django template resolution**.
   - Config knobs in `conf.py`: `DIGEST_MAX_TOPICS` (default ~10),
     `DIGEST_MAX_ROWS` — never a per-user cap baked in code.
   - Package tests pin: visibility filtering, no-activity → no email,
     off-by-default, template override resolution.
2. **Host (`apps/forum_host`):** Celery beat entry calling the management
   command weekly; the existing email service/wrappers for send-format.
3. **Web:** "Email digest" toggle on `SettingsPage` (folds into the pending
   "Email notifications preferences" planned section, `SettingsPage.tsx:1-13`)
   once todo 343 (notification preferences) exists — or its own checkbox if
   343 is still pending when this is picked up; dependencies are unordered.
4. Unsubscribe path: link in email → signed-in settings page. A
   no-login one-click unsubscribe (RFC 8058 headers) is a follow-up, not in
   scope.

## Technical Details

- Config pattern: `wagtail_forum/conf.py` `get_setting()` — DB value >
  Django setting > package default (mirrors `ForumSettings`,
  `apps/forum_host/forum_settings.py`).
- Send mechanics and `transaction.on_commit` enqueue conventions:
  `backend/docs/patterns/domain/celery.md`,
  `apps/forum_host/notifications.py:168-262`.
- Bracketed log prefixes (`[EMAIL]`) per `backend/CLAUDE.md`.
- The package must **not** import or depend on Celery (hosts may not run it)
  — the management command is the package boundary; Celery is host wiring.

## Acceptance Criteria

- [x] `wagtail_forum` ships the digest service + `send_forum_digest`
      command + `digest.txt/html` templates, all overridable
- [x] Off by default; users opt in via profile field
- [x] Package tests: digest content excludes hidden/restricted topics and
      blocked authors; zero qualifying content → no send
- [x] Host Celery beat sends weekly; a `--dry-run` run on prod data shows
      sane recipient counts before first real send
- [x] Web settings toggle for the digest frequency

## Work Log

### 2026-09-04 - Filed

- Surfaced by the 2026-09-04 forum competitive assessment, ranked gap #2:
  "No digest/thin email engagement — Discourse's best retention mechanic."

### 2026-09-05 - Started by completing-todos skill (run 2026-09-05-1142)

- Picked up by automated workflow.

### 2026-09-05 - Package + host implemented (run 2026-09-05-1142)

Decisions:

- **Package owns content + send; host owns scheduling.** `wagtail_forum/digest.py`
  (`build_digest` → `Digest{watched, trending}`, `render_digest`,
  `send_digest` via `EmailMultiAlternatives` from `DEFAULT_FROM_EMAIL`),
  `manage.py send_forum_digest --frequency weekly [--dry-run] [--window-days]`,
  templates `wagtail_forum/email/digest.txt|html` (host-overridable by
  shadowing). The package never imports Celery (test-pinned).
- **Sections:** watched = unread `reply` notifications since the window
  start, grouped per topic; trending = most active visible topics of the
  window the member has not read since their last post, excluding their own
  topics and the watched ones. Both go through `_visible_boards()` and
  `_exclude_blocked_authors()` — the API's rules.
- **Opt-in:** `ForumProfile.digest_frequency` (`off` default; the host's
  `DIGEST_DEFAULT_FREQUENCY` applies to NEW profiles only), exposed
  read/write on `me/profile/`. Migration 0033.
- **Idempotent:** `last_digest_sent_at` — a member is due when it is null or
  older than the window minus a day of scheduler jitter; the activity
  window starts at the last digest (capped at one window back). Empty →
  no email, no marker write. `--dry-run` builds every digest and prints
  counts; sends nothing, writes nothing.
- **The todo's premise "Celery beat already exists" was wrong** — there was
  no beat schedule. Added `CELERY_BEAT_SCHEDULE` (Monday 09:00 UTC →
  `apps.forum_host.tasks.send_forum_weekly_digest`, which `call_command`s
  the package command) and embedded beat in the co-located worker
  (`celery worker -B --schedule=/tmp/celerybeat-schedule`, bin/start.sh).
  One container → one beat; the idempotent command makes a deploy-overlap
  double fire harmless.
- Settings + README rows: `DIGEST_DEFAULT_FREQUENCY`, `DIGEST_WINDOW_DAYS`,
  `DIGEST_MAX_WATCHED_TOPICS`, `DIGEST_MAX_TRENDING_TOPICS`,
  `DIGEST_SETTINGS_PATH`, `EMAIL_SITE_URL` (None → host `SITE_URL`).

Evidence:

```text
$ pytest test_digest.py test_tasks.py test_docs.py → 56 passed
  (off-by-default + host default for new profiles; visibility: hidden/restricted boards, blocked repliers/authors, own topics, read-since-last-post, stale; nothing new → no email + no marker; opted-in only, from/subject/links/html, idempotent second run due=0; dry-run sends/writes nothing; due/since windows; template override wins; me/profile/ round trip + 400 on "daily"; no Celery import; beat entry names the registered task; task calls the command)
$ manage.py makemigrations --check --dry-run wagtail_forum → No changes detected; manage.py check → no issues
$ docker run bash:5.2 bin/test-start.sh → test-start: all cases passed (macOS bash 3.2 cannot run it)
```

### 2026-09-05 - Closing plan for the prod dry-run criterion

`--dry-run` against production data needs migration 0033's columns
(`digest_frequency`, `last_digest_sent_at`), which only exist in prod once
this PR deploys — a pre-merge run would fail on a missing column, and a
local run against `DATABASE_PUBLIC_URL` would too. So: merge, let Railway
deploy + migrate, then run
`railway run --service <backend> -- python manage.py send_forum_digest --frequency weekly --dry-run`
(nothing is sent or written) and record the `recipients=/due=/empty=` line
here before the first Monday fire. Until then this todo stays
`in_progress` with that box open (todo 337 precedent: closed by a chore PR
after the prod run). Expected: `recipients=0` — the field is opt-in and
brand new.

Full backend suite with the digest (alone, `--create-db`):

```text
2161 passed, 8 skipped, 5 warnings in 281.92s (0:04:41)
```

### 2026-09-05 - Web toggle (implemented by a general-purpose agent against the me/profile/ contract, reviewed below)

- `types/forum.ts`: `DigestFrequency`, `ForumMyProfile` (no `avatar_id`/`fcm_token` — both `write_only` on the serializer), `ForumMyProfilePatch`.
- `services/forumService.ts`: `fetchMyForumProfile()` / `updateMyForumProfile(patch)` over `${FORUM_BASE}/me/profile/`.
- `pages/SettingsPage.tsx`: `EmailDigestSection` between the theme and blocked-users sections — loads with an `ignore` flag, Retry via a `loadAttempt` counter, `<select id="digest-frequency">` Off/Weekly (disabled + `aria-busy` while saving, `aria-describedby` → the status region), optimistic update reverted to the last SAVED value on failure, one always-mounted `aria-live` region outside every conditional.

```text
$ vitest run src/pages/SettingsPage.test.tsx src/services/forumService.test.ts → 66 passed
$ vitest run (full web) → Test Files 94 passed / Tests 1166 passed
$ npm run type-check → rc=0; eslint clean; prettier clean
mutation checks (cp backups, no git checkout): conditional live region / revert deleted / disabled removed / URL `/me/` → each named test red; files restored byte-identical
```

### 2026-09-05 - Review round 1 (backend): celery-async, cross-cutting, django-drf — all repaired

- **[high, all three] "cannot double-send" was an unbacked claim.** Repaired
  twice over: the command holds a cache **run lock**
  (`wagtail_forum:digest-run:<frequency>`, 2 h, released in `finally`; a
  dry run neither takes nor honours it) so an overlapping fire exits, and
  each member is **claimed atomically** before the send (conditional
  `UPDATE … WHERE last_digest_sent_at = <value read>`), reverted on a failed
  send. Tests: overlapping run sends nothing and the lock is released; a
  failed send leaves the member due.
- **[high, celery/cross-cutting] the task inherited the request-shaped 90 s
  soft limit, had no retries, and a soft-limit exception would have been
  swallowed by `send_digest`'s `except Exception`.** Repaired: task-level
  `soft_time_limit` 25 min / `time_limit` 30 min, `autoretry_for=
  (OperationalError,)` ×3 with backoff, on `SoftTimeLimitExceeded` the task
  re-enqueues itself to finish the members still due (per-member marker),
  and both the package `send_digest` and the command re-raise a
  `SoftTimeLimitExceeded` matched by NAME (the package cannot import
  Celery). The command's summary is captured and logged with the task id.
- **[high, django] one member's exception aborted the whole run** —
  repaired: per-member `try/except`, `[EMAIL]` log, `failed` count,
  marker untouched (test).
- **[medium] `CELERY_TIMEZONE` implicit** → pinned to `TIME_ZONE` and
  asserted; **[medium] runbook stale** (`railway.md` said "no beat
  process") → topology + beat-liveness check + Docker recipe for
  `test-start.sh`; **[medium] `site_url()` fell back to ''** → raises
  `ImproperlyConfigured` (test); **[medium] second profile-creation path
  (`signals._refresh_profile`) skipped the digest default** → seeded
  (test); **[medium] `render_digest` re-fetched the profile per member** →
  `display_name` carried on the `Digest`, the command passes its loaded
  profile; **[medium] untested branches** → fixtures for a read
  notification, an inactive member, the caps (and the overflow-watched
  topic that must not resurface as trending — the [low] django finding),
  a `<script>` title escaped in the html part, the send-failure path, a
  `build_digest` query pin (7, flat in topics); **[low]** `-pk` tie-breaks,
  `Count("pk")`, the unused `now` parameter removed.

```text
pytest test_digest.py test_tasks.py → 65 passed
```

### 2026-09-05 - Review round 1 (web): react-typescript reviewer

Lows only; three taken: the select is **refocused** after the
disable/enable cycle (state bump + effect, ConversationPage's pattern);
the live region is asserted present **before the profile loads** and the
same node afterwards; a second change while a save is in flight is
exercised (`fireEvent.change` → still one PATCH; the handler also guards
on `saving`). Known gap, not new: like its sibling sections on this page,
the section is not keyed to `user?.id` (an account swap while on
`/settings` keeps the cached profile) — the page has no `useAuth` wiring;
fixing all three sections together is a follow-up, not this slice.

### 2026-09-05 - Acceptance criteria evidence (4 of 5; the prod dry-run waits for the deploy)

- AC1 service + command + templates: `wagtail_forum/digest.py`,
  `management/commands/send_forum_digest.py`, `templates/wagtail_forum/email/digest.txt|html`;
  override test `test_host_can_override_the_templates` green.
- AC2 off by default / opt-in: `test_digest_is_off_by_default_and_the_host_default_applies_to_new_profiles`,
  `test_recount_created_profiles_get_the_host_digest_default`, `me/profile/` round trip.
- AC3 package tests: `test_digest_content_respects_visibility_and_blocks`
  (hidden + restricted boards, blocked replier and author, read notification,
  own/seen/stale topics), `test_nothing_new_means_no_email_and_no_marker_write`.
- AC4 host beat: `CELERY_BEAT_SCHEDULE` + `send_forum_weekly_digest` pinned by
  `test_weekly_digest_is_scheduled_on_a_registered_task`; the **prod dry-run
  half stays open** until the deploy (see the closing plan above).
- AC5 web toggle: `SettingsPage` Email digest section, 15 SettingsPage tests
  incl. the five digest cases; full web suite 1166 passed.

Post-repair full backend suite (alone, `--create-db`) and full web suite:

```text
2172 passed, 8 skipped, 5 warnings in 294.56s (0:04:54)
Test Files 94 passed (94) / Tests 1166 passed (1166)
```

### 2026-09-05 - Prod dry-run after the deploy (PR #641 merged 13:30 UTC, Railway deployment SUCCESS)

Run locally against the PRODUCTION database (read-only: `--dry-run` sends
and writes nothing and never takes the run lock), with the app service's
environment from `railway run` and the Postgres service's public URL
injected as `DATABASE_URL` (the app env carries only the private one):

```text
$ railway run --service plant_id_community -- sh -c 'DATABASE_URL="$PUB" REDIS_URL=redis://localhost:6379/9 EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend venv/bin/python manage.py send_forum_digest --frequency weekly --dry-run'
[EMAIL] digest frequency=weekly window_days=7 recipients=0 due=0 empty=0 would send=0 failed=0 (dry run — nothing sent, nothing written)
```

Sane and expected: the preference is opt-in and brand new, so nobody is a
recipient yet; the first Monday 09:00 UTC fire will send nothing until
members opt in on `/settings`. Migration 0033 is live (the query on
`digest_frequency` succeeded).

### 2026-09-05 - Completed by completing-todos skill (run 2026-09-05-0408)

- Verification: all 5 acceptance criteria evidenced (backend 2172 passed / web 1166 passed; prod --dry-run recipients=0 after the deploy).
- Review: celery-async + cross-cutting + django-drf (backend), react-typescript (web) — 1 round each; every finding repaired (run lock + atomic claim, cohort limits/retries/continuation, per-member fault isolation, timezone pin, loud missing origin, second creation path, uncapped exclusion, no re-fetch, runbook; web refocus + stronger tests).
