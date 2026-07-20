---
status: in_progress
priority: p1
issue_id: "273"
tags: [forum, api, drf, web]
dependencies: []
source_review: "docs/audits/2026-07-11-forum-modernization.md"
source_finding: "H6, H7, L14, M6, M35, M36, M37, M39"
---

# Forum epic: Wave 2 — app-loop backend primitives (+ minimal web UI)

Wave 2 of `docs/superpowers/specs/2026-07-17-forum-app-loop-roadmap-design.md`.
Delivered as per-slice PRs off fresh `main`.

## Slices

- [x] **Slice 1 — Author display fix** (this PR): `PostAuthorSerializer` serves
  real integer `trust_level` + `display_name` from the joined `ForumProfile`
  (N+1-safe); web renders the integer as a label and hides NEW.
  Plan: `docs/superpowers/plans/2026-07-17-forum-wave2-slice1-author-display.md`.
  Addresses L14's `trust_level`-renders-as-raw-text item (the emoji-`aria-hidden`
  and reactions-`flex-wrap` items in that cluster remain at todo 257); serves the
  serializer subset of H7 (public profiles stay Wave 4 / todo 257).
- [ ] **Slice 2 — Solved answers** (H6, moved from todo 256): `Topic.solved_post`
  FK + `solved_at`, `POST/DELETE /topics/{id}/solution/`, Solved badge +
  accepted-post highlight, accepted-answer notification, clear-on-unpublish rule.
- [ ] **Slice 3 — Identification embed** (M6, moved from todo 263):
  `ForumIdentificationAttachment` snapshot model, compose-time photo copy through
  the forum image upload pipeline, card above the opening post, "Ask the
  community" web entry point.
- [ ] **Slice 4 — Mobile-gating API hardening** (M35, M36, M37, M39 subset of
  todo 258): idempotency for `PATCH /posts/{id}/` + image upload (and the new
  solution endpoint), OpenAPI response-code completeness, error-envelope
  consistency across mobile-bound endpoints.

## Notes

Solved answers moved out of 256; the identification embed moved out of 263; the
mobile-gating subset split out of 258 — the remainder of each stays put. See the
roadmap's "Todo bookkeeping" section.
