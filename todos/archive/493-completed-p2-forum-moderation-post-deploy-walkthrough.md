---
status: completed
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

- [x] A walkthrough from the owner's point of view: a trust-0 test account posts from the
      app, a moderator approves it once at CMS Reports > Pending forum content, and the
      thread shows up complete (title and body) in the app. Record the date and what you
      saw.

## Work Log

### 2026-10-25 - Walkthrough done on the iOS simulator against prod

- Setup: app built from main (`flutter run --dart-define-from-file=.env.production`)
  on the iPhone 17 Pro simulator (iOS 26.5), signed in as the prod sim test account
  "Sim Test" (william.tower+simtest). The account showed trust **Basic (1)**, not 0.
  Both are below the auto-publish level, so the post takes the same path (the spam
  screen, then pending if flagged).
- Finding: prod Forum settings had **Auto-publish from trust level = Basic**, so trust-1
  accounts skipped the spam screen and moderation entirely. Two test topics ("How often
  should I water a snake plant in winter?" and "Moderation walk through test: link-heavy
  topic", the second with six links) published at once. The owner set it to **Member**
  (the code default, `TRUST_AUTOPUBLISH_LEVEL = 2`) on 2026-10-25. Spam max links is
  inherited at 5.
- By design, a below-auto-publish author's *clean* topic still goes live without a
  moderator (`SpamCheckTask` approves clean content on the first screen). Only content
  the spam screen flags reaches Pending forum content. So the walkthrough post had six
  links to trip `SPAM_MAX_LINKS`.
- Walkthrough: posted "Todo 493 held-topic check" (six `example.com` links) in Care &
  problems. The composer showed "Your topic was submitted and is awaiting moderation.
  It will appear once approved." The topic was absent from the board list. The owner
  approved it once at CMS > Pending forum content. After a refresh, the board listed it,
  and the thread opened complete: title in the header, the full body with all six links
  rendered, author "Sim Test · Basic", Reply enabled.
