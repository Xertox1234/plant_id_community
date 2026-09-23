---
status: completed
priority: p3
issue_id: "399"
tags: [web, tailwind, ci, tooling]
dependencies: []
---

# CI guard: fail on a `className` utility the built CSS does not define

## Problem

Tailwind 4 emits nothing for an unrecognised utility. There is no build error
and no lint failure, so an invented class name ships as a silently missing
style. Todo 374 shipped `rounded-card` (square corners on three elements) this
way. It was caught only by a manual build-and-grep.

Todo 396 asked for a guard: build the CSS, extract every class literal from
`src/`, and fail on any utility the bundle does not define. **Declined for that
PR, filed here**, because it is not small.

## Why it is not small (measured in todo 396)

1. **A naive checker gives false positives.** Todo 396 was itself filed on a
   false negative. `grep '\.ring-primary' dist/assets/*.css` came back empty,
   but the class compiles: Tailwind emits only the forms that source uses, and
   all 22 uses were `focus:` / `focus-within:` prefixed. The build has
   `.focus\:ring-primary:focus{...}` and no bare `.ring-primary`. So the guard
   must match each token's exact escaped form, for example `focus:ring-2` →
   `.focus\:ring-2`, `bg-black/50` → `.bg-black\/50`, `max-h-[80vh]` →
   `.max-h-\[80vh\]`. It must not match the stripped base name.
2. **Class strings are not all literals.** Many are template literals with
   conditionals, e.g. `IdentificationResults.tsx:128` and
   `SettingsPage`'s `pending[...] ? ... : ...`. Some are built in helpers or
   passed through a `className` prop. The extractor needs a policy on dynamic
   fragments.
3. **Non-Tailwind classes share the attribute.** These include `gt-*`,
   `canopy-*`, `wf-*` and `forum-editor-content` from `index.css`, plus
   ProseMirror and TipTap classes. They need an allowlist, or a check that
   accepts any selector present in the built CSS, not just utilities.

## Recommended Action

Write a script (`web/scripts/check-tailwind-classes.mjs`) that:

- runs after `vite build`;
- collects the string-literal tokens from `className=` / `class=` in `src/**/*.tsx`
  (template-literal static parts included);
- escapes each token the way Tailwind does;
- asserts `.<escaped>` occurs in `dist/assets/*.css`;
- reads an explicit allowlist for classes the script can't resolve.

Wire it into `web-ci.yml` after the build step. Seed the check by planting
`rounded-card` in a scratch file and confirming it fails.

## Acceptance Criteria

- [x] The script fails on an invented utility (`rounded-card`) and passes on
      variant-prefixed real ones (`focus:ring-primary`, `focus-within:ring-2`).
      2026-09-23, planted `rounded-card md:rounded-card focus:ring-primary
      focus-within:ring-2` in `src/components/PlantedScratch.tsx`, rebuilt:
      exit 1, `PlantedScratch.tsx:2  rounded-card` and `md:rounded-card`
      flagged, the two real classes passed. Scratch file removed; exit 0.
      Pinned by `src/tests/checkTailwindClasses.test.ts` (16 tests).
- [x] It runs in CI on every web PR: a step "Build, then check class names
      against the built CSS" (`npm run check:classes`) was added to the required
      `web-checks` job in `web-ci.yml`, which has no path filter on
      `pull_request`
