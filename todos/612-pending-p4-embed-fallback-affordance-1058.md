---
status: pending
priority: p4
issue_id: "612"
tags: [web, forum, a11y, follow-ups]
dependencies: []
---

# Follow-ups from PR #1058 (todo 592, forum embed fallback affordance)

## Problem

Todo-sweep run 2026-10-11-2219 merged PR #1058 (todo 592, forum embed fallback affordance). The non-blocking review findings are below. The curator merged duplicates and checked each item against main, and the refuter dismissed what is listed as dropped. An item the curator did not return was kept as stored, unchecked. Line numbers are as of the PR head, so re-check each against main before acting on it.

## Findings

PR #1058 (todo sweep run 2026-10-11-2219, group g10, todos 592); follow-ups: verified; 1 item(s) the curator did not return were kept as stored.

1. **low** `web/src/components/StreamFieldRenderer.tsx:485` Untitled mailto: and relative-URL fallback cards still render target="_blank" but no longer get the "Opens in a new tab" hint, so screen-reader users are not told a new tab opens. This matches the owner's mobile-parity decision and how titled cards already behave.
2. **low** `web/src/components/StreamFieldRenderer.tsx:470` The EmbedFallbackCard doc comment still says an UNTITLED card always keeps the full-URL affordances. Since this change only an http(s) untitled card gets them, so the docblock contradicts the gate at line 485. | also: web/src/components/StreamFieldRenderer.tsx:472 The EmbedFallbackCard docblock still says every UNTITLED card shows the short address and keeps the full-URL affordances; after this change that holds only for http(s) URLs. A mailto: or relative URL shows its raw URL and gets no title or hint. The inline comment is correct, but the docblock above it is stale.
3. **low** `web/src/components/StreamFieldRenderer.tsx:472` The EmbedFallbackCard docblock still says every UNTITLED card shows the short address and keeps the full-URL affordances. After this change that holds only for http(s) URLs. A mailto: or relative URL shows its raw URL and gets no title or hint. The inline comment is correct, but the docblock above it is now stale.

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-11 - Filed from the PR #1058 review (todo sweep run 2026-10-11-2219)

Filed by the closing step of the run from `state.py followups-md g10`.
