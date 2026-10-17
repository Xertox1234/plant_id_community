---
status: pending
priority: p3
issue_id: "655"
tags: [forum, backend, mobile, link-preview]
dependencies: []
---

# A link on its own line never becomes a card when the post has other text

## Problem

A link posted on its own should become a preview card (todo 428). Today that
happens only when the link is the **whole post**. A link on its own line
between paragraphs of text stays a plain link, on web and on mobile. Both
clients send that line inside one `paragraph` block together with the
surrounding text, and the server cards only a paragraph whose entire text is
one URL. So a post can never get more than one card, the 5-card cap can't be
reached, and the mobile composer's "+N more" hint (todo 654) has nothing to
count.

## Findings

- **Server rule:** `_sole_url`
  (`backend/packages/wagtail_forum/wagtail_forum/api/sanitize.py:118`) reads
  a paragraph's text with every tag as a space, and returns `None` when that
  text contains any whitespace. `<p>a</p><p>url</p>` and `a<br>url` are
  therefore never candidates. `_convert_video_paragraphs` (`:152`) and
  `_convert_link_previews` (`:220`) both depend on it.
- **Web:** `docToBodyBlocks` (`web/src/utils/forumBody.ts:406`) splits out
  only images, quotes and **video** links (`embedUrlOf`). Every other
  paragraph, including a link on its own line, goes into one `paragraph`
  block as `<p>…</p><p>url</p><p>…</p>`.
- **Mobile:** `buildParagraphBody`
  (`plant_community_mobile/lib/features/forum/models/forum_body_block.dart:382`)
  sends the whole composer text as **one** `paragraph`, with lines joined by
  `<br>` (`generateForumRichHtml`).
- **Mobile edit round trip:** `ForumComposeArgs.edit`
  (`plant_community_mobile/lib/features/forum/screens/forum_composer_screen.dart:57`)
  pre-fills text only for a single-block body (one paragraph, or one card or
  embed). Anything else opens with `hasNonTextContent: true`, i.e. the "can't
  edit this here" warning. Once the server splits bodies, a mobile post like
  `text / url / text` is stored as three blocks, so **the server change
  without this fix would make those posts uneditable on mobile**. That's the
  same gate lesson as todo 428 slice C (`bodyBlocksToHtml` returning `''`).
- **Web edit round trip** should already hold:
  - `bodyBlocksToDoc` turns a `link_preview` back into a link paragraph
    (`linkParagraph`, `web/src/utils/forumBody.ts`);
  - `docToBodyBlocks` merges it back into the run;
  - the server splits it again, reusing the stored card with no fetch.

  Pin it with a test anyway.
- **Spam limit:** `HeuristicSpamBackend` refuses a post with more than
  `SPAM_MAX_LINKS` links (`backend/packages/wagtail_forum/wagtail_forum/spam/heuristic.py:21`).
  - The default is 3 (`conf.py:16`), overridable per site in the CMS
    (`spam_max_links`, `backend/apps/forum_host/models.py:208`).
  - The production LLM backend runs the heuristic first
    (`backend/apps/forum_host/spam.py:76`).
  - Cards count by URL (todo 428). So a post with 4 or 5 standalone links is
    refused before the 5-card cap matters.
- **Block limit:** `MAX_BODY_BLOCKS = 100` (`sanitize.py:45`) is checked on
  the submitted list (`:707`), before any split.

## Recommended Action

1. **Owner decision at triage: the spam link limit.** With the default of 3,
   a post can carry at most 3 cards. Either
   - (a) raise the package default `SPAM_MAX_LINKS` to 5, matching
     `MAX_LINK_PREVIEWS_PER_BODY`; or
   - (b) leave it at 3, so 3 is the real ceiling, and todo 654's hint caps
     there.

   Check the production CMS value of `spam_max_links` before deciding (owner
   hand-off; never read production from a worker).
