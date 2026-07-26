---
status: completed
priority: p3
issue_id: "263"
tags: [forum, product-ux, roadmap]
dependencies: []
source_review: "docs/audits/2026-07-11-forum-modernization.md"
source_finding: "M2, M3, M4, M6, M7, M8, M9, M10"
---

# Forum epic: content & social features (later wave)

## Problem

Parking epic for the content/social features that fell below the p1/p2 cut in
the 2026-07-11 forum-modernization audit: bookmarks, drafts/autosave, an edit-
history viewer, plant-domain linkage, image-authoring upgrades, polls,
block/mute, and private messaging. Grouped so none are dropped; promote
individually at roadmap reviews.

## Findings

Path shorthand: `W` = `backend/packages/wagtail_forum/wagtail_forum`, `web` = `web/src`.

> **As-of-2026-07-11 snapshot.** These statements were true when the audit filed
> them; M3 has since been fixed and every other finding has moved to its own
> todo. See the 2026-07-26 Work Log entry for the current disposition of each.

- **M2** — No bookmarks/saves.
- **M3** — No drafts/autosave: composer state is in-memory only, no
  `beforeunload` guard; refresh/back-nav/crash loses the post unrecoverably
  (failed-submit preservation DOES work) (`web/pages/forum/NewThreadPage.tsx:30`).
- **M4** — Edit history stored (RevisionMixin) but no endpoint/viewer —
  "Edited" stamp with nothing behind it (`W/models/posts.py:54-60`).
- **M6** — Zero linkage to the app's own plant domain: can't attach a plant-ID
  result/species to a question — the app's differentiator is absent from its
  forum (`W/blocks.py:13-30` anchor: new block).
- **M7** — Image authoring below par for a photo-centric community: alt-text
  authoring absent END-TO-END (composer inserts display-only alt, write path
  intentionally drops it, backend re-derives alt=filename, renderer falls back
  to `''`) — an a11y gap, not just polish; plus no paste/drag-drop upload, no
  lightbox (`W/api/serializers.py:147`, `web/utils/forumBody.ts:17-22`).
- **M8** — No polls.
- **M9** — No block/mute users.
- **M10** — No private messaging (M9 is a trust-and-safety prerequisite —
  never ship DMs without block/mute).

## Recommended Action

Promotion guidance (strongest candidates first):

1. **M7 alt-text chain** — an accessibility gap, not polish: thread alt through
   composer → `htmlToBodyBlocks` → write path → serializer → renderer.
2. **M6 plant-ID linkage** — the product differentiator: a `plant_reference`
   StreamField block (species/identification FK host-side adapter) + compose
   integration from an ID result ("Ask the community about this plant").
3. **M3 cheap slice** — a `beforeunload` dirty guard is ~10 lines and can ride
   any web PR; full drafts/autosave (localStorage or server drafts via
   DraftStateMixin) is the larger follow-on.
4. **M4** — read-only revision list/diff endpoint gated to author+mods; the
   data already exists via RevisionMixin.
5. **M2 bookmarks**, **M8 polls** — standard forum table stakes, independent.
6. **M9 block/mute before M10 DMs** — hard ordering.

## Technical Details

- M6 must respect package purity: the package defines an abstract/generic
  block or setting-injected chooser; the plant-ID specifics live host-side
  (`test_reusability.py` forbids `apps.*` imports).
- M7's write path intentionally drops alt today (`W/api/views.py:549` area) —
  changing it is a contract change; coordinate composer + serializer + tests
  in one PR.

## Acceptance Criteria

- [x] At each roadmap review, every member finding is either promoted (own
      todo/PR with concrete criteria) or explicitly re-deferred here with a
      dated note in the Work Log
- [x] M9 lands before or with M10 if DMs are ever promoted (hard gate)

## Work Log

### 2026-07-11 - Created from forum-modernization audit (Phase 4 deferral)

- Epic groups the 8 below-the-cut content/social findings per the manifest's
  Phase 4 grouping table.

### 2026-07-26 - Roadmap review → all 8 findings homed; epic closed

**Why this closes rather than stays parked.** AC1 allows two dispositions per
finding: promoted, or re-deferred *here*. Re-deferring anything here keeps the
epic open by construction, so the only terminal state for a parking epic is
**promote everything**. This review promoted every remaining finding, which is
what makes archiving correct rather than a silent drop.

**Disposition (all 8 member findings, verified against `main` @ 27ade0c):**

