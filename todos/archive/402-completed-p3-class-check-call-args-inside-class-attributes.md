---
status: completed
priority: p3
issue_id: "402"
tags: [web, tailwind, ci, tooling]
dependencies: []
---

# Class check: call arguments inside a class attribute are checked as classes

## Problem

Todo 399's `web/scripts/check-tailwind-classes.mjs` checks every literal in
class position with no filter (review round 1's fix). Review round 2 found two
edges in that rule. Neither occurs in `src/` today (the check passes on main).

1. **False positive.** A literal passed to any call *inside* a class attribute
   is checked as a class name. Each of these would fail CI on the token shown:
   - `className={tags.includes('featured') ? 'flex' : ''}` flags `featured`
   - `className={href.startsWith('/forum') ? … : …}` flags `/forum`
   - `className={variantClass('primary')}` flags `primary`
   - `className={['a', 'b'].includes(x) ? … : …}` flags `a` and `b`
   - `className={'foo' in obj ? … : …}` flags `foo`

   The only escape is `ALLOWLIST`, which is meant for real exceptions, so the
   first person to write one of these gets a confusing CI failure.
2. **False negative.** `isClassListArgument` matches only a literal passed
   directly. In `el.classList.add(on ? 'bogus-x' : 'flex')` the literals sit
   in a conditional, fall back to the utility-shape filter, and `bogus-x`
   passes.

## Recommended Action

- Inside a class attribute, treat a call argument as classes only when the
  callee is a class-joining helper (none exists in the repo today). Otherwise
  skip it, as the script already does outside class attributes. Also skip the
  `in` operator's left operand, and array elements whose array is the object
  of a method call.
- Let `isClassListArgument` climb through parentheses, conditionals and
  `||` / `??`, as `inGluedInterpolation` does.
- Add a unit test per probe above to `src/tests/checkTailwindClasses.test.ts`,
  mutation-checked.

## Acceptance Criteria

- [x] Each probe in (1) passes the check, and each has a test
- [x] `el.classList.add(on ? 'bogus-x' : 'flex')` is flagged, with a test
- [x] `npm run check:classes` still passes on main

## Work Log

### 2026-09-23 - Filed from todo 399 review round 2

Non-blocking under the two-round review budget. The probes came from the
bundled `/code-review` round 2.

### 2026-09-24 - Completed (goal run, todo-next → completing-todos)

- **Call arguments inside a class attribute.** A literal passed to a call is
  now skipped inside a class attribute too, unless the callee is a
  class-joining helper (`clsx`/`cn`/`cx`/`classNames`/`twMerge`/`twJoin`,
  none in the repo today). The `in` operator's left operand and the elements
  of an array searched with a lookup method (`includes`/`indexOf`/
  `lastIndexOf`) are treated like compared values: not class position. Any
  other array method keeps its elements in class position, since
  `[...].filter(Boolean).join(' ')` builds a class string.
- **classList false negative.** `isClassListArgument` now climbs through
  parentheses, conditional branches (not the test) and `||` / `??`.
- Tests (`src/tests/checkTailwindClasses.test.ts`): one per probe
  (`it.each`), plus the surrounding classes still checked, helper args,
  `.join` elements, both classList shapes, and a classList condition that is
  not a class. `Tests  26 passed (26)`.
- Mutation check, each change reverted in turn against a copy of the script:
  call-arg skip → 4 failed; `in` left → 1; array-method → 1; classList climb
  → 1; helper → 1; `.join` → 1. First run had the helper and `.join`
  mutations SURVIVING (their test tokens were flagged by the non-strict path
  either way); the tests now use `prose`, which only the strict path flags.
- `npm run check:classes` on this branch: `133 files, 5737 class tokens
  checked against 710 built classes; 136 dynamic fragments skipped.` —
  identical to main's checker on the same build, confirming none of these
  shapes occurs in `src/` today.

### 2026-09-24 - Review round 1 (bundled /code-review) — 2 findings, both repaired

- **Medium, confirmed by probe:** the first cut treated elements of *any*
  non-`.join` array method as values, so
  `['p-2', 'prose'].filter(Boolean).join(' ')` stopped flagging `prose`
  (main flagged it). Fixed by inverting the rule: only a lookup method
  (`includes`/`indexOf`/`lastIndexOf`) makes elements values. The `.join`
  special case in `isClassJoinCall` became dead code (its mutation
  survived), so it was removed.
- **Low:** `twJoin` was missing from `CLASS_JOIN_HELPERS`; added.
- New tests for both. Mutation check after the repair: all 7 mutations
  killed (call-arg skip 4, `in` 1, array branch 1, lookup-any 1, classList
  climb 1, helper 1, twJoin 1). `Tests 26 passed (26)`; `check:classes`
  still `5737 class tokens`.
