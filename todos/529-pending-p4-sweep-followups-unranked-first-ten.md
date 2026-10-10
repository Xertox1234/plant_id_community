---
status: pending
priority: p4
issue_id: "529"
tags: [todo-sweep, engine]
dependencies: []
triage: ready
triaged: 2026-10-10
owner_decision: "Include optional item 3: fold the per-PR curation + refuter pass into the completing-todos follow-ups step, in addition to the severity-ranked cap and file:line merge (2026-10-10)"
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
- [ ] A group's shared findings are stored once for the group, not copied to each of its todos (test).
      (From todo 537, engine finding 3, promoted 2026-10-10.)
- [ ] The completing-todos follow-ups step runs a curation pass per PR (merge duplicates, check each item
      against main) and an adversarial refuter, so the follow-up todo starts from verified items.
      (Optional item 3, included by owner decision 2026-10-10.)

## Work Log

- 2026-10-04: Filed from the codify pass after runs 2026-10-02-0335 and 2343
  (`docs/LEARNINGS.md` 2026-10-02 entry, PR #959).
