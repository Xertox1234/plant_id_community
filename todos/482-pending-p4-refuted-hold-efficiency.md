---
status: pending
priority: p4
issue_id: "482"
tags: [harness, todo-sweep]
dependencies: []
---

# Todo sweep: hold at round 1, and dedupe refuted findings by file:line

## Problem

Two non-blocking findings from PR #874's round-1 review, about the critical hold (todo 478):

1. **The hold waits for round 2.** A critical dismissed by refuters in round 1 guarantees a
   `held` outcome at round 2. Round 1 still returns `clean` or `repair-staged`, so the engine
   pays for the repair, the verifier, a commit and push, and a full round 2 before holding.
   This costs agents only: the PR is still never armed.
2. **`refuted` dedupes on the whole line.** Each line carries its `| also: …` phrasings,
   so the same file:line dismissed in both rounds with slightly different wording is stored
   twice. The hold reason then says "2 critical finding(s)" for one bug, and the PR comment
   repeats it.

## Recommended Action

1. In a round-1 ingest, if any dismissed critical exists, return `held` right away. Block the
   group with the hold reason and leave any staged repair uncommitted, for the owner.
2. Key `refuted` on severity plus file:line, and merge the phrasings into one line.

## Acceptance Criteria

- [ ] A critical dismissed in round 1 returns `held` from the round-1 ingest, with a test.
- [ ] The same file:line dismissed in both rounds is one `refuted` line with the phrasings
      merged, with a test.

## Work Log

### 2026-09-28 - Filed from PR #874 review round 1

- Non-blocking; filed under the two-round review budget.
