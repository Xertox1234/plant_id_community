---
status: pending
priority: p4
issue_id: "434"
tags: [web, backend, blog, observability]
dependencies: []
source_review: "PR #817"
---

# Follow-ups from moving profile/notification services onto apiClient (todo 407)

## Problem

The bundled `/code-review` of PR #817 raised these as non-blocking.

## Findings

- **Sentry noise from unread-count polling.** `UnreadNotificationsContext`
  polls every 30s per tab. The old fetch path failed silently; now every
  failure goes through `apiClient`'s response interceptor, which calls
  `logger.error('HTTP error')` (a Sentry event in production). A backend
  blip, or an expired cookie (apiClient has no 401 refresh), produces one
  event per tab every 30s. Give polling calls a way to opt out of that log.
- **Preview expiry lives in the viewset, not at the token source.**
  `BlogPostPreviewAPIViewSet` unsigns with `max_age`, then the library
  unsigns again without it. Another caller of
  `BlogPostPage.get_page_from_preview_token` would get tokens that never
  expire. Overriding that method on the model fixes both.
- **Two near-identical AxiosError → Error translators**
  (`profileService.toProfileError`, `notificationService.toNotificationError`)
  with different fallback strings. Share one next to `httpClient`.
- **Network/timeout errors show axios text** ("Network Error", "timeout of
  30000ms exceeded") in the profile banner instead of the page's fallback.

## Acceptance Criteria

- [ ] Each finding is fixed with a test, or declined with a reason.

## Work Log

### 2026-09-24 - Filed from PR #817 review round 1
