---
status: pending
priority: p3
issue_id: "413"
tags: [backend, web, notifications]
dependencies: []
source_review: "todos/archive/405-completed-p3-backend-endpoints-no-client-triage.md"
source_finding: "owner decision 2026-09-23"
---

# Wire up browser (web) push notifications (`me/push-notifications/*`)

## Problem

`me/push-notifications/*` (3 routes) stores `PushSubscription` rows, but
`pywebpush` is not in `requirements.txt`. `users/services.py:14-60` degrades to
a no-op, so nothing can ever send. Mobile push is FCM and works separately. The
owner decided (todo 405) to wire web push up.

## Findings

Evidence is recorded in todo 405's 2026-09-23 Work Log. It came from a
`get_resolver()` route walk, client greps, and an adversarial verifier that ran
the endpoints against a test DB.

## Recommended Action

1. Add `pywebpush`, run a dependency audit, and generate VAPID keys (Railway
   secrets; never commit them).
2. Add a service worker and a permission prompt on the web, and subscribe via
   the endpoint.
3. Send forum notifications (the same events as FCM) to web subscribers.

## Technical Details

See the file references above, and todo 405's Work Log.

## Acceptance Criteria

- [ ] A subscribed browser receives a forum notification. Record the date and what was observed.
- [x] The VAPID private key lives only in Railway and `.env`. (completed 2026-09-24)

## Work Log

### 2026-09-23 - Filed from todo 405

The owner decided, during the endpoint triage, to wire this up rather than
remove it.

### 2026-09-24 - Owner action needed: VAPID keys

Everything but the keys is sweep work. Owner step: generate a VAPID key pair in
your own terminal (NOT with the `!` prefix, so the private key never enters a
transcript), e.g. `npx web-push generate-vapid-keys`, and set
`VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` on the `plant_id_community` Railway
service and in `backend/.env`. Then this is ready for a sweep.

### 2026-09-24 - VAPID keys generated and set (owner gate removed)

A P-256 key pair was generated locally by a script that never printed the
private key. Both halves are set on the `plant_id_community` Railway service
(read back: `VAPID_PRIVATE_KEY` 43 chars, `VAPID_PUBLIC_KEY` 87 chars; raw
base64url, the format `npx web-push generate-vapid-keys` emits and
`py_vapid.Vapid.from_string` accepts) and in `backend/.env` (gitignored).
Declared `preserve()` in `.railway/railway.ts` (#830). Public key:
`BLrbiiidfpiAWj4ZHexQggpVCJue5b5tIjZ9KsgobEuNVz4wwNxPKsLmqHB1ANm31--xeXyulD-js65NgCr17G4`.

**Sweep notes, found while doing this:**

- `settings.py` reads NO `VAPID_*` value today. `apps/users/services.py` does
  `getattr(settings, "VAPID_PRIVATE_KEY", None)`, so setting the env var alone
  changes nothing: add `VAPID_PRIVATE_KEY` / `VAPID_PUBLIC_KEY = config(..., default="")`.
- `VAPID_CLAIMS_EMAIL` defaults to `admin@plantcommunity.com`, the old domain.
  Default it to `DEFAULT_FROM_EMAIL` instead.

Ready for a sweep.
