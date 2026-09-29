---
status: completed
priority: p3
issue_id: "437"
tags: [ops, email, railway]
dependencies: []
source_review: "todos/archive/416-completed-p3-digest-unsubscribe-and-one-click-post.md"
triage: blocked-prod
triaged: 2026-09-28
blocked_on: "Owner checks the raw headers of a received production forum reply or digest email (Gmail \"Show original\")"
owner_decision: "Owner confirmed on 2026-09-28 that the raw headers of a production reply/digest email show List-Unsubscribe (api.houseplant-md.com one-click URL) and List-Unsubscribe-Post"
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
- [x] A production reply email carries both one-click headers. (owner-confirmed
      2026-09-28: asked whether the raw headers of a recent production reply or
      digest email show List-Unsubscribe with the api.houseplant-md.com one-click
      URL and List-Unsubscribe-Post, the owner answered "Yes, both present")

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

### 2026-09-28 - Implemented by the todo sweep (run 2026-09-28-2018)

- AC 2 (a production reply email carries both one-click headers) was the
  owner's check. The owner answered it in this run's Decide stage, recorded in
  the frontmatter by the triage PR: "Owner confirmed on 2026-09-28 that the raw
  headers of a production reply/digest email show List-Unsubscribe
  (api.houseplant-md.com one-click URL) and List-Unsubscribe-Post".
- No code or `.railway/` change. AC 2 is an external, owner-only prod check:
  the repo cannot prove the headers, so the sweep leaves it for Land to settle
  from the recorded owner confirmation.
- Nothing was sent or read in production by the sweep.

### 2026-09-29 - Criterion 2 ticked by hand from the owner's confirmation

- `land.py flip-acs` flips a box only with a worker pass, verifier agreement and
  an evidence file, so an owner-only check came back blocked (todo 492 finding 1).
  The main session ticked it with the owner's recorded answer, quoted on the box.

### 2026-09-29 - Completed by the todo sweep (run 2026-09-28-2018)

- Archived by `land.py archive`; review is on the PR.
