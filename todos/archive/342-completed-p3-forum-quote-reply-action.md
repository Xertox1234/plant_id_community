---
status: completed
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

- [x] Package: structured quote (post ref + text) survives sanitize round-trip;
      quoted-post id validated server-side (invisible topic → rejected or
      stripped, decision recorded in Work Log)
- [x] Quoting generates a QUOTE notification to the quoted author, subject to
      block/visibility rules (test-pinned)
- [x] Web: one-click Quote action pre-fills composer; Flutter parity
- [x] Answer-escape contract tests extended to the new quote shape

## Work Log

### 2026-09-04 - Filed

- Surfaced by the 2026-09-04 forum competitive assessment (smaller-misses
  item). Initial catalog claimed "quote-reply absent"; verified against todo
  276 / PR #511: the **block** landed, action + notification did not.

### 2026-09-05 - Started by completing-todos skill (run 2026-09-05-1142)

- Picked up by automated workflow.

### 2026-09-05 - Package + host implemented (run 2026-09-05-1142)

Decisions:

- **Block shape:** a new `post_quote` StructBlock (`post` IntegerBlock,
  `text` TextBlock) beside the legacy free-form `quote` (migration 0034).
  `text` is plain text by the SAME escape contract (consumers escape at
  render; the API stores and returns it verbatim — extended contract test).
