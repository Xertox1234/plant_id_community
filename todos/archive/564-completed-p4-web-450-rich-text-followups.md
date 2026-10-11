---
status: completed
priority: p4
issue_id: "564"
tags: [web, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-11
---

# Follow-ups from PR #997 (todo 450, rich-text list markers)

## Problem

Todo-sweep run 2026-10-11-0053 merged PR #997. Its two review rounds reported the non-blocking
findings below. The curator merged duplicates and confirmed each item is still on main; the refuter dismissed none.
Line numbers are as of the PR head, so re-check each against main before acting on it.

## Findings

PR #997 (todo sweep run 2026-10-11-0053, group g2, todos 450); follow-ups: verified; 3 item(s) the curator did not return were kept as stored.

1. **low** `web/scripts/check-tailwind-classes.mjs:370` classValuedGroups promotes a whole conditional to strict class-checking once any one branch is all built classes with a utility-shaped token, so a mixed ternary like `x ? 'sr-only' : 'Show details'` or `big ? 'w-full' : 'auto'` would fail CI on the prose/CSS-value branch. No such case exists today. | also: A conditional with one utility-shaped built class makes every sibling token strict-checked. `x ? 'flex-col' : 'row'` or `a ? 'text-sm' : 'Close menu'` would now be reported as unknown classes (false positive in CI). (web/scripts/check-tailwind-classes.mjs:372) | A mixed ternary like `x ? 'p-2' : 'Loading...'` (or a message sibling) would then flag the prose branch as an unknown class. (web/scripts/check-tailwind-classes.mjs:373)
2. **low** `web/src/components/StreamFieldRenderer.test.tsx:860` The test says the .rich-text paragraph 'restores list markers' but only checks that ul/ol sit under a .rich-text wrapper; jsdom never loads index.css, so deleting the `.rich-text ul/ol` list-style rules would not fail it.
3. **low** `web/src/components/StreamFieldRenderer.test.tsx:868` The absence test 'carries no typography-plugin class' has no presence anchor: if the component rendered nothing, the class list would be empty and it would still pass, so it pins no behaviour beyond the first test. | also: The 'no prose class' test scans the whole container for `prose` classes. Removing the old class would pass it anyway, so it pins no behaviour beyond the first test. Its `.rich-text > ul` anchor test is fine. (web/src/components/StreamFieldRenderer.test.tsx:877)
4. **low** `web/scripts/check-tailwind-classes.mjs:372` A conditional with one utility-shaped built class makes every sibling token strict-checked. `x ? 'flex-col' : 'row'` or `a ? 'text-sm' : 'Close menu'` would now be reported as unknown classes (false positive in CI).
5. **low** `web/src/components/StreamFieldRenderer.test.tsx:877` The 'no prose class' test scans the whole container for `prose` classes. Removing the old class would pass it anyway, so it pins no behaviour beyond the first test. Its `.rich-text > ul` anchor test is fine.
6. **low** `web/scripts/check-tailwind-classes.mjs:373` classValuedGroups promotes a whole conditional to class-checking if any one branch is all built classes with a utility-shaped token. A mixed ternary like `x ? 'p-2' : 'Loading...'` (or a message sibling) would then flag the prose branch as an unknown class.

## Acceptance Criteria

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log

### 2026-10-11 - Implemented by the todo sweep (run 2026-10-11-1448)

- Findings 1, 4 and 6 (one issue): `web/scripts/check-tailwind-classes.mjs` now checks a conditional's sibling branch as classes only when it reads like a class list itself. Every token must be lower case with no prose punctuation, and at least one must be utility-shaped. This is `classValuedLiterals`, which replaces `classValuedGroups`. So `x ? 'p-2' : 'Loading...'`, `'Show details'`, `'auto'` and `'row'` are no longer false positives, while `'prose prose-lg'` beside a class list is still caught. The cost: a lone bare word beside a class list (`x ? 'p-2' : 'prose'`) is no longer caught. `checkTailwindClasses.test.ts` pins both directions, and the todo 450 cases pass unchanged. `npm run check:classes` is clean on `src/`.
- Finding 2: a new test in `StreamFieldRenderer.test.tsx` reads `web/src/index.css` and pins `.rich-text ul` to `list-style: disc` and `.rich-text ol` to `decimal`. The component test, renamed so it no longer claims to prove the markers, pins only the wrapper.
- Findings 3 and 5: the "no typography-plugin class" test first asserts that `.rich-text` and its list rendered, so an empty render can no longer pass the absence check.

### 2026-10-11 - Verified by the todo sweep (run 2026-10-11-1448)

- AC 1: `cd web && npx vitest run src/tests/checkTailwindClasses.test.ts src/components/StreamFieldRenderer.test.tsx` — evidence `.sweep-evidence/g7/564-ac0.txt` (not committed), last lines:

  ```text

   Test Files  2 passed (2)
        Tests  103 passed (103)
     Start at  10:31:10
     Duration  837ms (transform 166ms, setup 110ms, import 435ms, tests 250ms, environment 502ms)
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-11-1448)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
