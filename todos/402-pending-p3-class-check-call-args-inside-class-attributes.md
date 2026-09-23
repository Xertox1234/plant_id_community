---
status: pending
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

- [ ] Each probe in (1) passes the check, and each has a test
- [ ] `el.classList.add(on ? 'bogus-x' : 'flex')` is flagged, with a test
- [ ] `npm run check:classes` still passes on main

## Work Log

### 2026-09-23 - Filed from todo 399 review round 2

Non-blocking under the two-round review budget. The probes came from the
bundled `/code-review` round 2.
