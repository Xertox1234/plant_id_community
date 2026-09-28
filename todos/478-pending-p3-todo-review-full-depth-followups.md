---
status: pending
priority: p3
issue_id: "478"
tags: [harness, todo-sweep]
dependencies: []
---

# Todo sweep: non-blocking findings from PR #873 round 1 (full-depth review)

## Problem

PR #873 moved the review stage's fan-out into `todo-review.js` (todo 472 item 2).
Round 1 used the bundled `/code-review` at high effort and found 10 issues. The PR
fixed 9 of them: the refute rule now covers every phrasing on a line, the routing
floor is checked in code, dead refute judgments keep the finding blocking, refuted
findings persist in the run file, the domain reviewers get the read-only git guard,
round 2 has a `rerun` step, the routing caps were raised, and paths are normalized.
These were left for later.

## Findings

1. **Each domain reviewer gets the whole changed-file list.** The ROUTING record has
   no per-agent file mapping, so `flutter-dart-reviewer` also sees the `.py` files on
   a mixed diff. This costs tokens and invites out-of-domain checklist findings. The
   orchestrator's routing table assigns files to agents, so ROUTING could carry
   `{agent: [files]}` and `domainPrompt` could pass each agent its own files.
2. **The null-judgment path has no test.** `candidates.forEach` keeps a finding
   blocking when its whole refute judgment is null. The stub harness can't make the
   inner `parallel` return null, so a mutation back to `judged.filter(Boolean)` is
   not caught.
3. **`MUST_ROUTE` repeats three rows of the orchestrator's routing table.** If the
   table changes, the workflow floor does not follow. A shared routing file, or a test
   that reads both, would keep them in step.

4. **Round 2 lows.** Non-blocking findings are not path-normalised, so
   `/wt/g1/a.py:2 nit` and `a.py:2 nit` can both land in `followups`
   (`state.py` `ingest_review`). A refuted finding is recorded by its representative
   summary only, so the wrap-up leaves out its `also` phrasings.

5. **Live-run findings (PR #873, runs `wf_25180f55-a2f` and `wf_c08058cf-f8f`).**
   Deduplicated, and none blocking:
   - *Medium:* the routing floor and the domain file lists trust the haiku router's
     own `changed_files`. Five reviewers raised this. Compute the list in
     `state.py review_args` (`git -C WT diff --name-only origin/main...HEAD`) and take
     only `agents_to_invoke` from the router. That also closes the /tmp and
     /private/tmp alias gap in `relPath`.
   - *Medium:* a critical/high finding that both refuters dismiss in round 2 gives
     `clean` and arms auto-merge. It never becomes a follow-up or a PR comment, and
     `refuted` is cut to 10 without saying so.
   - *Medium:* `MUST_ROUTE` has no security rows (`firebase/**` or `*.rules` →
     flutter-firebase and cross-cutting; `functions/**` → firebase-cloudfunction;
     mobile auth or firebase `.dart` → flutter-firebase). Its `.dart` row is also
     looser than the table, which sends every mobile `.dart` to flutter-dart-reviewer.
   - *Medium:* nothing checks the tree between the review lane (8+ Bash-capable
     agents) and the repair worker's `git add -A`, so reviewer residue would be
     staged. Record `write-tree` and porcelain in review-args, and refuse to
     repair if either changed.
   - *Low:* a domain reviewer's "high" for a style-level pattern violation blocks,
     and refuters can't dismiss it because it is real. Cap it at medium unless there
     is a concrete bug.
   - *Low:* `rerun` is not counted in the run file, so the "second rerun → blocked"
     rule lives only in the runbook and is lost on resume.
   - *Low:* `REVIEW_AGENTS` (guard) and `DOMAIN_REVIEWERS` (workflow) are copied by
     hand, and the hook test loop covers 4 of the 9. A reviewer added only to the
     workflow would run unguarded.
   - *Low:* guard gaps: `git grep -O<cmd>`, and `GIT_EXTERNAL_DIFF`/`GIT_PAGER`
     prefixes on diff or log.
   - *Low:* test and doc hygiene. "round 1 with no blocking finding" reuses the
     previous case's `r`. The "no inline range" assertion can't fail on stubs. The
     critical-over-high swap can repeat a phrasing in `also`. The guard's docstring
     and hook header still name only three agents.

## Acceptance Criteria

- [x] Domain reviewers get only their routed files, or this records why not.
- [ ] A test fails when a null refute judgment drops its finding.
- [x] `MUST_ROUTE` and the orchestrator's table can't drift silently (shared source or
      a test).
- [ ] Follow-ups are path-normalised, and a refuted record keeps its `also` phrasings.
- [x] Routing reads a `changed_files` list that `review_args` computes, not the router's.
- [ ] A refuted critical/high finding in round 2 is visible before auto-merge (a follow-up
      or a PR comment), and `refuted` is not truncated silently.
- [x] `MUST_ROUTE` has the firebase, rules and functions security rows, with tests.
- [ ] A change to the PR tree during review stops the round-1 repair.
- [ ] Each remaining item in finding 5 is fixed or recorded here as accepted.

## Work Log

### 2026-09-28 - Filed from PR #873 round 1

- Round 1 of the bundled `/code-review` (high effort); findings 8 and two gaps found
  while fixing it.

### 2026-09-28 - Live-run findings added; raised to p3

- Two live `todo-review` rounds on PR #873 (finding 5). Four mediums touch sweep
  safety (routing trust, refuted criticals, security routing rows, residue before
  repair), so this is now p3.

### 2026-09-28 - Routing items fixed (PR #873)

- `state.review_args` sets `changed_files` from
  `git -C WT diff --name-only -z origin/main...HEAD`, and the router is given that
  list. The router no longer reports files, so its list can't be trusted by mistake.
  That closes the /tmp vs /private/tmp alias gap for routing, but `relPath` still
  strips a literal prefix when deduplicating findings, so that part of finding 5
  stays open.
- `MUST_ROUTE` is replaced by `ROUTES`, which mirrors all 12 rows of the
  orchestrator's table, security rows included: `firebase/**` and `*.rules` →
  flutter-firebase and cross-cutting; `functions/**` → firebase-cloudfunction; a
  mobile path segment starting `auth` or `firebase` → flutter-firebase. The router
  can add reviewers but never remove them, so a missed reviewer is dispatched
  instead of forcing a rerun (`floor_added` records it).
- Each path-routed reviewer gets only the files its rows match. A reviewer only the
  router chose (wagtail, found by content grep) gets every file.
- Drift: each `ROUTES` entry carries its table cell verbatim, and
  `test_workflows.js` compares all 12 rows (pattern and agents) with
  `code-review-orchestrator.md`. The orchestrator doc says to edit both.
- Evidence: `node scripts/todos/test_workflows.js`: all checks pass, with 13
  per-path dispatch cases plus the mixed-diff, file-subset and table-mirror checks.
  Mutations all caught: router-only ids (13 fails), dropping cross-cutting from the
  rules row (4), every reviewer given every file (1), auth matched on the file name
  only (1), an added table row (1).
  `python3 scripts/todos/test_state_flow.py`: all checks pass (NUL-split and exact
  git args).
