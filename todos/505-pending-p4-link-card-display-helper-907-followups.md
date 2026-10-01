---
status: pending
priority: p4
issue_id: "505"
tags: [forum, web, mobile]
dependencies: []
---

# Link-card display helper: non-blocking findings from PR #907 (todo 453)

## Problem

PR #907 (todo 453) merged after two review rounds in todo-sweep run 2026-10-01-0121. The findings below were rated non-blocking, so they were not repaired. Findings at the same file:line are merged; each one says which round reported it. Line numbers are as of the PR head. Re-check each finding against main before acting on it.

## Findings

1. **`plant_community_mobile/lib/features/forum/widgets/forum_body_renderer.dart:243`** (low, round 1). \_CompactCardRow builds its spoken label again (`detail.isEmpty ? title : '$title, $detail'`) instead of reading `d.label` from linkPreviewDisplay. That re-derives the rule the helper exists to centralise. The output is identical today, so this is drift risk only.
   Suggested: Carry the label in the switch tuple: `d.label` for a link row, and the embed's own 'title, provider' rule for a video row. Then drop the shared recomputation, or leave a comment saying it intentionally mirrors LinkPreviewDisplay.label.

2. **`plant_community_mobile/lib/features/forum/widgets/forum_body_renderer.dart:465`** (low, round 1, round 2). The full video card's new label 'title, Watch on PROVIDER' is documented and tested as 'the web's name', but the web only uses that text on the no-player fallback card. A YouTube or Vimeo embed with embed\_url is an iframe titled with the title alone, and a fallback card with no provider reads 'Open link'.
   Suggested: Change the docstring, the flutter-patterns.md text and the 'labelled like the web' test comment to say this label matches the web's fallback card only, or align the label with the iframe title. Keep the label itself as the owner decided.
   Also reported: Full video card with no provider is labelled by the title alone. The web's non-player embed card takes its name from its content, which is "title Open link" (StreamFieldRenderer.tsx:284). So the claim that all labels match the web (flutter-patterns.md, todo 453) does not hold in this one case. Parity nit only, no functional break.
   Also reported: With no provider, the mobile full embed card is labelled just the title. The web's full card reads 'title Open link'. That contradicts the new doc's claim that every card label matches the web.

3. **`plant_community_mobile/lib/features/forum/widgets/forum_body_renderer.dart:665`** (low, round 2). A compact embed row with an empty title falls back to the raw URL as title, so the new label 'title, provider' speaks the full URL (against the no-spoken-URL rule the link card follows).
   Suggested: For an empty embed title, use the short address (linkPreviewShortAddress) or the provider name for the row title and label.

4. **`plant_community_mobile/lib/features/forum/widgets/forum_body_renderer.dart:667`** (low, round 1). Embed compact row falls back to the full URL as title (e.url) when title is empty, so the spoken label becomes the full URL, against the doc's 'never the full URL' rule. Pre-existing, but this diff rewrote the label path.
   Suggested: Use linkPreviewShortAddress(e.url) as the empty-title fallback for the row title/label, and add a test.

5. **`plant_community_mobile/test/features/forum/widgets/forum_card_runs_test.dart:318`** (low, round 2). The 375pt run test asserts each InkWell width \<= 375, which a bounded parent passes trivially. Overflow is caught only via takeException, so the width loop adds no evidence.
   Suggested: Drop the width loop, or assert takeException after pump at each scale and that the row's text is ellipsized.

6. **`plant_community_mobile/test/features/forum/widgets/forum_card_runs_test.dart:518`** (low, round 2). The 'joins a run exactly when it renders' tests (Dart and web linkPreviewDisplay.test.ts) are close to tautological, since both sides now call linkPreviewDisplay. They guard against a future re-derivation but cannot catch a wrong null rule.
   Suggested: Optional: assert expected booleans per case as well, e.g. https/http true; '', javascript:, schemeless and credentials false, so a wrong rule in linkPreviewDisplay fails too.

7. **`web/src/components/forum/LinkPreviewCard.tsx:69`** (low, round 1). The card shows `address` under a `detail` guard (`{detail && <p>{address}</p>}`). The two are equal whenever detail is non-empty, but the guard and the content now come from different fields.
   Suggested: Render `{detail && <p ...>{detail}</p>}` so the second line reads exactly the field that decides whether it shows.

8. **`web/src/components/forum/linkPreviewDisplay.test.ts:58`** (low, round 2). Image-source test pins only one allowed case per variant, not the nearest disallowed neighbours: no 'post' + non-media/javascript:/http image\_url case, and no 'composer' + relative /media path case. A variant swap or loosened post-image guard may stay green.
   Suggested: Add post cases (javascript: image, http image -> null) and a composer case with the stored /media/... path expecting null.

9. **`web/src/components/forum/linkPreviewDisplay.test.ts:73`** (low, round 2). The run-parity test loops many cases under one assertion pair, so a failure does not name the case. Its '`http://example.org`' case has no expectation that it renders or not, so a scheme-policy change would be invisible.
   Suggested: Use it.each with labelled cases and include an explicit expected render/skip for the http case.

10. **`web/src/components/forum/linkPreviewDisplay.test.ts:77`** (low, round 2). The 'joins a run exactly when the card renders' test is partly tautological: the card, isCardBlock and linkPreviewDisplay all read the same function, so it cannot fail if that function is wrong. It only catches a call site that stops using it.
   Suggested: State that limit in a test comment, or add explicit expectations of what renders for the bad-URL cases.

11. **`web/src/components/forum/linkPreviewDisplay.test.ts:86`** (low, round 1). The run-parity loop renders LinkPreviewCard only with variant 'post'. A change to the composer-variant image or null rule would not fail it. The composer branch is pinned only on imageSrc, not on render/null parity.
   Suggested: Add a composer-variant render to the parity cases, or a small test that a composer card with a blank or unsafe URL returns null.

12. **`web/src/components/forum/linkPreviewDisplay.ts:38`** (low, round 2). linkPreviewDisplay defaults variant to 'post' while LinkPreviewCard defaults to 'composer'. A later caller that passes composer (third-party) data without a variant would send image\_url through mediaUrl and allow http, not https only. Every current caller is correct.
   Suggested: Make variant a required parameter, or give it the same default as LinkPreviewCard, so the image-source trust choice is always explicit at the call site. Have CompactCardRow and isCardBlock pass 'post'.

13. **`web/src/components/forum/linkPreviewDisplay.ts:870`** (low, round 1, round 2). linkPreviewDisplay defaults `variant` to 'post', while LinkPreviewCard defaults to 'composer'. A future composer call that leaves out the variant would resolve a third-party https image through mediaUrl. Every current caller is correct.
   Suggested: Make `variant` required, or default it to 'composer' to match LinkPreviewCard, so leaving it out can never pick the wrong image source.
   Also reported: linkPreviewDisplay defaults variant to 'post', but LinkPreviewCard defaults it to 'composer'. A future caller that passes a composer preview without a variant would get mediaUrl() image handling instead of the https-only external image.
   Also reported: linkPreviewDisplay defaults variant to 'post' but LinkPreviewCard defaults to 'composer'. A future caller that omits variant for a composer preview would get the post image path (mediaUrl, http allowed) instead of https-only.

## Acceptance Criteria

- [ ] Each finding above is fixed with a test, or the Work Log records why it was left as is.

## Work Log

- 2026-09-30: Filed from todo-sweep run 2026-10-01-0121, PR #907 review rounds 1-2.
