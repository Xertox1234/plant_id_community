---
status: completed
priority: p4
issue_id: "518"
tags: [forum, web, mobile]
dependencies: []
triage: ready
triaged: 2026-10-02
owner_decision: "Finding 1: the full video card (mobile _EmbedCard and web StreamFieldRenderer embed) uses the short address for untitled videos too (2026-10-02)"
---

# Compact row link label: non-blocking findings from PR #930 (todo 505)

## Problem

PR #930 (todo 505) merged after two review rounds in todo-sweep run 2026-10-02-0118. The findings below were rated non-blocking, so they were not repaired. Findings at the same file:line are merged; each one says which round reported it. Line numbers are as of the PR head. Re-check each finding against main before acting on it.

## Findings

1. **`plant_community_mobile/lib/features/forum/widgets/forum_body_renderer.dart:793`** (low, round 2). An untitled video's compact row now says its short address, but its full card (mobile \_EmbedCard, web StreamFieldRenderer embed case) still uses the full URL. The same video is named two ways depending on where it falls in a run. The Work Log says this was left out of scope on purpose.
   Suggested: File a follow-up so the full video card's untitled fallback uses linkPreviewShortAddress/shortLinkAddress too, or leave it as the Work Log records. No change is needed in this PR.

2. **`plant_community_mobile/test/features/forum/widgets/forum_card_runs_test.dart:259`** (low, round 1). The new test 'a link row is labelled by linkPreviewDisplay' takes its expected label from linkPreviewDisplay(\_link)!.label, so it passes whatever that function returns. The old inline derivation gives the same string, so the test cannot tell the refactor from the old code. The literal 'Delta guide, `https://example.org/…`' is already pinned by another test.
   Suggested: Assert a literal label such as 'Delta guide, `https://example.org/…`', or drop the test. The literal assertion in the 'labelled like the web' test and the display unit test already cover this.

3. **`plant_community_mobile/test/features/forum/widgets/forum_card_runs_test.dart:476`** (low, round 2). The 'link row is labelled by linkPreviewDisplay' test takes its expected label from linkPreviewDisplay(\_link)!.label, the function under test, so a wrong label derivation would still pass. Only the bare case asserts a literal.
   Suggested: Assert the literal 'Delta guide, `https://example.org/…`' for the \_link row, as the web test does, rather than reading it back from linkPreviewDisplay.

4. **`web/src/components/forum/CompactCardRow.test.tsx:172`** (low, round 2). The new web test covers only an untitled video WITH a provider. The no-provider case (label = short address alone) is pinned on mobile (vimeo.com/77) but not on web, so web/mobile parity on that branch is not tested.
   Suggested: Add a web case such as embed('c','','') with url '`https://vimeo.com/77`', and assert getByRole('button',{name:'`https://vimeo.com/…`'}) and not.toHaveTextContent('/77'), matching the mobile test.

5. **`web/src/components/forum/CompactCardRow.tsx:46`** (low, round 1). The video row still derives its own title and label inline (`t || shortLinkAddress(url) || url`, then `title, detail`). Only the link row reads linkPreviewDisplay, so web and mobile embed labels can drift. The new test covers only the untitled case.
   Suggested: Optionally extract an embedRowDisplay helper next to linkPreviewDisplay and test it directly, titled and untitled.

6. **`web/src/components/forum/linkPreviewDisplay.test.ts:112`** (low, round 1). The `@ts-expect-error` test calls linkPreviewDisplay without a variant at runtime. It only proves the variant is required if `tsc` covers test files, and Vitest does not typecheck. If tsconfig excludes tests, the directive is inert.
   Suggested: Confirm `tsc --noEmit` includes *.test.ts, or rely on the call-site type check and drop the runtime assertion.

## Acceptance Criteria

- [x] Each finding above is fixed with a test, or the Work Log records why it was left as is.

## Work Log

- 2026-10-01: Filed from todo-sweep run 2026-10-02-0118, PR #930 review rounds 1-2.

### 2026-10-02 - Implemented by the todo sweep (run 2026-10-02-0335)

