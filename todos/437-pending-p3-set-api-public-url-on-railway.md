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

- [ ] `API_PUBLIC_URL` is set in production and declared in `.railway/railway.ts`.
- [ ] A production reply email carries both one-click headers.

## Work Log

### 2026-09-24 - Filed from todo 416

Operator-gated: setting a Railway variable and merging a `.railway` edit are
the owner's.
