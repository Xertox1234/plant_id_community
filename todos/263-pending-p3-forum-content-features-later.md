---
status: pending
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

- [ ] At each roadmap review, every member finding is either promoted (own
      todo/PR with concrete criteria) or explicitly re-deferred here with a
      dated note in the Work Log
- [ ] M9 lands before or with M10 if DMs are ever promoted (hard gate)

## Work Log

### 2026-07-11 - Created from forum-modernization audit (Phase 4 deferral)

- Epic groups the 8 below-the-cut content/social findings per the manifest's
  Phase 4 grouping table.

## Notes

p3 parking epic. M7 and M6 are flagged as promotion-first: M7 is an a11y gap
misfiled as polish, M6 is the app's differentiator.