- [x] The allowlist of unresolvable/dynamic classes is short and each entry
      says why: 2 entries (`gt-density`, `gt-mode`, both "localStorage key in
      ThemeContext KEYS, not a class"). Dynamic fragments are skipped by rule,
      not allowlisted.

## Work Log

### 2026-09-23 - Filed from todo 396

Todo 396's AC2 asked for a decision on this guard. The decision: worth
building, but it is more than a small change, for the three reasons above.

### 2026-09-23 - Completed

- **Design.** The CSS side is unescaped, not the tokens escaped:
  `.focus\:ring-primary` → `focus:ring-primary`, `.\32 xl\:flex` → `2xl:flex`,
  then exact `Set` lookup. Hand-written `index.css` classes (`gt-*`, `canopy-*`,
  `wf-*`, `ProseMirror`) are selectors too, so none needed an allowlist entry.
  The source side walks every string/template literal with the TypeScript
  parser, so class constants (`POST_CARD_PADDING`, `TILE_BOX.sm`) and ternaries
  inside template literals are covered. Skipped: non-class JSX attributes (`id`,
  `data-testid`), literals passed straight to a call (log messages, selectors,
  storage keys), and tokens glued to `${...}` (129 fragments on main). A token
  is looked up only if it contains `-`, `:`, `/` or `[` and its utility head is
  the head of some built class.
- **Run on main:** 143 files, 6378 tokens checked against 750 built classes.
  3 hits: 1 dead class, 2 false positives. Found 1 dead class, fixed 1:
  `forum-link-preview-card` in `LinkPreviewCard.tsx` had no CSS and no other
  reference, so it was removed. `gt-density` / `gt-mode` are localStorage keys
  and went on the allowlist. The first, cruder run found 108 hits, all log
  prefixes (`[AuthContext]`), test ids and ids, which the skips above remove.
- **Found while building:** Tailwind scans `web/scripts/`, so utilities named
  in the checker's own comments (`2xl:flex`, `md:hover:-mt-2`) were compiled
  into the bundle. `@source not '../scripts'` in `index.css` stops it (750
  classes again).
- **Mutation testing:** 12 of 13 mutants caught. They were: no hex unescape,
  comments kept, quoted values kept, the fragment rule off at either end, all
  JSX attributes scanned, call arguments scanned, the loose `[...]` rule,
  templates not scanned, the allowlist ignored, the 396-shape base-name match,
  and variants not stripped for the head. The survivor, the at-rule prelude
  skip, had no effect, so it was removed.
- **Verification:** `npm run check:classes` exit 0; tsc, eslint (which now
  lints `scripts/**/*.mjs`) and prettier clean; full vitest 101 files, 1410
  tests passed.

### 2026-09-23 - Review round 1 (bundled /code-review): 1 blocking, fixed

- **Blocking:** the "looks like a utility" filter applied to class attributes
  too, so a token whose first segment matched no built class was never
  checked. Live on main: `prose prose-sm` (CategoryListPage) and
  `prose prose-green` (DiagnosisDetailPage) passed because only
  `max-w-prose` is built. Invented families (`shadow-card`) and first-segment
  typos (`roundd-sm`) passed too. **Fix:** a literal in class position (class
  attribute, or a `classList.add/remove/toggle/replace/contains` argument) is
  checked token by token with no filter. Values compared or used as keys
  inside a class attribute (`tab === 'active'`, `TONES['warm']`) and literals
  inside an interpolation glued to text (`` `language-${lang || 'text'}` ``)
  are excluded. The `classList` part was the review's low finding; it is the
  same mechanism, so it went in with the fix.
- **Re-run on main:** 6992 tokens checked (was 6378), 5 hits. `text` was a
  false positive (the glued-interpolation case, now excluded). The other 4
  were dead: `prose`, `prose-sm`, `prose-green`. **Dead classes found 4 in
  total (with `forum-link-preview-card`), fixed 4:** all removed. That changes
  nothing on screen, because none ever compiled. The rich-text styling `prose`
  was meant to supply is a design decision, filed as **todo 401**.
- **Mutation testing, re-run:** 16 of 16 caught (4 new mutants: strict mode
  ignored, classList not detected, compared values checked, glued
  interpolation checked). One mutant survived at first ("variants not
  stripped for head"), because `md:rounded-card` was then tested only in class
  position; a constant-held `md:rounded-card` now pins it.

### 2026-09-23 - Review round 2 (bundled /code-review): verified, 0 blocking

- Both round-1 fixes confirmed by probes; current `src/` passes (exit 0,
  6987 tokens). Two non-blocking edges (call arguments inside a class
  attribute checked as classes; a conditional inside `classList.add()` falls
  back to the shape filter), neither present in `src/`, filed as **todo 402**.
