---
status: completed
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

- [x] `--text-*` scale in `index.css`; zero `text-[NNpx]` or
      `text-[NN.Npx]` utilities remain under `components/forum/` and
      `pages/forum/` (grep shows 0)
- [x] `rounded-[10px]` twin removed; no radius value duplicates a token
- [x] Featured-artwork dimensions flow through `dimensions.ts` in both
      card and skeleton
- [x] `npm run type-check`, `npm run lint`, `npm run test` green; visual
      smoke of forum pages in dark + light

## Work Log

### 2026-09-04 - Filed

- Surfaced by the 2026-09-04 design-system adherence audit: forum rated 8/10
  overall, with typography (6/10) as the sole systemic gap — colors, dark
  mode, and materials at 9-10/10. One token-layer fix closes nearly every
  call-site violation.

### 2026-09-05 - Started by completing-todos skill (run 2026-09-05-1142)

- Picked up by automated workflow.

### 2026-09-05 - Implemented (run 2026-09-05-1142)

Decisions:

- **Token layer:** a static `@theme` block in `index.css` (like the radius
  scale): `--text-micro` 11, `--text-meta` 12.5, `--text-body-sm` 13,
  `--text-body` 14, `--text-body-lg` 15, `--text-lead` 17 and `--text-hero`
  38 (the one display rung used as a responsive override, `gt-h1
  md:text-hero`), each with a paired `--line-height`. Display sizes stay on
  the `gt-*` classes.
- **Sweep = one deterministic script** over `src/**/*.tsx` (tests untouched;
  no test asserted a class name): 11/11.5→micro, 12/12.5→meta,
  13/13.5→body-sm, 14/14.5→body, 15→body-lg, 17→lead, 38→hero,
  10/10.5→micro — the sub-pixel twins were consolidated; the visual delta is
  not load-bearing anywhere they occurred (meta rows, badges, kbd hints).
- **Recorded exceptions (5 remain, none in forum):** AppShell wordmark
  micro-label 9.5px (tracked uppercase brand mark), StatCard value 22px
  (mono figure), StreamFieldRenderer article `h2`/`h3` 24/19px (an article
  scale, not body text — promoting them to `gt-h2/h3` would change the font
  family of every blog article).
- **Thread title:** `gt-display` alone (32px at every width; the
  26/34 override was the antipattern). Hero titles: `gt-h1 md:text-hero`.
- **Radius:** `rounded-[10px]` → `rounded-sm` (ActiveNowModule, HomeActivity —
  the twin of `--radius-sm`). The 11/12/14px values in `dimensions.ts` sit
  between rungs by design and stay (documented there).
- **Artwork:** `FEATURED_ART_WIDTH` / `FEATURED_ART_MAX_WIDTH` in
  `dimensions.ts`, shared by CategoryListPage, BlogListPage and the skeleton.
- A write-time trigger (`web-arbitrary-text-size`) now fires on any new
  `text-[NNpx]` under `web/src/**/*.tsx`.

Evidence (grep counts before → after):

```text
$ rg -o 'text-\[[0-9.]+px\]' src | wc -l            → 101 → 5 (the recorded exceptions)
$ rg -o 'text-\[[0-9.]+px\]' src/components/forum src/pages/forum | wc -l → 27 → 0
$ rg -c 'rounded-\[10px\]' src | wc -l              → 2 → 0
$ rg -n '200px\] md:' src | grep -v dimensions.ts   → 3 → 0
$ npm run type-check → exit 0; eslint + prettier clean on the 30 changed files
$ npx vitest run → Test Files 96 passed (96) / Tests 1236 passed (1236)
```

Visual smoke (Playwright, chromium, 1280×900 and 360×780, `gt-mode` light
and dark, local dev servers): forum index, "General Discussion" board and a
thread page — meta rows, badges, rail modules and thread titles all render
on the new rungs; the thread title on `gt-display` wraps cleanly at 360px
with no horizontal overflow. Screenshots reviewed in the session scratchpad
(`shots351/{forum,category,thread}-{light,dark}.png`, `thread-*-360.png`).
Note: the board page first showed "An unexpected error occurred" because the
local dev DB lacked this branch's migrations 0034/0035 (the running server
selects the new profile column) — `manage.py migrate` fixed it; not a web
regression.

### 2026-09-05 - Review round 1 (react-typescript): 6 findings — 4 repaired, 2 info

The reviewer built the CSS against the installed tailwindcss 4.2.4 and
confirmed the `--text-<name>--line-height` pairing, that `leading-*` still
wins at the 12 combined sites, the `@layer theme, base, components,
utilities` order (so `md:text-hero` overrides `.gt-h1`), and the scanner
seeing the `dimensions.ts` strings.

- **MEDIUM no guard against re-introducing `text-[NNpx]`** → `src/designTokens.test.ts`
  pins the seven tokens with paired line-heights and scans `src/**/*.tsx`
  against an explicit allowlist of the recorded exceptions (mutation:
  re-adding `text-[13px]` to ThreadListPage → 1 failed). The write-time
  trigger covers the edit moment; the test covers CI.
- **LOW hero rung tightened gt-h1's leading** (1.02 vs 1.1) → `--text-hero--line-height: 1.1`
  so the responsive override changes size only.
- **LOW thread title lost its 26px mobile size with no wrap safety** →
  `break-words` on the h1 (visual smoke at 360px already wrapped cleanly).
- **INFO article wrapper line-height drifted 1.5 → 1.55** → `text-body-lg`
  pairs 1.5, matching the previously inherited preflight value.
- INFO `gt-label` + `text-body-sm` leading 1.45 — accepted (sub-pixel).

```text
$ npx vitest run → Test Files 97 passed (97) / Tests 1244 passed (1244)
$ npm run type-check → exit 0; eslint + prettier clean
```

### 2026-09-05 - Acceptance criteria flipped (evidence)

- AC1: `rg -o 'text-\[[0-9.]+px\]' src/components/forum src/pages/forum | wc -l` → 0 (was 27); the scale is in `index.css` and pinned by `designTokens.test.ts`.
- AC2: `rg -c 'rounded-\[10px\]' src` → 0 (was 2); the remaining 11/12/14px radii sit between rungs by design in `dimensions.ts`.
- AC3: `FEATURED_ART_WIDTH` in CategoryListPage + BlogListPage, `FEATURED_ART_MAX_WIDTH` in ForumSkeleton — `rg '200px\] md:' src | grep -v dimensions.ts` → 0.
- AC4: type-check exit 0, eslint clean, vitest 1244 passed; visual smoke of forum index/board/thread in light + dark (1280 and 360 wide) reviewed.

### 2026-09-05 - Completed by completing-todos skill (run 2026-09-05-1142)

- Verification: all 4 acceptance criteria passed (web 1244; grep counts 101 → 5 web-wide, 27 → 0 forum).
- Review: react-typescript, 6 findings (1 medium) — repaired in one round.
- Codified: `docs/rules/react.md`, `web/docs/patterns/tailwind.md`, trigger `web-arbitrary-text-size`.
