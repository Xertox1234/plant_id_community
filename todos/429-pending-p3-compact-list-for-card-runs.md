---
status: pending
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

- [ ] Web: a body with 3 consecutive embeds renders 1 full card + 2 compact
      rows; a body with 1 embed, or 2 embeds separated by a paragraph,
      renders as today. Pinned by Vitest component tests.
- [ ] Web: clicking a video row replaces it with the sandboxed player; each
      row is a separately focusable element named "title, site".
- [ ] Mobile: same grouping, pinned by widget tests. Each row is its own
      semantics node with a tap action that calls `onOpenLink` with that
      row's URL.
- [ ] The card-type set is one constant per client; the todo 428 handoff
      (adding `link_preview`) is noted in 428 if 428 is still open.
- [ ] Checked visually at desktop and phone widths against the mockup.

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
