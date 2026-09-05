---
status: pending
priority: p4
issue_id: "350"
tags: [forum, dm, package]
dependencies: ["339"]
---

# Group DMs — conversations with more than two members

## Problem

`Conversation` is a canonicalized 1:1 pair by design
(`wagtail_forum/models/messages.py:1-92`). Regional seed swaps, club
committees, and moderator→ambassador coordination all want small group
threads. Both Discourse and NodeBB treat group messages as core.

## Findings

- The 1:1 canonicalization (probably a normalized `(user_a, user_b)` pair
  with an ordering constraint) is exactly the schema that makes group
  retrofitting breaking — `wagtail_forum/models/messages.py`.
- Block semantics get harder: in a group, does one block eject the blockee,
  filter their messages for the blocker, or prevent group formation?
- Depends on 339: no UI exists even for 1:1, so group DMs have no surface
  to extend until that lands.

## Recommended Action

**Do not** retrofit groups onto the current `Conversation` row. Preferred:

1. **Package (`wagtail_forum`):** add `ConversationParticipant` M2M-through
   model on `Conversation`; keep the 1:1 path as the degenerate case and
   migrate existing pairs to two participants each. A `kind` field
   (`direct`/`group`) lets direct chats keep canonical-pair dedup while
   groups dedup only on explicit idempotency keys.
2. Group policies to decide and record: max participants (suggest ~8, via
   `get_setting`), add/remove members, who can add members (creator only?),
   block interaction (suggest: DM send blocked if ANY participant blocks or
   is blocked by the sender — conservative).
3. Spam surface widens (bulk invites) — extend `DEFAULT_FORUM_RATELIMITS`
   with a `dm_group_create` bucket.
4. UI lands after 339: group creation from the new messages screen.

## Technical Details

- Base implementation: `wagtail_forum/api/direct_messages.py:1-356`,
  `wagtail_forum/models/messages.py:1-92`.
- Notification behavior for group replies: default notify all participants
  (batched push per `send_forum_push_batch` precedent).
- Keep per-pair canonicalization tests from todo 319 passing for `direct`.

## Acceptance Criteria

- [ ] Group conversations creatable via API with participant model +
      migration of existing pairs (no data loss; test-pinned)
- [ ] Block policy decision recorded + enforced (test-pinned)
- [ ] Rate limit on group creation
- [ ] Web + Flutter group UI (after 339)

## Work Log

### 2026-09-04 - Filed

- Surfaced by the 2026-09-04 forum competitive assessment (smaller-misses:
  group DMs). P4 and dependency-gated on 339 — the voluntary defer.
