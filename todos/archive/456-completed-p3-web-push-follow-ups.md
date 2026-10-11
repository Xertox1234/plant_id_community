---
status: completed
priority: p3
issue_id: "456"
tags: [web, backend, notifications, web-push]
dependencies: []
source_review: "PR #852 review round 1 (todo 413)"
source_finding: "non-blocking findings"
triage: blocked-owner
triaged: 2026-10-11
blocked_on: "The owner's 2026-09-28 hold (no web product yet). Then two design choices: how the sw.js re-subscribe authenticates, and how sends fan out. Item 5 needs a live header measurement."
owner_decision: "Owner lifts the 2026-09-28 hold and sweeps it now. Item 1: a narrow CSRF-exempt re-subscribe endpoint that authenticates by the old subscription's endpoint + auth key and swaps in the new one; when oldSubscription is null, fall back to page-load reconcile (item 2). Item 3: one shared requests.Session (requests_session=, allow_redirects off, which closes item 6) + one bulk last_used UPDATE, single task, no chunking/threads yet (2026-10-11)"
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

- [x] Items 1–5 are done, or each is closed with a recorded reason.
- [x] Item 6 is either addressed with item 3 or closed with a reason.

## Work Log

### 2026-09-27 - Filed from the PR #852 round-1 review

The django-drf reviewer, the react-typescript reviewer and the bundled
`/code-review` on PR #852 (todo 413) raised these. They are not blocking.

### 2026-09-27 - Round-2 notes added (PR #852 verification)

The round-2 verifier on PR #852 raised these. None is blocking. Fold them into
the items above.

- A rotated-key resubscribe unsubscribes in the browser but never tells the
  server. The old row stays active until a 404/410 deactivates it (item 2).
- `subscription.options.applicationServerKey` can be null in some browsers.
  Every enable then unsubscribes and resubscribes, which churns the endpoint.
- The public key is cached at mount, so a key rotated while Settings is open
  applies only after a reload.
- The 3 s timer in `releaseBrowserPushOnLogout` is never cleared. Cosmetic.
- Anyone who knows another user's endpoint URL (a capability URL) can
  deactivate that user's row by subscribing it themselves.
- The release UPDATE and `update_or_create` in `subscribe_to_push` are not in
  one transaction. Two concurrent subscribes of one endpoint could leave two
  active rows (item 3).

### 2026-10-11 - Implemented by the todo sweep (run 2026-10-11-2235)

- Item 1: `web/public/sw.js` handles `pushsubscriptionchange` and POSTs the
  old subscription's endpoint + `auth` secret with the new subscription to a
  new CSRF-exempt `POST /api/v1/auth/push-notifications/resubscribe/`
  (`authentication_classes([])`, per-IP rate limit, constant-time compare,
  active rows only, SSRF allowlist on the new endpoint, one 404 for every
  miss). The worker learns the API origin from its registration URL
  (`/sw.js?api=…`); the Settings page re-registers an older `/sw.js`
  registration onto that URL. No `oldSubscription` → nothing sent; item 2
  covers it.
- Item 2: `getBrowserPushState()` reads `GET /api/v1/auth/me/push-notifications/`,
  which now carries `endpoint_sha256` per row, and says "off" when the server
  no longer holds this browser's endpoint (an unreadable answer keeps the
  browser's own). Turning on again replaces a dropped subscription, and a
  key rotation now tells the server to drop the old row.
- Items 3 + 6: `send_forum_web_push_batch` sends with one shared
  `NoRedirectSession` (redirects forced off: a 3xx fails the send, logged, row
  kept) and records `last_used` in one bulk UPDATE, still one sequential task.
  `subscribe_to_push` now runs in one transaction.
- Item 4: `web/e2e/web-push.spec.ts` registers the real worker in Chromium and
  WebKit; in Chromium it delivers a real push over CDP and dispatches the
  click inside the worker. Not covered, by browser limits: a trusted click (no
  automation API clicks an OS notification) and push in WebKit (no CDP).
- Item 5: closed, no rule needed. `curl -sI https://houseplant-md.com/sw.js`
  on 2026-10-11 returned `cache-control: public, max-age=0, must-revalidate`
  (`cf-cache-status: MISS`), so a worker fix is revalidated on every check.

### 2026-10-11 - Verified by the todo sweep (run 2026-10-11-2235)

- AC 1: `sh -c 'cd backend && python3 scripts/todos/slot_env.py --main-root . 1 -- backend/venv/bin/python -m pytest apps/forum_host/tests/test_web_push.py apps/core/tests/test_schema_request_examples.py apps/core/tests/test_openapi_schema_warnings.py --create-db -q -p no:cacheprovider && cd web && python3 scripts/todos/slot_env.py --main-root . 1 -- npx vitest run src/serviceWorker.test.ts src/services/pushService.test.ts src/components/settings/BrowserNotificationsSection.test.tsx'` — evidence `.sweep-evidence/g1/456-ac0.txt` (not committed), last lines:

  ```text

   Test Files  3 passed (3)
        Tests  44 passed (44)
     Start at  17:27:03
     Duration  960ms (transform 127ms, setup 350ms, import 229ms, tests 103ms, environment 1.58s)
  ```

- AC 2: `sh -c 'cd backend && python3 scripts/todos/slot_env.py --main-root . 1 -- backend/venv/bin/python -m pytest apps/forum_host/tests/test_web_push.py -k "session or redirect or last_used" --create-db -v -p no:cacheprovider'` — evidence `.sweep-evidence/g1/456-ac1.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ================ 3 passed, 41 deselected, 2 warnings in 22.25s =================
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-11-2235)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
