---
status: completed
priority: p2
issue_id: "622"
tags: [backend, web, email, templates, accessibility, testing]
dependencies: []
triage: ready
triaged: 2026-10-12
owner_decision: "Owner: keep all scope in 622; standardize every live email family on templates/emails/base.html (mail-safe, inlined) (2026-10-12). Owner: fix blog_post.html's #!/ links too, even though no caller renders it (2026-10-12). Owner: AC6 inbox checks re-pointed to todo 626 (2026-10-12)"
---

# Repair email navigation and standardize readable message presentation

## Problem

Both welcome-email action buttons use obsolete hash routes and open the home page instead of their destination. The plain-text fallback includes stylesheet rules and loses button URLs; email families also have inconsistent presentation and unverified mail-client rendering.

## Findings

Source: Devin's read-only email audit, 2026-10-12. Welcome rendering and route behavior were reproduced in memory without database access, SMTP or code changes.

- `backend/templates/emails/welcome_email.html:58-65` renders `#!/identify` and `#!/forum`. The installed react-router-dom matched both to `/`; `/identify` and `/forum` matched the intended routes. `web/src/main.tsx:75-81` uses BrowserRouter and `web/src/App.tsx:78-90` defines pathname routes; the audit found no hashbang compatibility handler.
- `backend/apps/core/services/email_service.py:146-159` uses `strip_tags(html_content)` when a text template is absent. Rendered welcome text contained `.email-container {` and no identification destination URL; it was 6,422 characters with the audit fixture. Archived 267 fixed missing-text delivery, not this content quality.
- `backend/templates/emails/base.html:9-12,57-80,127-165` places a preheader div in head and relies on class-based layout; `welcome_email.html:24-54` uses flexbox. These are compatibility risks, not proof of failure in a specific inbox.
- Forum digest has a standalone minimal template (`backend/packages/wagtail_forum/wagtail_forum/templates/wagtail_forum/email/digest.html`), while verification/provider-link notices build bare HTML in `backend/apps/users/email_verification.py:189-219` and `account_links.py:100-133`.
- `backend/apps/forum_host/tasks.py:563-564` builds a topic-only email URL. Web/browser notifications already navigate to a post anchor. Archived 408 fixed the preferences link only, not the welcome buttons.

## Recommended Action

1. Replace welcome hashbang links with current absolute web destinations; normalize the origin and test every live email action link against its intended route. Add exact-reply anchors to reply email.
2. Add explicit readable text alternatives for live HTML-only message families, preserving meaningful action URLs and excluding style/script content. Keep a safe fallback for unsupported templates without treating raw strip_tags as a complete text renderer.
3. Standardize branding, typography, spacing, accessible links/buttons, preheaders and footer policy across live transactional/activity/digest/newsletter messages. Keep security notices clear; do not insert marketing consent or unsubscribe behavior into required security mail by accident.
4. Use mail-safe layout and inline essential styles, with conservative dark-mode handling. Do not revive unused legacy templates merely for visual consistency; first verify each template's live caller.
5. Render representative emails in Gmail, Apple Mail and Outlook with light/dark and narrow-screen checks. Use approved test inboxes only, not users, and record results rather than treating browser screenshots as inbox evidence.

## Technical Details

Target the cited templates/services, account reset templates under `backend/templates/account/email/`, and relevant core/forum/blog/users tests. Reference `web/docs/patterns/testing.md`; preserve inline button-color coverage in `backend/apps/core/tests/test_email_button_inline_color.py` and signed unsubscribe headers from 408/416.

Audit baseline: five targeted web test files passed (100 tests), but did not exercise these rendered-email navigation defects. Add targeted regression tests rather than broad snapshot-only assertions. Mail-client rendering was not performed in the audit.

## Acceptance Criteria

- [x] Rendered welcome buttons use `/identify` and `/forum` at the configured origin; tests reject legacy hashbang links and demonstrate matching current web routes.
- [x] Reply email links reach the referenced post, with a valid topic fallback where appropriate; tests cover canonical board/topic paths and trailing-slash origins.
- [x] Every live message family has a meaningful text alternative with action URLs and no CSS/script source; tests assert content and destinations, not only nonempty bodies or send counts.
- [x] Representative HTML follows a consistent brand/layout, valid preheader placement and accessible essential inline styling; verification, reset and security notices retain their meaning and escape user content.
- [x] Unsubscribe/preferences links and headers remain correct for optional mail; required security mail is not disabled by optional-mail preferences. Relevant template, account, newsletter and forum tests pass.
- [ ] Approved Gmail, Apple Mail and Outlook checks record date, client/version, light/dark/narrow-screen observations and any accepted limitation. If unavailable, keep this criterion open or explicitly re-point it to a dedicated verification todo; do not claim inbox compatibility from a browser-only render. → todo 626 (re-pointed 2026-10-12)

## Work Log

### 2026-10-12 - Created from reproduced audit findings

- Grouped broken welcome navigation, text alternatives, exact-reply links and email visual consistency. Existing 267/408 work was checked and does not cover the remaining issues.
- Recorded the in-memory render/router evidence; no mail was sent and no permanent application changes were made during the audit.

### 2026-10-12 - Triage (run 2026-10-12-1637)

