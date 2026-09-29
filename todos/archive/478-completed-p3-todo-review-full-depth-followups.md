---
status: completed
priority: p3
issue_id: "478"
tags: [harness, todo-sweep]
dependencies: []
triage: ready
triaged: 2026-09-28
owner_decision: "Finding 5: fix all the low items (2026-09-28)"
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

6. **Live run 3 findings (`wf_f1dbd020-8ac`, the new router contract).** Fixed in the
   PR: a router pick now gets every file, since content-grep picks were losing
   files; `--no-renames` on the `changed_files` diff; the refuter wording in
   `todo-reviewer.md`; and a loud-failure test for `review_args`. Left:
   - *Low:* a dead router discards the checklist lane and forces a rerun, though the
     path rules alone could still dispatch every row except wagtail-by-content.
   - *Low:* `routingPrompt` puts raw file names in the router's prompt next to a
     `grep '<wt>/<path>'` instruction, so a name holding `'` or `$(...)` could
     escape quoting. The guard vets only git and gh.
   - *Low:* no test runs `review_args` with the real `run_git` against a temp repo
     that has `origin/main`.

## Acceptance Criteria

- [x] Domain reviewers get only their routed files, or this records why not. (A router pick
      gets every file: its choice may rest on content the path rules can't see.)
- [x] A test fails when a null refute judgment drops its finding.
- [x] `MUST_ROUTE` and the orchestrator's table can't drift silently (shared source or
      a test).
- [x] Follow-ups are path-normalised, and a refuted record keeps its `also` phrasings.
- [x] Routing reads a `changed_files` list that `review_args` computes, not the router's.
- [x] A refuted critical/high finding in round 2 is visible before auto-merge (a follow-up
      or a PR comment), and `refuted` is not truncated silently.
- [x] `MUST_ROUTE` has the firebase, rules and functions security rows, with tests.
- [ ] Review residue before the repair → todo 480 (re-pointed 2026-09-28; owner asked for its own todo)
- [x] Each remaining item in finding 5 is fixed or recorded here as accepted.
- [ ] Finding 6 router hardening → todo 481 (re-pointed 2026-09-28; owner asked for its own todo)

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

### 2026-09-28 - Live run 3: new router contract proven

- Run `wf_f1dbd020-8ac`: round 2 with `changed_files` from `review_args` (14
  files). The router returned ROUTING without a file list, `floor_added: []`
  (it agreed with the path rules), `reviewers_ok: true`, 5 agents, 0 errors,
  12 findings, none blocking. Fixes and leftovers are in finding 6.

### 2026-09-28 - Refuted criticals can no longer auto-merge; residue and router split out

- `ingest_review` keeps refuted findings whole (`<severity>: file:line summary | also: …`,
  no cap). At round 2, if any critical was dismissed only by the refuters, in either
  round, the group is `held`: blocked and reported to the owner, never armed. A
  refuted high doesn't hold the PR, but the runbook posts every refuted finding as a
  PR comment before arming, and the follow-ups PR files them as a todo.
- Evidence: `python3 scripts/todos/test_state_flow.py`: all checks pass, with new
  cases for a round-2 critical hold, a round-1 critical still holding at round 2, 15
  refuted highs kept uncapped and not held, and blocking winning over a refuted
  critical. Three mutations each fail 1–2 checks: removing the hold, restoring the
  `[:10]` cap, and matching only one critical.
- The residue and router items went to their own todos, 480 and 481, as the owner asked.

### 2026-09-28 - PR #874 review round 1 (bundled /code-review high)

- Fixed, blocking:
  - A hold had no exit. New `state.py clear-hold G --decision …` is the only path out:
    blocked-and-held → reviewed, with the owner's decision recorded. It refuses a group
    blocked for any other reason.
  - The PR comment was built with `--body` from LLM text. New
    `state.py refuted-comment G --out FILE` writes the body for `gh pr comment --body-file`,
    so the main session no longer reads the run file by hand.
  - A refuted line without a severity (a run file from before this change) fails
    closed and counts as critical.
  - When round 2 still has blocking findings, the reason also names any dismissed
    critical.
- Also: held groups are owner hand-offs, not p4 follow-ups, and there is a real round-1
  ingest → round-2 hold test.
- Not fixed: holding already at round 1, which would save a repair and a round 2
  (cost only), and deduplicating `refuted` by file:line across rounds (a count can
  double). Both → todo 482.

### 2026-09-28 - Implemented by the todo sweep (run 2026-09-28-2018)

- Null refute judgment (finding 2): `test_workflows.js` `run()` gained `parallelThrows` (a nested
  `parallel()` that throws, as a real one can) and `mutate`. The new check proves a null judgment keeps its
  own finding blocking, and a second check proves that same case fails under `judged.filter(Boolean)`.
- Finding 4: follow-ups and refuted records are path-normalised in `state.ingest_review` (`_rel_file`: the
  worktree prefix in either /tmp or /private/tmp form, and `./`). A refuted record keeps its `also` phrasings.
- Finding 5, every remaining item, each fixed:
  - relPath /tmp alias: `relPath` in `todo-review.js` and `_rel_file` in `state.py` both strip the
    /tmp↔/private/tmp and /var↔/private/var forms.
  - A style-level "high": the domain prompt now says a checklist or pattern deviation is at most medium
    unless the reviewer names the input or state that makes it fail (`CHECKLIST_CAP`).
  - `rerun` counted: `review_reruns` per round in the run file; a second `rerun` or `residue` in a round
    blocks the group from `ingest-review` itself, so the rule survives a resume.
  - REVIEW_AGENTS vs DOMAIN_REVIEWERS: `test_workflows.js` fails if any agentType the review workflow
    dispatches is not guarded, and the hook test loops over all 9 review agents read from the guard.
  - Guard gaps: `git grep -O`/`--open-files-in-pager` (alone or in a bundle) is denied, and so is any
    `GIT_*` assignment (prefix, `env`, `export`). Accepted breadth: that denial is program-agnostic, so
    `GIT_TERMINAL_PROMPT=0 python …` from a guarded agent is refused too.
  - Hygiene: "round 1 with no blocking finding" has its own run; the vacuous "no inline range" check is
    replaced by one that each reviewer's own range is relayed; the critical that takes over as
    representative no longer repeats its summary in `also`; the guard docstring and hook headers name all
    the guarded agents.
- Evidence: `node scripts/todos/test_workflows.js`, `bash .claude/hooks/test-guard-todo-worker-git.sh` and
  `python3 scripts/todos/test_state_flow.py` all pass; each new check was mutation-tested (it fails on the
  old behaviour).

### 2026-09-28 - Verified by the todo sweep (run 2026-09-28-2018)

- AC 2: `node /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-3/scripts/todos/test_workflows.js` — evidence `.sweep-evidence/g8/478-ac1.txt`, last lines:

  ```text
    PASS  476 AC2: items are checked whenever present, even without type: array
    PASS  WORKER schema is identical in execute and review
    PASS  VERDICT schema is identical in execute and review

  All checks passed.
  ```

- AC 4: `python3 /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-3/scripts/todos/test_state_flow.py` — evidence `.sweep-evidence/g8/478-ac3.txt`, last lines:

  ```text
    PASS  482: finish still removes the run file when every todo is terminal and none is held
    PASS  473 AC1: the wrap-up lists a landed todo's earlier blocked worktree (not its removed own one)
    PASS  477 AC4: the rename message prints the source and destination unquoted

  All checks passed.
  ```

- AC 9: `sh -c 'node /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-3/scripts/todos/test_workflows.js; bash /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-3/.claude/hooks/test-guard-todo-worker-git.sh; python3 /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-3/scripts/todos/test_state_flow.py; grep -n -A26 "Implemented by the todo sweep (run 2026-09-28-2018)" /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-3/todos/478-pending-p3-todo-review-full-depth-followups.md'` — evidence `.sweep-evidence/g8/478-ac8.txt`, last lines:

  ```text
  206-    representative no longer repeats its summary in `also`; the guard docstring and hook headers name all
  207-    the guarded agents.
  208-- Evidence: `node scripts/todos/test_workflows.js`, `bash .claude/hooks/test-guard-todo-worker-git.sh` and
  209-  `python3 scripts/todos/test_state_flow.py` all pass; each new check was mutation-tested (it fails on the
  210-  old behaviour).
  ```

### 2026-09-28 - Completed by the todo sweep (run 2026-09-28-2018)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
