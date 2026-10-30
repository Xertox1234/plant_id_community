---
status: pending
priority: p4
issue_id: "681"
tags: [forum, forum-categories, web, backend]
dependencies: ["669"]
triage: needs-design
triaged: 2026-10-29
blocked_on: "Theme variant list + relation to 669's colour field undecided; 669 must land first"
owner_decision: "owner question at triage; skipped per overnight orders (2026-10-29)"
---

# Forum categories slice 15: per-forum theme override

## Problem

phpBB can give one forum its own style. With a single Canopy design system this means a constrained accent/theme override, not arbitrary CSS.

## Findings

- `docs/superpowers/specs/2026-10-28-forum-categories-design.md` §2 (phpBB forum_style).
- Source: owner request + phpBB/Discourse research, 2026-10-28 (Claude session).

## Recommended Action

1. Field `theme` from a fixed list of Canopy-safe variants; web applies it as a token scope on the forum and thread pages.

## Technical Details

- `web/docs/patterns/tailwind.md`, Canopy tokens.
- Design: `docs/superpowers/specs/2026-10-28-forum-categories-design.md`. Web only — no Flutter changes.

## Acceptance Criteria

- [ ] Test: only listed theme values are accepted.
- [ ] Web Vitest: the forum page applies the theme scope; contrast checks pass in light and dark.

## Work Log

### 2026-10-28 - Filed

- Filed from the forum-categories research session (owner decisions in the design spec §1).