- Owner: AC6 inbox checks re-pointed to [todo 626](626-completed-p2-email-inbox-rendering-verification.md); blog_post.html links fixed too despite no caller.

### 2026-10-12 - Implemented by the todo sweep (run 2026-10-12-1637)

- Welcome buttons now link `{{ app_url }}/identify` and `/forum`; `EmailService._get_base_context` strips a trailing slash from `SITE_URL`, and `blog_post.html` lost its `#!/` links. Reply emails open `<topic>#post-<id>` (the anchor `ThreadDetailPage` renders) with the topic as the fallback link.
- Live families checked against their callers: welcome, forum reply, newsletter confirm and issue, forum digest, verification, provider-linked notice and the allauth password reset. Welcome gained a `.txt`; verification and provider notices moved from f-strings to `emails/email_verification.*` and `emails/provider_linked.*`; the forum digest HTML is a host shadow at `backend/templates/wagtail_forum/email/digest.html`. A missing `.txt` now falls back to `html_to_text()` rather than raw `strip_tags`.
- `templates/emails/base.html` is a table layout with inline styles, the preheader as the first element of `<body>`, `color-scheme: light`, and the old partial dark-mode rule removed (it set light text over the light inline panels). Security mail (verification, provider notice, reset) uses `emails/_security_footer.html`: no preferences or unsubscribe link.
- Found and fixed: `_should_send_email` checked the master `email_notifications` toggle before the system-email allowlist, so required account mail sent through it could be held back by an optional-mail preference.
- Tests: `apps/core/tests/test_email_links_and_text.py`, `apps/forum_host/tests/test_reply_email_links.py`, `apps/users/tests/test_email_presentation.py` (every live family, rendered). Inbox checks stay with todo 626.

### 2026-10-12 - Verified by the todo sweep (run 2026-10-12-1637)

- AC 1: `python3 scripts/todos/slot_env.py --main-root . 1 -- backend/venv/bin/python -m pytest backend/apps/core/tests/test_email_links_and_text.py backend/apps/core/tests/test_email_service_silent_failures.py --create-db -q -p no:cacheprovider` — evidence `.sweep-evidence/g1/622-ac0.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================= 14 passed, 2 warnings in 17.16s ========================
  ```

- AC 2: `python3 scripts/todos/slot_env.py --main-root . 1 -- backend/venv/bin/python -m pytest backend/apps/forum_host/tests/test_reply_email_links.py backend/apps/forum_host/tests/test_tasks.py backend/apps/forum_host/tests/test_notification_copy.py --create-db -q -p no:cacheprovider` — evidence `.sweep-evidence/g1/622-ac1.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================= 89 passed, 2 warnings in 18.04s ========================
  ```

- AC 3: `python3 scripts/todos/slot_env.py --main-root . 1 -- backend/venv/bin/python -m pytest backend/apps/users/tests/test_email_presentation.py backend/apps/core/tests/test_email_links_and_text.py backend/apps/core/tests/test_email_service_silent_failures.py --create-db -v -p no:cacheprovider` — evidence `.sweep-evidence/g1/622-ac2.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ============== 50 passed, 3 warnings, 9 subtests passed in 17.46s ==============
  ```

- AC 4: `python3 scripts/todos/slot_env.py --main-root . 1 -- backend/venv/bin/python -m pytest backend/apps/users/tests/test_email_presentation.py backend/apps/core/tests/test_email_button_inline_color.py backend/packages/wagtail_forum/wagtail_forum/tests/test_digest.py backend/apps/users/tests/test_email_verification.py backend/apps/users/tests/test_email_verification_hardening.py --create-db -v -p no:cacheprovider` — evidence `.sweep-evidence/g1/622-ac3.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ============= 156 passed, 3 warnings, 6 subtests passed in 26.11s ==============
  ```

- AC 5: `python3 scripts/todos/slot_env.py --main-root . 1 -- backend/venv/bin/python -m pytest backend/apps/users/tests/test_email_presentation.py backend/apps/users/tests/test_email_unsubscribe.py backend/apps/users/tests/test_email_verification.py backend/apps/users/tests/test_email_verification_hardening.py backend/apps/users/tests/test_allauth_surface.py backend/apps/blog/tests/test_newsletter.py backend/apps/blog/tests/test_newsletter_digest.py backend/apps/forum_host/tests/test_tasks.py backend/apps/forum_host/tests/test_notification_copy.py backend/apps/forum_host/tests/test_notification_preferences.py backend/apps/forum_host/tests/test_reply_email_links.py backend/apps/core/tests/test_email_button_inline_color.py backend/apps/core/tests/test_email_links_and_text.py backend/apps/core/tests/test_email_service_silent_failures.py backend/apps/core/tests/test_mail_call_sites_deprecation_gate.py backend/packages/wagtail_forum/wagtail_forum/tests/test_digest.py --create-db -q -p no:cacheprovider` — evidence `.sweep-evidence/g1/622-ac4.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================= 394 passed, 3 warnings in 30.40s =======================
  ```

### 2026-10-12 - Completed by the todo sweep (run 2026-10-12-1637)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

## Notes

P2 because onboarding action links are demonstrably broken; cosmetic standardization can ship after the correctness fixes within this initiative. Provider delivery/engagement measurement and sender-domain checks belong to todo 623, not visual rendering.
