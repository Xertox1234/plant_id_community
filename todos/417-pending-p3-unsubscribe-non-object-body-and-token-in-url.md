---
status: pending
priority: p3
issue_id: "417"
tags: [backend, email, users, security]
dependencies: []
source_review: "todos/archive/408-completed-p2-email-unsubscribe-signed-token-and-pages.md"
source_finding: "PR #802 code review, non-blocking 1 and 2"
---

# Unsubscribe API: reject non-object bodies with a 400, and correct the token-exposure comment

## Problem

The bundled `/code-review` of PR #802 (todo 408) found two non-blocking issues
in the new unsubscribe endpoints.

## Findings

1. **A non-object JSON body returns a 500.**
   `apps/users/email_preferences_views.py` calls `request.data.get("token")` in
   both `email_unsubscribe_check` and `email_unsubscribe`. If the JSON body is
   an array or a bare string, DRF parses it to a `list` or `str`, `.get`
   raises `AttributeError`, and the endpoint returns a 500. This needs no
   token at all, and every hit creates a Sentry event. The per-IP rate limit
   (30/h) caps how often it happens but does not stop it.
2. **A comment overstates what POST protects.** The comment above the views
   says POST "keeps the token out of access logs". That holds only for the
   API. The email link is a GET to `https://houseplant-md.com/unsubscribe?token=…`,
   so the token lands in the web host's logs and in browser history. The
   token is also signed, not encrypted, so the UUID it carries is readable.
   Anyone who sees the URL can unsubscribe that user from reply emails for up
   to 90 days; the user can turn it back on in Settings.

## Recommended Action

1. Treat any body that is not a `dict` as `invalid` (400). Add a test that
   POSTs `[]` and `"x"` to both endpoints.
2. Rewrite the comment to state what is actually exposed and why it is
   accepted: low impact, the user can undo it, and the link expires.
   Optionally, have the page call `history.replaceState` to remove `?token=`
   from the URL once the token has been read.

## Technical Details

- `backend/apps/users/email_preferences_views.py`
- `backend/apps/users/tests/test_email_unsubscribe.py`
- `web/src/pages/UnsubscribePage.tsx`

## Acceptance Criteria

- [ ] POSTing a JSON array or string body to either endpoint returns 400 `invalid` (test).
- [ ] The comment matches the actual exposure.

## Work Log

### 2026-09-23 - Filed from PR #802 review

Non-blocking under the two-round review budget. The third finding (not
RFC 8058 one-click) is already todo 416.
