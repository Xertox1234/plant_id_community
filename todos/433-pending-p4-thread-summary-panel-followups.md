---
status: pending
priority: p4
issue_id: "433"
tags: [web, forum, premium, ai]
dependencies: []
source_review: "PR #816"
---

# Thread summary panel: non-blocking review findings

## Problem

The bundled `/code-review` of PR #816 (todo 414) raised these. None was
blocking, so under the two-round review budget they land here.

## Findings

- **Button on too-short threads.** The page already has `thread.post_count`.
  Below 3 posts every click spends a 30/h slot to learn `too_short`. Hide or
  disable the button there.
- **`throttledMessage` rounds to minutes with no plural** ("about 1
  minutes"), and duplicates `describeWait()` in
  `NewGroupConversationForm.tsx`. Share one formatter.
- **A 404 (topic unpublished or moved to a restricted board) says "try
  again"**, and each retry spends a slot. Treat 404 as non-retryable.
- **`readRetryAfterSeconds` copies `messageService.readRetryAfter`.** Export
  one.
- **Third copy of the capability latch + error class** (compose assist, RAG,
  thread summary), each with its own manual reset line in `AuthContext`. A
  keyed latch registry with one reset-all removes the "forgot to add the
  reset" failure mode.
- **Polls keep firing while the tab is hidden**, against the
  `docs/rules/react.md` polling rule. Skip the tick while
  `document.visibilityState === 'hidden'`.

- **Same 401 latch in plant-care ask** (round 2). `RagError.permanent`
  (`forumService.ts`, used by `PlantCareAskPanel`) includes 401 on purpose,
  because that page is public and a 401 teaches an anonymous visitor. For a
  SIGNED-IN user it is the same expired-cookie bug #816 fixed: latch 401 only
  when there is no signed-in user.

## Acceptance Criteria

- [ ] Each finding is fixed with a test, or explicitly declined with a reason.

## Work Log

### 2026-09-24 - Filed from PR #816 review round 1
