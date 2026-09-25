---
status: pending
priority: p3
issue_id: "437"
tags: [ops, email, railway]
dependencies: []
source_review: "todos/archive/416-completed-p3-digest-unsubscribe-and-one-click-post.md"
---

# Set API_PUBLIC_URL on Railway to turn on one-click unsubscribe

## Problem

Todo 416 shipped RFC 8058 one-click unsubscribe dark: emails carry
`List-Unsubscribe-Post` only when `API_PUBLIC_URL` (this API's public origin)
is set. It is not set in production, and `.railway/railway.ts` does not list
it. Gmail and Yahoo require one-click for bulk senders (above about 5,000
messages a day).

## Recommended Action

1. Owner: set `API_PUBLIC_URL=https://api.houseplant-md.com` on the `web`
   service (and `forum-prune-cron` if it ever sends mail), and add
   `API_PUBLIC_URL: preserve()` to its `env` in `.railway/railway.ts` so the
   IaC plan doesn't flag drift.
2. Send yourself a forum reply email and check its raw headers show
   `List-Unsubscribe: <https://api.houseplant-md.com/api/v1/auth/unsubscribe/one-click/?token=…>`
   and `List-Unsubscribe-Post: List-Unsubscribe=One-Click`.

## Acceptance Criteria

- [x] `API_PUBLIC_URL` is set in production and declared in `.railway/railway.ts`.
- [ ] A production reply email carries both one-click headers.

## Work Log

### 2026-09-24 - Filed from todo 416

Operator-gated: setting a Railway variable and merging a `.railway` edit are
the owner's.

### 2026-09-24 - API_PUBLIC_URL set on Railway

Set `API_PUBLIC_URL=https://api.houseplant-md.com` on the `plant_id_community`
service on 2026-09-24 (Railway MCP, owner approved). The `.railway/railway.ts`
declaration is in its own PR for the owner to merge. Remaining (owner): the
AC 2 check — a production reply email's raw headers show both one-click
headers.

### 2026-09-24 - AC 1 done; AC 2 checked up to the send, not on a received email

- **AC 1:** `API_PUBLIC_URL=https://api.houseplant-md.com` on Railway, declared
  in `.railway/railway.ts` (#828, Railway apply succeeded 2026-09-25T03:59Z).
- **Toward AC 2:** in a production shell, `unsubscribe_headers()` for a real user
  returned `List-Unsubscribe: <https://api.houseplant-md.com/api/v1/auth/unsubscribe/one-click/?token=…>`
  and `List-Unsubscribe-Post: List-Unsubscribe=One-Click`, and `send_email`
  passes that dict to `EmailMultiAlternatives(headers=...)` unchanged. The
  endpoint: `POST ?token=bogus` → 400, `GET` → 302 to the web page. Production
  mail is Django's SMTP backend to `smtp.resend.com:587`.
- **Not done:** a sent email's raw headers. The agent's attempt to send a test
  message to the owner over production SMTP was refused by the auto-mode
  permission classifier, so AC 2 stays open. Owner step (one minute): on the
  next forum reply or digest email, Gmail → "Show original", confirm both
  headers, record the date here, archive.
