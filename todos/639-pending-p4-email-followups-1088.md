---
status: pending
priority: p4
issue_id: "639"
tags: [email, templates, follow-ups]
dependencies: []
---

# Follow-ups from PR #1088 (todo 622, email links, text parts and layout)

## Problem

Todo-sweep run 2026-10-12-1637 merged PR #1088 (todo 622, email links, text parts and layout). The non-blocking review findings are below. The curator merged duplicates and checked each one against main. The refuter then tried to refute what was left. The findings that survived are listed.

## Findings

PR #1088 (todo sweep run 2026-10-12-1637, group g1, todos 622); follow-ups: verified.

1. **low** `backend/apps/core/services/email_service.py:49` html_to_text() drops head/style/script/title but keeps the hidden preheader div that base.html puts first in `<body>`, so every fallback text part (no .txt) opens with the inbox-preview line, e.g. 'Stay connected with your plant community'. | also: html_to_text() keeps the hidden preheader div from base.html, so a fallback text part (e.g. identification_result.html, which has a preheader and no .txt) opens with the inbox-preview line as body text.
2. **low** `backend/apps/users/email_verification.py:201` deliver_verification_email and deliver_provider_linked_notice call render_to_string outside any try; a template error raises out of the Celery task, skipping_retry_or_give_up and its '[EMAIL]' give-up logging. | also: render_to_string now runs outside any try. A template error raises out of deliver_verification_email (and deliver_provider_linked_notice) instead of returning False, so send_verification_email_task never reaches its_retry_or_give_up path or its [EMAIL] failure log.
3. **low** `backend/apps/core/tests/test_email_service_silent_failures.py:28` FALLBACK_RENDERABLE_TEMPLATES still lists welcome_email, which now ships welcome_email.txt, so the missing-.txt fallback tests no longer cover it; comments ('strip_tags(html) body', 'forum_reply is the one EmailType with a real .txt') are stale.
4. **low** `backend/apps/users/tests/test_email_presentation.py:297` test_required_mail_ignores_optional_mail_preferences: the integration loop does not exercise the _should_send_email reorder (send_transactional_email never checks preferences; send_welcome_email passes respect_preferences=False). Only the direct _should_send_email asserts test the change.
5. **low** `backend/apps/forum_host/tasks.py:598` settings.SITE_URL.rstrip('/') raises AttributeError if SITE_URL is None, unlike email_service's `(site_url or "")` guard; in the Celery batch task that fails the whole reply-email batch with a permanent error that retrying won't fix. | also: settings.SITE_URL.rstrip('/') raises AttributeError if SITE_URL is None. email_service's base context guards with `or ''`, but this Celery task does not, so a misconfigured env fails every batch (and may retry a permanent error). | settings.SITE_URL.rstrip('/') assumes SITE_URL is a non-empty str, while email_service guards with (site_url or ''). A None or unset value would raise AttributeError and abort the whole reply-email batch.
6. **low** `backend/templates/emails/blog_post.html:74` app_url is concatenated with `/blog/...` (trailing-slash risk); the 'Leave a Comment' link lost its #comments anchor. | also: blog_post.html gets only link fixes. It still has display:flex and inline-flex layout and the old non-presentation structure, and the new families' layout and no-flex tests do not cover it. It is documented as having no live caller, so the risk is contained.
7. **low** `backend/apps/core/services/email_service.py:32` The _LINK pattern's \bhref also matches data-href= (a '-' gives a word boundary), so `<a data-href=x href=y>` would print x as the link URL.
8. **low** `backend/templates/emails/email_verification.txt:1` Verification and provider-linked bodies use {{ site_name }} (SITE_NAME, default "Houseplant-MD"), while their subjects hardcode "Houseplant MD", so one message names the product two ways; no test checks the body name.

3 more location(s) were dropped by the cap of 10 (the most severe are kept).

Dropped by curation (fixed on main, refuted, or not a reported location):

- low: backend/templates/account/email/password_reset_key_message.html:8 Template uses `{% if username %}`, but allauth's password-reset context may supply only `user` (username is set only for some auth-method configs), so the account name could silently never render. (refuted: Main sets ACCOUNT_LOGIN_METHODS={'username','email'}. allauth 65 adds context['username'] when USERNAME is among LOGIN_METHODS (from my knowledge of allauth, not checked in this repo), so {% if username %} renders.)

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-12 - Filed from the PR #1088 review (todo sweep run 2026-10-12-1637)

Filed by the closing step of the run from `state.py followups-md g1`.
