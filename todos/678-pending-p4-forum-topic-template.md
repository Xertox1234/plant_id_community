---
status: pending
priority: p4
issue_id: "678"
tags: [forum, forum-categories, backend, web]
dependencies: ["666"]
triage: ready
triaged: 2026-10-29
owner_decision: "owner question at triage; skipped per overnight orders (2026-10-29)"
---

# Forum categories slice 12: topic template per forum

## Problem

Discourse prefills the new-topic composer with a per-category template (e.g. a plant-problem checklist).

## Findings

- `docs/superpowers/specs/2026-10-28-forum-categories-design.md` §2 (Discourse topic_template).
- Source: owner request + phpBB/Discourse research, 2026-10-28 (Claude session).

## Recommended Action

1. Field `topic_template` (plain text/markdown in the composer's input format), admin *Posting* tab, exposed in the forum API; web `NewThreadPage.tsx` prefills when the body is empty.

## Technical Details

- `NewThreadPage.tsx`, forum serializer.
- Design: `docs/superpowers/specs/2026-10-28-forum-categories-design.md`. Web only — no Flutter changes.

## Acceptance Criteria

- [ ] Test: API exposes the template.
- [ ] Web Vitest: composer prefills only when empty and never overwrites a draft.

## Work Log

### 2026-10-28 - Filed

- Filed from the forum-categories research session (owner decisions in the design spec §1).