2. **Server split, in `validate_forum_body`, before the video and card
   conversions.**
   - For each `paragraph` block, split its HTML at **top-level** `<p>`
     boundaries and `<br>` line breaks. Only a line that is a candidate
     becomes its own `paragraph` block: one sole `http(s)` URL token, not
     inside `<code>`/`<pre>`, `<li>`, or a blockquote. The runs of other
     lines stay together as paragraphs, with their markup intact.
   - A paragraph with **no** candidate line is left byte-for-byte unchanged,
     so existing posts and plain prose see no change in shape.
   - The video conversion then runs as now ("video wins"), then cards (cap 5,
     first distinct URLs), then auto-linking.
   - Check `MAX_BODY_BLOCKS` again **after** the split. Refuse with the same
     message rather than storing over 100 blocks.
   - Parse with the same HTML parser the module already uses; never split on
     a regex over raw markup.
3. **Mobile edit round trip, same PR (gate):** `ForumComposeArgs.edit`
   accepts a body made only of `paragraph`, `link_preview` and `embed`
   blocks. It rebuilds the composer text in body order: each paragraph
   through `parseForumRichHtmlToMarkup` (falling back to
   `plainTextFromParagraphHtml`), and each card or embed as its escaped URL
   on its own line. Saving unchanged must store the same body (cards reused,
   no fetch). Any other block type keeps today's `hasNonTextContent` warning.
4. Update the package README's "Link previews" contract section to describe
   the split.

## Technical Details

- Package boundary: everything server-side is in `wagtail_forum` (no
  `apps.forum_host` import). The fetcher hook is unchanged.
- Tests: package `api/tests` beside the todo 428 link-preview tests (fetcher
  faked, never the network), and Flutter tests in
  `plant_community_mobile/test/features/forum/`.
- Patterns: `docs/rules/wagtail.md` (StreamField), `backend/docs/patterns/domain/forum.md`.
- No migration (no block schema change).

## Acceptance Criteria

- [ ] The owner's spam-limit decision (1a or 1b) is recorded here with its
      date, and the code matches it.
- [ ] A body `<p>Intro</p><p>https://example.com/a</p><p>Outro</p>` is
      stored as paragraph / `link_preview` / paragraph. The same holds for
      the mobile shape `Intro<br>https://example.com/a<br>Outro`. Pinned by
      tests with the fetcher faked.
- [ ] Five link lines in one post give five cards and a sixth stays a
      tappable link (under the decided spam limit). A video line becomes an
      `embed`. Pinned by tests.
- [ ] A URL inside a sentence, a list item, `<code>`/`<pre>` or a blockquote
      is not split out. A paragraph with no candidate line is stored
      unchanged. Pinned by tests.
- [ ] A split that would pass `MAX_BODY_BLOCKS` is refused (400, the same
      message). Pinned by a test.
- [ ] Round trip: an unchanged re-save of a split post stores the same body
      with no fetch, from both the web shape (`bodyBlocksToDoc` →
      `docToBodyBlocks`) and the mobile shape (`ForumComposeArgs.edit` text →
      `buildParagraphBody`). Pinned by backend, Vitest and Flutter tests.
- [ ] Mobile: a body of paragraphs, cards and embeds opens fully editable,
      with no `hasNonTextContent` warning. Pinned by a widget or unit test.
- [ ] The README "Link previews" section describes the split.
- [ ] Full backend suite, web Vitest, Flutter forum tests and
      `flutter analyze` are green.

## Work Log

### 2026-10-17 - Filed while scoping todo 654

- Found while triaging todo 654: a card only ever appears when the whole post
  is one link, on both platforms, so todo 654's "+N more" hint could never
  show. The owner chose to fix this on the server ("Server, new todo"), so it
  covers web, mobile and API clients with one rule. Todo 654 depends on this
  todo.

## Notes

- P3 to match todo 654: readers already get a card for a lone link; this
  widens which links qualify.
- Already-stored posts are not rewritten. An old post is split the next time
  it's edited and saved, which is the intended result.