- **Server-validated on write, REJECTED not stripped** (recorded decision):
  the quoted post must be live on a live, visible board and its author not
  block-paired with the writer; missing, unpublished, restricted and
  blocked all get ONE generic 400 ("One of the quoted posts is not
  available.") so the endpoint is no oracle. Caps: `QUOTES_MAX_PER_POST`
  (3 distinct posts) and `QUOTE_MAX_CHARS` (1000) — README rows. The
  struct sub-value type check became per-child-block (IntegerBlock takes
  an int) instead of "all strings".
- **Resolved on read in one query per page** (`build_forum_quote_map`,
  like the image/embed maps; flatness-pinned 1 vs 3 posts × 2 quotes):
  envelope `{text, post_id, available, topic_id, author}`; a quoted post
  that went away renders its text with `available: false` and no
  attribution.
- **QUOTE notifications:** `NotificationVerb.QUOTE` + `Notification.quoted_post`
  (exposed as `quoted_post_id`); host fan-out mirrors mentions in BOTH
  handlers (reply and opening post): quoted authors are excluded from the
  reply recipients, a mention of the same person wins, blocked pairs and
  self-quotes notify nobody, push event `"quote"` (copy added, no email
  arm like mention).

Evidence:

```text
$ pytest test_post_quotes.py test_quote_notifications.py test_topic_create.py test_docs.py → 30 passed
$ manage.py makemigrations wagtail_forum → 0034 (quoted_post, verb choices, Post.body); manage.py check → no issues
$ pytest apps/forum_host/tests/test_signals.py test_notification_copy.py → 42 passed (no regression)
```

Full backend suite with the quote contract (alone, `--create-db`):

```text
2202 passed, 8 skipped, 5 warnings in 250.02s (0:04:10)
```

### 2026-09-05 - Review round 1 (backend): django-drf 7 findings, cross-cutting 6 — all repaired

- **HIGH (django) edit path re-validated stored quotes** → an author (or a
  moderator) could not save any change once a quoted post was unpublished
  or its author blocked them. Fixed like the image precedent (audit L21):
  the edit call site passes `existing_quote_ids`; only NEWLY added quotes
  must resolve (shape and caps still apply to all). New test drives keep /
  add-new-rejected / remove through PATCH. Mutation `new_ids = ids` → the
  test fails.
- **MEDIUM (django) quoted author lacked block/mute signals** → the envelope
  now carries `is_blocked` / `is_muted` for the viewer (bounded queries only
  for filtered viewers; anonymous and moderators constant False), mirroring
  `PostSerializer`. Test covers blocker / muter / anon; mutation (constant
  False) fails it.
- **MEDIUM (cross-cutting) dead `topic` join + avatar leg never exercised**
  → `select_related` trimmed to the author/avatar leg; the flat-count
  fixture gives the quoted author an avatar. Mutation (drop `__avatar`) →
  the pin goes red.
- **MEDIUM ×2 (cross-cutting) no edit-path test, no opening-post-via-API
  test** → both added (`test_editing_keeps_…`, `test_an_opening_post_can_
  quote_through_the_topic_create_api` incl. the rejected case).
- **LOW** magic `"quote"` → `NotificationVerb.QUOTE`; `plain_text_excerpt`
  gained the `post_quote` text (test + mutation); stale docstrings
  (`tasks.py`, `FORUM_BODY_SCHEMA` comment); `quoted_post_id` pinned
  `None` for a REPLY row. Bounded per-author `create_notifications` loop
  (≤ 3) left as is; edit-time fan-out limitation and the "quoter's excerpt"
  presentation rule documented in `forum.md` + a `docs/rules/api.md` bullet.

```text
$ pytest test_post_quotes.py → 15 passed (4 mutation checks each turned red, guards restored via cp)
```

Full backend suite after the round-1 repairs (alone, `--create-db`):

```text
2206 passed, 8 skipped, 5 warnings in 276.27s (0:04:36)
```

### 2026-09-05 - Review round 1 (Flutter): flutter-dart 7 findings — 6 repaired, 1 info (pre-existing cast convention)

- **MEDIUM same-topic "in topic" stacked a duplicate thread screen** →
  `currentTopicId` threaded through `ForumBodyRenderer` (thread screen →
  PostCard, and the edit-history sheet); link hidden when equal, attribution
  kept. Tests at renderer, PostCard and thread-screen levels.
- **MEDIUM `quotedPostId` never asserted** → new `forum_notification_test.dart`
  (round-trip + `asRead()`); mutation of the JSON key → 2 tests fail, restored via cp.
- **LOW fingerprint on quote removal untested** → test: submit with quote →
  400 → remove chip → resubmit → the two Idempotency-Keys differ.
- **LOW "gone" copy on any missing attribution** → notice only when
  `available == false`; defensive null author/topic renders neutral attribution.
- **LOW no Semantics** → `Semantics(container, label: 'Quote from <name|a member>')`.
- **LOW 403 mapping undocumented** → comment records the generic copy decision.
- Also wired the new backend `is_blocked` / `is_muted` flags: collapsed
  notice + "Show anyway" reveal reusing `PostCard._BlockedPlaceholder`'s
  affordance (no mute collapse existed in Flutter yet — blocked wins when both).

```text
$ flutter analyze → No issues found!
$ flutter test → 00:40 +636 ~3: All tests passed!
$ dart format --set-exit-if-changed (12 files) → 0 changed; no @riverpod file touched (no codegen)
```

### 2026-09-05 - Acceptance criteria 1, 2, 4 flipped (backend evidence)

- AC1 (package round-trip): `test_a_valid_quote_is_stored_and_read_as_a_safe_attribution_envelope`
  stores `{"post": id, "text": …}` verbatim and reads the resolved envelope;
  `test_editing_keeps_a_stored_quote_…` round-trips it through PATCH.
- AC2 (QUOTE notification with block/visibility rules, mention precedence):
  `apps/forum_host/tests/test_quote_notifications.py` — QUOTE not REPLY with
  `quoted_post_id`, blocked pair and self-quote notify nobody, mention wins.
- AC4 (escape contract extended): `test_quote_text_is_plain_text_by_contract_never_sanitized_or_rendered`
  stores and returns `<script>` verbatim; web + Flutter renderers assert text-only rendering.

```text
$ pytest test_post_quotes.py apps/forum_host/tests/test_quote_notifications.py … → 95 passed (with the signal/copy/search/recent suites)
```

### 2026-09-05 - Review round 1 (web): react-typescript 8 findings — 5 repaired, 3 info (2 pre-existing fixed anyway, 1 out of scope)

- **HIGH renderer ignored `is_blocked` / `is_muted`** → `PostQuoteBlock` child
  component with the PostCard-style placeholder ("Quote from a member you
  blocked/muted.") + "Show anyway" reveal; blocked wins. Mutation (collapse
  never renders) → 2 tests fail.
- **MEDIUM stale availability downgrade on re-edit** → `bodyBlocksToHtml`
  keeps `data-post-id` regardless of `available` (the server's
  `existing_quote_ids` carve-out makes the downgrade unnecessary and it was
  discarding the reference permanently). Mutation → the updated test fails.
- **MEDIUM identical announcement swallowed** → message varies per quote
  ("Quote of Ada's post added to your reply."); test quotes two posts in a row.
- **MEDIUM list lines collapsed by ProseMirror** → a single "\n" inside a
  quote paragraph renders as `<br>` and reads back as "\n" (unit + real
  TipTap round trip); mutation → 2 tests fail. Follow-up caught by the
  agent and fixed in the same round: a hard break in the SOURCE paragraph
  (`<p>a<br>b</p>`) was lifted as "ab" — `richTextParagraphs` now keeps line
  structure (test `keeps a hard line break inside a source paragraph`).
- LOW nested-blockquote-in-list detection stays top-level only (comment);
  INFO implicit-any fixture typed, unused `Editor` import dropped;
  `EditHistoryDialog` has no topic id in scope (left as is).

```text
$ npm run type-check → exit 0; eslint + prettier clean
$ npx vitest run → Test Files  96 passed (96)
      Tests  1225 passed (1225)
```

### 2026-09-05 - AC3 flipped (web + Flutter evidence)

- Web: `ThreadDetailPage.test.tsx` "Quote" pre-fills the composer with the
  `post_quote` HTML, remounts it focused and announces; `PostCard.test.tsx`
  shows the button only with `onQuote`. Flutter parity:
  `forum_thread_engagement_test.dart` Quote → composer chip "Water it less." /
  "— Bob B", sends `post_quote` with `post: 2`.

### 2026-09-05 - Completed by completing-todos skill (run 2026-09-05-1142)

- Verification: all 4 acceptance criteria passed (backend 2206, web 1225 passed (1225), Flutter 636).
- Review: 4 reviewers, 28 findings (1 high backend, 1 high web, 8 medium) — all actionable findings repaired in one round; infos documented.
- Codified: `docs/rules/{security,api,react,flutter}.md`, `backend/docs/patterns/domain/forum.md`,
  `web/docs/patterns/react-typescript.md`, `plant_community_mobile/docs/patterns/flutter-patterns.md`,
  `docs/LEARNINGS.md`, django/react/flutter reviewer checklists.
