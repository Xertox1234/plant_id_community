---
status: pending
priority: p3
issue_id: "429"
tags: [forum, web, mobile, design, embeds, link-preview]
dependencies: ["428"]
---

# Explore a better layout for posts with several video or link cards

## Problem

A post can hold up to 5 video embeds (`MAX_EMBED_URLS_PER_BODY`, todo 344)
and, once todo 428 lands, up to 5 link-preview cards. Every client renders
each card at full width, one below another, so a post with several links
becomes a long stack of large cards. The owner wants to explore a better
presentation. This is exploration, not a committed design. Raised
2026-09-24, deferred by the owner ("I will worry about that later").

## Findings

- Cards come from separate body blocks (`embed`, and `link_preview` after
  428), each rendered on its own: the web `ForumBodyRenderer` and the Flutter
  `forum_body_renderer.dart`. A grouped layout would group consecutive card
  blocks at render time. Nothing about how bodies are stored needs to change.

## Recommended Action

Explore it with the owner before building. Options to compare:

- **A horizontal carousel** of consecutive cards, which pages sideways.
- **A compact list:** a small thumbnail with title and site for each card,
  with the first card at full size.
- **A grid** (2 across on wide screens, 1 on phones).
- **Collapse after N:** show 2 cards, then a "Show 3 more" button.

Each option must keep what 424 and 398 fixed: every card is a separate
screen-reader element with a tap action, and swiping through a carousel
must not trap VoiceOver focus.

## Acceptance Criteria

- [ ] The owner picks a direction from mockups (web and mobile).
- [ ] That direction is filed as its own implementation todo, or this one is
      rewritten into one.

## Work Log

### 2026-09-24 - Filed at the owner's request, deferred

### 2026-09-24 - Owner: reopened; pick from mockups

The owner reopened this and wants to choose from mockups. A web page showing
the four layouts (carousel, compact list, grid, collapse-after-N) at web and
phone widths is being prepared; the owner's pick gets recorded here, then this
todo is rewritten into the implementation todo (AC 2).
