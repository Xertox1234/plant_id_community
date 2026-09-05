---
status: pending
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

- [ ] `wagtail_forum` ships the digest service + `send_forum_digest`
      command + `digest.txt/html` templates, all overridable
- [ ] Off by default; users opt in via profile field
- [ ] Package tests: digest content excludes hidden/restricted topics and
      blocked authors; zero qualifying content → no send
- [ ] Host Celery beat sends weekly; a `--dry-run` run on prod data shows
      sane recipient counts before first real send
- [ ] Web settings toggle for the digest frequency

## Work Log

### 2026-09-04 - Filed

- Surfaced by the 2026-09-04 forum competitive assessment, ranked gap #2:
  "No digest/thin email engagement — Discourse's best retention mechanic."
