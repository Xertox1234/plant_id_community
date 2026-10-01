---
status: pending
priority: p4
issue_id: "487"
tags: [testing, backend, web, forum]
dependencies: []
source_review: "PR #879"
triage: ready
triaged: 2026-09-30
---

# Todo 464's new tests: non-blocking findings from PR #879

## Problem

PR #879 added tests for four behaviours that had shipped untested. Both review rounds were
clean. These are the non-blocking findings.

## Findings

1. **`Reaction.recount`'s row lock is still untested.** The race test runs both requests on one
   connection in one transaction, so it proves only the unique-constraint double INSERT.
   Deleting `select_for_update` in `Reaction.recount` leaves the suite green. Todo 464's AC 2 asked
   for "a ReactionToggleView concurrency test", and its Work Log says the lock half was reasoned,
   not tested (`test_replies_reactions.py:281`).
2. **The race test fails obscurely if the view changes shape.** The interleave hooks
   `Reaction.objects.filter(...).first()`. If the view switches to `.exists()` or `.get()`, the test
   dies with a bare `KeyError: 'a'`. Assert the hook fired first (`test_replies_reactions.py:322`).
3. **The breaker tests track the constant instead of pinning it.** Both derive their failure count
   from `PLANTNET_CIRCUIT_FAIL_MAX`, so shrinking it to 1 still passes. Pin the documented 5
   (`test_plantnet_circuit_breaker.py:76`; the `docs/rules/testing.md` constant-tracking rule).
4. **A comment is wrong.** "A distinct colour per call keeps each cache key distinct" is false:
   after the JPEG q85 re-encode, `(0,0,0)` and `(1,0,0)` are byte-identical
   (`test_plantnet_circuit_breaker.py:73`). The test is still correct, because failures are never
   cached.
5. **`Editor` comes from an undeclared package.** `TipTapEditor.test.tsx:5` imports it from
   `@tiptap/core`, which `web/package.json` does not declare. `@tiptap/react` re-exports it.
6. **A 15-line upload closure is duplicated** across two tests in `test_ratelimits.py:361`.

## Acceptance Criteria

- [ ] A test fails when `select_for_update` is removed from `Reaction.recount` (for example, a
      `CaptureQueriesContext` assertion for `FOR UPDATE`), or this todo records why not.
- [ ] The race test asserts that its hook fired before reading the result.
- [ ] `PLANTNET_CIRCUIT_FAIL_MAX == 5` is pinned with a literal.
- [ ] The cache-key comment is corrected, or the colours are spread far enough apart to survive
      JPEG.
- [ ] `TipTapEditor.test.tsx` imports `Editor` from `@tiptap/react`.
- [ ] The upload helper is shared.

## Work Log

### 2026-09-28 - Filed from PR #879 rounds 1 and 2 (todo sweep run 2026-09-28-2018)
