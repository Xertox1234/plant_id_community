---
status: completed
priority: p3
issue_id: "655"
tags: [forum, backend, mobile, link-preview]
dependencies: []
triage: ready
triaged: 2026-10-17
owner_decision: "1a: raise the package default SPAM_MAX_LINKS to 5, matching MAX_LINK_PREVIEWS_PER_BODY; a prod CMS spam_max_links override is the owner's to raise (2026-10-17)"
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

- [x] The owner's spam-limit decision (1a or 1b) is recorded here with its
      date, and the code matches it.
- [x] A body `<p>Intro</p><p>https://example.com/a</p><p>Outro</p>` is
      stored as paragraph / `link_preview` / paragraph. The same holds for
      the mobile shape `Intro<br>https://example.com/a<br>Outro`. Pinned by
      tests with the fetcher faked.
- [x] Five link lines in one post give five cards and a sixth stays a
      tappable link (under the decided spam limit). A video line becomes an
      `embed`. Pinned by tests.
- [x] A URL inside a sentence, a list item, `<code>`/`<pre>` or a blockquote
      is not split out. A paragraph with no candidate line is stored
      unchanged. Pinned by tests.
- [x] A split that would pass `MAX_BODY_BLOCKS` is refused (400, the same
      message). Pinned by a test.
- [x] Round trip: an unchanged re-save of a split post stores the same body
      with no fetch, from both the web shape (`bodyBlocksToDoc` →
      `docToBodyBlocks`) and the mobile shape (`ForumComposeArgs.edit` text →
      `buildParagraphBody`). Pinned by backend, Vitest and Flutter tests.
- [x] Mobile: a body of paragraphs, cards and embeds opens fully editable,
      with no `hasNonTextContent` warning. Pinned by a widget or unit test.
- [x] The README "Link previews" section describes the split.
- [x] Full backend suite, web Vitest, Flutter forum tests and
      `flutter analyze` are green.

## Work Log

### 2026-10-17 - Filed while scoping todo 654

- Found while triaging todo 654: a card only ever appears when the whole post
  is one link, on both platforms, so todo 654's "+N more" hint could never
  show. The owner chose to fix this on the server ("Server, new todo"), so it
  covers web, mobile and API clients with one rule. Todo 654 depends on this
  todo.

### 2026-10-17 - Implemented by the todo sweep (run 2026-10-17-1622)

- Owner decision 1a (2026-10-17, frontmatter): the package default
  `SPAM_MAX_LINKS` is now 5, matching `MAX_LINK_PREVIEWS_PER_BODY`
  (`backend/packages/wagtail_forum/wagtail_forum/conf.py`, README). The prod
  CMS `spam_max_links` override stays the owner's to raise (todo 656).
- `validate_forum_body` now splits each paragraph at top-level `<p>` and
  `<br>` lines before the video and card conversions
  (`_split_link_paragraphs` in `wagtail_forum/api/sanitize.py`, an
  `HTMLParser` over the nh3-cleaned HTML). Only a line that is one card-able
  URL becomes its own paragraph; lists, code, `<pre>` and blockquotes are
  never split; a paragraph with no link line is returned as the same object;
  `MAX_BODY_BLOCKS` is checked again after the split.
- Mobile: `ForumComposeArgs.edit` accepts any body of paragraphs, cards and
  embeds and rebuilds the text in body order, so a split post stays
  editable. Web needed no code change; its round trip is pinned in
  `web/src/utils/forumBody.test.ts`.
- Tests changed for the new behaviour: 15 spam fixtures went from 5 (or 4)
  links to 6; three `test_embed_autoconvert.py` cases that expected a
  multi-line video post to stay one paragraph moved to a new test of the
  split; two Flutter tests that expected "paragraph + card/embed" to warn now
  use a heading.

### 2026-10-17 - Verified by the todo sweep (run 2026-10-17-1622)

- AC 1: `grep -n 'owner_decision' todos/archive/655-completed-p3-split-link-lines-into-card-paragraphs.md && grep -n -B4 'SPAM_MAX_LINKS' backend/packages/wagtail_forum/wagtail_forum/conf.py && grep -n 'WAGTAILFORUM_SPAM_MAX_LINKS' backend/packages/wagtail_forum/README.md && cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 2 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_spam.py -k default_limit --create-db -q -p no:cacheprovider` — evidence `.sweep-evidence/g2/655-ac0.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ================= 1 passed, 14 deselected, 2 warnings in 0.29s =================
  ```

- AC 2: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 2 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_link_previews.py -k 655_a_link_line_between_text --create-db -q -p no:cacheprovider` — evidence `.sweep-evidence/g2/655-ac1.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ================ 3 passed, 133 deselected, 3 warnings in 20.54s ================
  ```

- AC 3: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 2 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_link_previews.py -k '655_five_link_lines or 655_a_sixth_link_line' --create-db -q -p no:cacheprovider && cd . && python3 ../scripts/todos/slot_env.py --main-root .. 2 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_embed_autoconvert.py -k video_link_on_its_own_line --create-db -q -p no:cacheprovider` — evidence `.sweep-evidence/g2/655-ac2.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ================ 3 passed, 17 deselected, 3 warnings in 19.60s =================
  ```

