---
status: pending
priority: p4
issue_id: "529"
tags: [todo-sweep, engine]
dependencies: []
---

# Sweep follow-ups keep the first ten findings in arrival order, without severity

## Problem

`ingest-review` stores each todo's non-blocking review findings as
`"<file>:<line> <summary>"` strings and keeps the first ten
(`scripts/todos/state.py:1091-1100`):

- **Arrival order, not severity.** A medium that arrives eleventh is dropped
  while ten lows stay. The stored string also drops the severity, so the
  follow-up todo cannot rank what it kept.
- **Exact-string de-duplication.** Several reviewers report the same issue in
  different words, and each phrasing counts as a new finding.

In run 2026-10-02-0335 the merged PRs' review rounds reported 307 non-blocking
findings. A curation workflow (merge duplicates, check each against main, then
an adversarial refuter) kept 56. The main session had to rebuild the full list
from the review workflow outputs, because the run file held only ten per todo.

## Proposed fix

1. Store follow-ups with their severity, and when over the cap keep the most
   severe first (medium before low), saying how many were dropped.
2. De-duplicate by `file:line` (merging phrasings, as `_merge_refuted` already
   does for refuted findings) rather than by the whole string.
3. Optionally, fold the curation pass (one agent per PR merges duplicates and
   checks each item on main; a second tries to refute it) into the follow-ups
   step of `completing-todos`, so the follow-up todo starts from verified items.

## Acceptance Criteria

- [ ] With more than ten non-blocking findings, the stored follow-ups keep
  every medium before any low, and record the dropped count (test).
- [ ] Two phrasings of one `file:line` are stored as one follow-up (test).
- [ ] The follow-up todo written from the run shows each item's severity.

## Work Log

- 2026-10-04: Filed from the codify pass after runs 2026-10-02-0335 and 2343
  (`docs/LEARNINGS.md` 2026-10-02 entry, PR #959).