- Findings 1 and 5: an untitled video's full card now uses its short address, like its row (owner decision 2026-10-02). On the web, the new `embedDisplay` helper (`web/src/components/forum/embedDisplay.ts`) derives a video's title, second line and row label. `CompactCardRow` reads all three, and the `embed` case of `StreamFieldRenderer` reads its `title` for the iframe `title` and the fallback card's first line. `embedDisplay.test.ts` tests it directly: titled, untitled with and without a provider, a bare origin, and a non-http URL. On mobile, `_EmbedCard` and `_embedRow` share one rule, `_embedTitle`. New tests on both platforms cover the untitled player, the fallback card, and the same video as a full card and as a row. The pattern docs now say so.
- Two existing tests pinned the old full-URL name and were changed to match the decided behaviour. `StreamFieldRenderer.test.tsx` "renders an embed without a player URL..." now matches the link by its short address and still checks it opens the full URL. In `forum_body_renderer_test.dart`, "embed renders a thumbnail card, never a player" now expects the short address once and the URL once. Left as is: with no provider, the mobile full card's second line still shows the URL itself. So an untitled card with no provider (a bare-URL embed from an older client) shows the short address above the full URL. That line is shown but never spoken (`excludeSemantics`), and neither the finding nor the owner decision named it.
- Findings 2 and 3 (one test): "a link row is labelled by linkPreviewDisplay" now asserts the literal `Delta guide, https://example.org/…` instead of reading the label back from `linkPreviewDisplay`. A mutation check showed the difference: changing the label separator in `linkPreviewDisplay` now fails this test.
- Finding 4: a new web test covers an untitled video row with no provider (`https://vimeo.com/77`). It is named `https://vimeo.com/…` alone, with no `/77` in its text, as on mobile.
- Finding 6: confirmed, with no code change. `web/tsconfig.json` includes `src/**/*` with no test exclusion, and `web-ci.yml` runs `npm run type-check` (`tsc --noEmit`), so the `@ts-expect-error` is live. A mutation check confirmed it: an optional `variant` fails tsc with TS2578 at `linkPreviewDisplay.test.ts(108,5)`. A comment in the test now records this.

### 2026-10-02 - Verified by the todo sweep (run 2026-10-02-0335)

- AC 1: `bash -c 'sed -n "/^### 2026-10-02 - Implemented by the todo sweep (run 2026-10-02-0335)/,\$p" todos/archive/518-completed-p4-compact-row-link-label-930-followups.md && cd web && ./node_modules/.bin/tsc --noEmit && echo "tsc --noEmit: exit 0" && ./node_modules/.bin/tsc --listFilesOnly | grep -E "src/components/forum/(linkPreviewDisplay|embedDisplay)\.test\.ts$" && ./node_modules/.bin/vitest run src/components/forum/embedDisplay.test.ts src/components/forum/linkPreviewDisplay.test.ts src/components/forum/CompactCardRow.test.tsx src/components/forum/LinkPreviewCard.test.tsx src/components/StreamFieldRenderer.test.tsx && cd plant_community_mobile && flutter analyze lib/features/forum test/features/forum && flutter test --reporter expanded test/features/forum/widgets/forum_card_runs_test.dart test/features/forum/widgets/forum_body_renderer_test.dart'` — evidence `.sweep-evidence/g14/518-ac0.txt` (not committed), last lines:

  ```text
  00:01 +48: plant_community_mobile/test/features/forum/widgets/forum_card_runs_test.dart: an untitled video row says its short address, not its URL
  00:01 +49: plant_community_mobile/test/features/forum/widgets/forum_card_runs_test.dart: a link row is labelled by linkPreviewDisplay
  00:01 +50: plant_community_mobile/test/features/forum/widgets/forum_card_runs_test.dart: an untitled full video card says its short address, like its row
  00:01 +51: plant_community_mobile/test/features/forum/widgets/forum_card_runs_test.dart: an untitled full video card with no provider is labelled by its short address alone
  00:01 +52: All tests passed!
  ```

### 2026-10-02 - Completed by the todo sweep (run 2026-10-02-0335)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
