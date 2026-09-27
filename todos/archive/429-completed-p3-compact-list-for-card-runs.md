---
status: completed
priority: p3
issue_id: "429"
tags: [forum, web, mobile, design, embeds, link-preview]
dependencies: []
---

# Show runs of video/link cards as a compact list (first card full, rest as rows)

## Problem

A post can hold up to 5 video embeds (`MAX_EMBED_URLS_PER_BODY`, todo 344)
and, once todo 428 lands, up to 5 link-preview cards. Every client renders
each card at full width, one below another, so a post with several links
becomes a long stack of large cards.

**Decided by the owner 2026-09-25: option B, the compact list.** In a run of
consecutive cards the first keeps its full card; each card after it becomes a
compact row: a small thumbnail (about 72x48) beside the title and the site
name, on the same surface and border as the card. Mockups (web and phone):
<https://claude.ai/artifact/LSrH2iRvSGpPeuBy4nYW3k> (boards "B. Compact list").

## Findings

- Cards are separate body blocks, rendered one by one: web
  `web/src/components/StreamFieldRenderer.tsx` (`case 'embed'`, an inline
  sandboxed player) and Flutter
  `plant_community_mobile/lib/features/forum/widgets/forum_body_renderer.dart`
  (`_EmbedCard`, a thumbnail card that hands the URL to `onOpenLink`).
- Grouping is a render-time concern. Nothing about how bodies are stored
  changes, and there is no backend work.
- The embed envelope already carries everything a row needs: `url`, `title`,
  `thumbnail_url`, `provider_name` (`wagtail_forum/embeds.py`).

## Recommended Action

1. On each client, walk the body and group **runs of 2 or more consecutive
   card blocks**. A paragraph, image or other block between two cards ends
   the run. A lone card renders exactly as today.
2. Card block types: `embed` now. Keep the set in one named constant per
   client, so todo 428's `link_preview` joins it with a single entry. If 428
   has already landed when this is built, include `link_preview` now.
3. In a run: render the first block with today's full card, and each later
   block as a compact row (thumbnail, title, site). A row with no thumbnail
   shows a neutral placeholder tile; a blank envelope keeps today's
   "unavailable" placeholder.
4. What tapping a row does matches that platform's full card:
   - **Mobile:** `onOpenLink(url)`, like `_EmbedCard` (in-app browser, todo 424).
   - **Web, video row:** swap the row in place for today's sandboxed player
     (click-to-load), rather than loading every iframe up front. **Web, link
     row:** a normal link to the URL.
5. Accessibility, keeping what 424 and 398 fixed. Each row is its **own**
   screen-reader element with a tap action: a web `<a>`/`<button>` whose
   accessible name is "title, site"; Flutter `Semantics(button: true, label:
   ...)` with `onTap`. Rows are never merged into one node. The tap target
   is at least 44 px (web) / 48 dp (mobile) tall.

## Acceptance Criteria

- [x] Web: a body with 3 consecutive embeds renders 1 full card + 2 compact
      rows; a body with 1 embed, or 2 embeds separated by a paragraph,
      renders as today. Pinned by Vitest component tests. (`CompactCardRow.test.tsx`)
- [x] Web: clicking a video row replaces it with the sandboxed player; each
      row is a separately focusable element named "title, site". A link row's
      "site" is the short address from the URL; see the Work Log.
- [x] Mobile: same grouping, pinned by widget tests. Each row is its own
      semantics node with a tap action that calls `onOpenLink` with that
      row's URL. (`forum_card_runs_test.dart`)
- [x] The card-type set is one constant per client; the todo 428 handoff
      (adding `link_preview`) is noted in 428 if 428 is still open.
- [x] Checked visually at desktop and phone widths against the mockup
      (2026-09-26, see Work Log).

## Work Log

### 2026-09-24 - Filed at the owner's request, deferred

### 2026-09-24 - Owner: reopened; pick from mockups

The owner reopened this and wants to choose from mockups. A web page showing
the four layouts (carousel, compact list, grid, collapse-after-N) at web and
phone widths is being prepared; the owner's pick gets recorded here, then this
todo is rewritten into the implementation todo (AC 2).

### 2026-09-25 - Owner picked B (compact list); rewritten for implementation

The owner chose option B from the four mockups (carousel, compact list, grid,
collapse-after-N). AC 1 of the exploration is done; AC 2 is met by rewriting
this todo into the implementation above. Tap behavior per platform and the
web click-to-load player are the agent's defaults, which follow the existing
full-card behavior.

### 2026-09-26 - Completed (PR #849, P3 sweep)

- **Web.** `components/forum/cardRuns.ts` holds `CARD_BLOCK_TYPES` and
  `groupCardRuns`. `CompactCardRow.tsx` renders each later card. A video row is
  a `<button>` that swaps itself for the sandboxed player and moves focus to
  it. Other rows are `<a>` links described "Opens in a new tab". Each row is
  `min-h-11`, with a focus-visible outline and a lazy, no-referrer thumbnail
  that falls back to a neutral tile.
- **Mobile.** `forumCardBlockTypes`, `isForumCardBlock` and `_CompactCardRow`.
  Each row is one semantics node (`childrenCount` 0) with a tap that calls
  `onOpenLink`. Link rows keep the long-press sheet and both custom actions.
  Rows are at least 48 dp tall.
- **Deviation from the AC wording, for anti-spoofing** (review round 1): a
  link row's second line and label use the **short address** from the URL,
  not `og:site_name`. That is the todo 428 rule for the full card: a row
  must not claim a site it doesn't link to. Video rows use the provider.
  Mobile labels keep the full cards' "PROVIDER video:" and "Link:" prefixes.
- **Run membership matches across clients.** Only a card with a usable
  http(s) URL joins a run, so a row always renders and always has a
  destination. A null link card, or a blank or scheme-less embed, breaks a
  run.
- **Visual check (2026-09-26)** at :5174, against a local post (restored
  afterwards) with a paragraph, 3 embeds and a link card, in dark mode:
  - at 1280 px: 1 player and 3 rows, each 66 px tall;
  - at 390 px: titles truncate, with no horizontal overflow;
  - clicking a row loaded its player in place.

  A Flutter golden render at 390 dp, light and dark, showed the same
  layout. These checks predate the round-1 change that replaced a link
  row's site name with its address.
- **Verified:**
  - Vitest: 110 files, 1523 tests before the repairs; 13 card-run tests
    after.
  - `flutter test test/features/forum/`: 537 before; 127 widget tests after.
  - `check:classes` passes, and `flutter analyze` is clean.
  - Mutation-checked: grouping on both clients, focus, anti-spoofing on
    both, and the single-node assertion.
- **Reviews.**
  - Round 1: bundled `/code-review` (10 findings), react-typescript (6) and
    flutter-dart (11). Blocking findings were fixed in dd0449bd, and the
    coverage gaps closed in df272307.
  - Round 2: `/code-review` on the repairs found none.
  - Non-blocking items are filed as **todo 453**.
