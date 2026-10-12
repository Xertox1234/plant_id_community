---
status: pending
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

- [ ] Rendered welcome buttons use `/identify` and `/forum` at the configured origin; tests reject legacy hashbang links and demonstrate matching current web routes.
- [ ] Reply email links reach the referenced post, with a valid topic fallback where appropriate; tests cover canonical board/topic paths and trailing-slash origins.
- [ ] Every live message family has a meaningful text alternative with action URLs and no CSS/script source; tests assert content and destinations, not only nonempty bodies or send counts.
- [ ] Representative HTML follows a consistent brand/layout, valid preheader placement and accessible essential inline styling; verification, reset and security notices retain their meaning and escape user content.
- [ ] Unsubscribe/preferences links and headers remain correct for optional mail; required security mail is not disabled by optional-mail preferences. Relevant template, account, newsletter and forum tests pass.
- [ ] Approved Gmail, Apple Mail and Outlook checks record date, client/version, light/dark/narrow-screen observations and any accepted limitation. If unavailable, keep this criterion open or explicitly re-point it to a dedicated verification todo; do not claim inbox compatibility from a browser-only render. → todo 626 (re-pointed 2026-10-12)

## Work Log

### 2026-10-12 - Created from reproduced audit findings

- Grouped broken welcome navigation, text alternatives, exact-reply links and email visual consistency. Existing 267/408 work was checked and does not cover the remaining issues.
- Recorded the in-memory render/router evidence; no mail was sent and no permanent application changes were made during the audit.

### 2026-10-12 - Triage (run 2026-10-12-1637)

- Owner: AC6 inbox checks re-pointed to [todo 626](626-pending-p2-email-inbox-rendering-verification.md); blog_post.html links fixed too despite no caller.

## Notes

P2 because onboarding action links are demonstrably broken; cosmetic standardization can ship after the correctness fixes within this initiative. Provider delivery/engagement measurement and sender-domain checks belong to todo 623, not visual rendering.
