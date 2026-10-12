---
status: completed
priority: p4
issue_id: "592"
tags: [todos, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-11
owner_decision: "Worker picks: web adopts mobile's http(s)-only gate; decline the rest with reasons (owner, 2026-10-11)"
---

# Follow-ups from PR #1031 (todos 563, 564)

## Problem

Todo-sweep run 2026-10-11-1448 merged PR #1031 (untitled embed card affordances and the Tailwind class checker). Its review rounds reported the non-blocking
findings below. The curator merged duplicates and checked each item against main; the refuter dismissed
what is listed as dropped. Line numbers are as of the PR head, so re-check each against main before acting on it.

## Findings

PR #1031 (todo sweep run 2026-10-11-1448, group g7, todos 563, 564); follow-ups: verified; 1 item(s) the curator did not return were kept as stored.

1. **medium** `plant_community_mobile/lib/features/forum/widgets/forum_body_renderer.dart:758` The full-address affordance for untitled videos covers only the full card. An untitled video in a compact row shows only its short address and has no long-press sheet or Show full address / Copy link actions (isLink false). On web, a non-playable untitled row gets no hover title.
2. **low** `web/scripts/check-tailwind-classes.mjs:365` classShaped accepts any lower-case token, and ':' or '-' make it utility-shaped. So lower-case or hyphenated prose beside a class list is still strict-checked and fails CI, for example `x ? 'p-2' : 'sign-in required'`, `'error: retry'` or `'well-known issue'`. The todo 564 fix covers only capitalised or punctuated prose. | also: web/scripts/check-tailwind-classes.mjs:409 classValuedLiterals fixes only part of the false positive. A lowercase hyphenated prose sibling such as `x ? 'p-2' : 'well-known issue'` still counts as class-shaped and utility-shaped, so it is strict-checked and fails CI. Also no longer caught: `x ? 'p-2' : 'prose'` (documented). | CLASS_SHAPED requires the first character to be [a-z0-9], after an optional !/@/-. A sibling class list that starts with a variant such as `*:p-2` is therefore never promoted, so `x ? 'p-2' : '*:bogus-x'` goes unchecked. A hyphenated prose sibling such as 'sign-in' is still promoted and flagged.
3. **low** `web/scripts/check-tailwind-classes.mjs:359` Narrowing sibling promotion to class-shaped utility literals means a lone bare-word typo beside a class list (`x ? 'p-2' : 'prose'`) is no longer caught. This is documented as a trade-off, but it regresses the todo 450 'prose' case for single-token siblings.
4. **low** `web/src/components/StreamFieldRenderer.tsx:503` The sr-only 'Opens in a new tab' hint is rendered as a sibling outside the anchor. In browse mode a screen reader reads it as a stray standalone line after the card, as well as reading it as the link's description.
5. **low** `web/src/components/StreamFieldRenderer.tsx:634` The web and mobile untitled-card affordance gates differ. Web uses `href !== '#'`, which also accepts mailto: and relative URLs. Mobile uses `linkPreviewShortAddress(url) != null`, which accepts http(s) only. So the same block can expose its full address on one platform and not the other.
6. **low** `plant_community_mobile/test/features/forum/widgets/forum_body_renderer_test.dart:186` The untitled `_EmbedCard` adds two custom semantics actions, but the test drives only 'Show full address'. The 'Copy link' action (the `_copyLink` closure) is never invoked for the embed card, so a broken closure would still pass.
7. **low** `web/src/components/StreamFieldRenderer.test.tsx:984` The index.css test parses CSS with a brace regex. If a rule moves inside an `@layer` block, or a comment comes before a selector, `rule()` returns nothing or mis-splits selectors, so the test can fail for the wrong reason.
8. **low** `web/src/components/StreamFieldRenderer.tsx:128` untitledEmbedOrdinals(blocks) is recomputed on every render of StreamFieldRenderer, which is rendered once per post in lists. It is cheap but unmemoized.
9. **low** `web/scripts/check-tailwind-classes.mjs:409` classValuedLiterals fixes only part of the false positive. A lowercase hyphenated prose sibling such as `x ? 'p-2' : 'well-known issue'` still counts as class-shaped and utility-shaped, so it is strict-checked and fails CI. Also no longer caught: `x ? 'p-2' : 'prose'` (documented).

2 more location(s) were dropped by the cap of 10 (the most severe are kept).

Dropped by curation (fixed on main, refuted, or not a reported location):

- low: web/src/components/forum/embedDisplay.ts:35 `detail = value.provider_name` dropped the old `|| ''` coercion. If the API sends null or omits provider_name, `detail` is null or undefined despite its `string` type, and that can leak into the compact row's second line. (refuted: Unreachable. The backend embed_envelope always sends provider_name as a str (cached.provider_name, or ''; Embed.provider_name is a non-null TextField). Blog has no embed block. CompactCardRow renders detail only when truthy, and label is guarded.)

## Acceptance Criteria

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log

### 2026-10-11 - Filed from todo-sweep run 2026-10-11-1448

Follow-ups for PR #1031 (todos 563, 564).

### 2026-10-11 - Implemented by the todo sweep (run 2026-10-11-2219)

- Finding 5 fixed (owner decision 2026-10-11): `EmbedFallbackCard` in `web/src/components/StreamFieldRenderer.tsx`
  now gates the untitled full-address affordance on `shortLinkAddress(href) !== null`, the twin of mobile's
  `linkPreviewShortAddress(url) != null`. A mailto: or relative URL still links but gets no hover title and no
  new-tab description, on either platform. Tested by the two `todo 592` cases in `StreamFieldRenderer.test.tsx`.
- Declined 1: a compact row is a run summary shared by link cards and videos; giving a video row the long-press
  sheet is a new affordance, not a fix, and the full card (and the player it opens) carries the address.
- Declined 2, 3 and 9 (one heuristic): `check-tailwind-classes.mjs` sibling promotion trades a narrow false
  positive for a narrow false negative by design (todo 564). Main passes `npm run check:classes`, so no real
  literal hits either edge; a hit fails CI loudly and is fixed at the call site.
- Declined 4: the hint sits outside the anchor on purpose (the anchor has no `aria-label`, so a hint inside it
  would join its name); a sr-only "Opens in a new tab" line in browse mode is harmless.
- Declined 6, 7 and 8: `_copyLink` is one shared function already tapped by the link-card test; the index.css
  test fails loudly (never falsely passes) if a rule moves; `untitledEmbedOrdinals` is one O(n) pass per body.

### 2026-10-11 - Verified by the todo sweep (run 2026-10-11-2219)

- AC 1: `bash -c 'cd web && python3 scripts/todos/slot_env.py --main-root . 4 -- npx vitest run src/components/StreamFieldRenderer.test.tsx && python3 scripts/todos/slot_env.py --main-root . 4 -- npx tsc --noEmit -p . && grep -nE "Finding 5 fixed|Declined (1|2, 3 and 9|4|6, 7 and 8)" todos/archive/592-completed-p4-forum-embed-affordance-pr1031-followups.md'` — evidence `.sweep-evidence/g10/592-ac0.txt` (not committed), last lines:

  ```text
  53:- Finding 5 fixed (owner decision 2026-10-11): `EmbedFallbackCard` in `web/src/components/StreamFieldRenderer.tsx`
  57:- Declined 1: a compact row is a run summary shared by link cards and videos; giving a video row the long-press
  59:- Declined 2, 3 and 9 (one heuristic): `check-tailwind-classes.mjs` sibling promotion trades a narrow false
  62:- Declined 4: the hint sits outside the anchor on purpose (the anchor has no `aria-label`, so a hint inside it
  64:- Declined 6, 7 and 8: `_copyLink` is one shared function already tapped by the link-card test; the index.css
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-11-2219)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
