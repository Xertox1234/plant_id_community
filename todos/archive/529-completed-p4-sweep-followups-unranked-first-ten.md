---
status: completed
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

- [x] With more than ten non-blocking findings, the stored follow-ups keep
  every medium before any low, and record the dropped count (test).
- [x] Two phrasings of one `file:line` are stored as one follow-up (test).
- [x] The follow-up todo written from the run shows each item's severity.
- [x] A group's shared findings are stored once for the group, not copied to each of its todos (test).
      (From todo 537, engine finding 3, promoted 2026-10-10.)
- [x] The completing-todos follow-ups step runs a curation pass per PR (merge duplicates, check each item
      against main) and an adversarial refuter, so the follow-up todo starts from verified items.
      (Optional item 3, included by owner decision 2026-10-10.)

## Work Log

- 2026-10-04: Filed from the codify pass after runs 2026-10-02-0335 and 2343
  (`docs/LEARNINGS.md` 2026-10-02 entry, PR #959).

### 2026-10-10 - Implemented by the todo sweep (run 2026-10-10-1537)

- `ingest-review` stores follow-ups once per group (`run["groups"][G]["followups"]`), as
  `severity: file:line summary | also: …`, merged on file:line with the higher severity kept, ranked medium before
  low on every ingest, capped at 10, and `followups_dropped` = distinct locations seen minus those kept, so a
  round-2 repeat is not counted twice. A pre-529 run file's per-todo lists move to the group and rank last.
- Item 3 (owner decision): new `todo-followups` workflow, one curator per PR (merge duplicates, check each item on
  origin/main through `git -C MAIN show/grep`) then one refuter; `state.py followups-args`, `ingest-followups`
  (keeps an item only at a location the review reported) and `followups-md`, which writes each item's severity
  and the refuted lines under their own heading. The refuted lines never reach the curator or refuter.
- The per-todo `refuted` lists are unchanged: the critical-hold logic reads them per todo and dedupes per group.
- Existing tests that read the per-todo `followups` now read the group's, with the severity prefix.

### 2026-10-10 - Verified by the todo sweep (run 2026-10-10-1537)

- AC 1: `python3 scripts/todos/test_state_flow.py | grep -E '529 AC1|round 2|FAIL|All checks passed'` — evidence `.sweep-evidence/g1/529-ac0.txt` (not committed), last lines:

  ```text
    PASS  529 AC1: with more than ten, every medium is kept before any low, and the dropped count is recorded
    PASS  529: round 2's repeat of the same locations does not double-count the dropped ones
  All checks passed.
  state: --reverify takes stage ready and exactly one --field reason=...
  state: 7: --date must be a YYYY-MM-DD date, not 'tomorrow'
  ```

- AC 2: `python3 scripts/todos/test_state_flow.py | grep -E '529 AC2|more severely|FAIL|All checks passed'` — evidence `.sweep-evidence/g1/529-ac1.txt` (not committed), last lines:

  ```text
    PASS  529: a location re-reported more severely takes the higher severity and keeps both phrasings
    PASS  529 AC2: two phrasings of one file:line are stored as one follow-up
  All checks passed.
  state: --reverify takes stage ready and exactly one --field reason=...
  state: 7: --date must be a YYYY-MM-DD date, not 'tomorrow'
  ```

- AC 3: `python3 scripts/todos/test_state_flow.py | grep -E '529 AC3|FAIL|All checks passed'` — evidence `.sweep-evidence/g1/529-ac2.txt` (not committed), last lines:

  ```text
    PASS  529 AC3: the follow-up todo's Findings show each item's severity, and the refuted lines on their own
    PASS  529 AC3: the followups-md command writes that text for the follow-up todo
  All checks passed.
  state: --reverify takes stage ready and exactly one --field reason=...
  state: 7: --date must be a YYYY-MM-DD date, not 'tomorrow'
  ```

- AC 4: `python3 scripts/todos/test_state_flow.py | grep -E '529 AC4|pre-529|FAIL|All checks passed'` — evidence `.sweep-evidence/g1/529-ac3.txt` (not committed), last lines:

  ```text
    PASS  529 AC4: a group's findings are stored once for the group, not copied to each todo
    PASS  529: a pre-529 run file's per-todo follow-ups move to the group and rank after severities
  All checks passed.
  state: --reverify takes stage ready and exactly one --field reason=...
  state: 7: --date must be a YYYY-MM-DD date, not 'tomorrow'
  ```

- AC 5: `python3 scripts/todos/test_state_flow.py | grep -E '529 item 3|529: the runbook|FAIL|All checks passed' && node scripts/todos/test_workflows.js | grep -E '529 item 3|FAIL|All checks passed'` — evidence `.sweep-evidence/g1/529-ac4.txt` (not committed), last lines:

  ```text
    PASS  529 item 3: the git guard allows the curator's two read commands against the main checkout
    PASS  529 item 3: every agentType in todo-followups.js is one the git guard limits to read-only git
  All checks passed.
  state: --reverify takes stage ready and exactly one --field reason=...
  state: 7: --date must be a YYYY-MM-DD date, not 'tomorrow'
  ```

### 2026-10-10 - Completed by the todo sweep (run 2026-10-10-1537)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-10-10 - Repaired by the todo sweep (run 2026-10-10-1537)

- Round-1 review (high): the curator checked each follow-up on origin/main while `followups-args` also took
  `reviewed` groups, whose PR is not merged, so every item the PR added read as `fixed` and was dropped.
- `state.py`: `FOLLOWUP_STAGES` is now `LANDED` (`merged`, `archived`); a reviewed group waits for its merge.
- `todo-followups.js`: the curator first looks for the PR's `(#<pr>)` squash commit on origin/main and returns
  `pr_on_main`; when it is false the group is left `uncurated`, nothing is dropped and no refuter runs.
- The runbook's follow-ups step now runs after the merge, fetches origin/main first, and says why.
- Tests: a reviewed group gets no curation, an archived one does, and a PR missing from origin/main drops nothing.
