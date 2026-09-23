---
status: pending
priority: p3
issue_id: "416"
tags: [backend, email, forum]
dependencies: []
source_review: "todos/408-pending-p2-email-unsubscribe-signed-token-and-pages.md"
source_finding: "follow-up filed 2026-09-23"
---

# Give the forum digest an unsubscribe link, and add one-click unsubscribe

## Problem

Todo 408 built signed unsubscribe links for the one email `EmailService` sends
today, the forum reply notification. Two gaps remain:

- **The weekly forum digest has no unsubscribe link.** It is sent by the
  package (`wagtail_forum/digest.py`) from its own templates, not through
  `EmailService`, so it gets no `unsubscribe_url` and no `List-Unsubscribe`
  header.
- **No RFC 8058 one-click unsubscribe.** Todo 408 sends
  `List-Unsubscribe: <https://…/unsubscribe?token=…>`, which opens the web
  page. Gmail and Yahoo require `List-Unsubscribe-Post: List-Unsubscribe=One-Click`
  for bulk senders (above about 5,000 messages a day). That needs a URL on the
  **API** origin that accepts a bare POST, and the backend has no setting for
  its own public origin (`SITE_URL` is the web app's).

## Findings

- `apps/users/email_unsubscribe.py` has a `LISTS` registry. A digest list would
  set `ForumProfile.digest_frequency` to off, which the Settings page's
  "Email digest" select can turn back on.
- The reply email's HTML body links "Unsubscribe from Topic" to
  `{{ topic_url }}#unsubscribe` (`templates/emails/forum_reply.html:50`). Check
  that the SPA topic page does something with that fragment. If it doesn't,
  point the link at the topic itself and say "unfollow".

## Recommended Action

1. Register a `forum_digest` list. Have the host shadow the package's digest
   templates, or add a context hook, so the digest gets a signed link and the
   header.
2. For one-click: add a backend public-origin setting (`API_PUBLIC_URL`), a
   `POST` endpoint that takes the token from the query string, and the
   `List-Unsubscribe-Post` header. Add the new variable to `.railway/railway.ts`.

## Technical Details

- `backend/packages/wagtail_forum/wagtail_forum/digest.py`
- `backend/apps/users/email_unsubscribe.py`
- `backend/apps/core/services/email_service.py` (`UNSUBSCRIBE_LISTS`, headers)
- RFC 8058; RFC 2369

## Acceptance Criteria

- [ ] A digest email carries a signed unsubscribe link that turns the digest off (test).
- [ ] Emails carry `List-Unsubscribe-Post: List-Unsubscribe=One-Click`, and a
      bare POST to the header's URL unsubscribes (test).

## Work Log

### 2026-09-23 - Filed from todo 408

Left out of todo 408 to keep it to the reply email, the only live
`EmailService` path.
