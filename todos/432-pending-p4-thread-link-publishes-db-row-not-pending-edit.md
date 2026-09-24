---
status: pending
priority: p4
issue_id: "432"
tags: [forum, backend, moderation]
dependencies: []
source_review: "PR #815"
---

# Approving a topic publishes its opening post's DB row, not a pending edit

## Problem

Todo 422's forward link (`signals._publish_counterpart`, topic → never-published
opening post) publishes `obj.save_revision()`, a revision built from the post's
DB row. If the author edited the opening post while it was still pending, that
edit exists only as a revision: `submit_edit_for_moderation` never writes the
row. So the ORIGINAL body goes live when a moderator approves the topic, and
publishing cancels the edit's workflow state.

## Findings

- Raised as non-blocking by the round-2 review of PR #815.
- Narrow: it needs an edit to a post that was never published.

## Recommended Action

For the post side, publish `opening.get_latest_revision()` when it is newer
than the row, else `save_revision()`. Keep `save_revision()` for the topic
side: its row carries freshly recounted counters that a stale revision would
overwrite (see the todo 422 work log).

## Acceptance Criteria

- [ ] Test: pending opening post, author edits it (revision only), moderator
      publishes the topic → the EDITED body is live.

## Work Log

### 2026-09-24 - Filed from PR #815 round 2
