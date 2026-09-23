---
status: pending
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

- [ ] The script fails on an invented utility (`rounded-card`) and passes on
      variant-prefixed real ones (`focus:ring-primary`, `focus-within:ring-2`)
- [ ] It runs in CI on every web PR
- [ ] The allowlist of unresolvable/dynamic classes is short and each entry
      says why

## Work Log

### 2026-09-23 - Filed from todo 396

Todo 396's AC2 asked for a decision on this guard. The decision: worth
building, but it is more than a small change, for the three reasons above.