- AC 4: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 2 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_link_previews.py -k '655_a_url_in_a_sentence or 655_a_paragraph_with_no_link_line or 655_the_first_piece' --create-db -q -p no:cacheprovider` — evidence `.sweep-evidence/g2/655-ac3.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  =============== 18 passed, 118 deselected, 3 warnings in 22.85s ================
  ```

- AC 5: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 2 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_link_previews.py -k 655_a_split_past_the_block_cap --create-db -q -p no:cacheprovider` — evidence `.sweep-evidence/g2/655-ac4.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ================ 1 passed, 135 deselected, 3 warnings in 42.72s ================
  ```

- AC 6: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 2 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_link_previews.py -k 655_an_unchanged_resave --create-db -q -p no:cacheprovider && cd ../web && npx vitest --run src/utils/forumBody.test.ts -t 'todo 655' && cd ../plant_community_mobile && flutter test test/features/forum/forum_composer_link_preview_test.dart --plain-name 'saving it unchanged'` — evidence `.sweep-evidence/g2/655-ac5.txt` (not committed), last lines:

  ```text
  143 packages have newer versions incompatible with dependency constraints.
  Try `flutter pub outdated` for more information.
  00:00 +0: loading plant_community_mobile/test/features/forum/forum_composer_link_preview_test.dart
  00:00 +0: a post the server split into paragraphs and cards (todo 655) saving it unchanged sends the lines the server splits back into the same blocks
  00:00 +1: All tests passed!
  ```

- AC 7: `cd plant_community_mobile && flutter test test/features/forum/forum_composer_link_preview_test.dart --plain-name 'a post the server split into paragraphs and cards'` — evidence `.sweep-evidence/g2/655-ac6.txt` (not committed), last lines:

  ```text
  00:00 +4: a post the server split into paragraphs and cards (todo 655) an image among them still warns
  00:00 +5: a post the server split into paragraphs and cards (todo 655) markup outside the grammar among them still warns
  00:00 +6: a post the server split into paragraphs and cards (todo 655) a card with no usable link among them still warns
  00:00 +7: a post the server split into paragraphs and cards (todo 655) opens in the composer with no warning, and its card is previewed
  00:00 +8: All tests passed!
  ```

- AC 8: `grep -n -A20 'A link on its own line is split out first' backend/packages/wagtail_forum/README.md` — evidence `.sweep-evidence/g2/655-ac7.txt` (not committed), last lines:

  ```text
  583-  edited and saved. A client resending a split post, whether merged back
  584-  into one paragraph (the web editor) or as `<br>`-joined lines (the mobile
  585-  composer), gets the same body back, its cards reused with no fetch.
  586-  `WAGTAILFORUM_SPAM_MAX_LINKS` defaults to `5` to match the card cap, since
  587-  every card counts as one link.
  ```

- AC 9: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 2 -- venv/bin/python -m pytest --create-db -q -p no:cacheprovider && cd ../web && npx vitest --run && cd ../plant_community_mobile && flutter test test/features/forum && flutter analyze` — evidence `.sweep-evidence/g2/655-ac8.txt` (not committed), last lines:

  ```text
  Got dependencies!
  143 packages have newer versions incompatible with dependency constraints.
  Try `flutter pub outdated` for more information.
  Analyzing plant_community_mobile...
  No issues found! (ran in 2.1s)
  ```

### 2026-10-17 - Completed by the todo sweep (run 2026-10-17-1622)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-10-17 - Repaired by the todo sweep (run 2026-10-17-1622)

- Round-1 review (medium, regression): a legacy body of one paragraph with
  101 URL lines, or about 50 link lines between text, saved on main as one
  block but 400'd after the split ("too many blocks"), so it could not be
  edited at all.
- `_split_link_paragraphs` (`backend/packages/wagtail_forum/wagtail_forum/api/sanitize.py`)
  now splits out only link lines that can still become a card or embed: the
  first `MAX_LINK_PREVIEWS_PER_BODY` distinct card URLs and the first
  `MAX_EMBED_URLS_PER_BODY` distinct video URLs, counting the body's own
  cards and embeds first. Repeats and links past the cap stay lines of
  their run, so the split adds only a handful of blocks.
- The post-split `MAX_BODY_BLOCKS` check (AC 5) is kept: 99 paragraphs plus
  one that splits into three is still refused. New tests pin a wall of 101
  link lines and 50 interleaved link lines saving with five cards, and the
  repeat/over-cap rule; the README "Link previews" section says so.

## Notes

- P3 to match todo 654: readers already get a card for a lone link; this
  widens which links qualify.
- Already-stored posts are not rewritten. An old post is split the next time
  it's edited and saved, which is the intended result.
