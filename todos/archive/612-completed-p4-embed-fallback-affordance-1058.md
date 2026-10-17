---
status: completed
priority: p4
issue_id: "612"
tags: [web, forum, a11y, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-11
owner_decision: "Finding 1 declined per todo 592's http(s)-only parity decision; fix only the stale docblock (2026-10-11)"
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

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-11 - Filed from the PR #1058 review (todo sweep run 2026-10-11-2219)

Filed by the closing step of the run from `state.py followups-md g10`.

### 2026-10-12 - Implemented by the todo sweep (run 2026-10-12-0349)

- Finding 1 (untitled mailto:/relative fallback cards get no "Opens in a new tab" hint): declined,
  per the owner decision of 2026-10-11 — it is the intended mobile-parity behaviour from todo 592
  (only an http(s) URL gets the full-address affordances), and titled cards already behave this way.
- Findings 2 and 3 (one defect, reported twice): fixed. The `EmbedFallbackCard` docblock in
  `web/src/components/StreamFieldRenderer.tsx` now says only an untitled http(s) card gets the hover
  `title` and the hint, and that a titled card or an untitled mailto:/relative URL gets neither.
- Comment-only change: no behaviour change, so no new test.

### 2026-10-11 - Verified by the todo sweep (run 2026-10-12-0349)

- AC 1: `sed -n 466,491p web/src/components/StreamFieldRenderer.tsx && grep -n -A10 '### 2026-10-12 - Implemented' todos/archive/612-completed-p4-embed-fallback-affordance-1058.md` — evidence `.sweep-evidence/g9/612-ac0.txt` (not committed), last lines:

  ```text
  41-  (only an http(s) URL gets the full-address affordances), and titled cards already behave this way.
  42-- Findings 2 and 3 (one defect, reported twice): fixed. The `EmbedFallbackCard` docblock in
  43-  `web/src/components/StreamFieldRenderer.tsx` now says only an untitled http(s) card gets the hover
  44-  `title` and the hint, and that a titled card or an untitled mailto:/relative URL gets neither.
  45-- Comment-only change: no behaviour change, so no new test.
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-12-0349)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
