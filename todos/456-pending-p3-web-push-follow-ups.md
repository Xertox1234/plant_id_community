---
status: pending
priority: p3
issue_id: "456"
tags: [web, backend, notifications, web-push]
dependencies: []
source_review: "PR #852 review round 1 (todo 413)"
source_finding: "non-blocking findings"
---

# Web Push follow-ups from the PR #852 review

## Problem

Todo 413 shipped browser (Web Push) notifications for forum events. Round 1
of the PR #852 review fixed the blocking findings. These did not block the
merge and were left for later:

1. **No `pushsubscriptionchange` handler in `web/public/sw.js`.** Firefox,
   and Chrome when a subscription expires, replace the endpoint. The server
   keeps the old one and is never told the new one, so notifications stop
   without any error. The worker has no `document.cookie`, so decide how it
   authenticates the re-subscribe: cookie-only auth, or a narrow endpoint.
2. **The settings UI's "on" state is local only.** `getBrowserPushState()`
   reads the browser's subscription and never checks the server's
   `is_active`. After the server deactivates a row (a 404/410 from the push
   service), the page still says "on". Reconcile it with
   `GET /api/v1/auth/me/push-notifications/`.
3. **Sends are sequential.** `send_forum_web_push_batch` makes one blocking
   HTTPS POST and one `mark_as_used()` UPDATE per subscription, in one task.
   A busy topic means hundreds of round trips back to back. Reuse one
   `requests.Session`, fan out (chunked subtasks or a small pool), and
   bulk-update `last_used` once.
4. **No real-browser coverage.** `src/serviceWorker.test.ts` runs `sw.js` in
   a node vm with a fake `self`. Add a Playwright spec (chromium + webkit)
   that registers the real worker, dispatches a synthetic push, and clicks
   the notification.
5. **Check the `/sw.js` cache headers on Cloudflare.** If Workers static
   assets serve it with a long `Cache-Control`, a worker fix rolls out
   slowly. Measure the live header. If it is long-lived, add a
   `Cache-Control: no-cache` rule for `/sw.js`.
6. **Info: redirects after the SSRF check.** The endpoint allowlist runs once,
   at subscribe time. pywebpush's `requests.post` follows redirects, so a
   redirect from an allowlisted push service is not re-checked. The risk is
   low, because every allowlisted host is a browser vendor's own
   infrastructure. Consider passing a session with `allow_redirects=False`
   when doing item 3.

## Acceptance Criteria

- [ ] Items 1–5 are done, or each is closed with a recorded reason.
- [ ] Item 6 is either addressed with item 3 or closed with a reason.

## Work Log

### 2026-09-27 - Filed from the PR #852 round-1 review

The django-drf reviewer, the react-typescript reviewer and the bundled
`/code-review` on PR #852 (todo 413) raised these. They are not blocking.
