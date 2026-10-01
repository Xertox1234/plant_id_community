---
status: pending
priority: p4
issue_id: "453"
tags: [forum, web, mobile, refactor, testing]
dependencies: []
source_review: "todos/archive/429-completed-p3-compact-list-for-card-runs.md"
triage: ready
triaged: 2026-09-30
owner_decision: "Finding 4: align all four mobile labels with web — compact rows (675/693) and the full link and video cards (457/559) (2026-09-30)"
---

# Todo 429 review: non-blocking follow-ups

## Findings

1. **One display helper per client for a link card.** `LinkPreviewCard.tsx`,
   `CompactCardRow.tsx` and `cardRuns.isCardBlock` each re-derive the href,
   short address, title fallback and image source. Dart repeats the same
   pattern across `_LinkPreviewCard`, `_CompactCardRow` and
   `isForumCardBlock`. Extract `linkPreviewDisplay(preview) →
   {href, address, title, imageSrc} | null` (web) and its Dart twin, and use
   it everywhere, so "renders nothing" and "joins a run" cannot drift apart.
2. **Thumbnail size literals.** 72×48 and the 48 dp minimum height appear
   three times in `_CompactCardRow`. Use one set of constants.
3. **Narrow viewport.** No widget test pumps a run at 375 pt with long
   titles. It looks safe by inspection (`Expanded` + `maxLines: 1`), but see
   LEARNINGS 2026-08-28 (todo 317).
4. **Label parity is intentional but undocumented.** Web rows are named
   "title, provider/address", with the element role saying button or link.
   Mobile rows say "PROVIDER video: title" and "Link: title, address", like
   the full cards. Record the choice in `web/docs/patterns/react-typescript.md`
   and `flutter-patterns.md`, or align the two.

## Acceptance Criteria

- [ ] Each finding is fixed with a test, or closed with a recorded reason.

## Work Log

### 2026-09-26 - Filed from the todo 429 review (PR #849)
