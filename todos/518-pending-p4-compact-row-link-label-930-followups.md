---
status: pending
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

- [ ] Each finding above is fixed with a test, or the Work Log records why it was left as is.

## Work Log

- 2026-10-01: Filed from todo-sweep run 2026-10-02-0118, PR #930 review rounds 1-2.