| Finding | Disposition |
|---------|-------------|
| M2 bookmarks | promoted → todo 283 (with M8) |
| M3 drafts/autosave | **RESOLVED on main** — shipped Wave 1 (#473) |
| M4 edit-history viewer | promoted → todo 282 |
| M6 plant-domain linkage | already promoted → todo 273 (Wave 2 slice 3) |
| M7 image alt-text | promoted → todo 281, raised to **p2** (a11y) |
| M8 polls | promoted → todo 283 (with M2) |
| M9 block/mute | promoted → todo 284 (phase 1) |
| M10 private messaging | promoted → todo 284 (phase 2, gated on M9) |

**AC1 evidence.** Each promoted todo carries file-anchored findings re-verified
against current `main` and objectively checkable acceptance criteria (not
restatements of the finding). M2/M8/M9/M10 were re-verified absent by grep over
`backend/packages/wagtail_forum/` — the only `poll` matches in the package are
delta-sync polling comments (`models/topics.py:87`, `api/views.py:1316`), not a
poll feature.

**AC2 evidence.** The hard gate is now structural, not prose: M9 and M10 live in
one todo (284) whose *first* acceptance criterion reads —

> **Hard gate — no private-messaging code may merge until block/mute is
> merged.** A DM PR that touches this repo before `UserBlock` exists on `main`
> must be closed or held, and this box may only be checked by recording the
> block/mute merge commit here

Keeping them in a single todo (rather than two with a `dependencies:` link)
means M10 cannot be picked up as an independent unit of work without reading
M9's gate.

**M3 resolution evidence.** Wave 1 (#473) shipped `web/src/utils/forumDrafts.ts`,
wired into both composers (`NewThreadPage.tsx:39-49,98-102,118` and
`ThreadDetailPage.tsx:129-131,267,678`): composer state is written to
sessionStorage on every keystroke and restored on mount, so the failure mode the
finding described — "refresh/back-nav/crash loses the post unrecoverably" — no
longer holds. Only the storage helper was under test, so a page-level restore
test was added at close-out (`NewThreadPage.test.tsx`, "restores a saved
composer draft, then clears it once posted (M3)"):

```
✓ src/utils/forumDrafts.test.ts > forumDrafts > round-trips a draft 1ms
✓ src/utils/forumDrafts.test.ts > forumDrafts > saving an empty value removes the draft 0ms
✓ src/utils/forumDrafts.test.ts > forumDrafts > swallows storage errors 1ms
✓ src/pages/forum/NewThreadPage.test.tsx > NewThreadPage > restores a saved composer draft, then clears it once posted (M3) 13ms
...
Test Files  2 passed (2)
     Tests  9 passed (9)
```

The finding's suggested `beforeunload` dirty guard is recorded as **superseded,
not deferred**: with autosave in place it would only add a leave-confirmation
prompt, and it no longer prevents data loss. `forumDrafts.ts:1-5` documents the
sessionStorage choice (survives navigation within the tab, deliberately not
across sessions) as intentional.

**Source-review bookkeeping.** The audit's `## Finding Status` lines for M2, M4,
M6, M7, M8, M9, M10 were **re-pointed** to their new todos, not checked off —
checking off e.g. `#M8 polls` as completed when polls do not exist would falsify
the tracking doc. Only M3 was checked off, as genuinely shipped. Consequently
open `- [ ]` lines remain and the audit doc is correctly NOT renamed
`-COMPLETED.md`. The stale `#M6 → todo 263` line was corrected to todo 273.

### 2026-07-26 - Completed by completing-todos skill (run 2026-07-26-2319)

- Verification: both acceptance criteria passed — AC1 by the 8-finding
  disposition table above (every finding promoted, M3 resolved, M6 already
  routed to 273), AC2 by todo 284's first acceptance criterion carrying the
  gate structurally. Supporting suite: `npm run type-check` clean;
  `vitest --run` → `Test Files 54 passed (54) / Tests 694 passed (694)`.
- Review: `code-review-orchestrator` — 0 findings, none blocking. It
  independently re-verified a sample of the cited anchors, confirmed the new
  M3 test is substantive (not tautological) and that the `TipTapEditor` mock
  change does not weaken the pre-existing tests in that file, and confirmed the
  re-point-not-checkoff bookkeeping in the audit doc.

## Notes

p3 parking epic. M7 and M6 were flagged as promotion-first: M7 is an a11y gap
misfiled as polish, M6 is the app's differentiator. Both were promoted first —
M6 to todo 273 (Wave 2 slice 3) on 2026-07-17, M7 to todo 281 at p2 on
2026-07-26 — and the epic closed once nothing remained parked.
