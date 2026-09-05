---
status: pending
priority: p3
issue_id: "342"
tags: [forum, backend, package, web, flutter]
dependencies: []
---

# Quote-reply: real quote action + notification (block exists, feature doesn't)

## Problem

Todo 276 (PR #511) added a `quote` **block** to the composer and the
"quote/heading/code values escape at render time" contract — but there is no
"Quote this post" action anywhere. Users must hand-copy text into a
blockquote; the quoted author gets no notification. Verified 2026-09-04: the
only quote references in the web forum are the TipTap blockquote toolbar
(`TipTapEditor.tsx:345-349`); the package has only `blocks.BlockQuoteBlock`
(`wagtail_forum/blocks.py:25`) and no quote verb or relationship.

## Findings

- `wagtail_forum/models/notifications.py` — `NotificationVerb` has REPLY,
  MENTION, SOLUTION, MODERATION; no QUOTE (2026-09-04 backend catalog §6.6).
- `wagtail_forum/blocks.py:13-30` — `ForumBodyBlock` supports a `quote`
  block whose value is **plain text by contract**
  (`api/sanitize.py:7` docstring; test-pinned in
  `tests/api/test_topic_create.py:83-108`): consumers MUST escape at render
  time. Any structured quote (author/post reference) must extend this
  contract deliberately.
- No "-quote this post" affordance in `PostCard.tsx` or `post_card.dart`.

## Recommended Action

1. **Package (`wagtail_forum`):**
   - Add `NotificationVerb.QUOTE` + a `quoted_post` (nullable FK to `Post`)
      on `Notification`, reusing the existing fan-out path in
      `apps/forum_host/notifications.py` pattern (in-app first; push/email
      opt-ins follow the existing verb-gating).
   - Preferred block shape: keep the `quote` block **text** but introduce a
      package-level quote convention — e.g. a `quote` block paired with an
      optional `attribution` (post id + author) in a wrapper StructBlock, OR
      a new `PostQuoteBlock(StructBlock)` with `post`/`text` sub-blocks.
      Decide by honoring the existing escape contract: the serializer must
      still deliver render-safe values (`api/sanitize.py`, `_ForumBodyContract`
      in `api/serializers.py:842-987`).
   - Keep the quote link-or-id **server-validated**: on post create/edit,
      resolve quoted post ids, verify the topic is visible to the author and
      the quoted author isn't blocked (`Post.edit_block` /
      `solution_block` precedent — single-source the policy in models).
   - Respect existing caps: `MENTION_MAX_PER_POST`-style cap for quotes
      (`QUOTES_MAX_PER_POST`, default ~3) added to `conf.py` via
      `get_setting()`.
2. **Web:** "Quote" action in `PostCard` → prefills composer with the quote
   block; render quoted-post cards with a jump-to-post link (jump already
   exists, `ThreadDetailPage.tsx:290-326`).
3. **Flutter:** same action on `post_card.dart`; the quote renderer exists
   already (`forum_body_block.dart:35`).

## Technical Details

- Notification fan-out / visibility filtering:
  `wagtail_forum/notifications.py`, `wagtail_forum/api/notifications.py:1-142`
  (hidden/restricted topics + blocked authors already excluded — quote
  notifications must inherit both).
- Package config: `wagtail_forum/conf.py` (`get_setting` package default;
  host override via `ForumSettings`, `apps/forum_host/models.py:140-246`).
- Trust/spam: quote attribution must pass through the same `SpamCheckTask`
  workflow as the post body (`wagtail_forum/workflow.py:74-246`) — no
  separate trust path.

## Acceptance Criteria

- [ ] Package: structured quote (post ref + text) survives sanitize round-trip;
      quoted-post id validated server-side (invisible topic → rejected or
      stripped, decision recorded in Work Log)
- [ ] Quoting generates a QUOTE notification to the quoted author, subject to
      block/visibility rules (test-pinned)
- [ ] Web: one-click Quote action pre-fills composer; Flutter parity
- [ ] Answer-escape contract tests extended to the new quote shape

## Work Log

### 2026-09-04 - Filed

- Surfaced by the 2026-09-04 forum competitive assessment (smaller-misses
  item). Initial catalog claimed "quote-reply absent"; verified against todo
  276 / PR #511: the **block** landed, action + notification did not.
