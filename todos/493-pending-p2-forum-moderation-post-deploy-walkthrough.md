---
status: pending
priority: p2
issue_id: "493"
tags: [forum, moderation, owner]
dependencies: []
---

# Forum moderation: owner walkthrough after 423 deploys

## Problem

Todo 423 changed how forum moderation works. Superusers and forum moderators (the
`publish_post` permission) now skip moderation. A new CMS page, Reports > Pending forum
content, approves a topic and its opening post together. The tests cover each piece. Only
the owner can check the whole flow end to end in the app, and the app talks to the
deployed API, so the check has to wait until 423 is live. The criterion moved here from 423
(re-pointed 2026-09-28).

## Acceptance Criteria

- [ ] A walkthrough from the owner's point of view: a trust-0 test account posts from the
      app, a moderator approves it once at CMS Reports > Pending forum content, and the
      thread shows up complete (title and body) in the app. Record the date and what you
      saw.

## Work Log
