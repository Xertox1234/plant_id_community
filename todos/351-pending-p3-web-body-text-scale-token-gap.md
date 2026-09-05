---
status: pending
priority: p3
issue_id: "351"
tags: [web, design-system, forum]
dependencies: []
---

# Add a body-text type scale — forum has 20+ arbitrary font sizes where tokens should be

## Problem

The Canopy/Green Thumb design system tokenizes display typography
(`gt-display`, `gt-h1–h3`, `gt-label`) but has **no body-text scale**, so
forum components improvise with 20+ arbitrary Tailwind values
(`text-[11px]`, `[12.5px]`, `[13px]`, `[13.5px]`, `[14px]`, `[15px]`).
Adherence is excellent everywhere the system has tokens (zero hardcoded
hex colors) and loose exactly here — this is a system gap, not developer
discipline.

## Findings

2026-09-04 design adherence audit (grep over `web/src/{components,pages}/forum`):

- Arbitrary text sizes: `ThreadDetailPage.tsx:845,1111,1129`,
  `ThreadListPage.tsx:303,407`, `PlantCareAskPanel.tsx` (14 instances),
  `rail/CommunityExpertsModule.tsx:69`, `rail/ActiveNowModule.tsx:79`,
  `rail/FromTheBlogModule.tsx:44,50`, `IdentificationCard.tsx:41`.
- Worst case: thread title overrides the token
  (`gt-display text-[26px] sm:text-[34px]`, `ThreadDetailPage.tsx:845`)
  instead of the tokenized display scale.
- Radius twin-leaks: `rounded-[10px]` = `rounded-sm`'s value
  (`rail/ActiveNowModule.tsx:71`) — the exact antipattern `dimensions.ts`
  warns against ("the token, not an arbitrary twin"); `rounded-[11px]`/
  `[12px]`/`[14px]` sit between the `--radius-*` scale.
- Missed todo-333 follow-through: featured-board artwork dimensions
  duplicated literally between `CategoryListPage.tsx:200`
  (`w-[200px] md:w-[260px]`) and `ForumSkeleton.tsx:178`
  (`max-w-[200px] md:max-w-[260px]`) instead of a shared constant in
  `components/ui/dimensions.ts`.

## Recommended Action

One pass, system-first (fix the token layer, then sweep the call sites):

1. **Add `--text-*` tokens to `@theme inline` in `web/src/index.css`** for
   the rungs actually in use (suggest: `--text-micro: 11px`,
   `--text-meta: 12.5px`, `--text-body-sm: 13px`,
   `--text-body: 14px`, `--text-body-lg: 15px` — final names per the
   design spec under `docs/`). Keep line-heights paired per token. This
   gives `text-meta` etc. utilities and a documented vocabulary.
2. **Sweep the forum call sites** onto the new utilities; consolidate the
   two near-identical sizes (13 vs 13.5, 12 vs 12.5) to single rungs where
   the visual delta isn't load-bearing — record any kept distinctions.
3. **Fix the twin/duplicate leaks:** `rounded-[10px]` → `rounded-sm`;
   extract the 200/260px artwork pair into `dimensions.ts`
   (e.g. `FEATURED_ART_BOX`) shared by `CategoryListPage` and
   `ForumSkeleton`.
4. **Thread title:** either keep `gt-display` as-is (accept the rem) or
   promote the larger hero size into the display scale — don't keep a
   per-component override.
5. Sweep the rest of web (`home/`, `diagnosis/`, `blog` cards) for the
   same arbitrary-size pattern in the same pass — evidence before claims:
   grep count before/after.

## Technical Details

- Token layer: `web/src/index.css` `@theme inline` block (lines 176-212)
  and radius scale (lines 215-222).
- Shared-dimension precedent + rationale:
  `web/src/components/ui/dimensions.ts` (todo 333).
- Tailwind 4 arbitrary-value scanning: full class names only (per the
  dimensions.ts docstring) — constants must be complete strings.

## Acceptance Criteria

- [ ] `--text-*` scale in `index.css`; zero `text-[NNpx]` or
      `text-[NN.Npx]` utilities remain under `components/forum/` and
      `pages/forum/` (grep shows 0)
- [ ] `rounded-[10px]` twin removed; no radius value duplicates a token
- [ ] Featured-artwork dimensions flow through `dimensions.ts` in both
      card and skeleton
- [ ] `npm run type-check`, `npm run lint`, `npm run test` green; visual
      smoke of forum pages in dark + light

## Work Log

### 2026-09-04 - Filed

- Surfaced by the 2026-09-04 design-system adherence audit: forum rated 8/10
  overall, with typography (6/10) as the sole systemic gap — colors, dark
  mode, and materials at 9-10/10. One token-layer fix closes nearly every
  call-site violation.
