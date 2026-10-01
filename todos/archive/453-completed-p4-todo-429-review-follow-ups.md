---
status: completed
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

- [x] Each finding is fixed with a test, or closed with a recorded reason.

## Work Log

### 2026-09-26 - Filed from the todo 429 review (PR #849)

### 2026-09-30 - Implemented by the todo sweep (run 2026-10-01-0121)

- Finding 1: one link-card derivation per client — `linkPreviewDisplay`
  (`web/src/components/forum/linkPreviewDisplay.ts`; Dart twin in
  `forum_body_block.dart`) returns href, short address, title, second line,
  label and image, or null. The full card, the compact row and the run rule
  (`isCardBlock` / `isForumCardBlock`) all read it; tests on both clients pin
  "joins a run" == "renders something" over a table of good and bad URLs.
- Finding 2: `_CompactCardRow` takes its 72x48 thumbnail and 48 dp minimum
  height from `_rowThumbSize` / `_rowMinHeight`; a new test pins the
  no-thumbnail tile at 72x48 (the third site).
- Finding 3: a run of long-titled cards is pumped on a 375 pt screen at 1.0x
  and 2.0x text with no overflow; mutation-checked (dropping the row's
  `Expanded` makes it fail with a RenderFlex overflow).
- Finding 4 (owner decision 2026-09-30): all four mobile labels now match the
  web — rows "title, provider" / "title, address", the full link card
  "title, address", the full video card "title, Watch on PROVIDER" (its web
  name, from content). The contract is recorded in
  `web/docs/patterns/react-typescript.md` and `flutter-patterns.md`.

### 2026-09-30 - Verified by the todo sweep (run 2026-10-01-0121)

- AC 1: `bash -c '(cd plant_community_mobile && flutter test test/features/forum/widgets/forum_card_runs_test.dart test/features/forum/widgets/forum_body_renderer_test.dart test/features/forum/screens/forum_thread_links_test.dart) && (cd web && npx vitest run src/components/forum/linkPreviewDisplay.test.ts src/components/forum/CompactCardRow.test.tsx src/components/forum/LinkPreviewCard.test.tsx) && grep -n "Forum card labels" web/docs/patterns/react-typescript.md plant_community_mobile/docs/patterns/flutter-patterns.md'` — evidence `.sweep-evidence/g4/453-ac0.txt`, last lines:

  ```text
     Duration  819ms (transform 200ms, setup 203ms, import 548ms, tests 272ms, environment 927ms)

  web/docs/patterns/react-typescript.md:549:## Forum card labels and the one link-card derivation (todo 453)
  web/docs/patterns/react-typescript.md:559:"Forum card labels match the web").
  plant_community_mobile/docs/patterns/flutter-patterns.md:383:### Forum card labels match the web (todo 453)
  ```

### 2026-09-30 - Completed by the todo sweep (run 2026-10-01-0121)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
