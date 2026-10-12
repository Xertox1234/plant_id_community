---
status: pending
priority: p4
issue_id: "604"
tags: [todo-sweep, harness, security, follow-ups]
dependencies: ["618"]
owner_decision: "Owner decision 2026-10-11: after 618 merges, verify probes denied, fix item 9, close. 618 merged (#1095); verify-only (2026-10-12)"
triage: ready
triaged: 2026-10-12
---

# Follow-ups from PR #1049 (todo 584, worker git guard follow-ups)

## Problem

Todo-sweep run 2026-10-11-2219 merged PR #1049 (todo 584, worker git guard follow-ups). The non-blocking review findings are below. The curator merged duplicates and checked each item against main, and the refuter dismissed what is listed as dropped. An item the curator did not return was kept as stored, unchecked. Line numbers are as of the PR head, so re-check each against main before acting on it.

Every medium below is a fail-open in the worker git guard: a probed command the guard ALLOWS that stages in the main checkout. Before arming #1049 they were probed against origin/main's guard as well; all were already allowed there, so none is a regression from #1049, but they are real bypasses and should be fixed together (the shared root cause is zsh-only grammar applied to every shell). The cap of 10 left out 9 more locations.

## Findings

PR #1049 (todo sweep run 2026-10-11-2219, group g2, todos 584); follow-ups: verified; 3 item(s) the curator did not return were kept as stored.

1. **medium** `scripts/todos/worker_git_guard.py:396` compound_delta (and segments) count reserved words that are not in command position: a trailing `}` argument (`echo }`, a closer only in zsh) and case patterns named fi/done/esac/if/} change the nesting level, so a piped group's stage ends early or never pops and a cd inside fails open under bash/zsh. | also: compound_delta counts a trailing `}` argument as a closer (zsh rule). bash treats it as data, so the finding-4 stage tracking ends a piped group early. From MAIN, `bash -c 'true | { echo }; cd WT; }; git add -A'` is allowed, but bash undoes the cd and stages MAIN. (reported at :169) | compound_delta also counts reserved words in case-pattern segments (`y) ;; if)`). The piped group's level never returns, so its stage never pops and a cd inside sticks. Probed: `true | { case x in y) ;; if) ;; esac; cd WT; } | cat; git add -A` from MAIN under zsh is ALLOWED. (reported at :471) | Finding-4 fix is bypassable under bash: segments() and compound_delta() treat a trailing `}` argument (`echo }`) as closing the piped group. Verified: `bash -c 'true | { cd MAIN; echo }; git add -A; }'` from WT is ALLOWED, yet git add -A runs in MAIN. (reported at :412)
2. **medium** `scripts/todos/worker_git_guard.py:785` shopt_lastpipe fails closed only for -u: outside a function body, `shopt -s lastpipe` still sets True even when it may not run (subshell, `&&`, pipeline stage). `bash -c '(shopt -s lastpipe); true | cd WT; git add -A'` from MAIN is ALLOWED, but git add stages in MAIN.
3. **medium** `scripts/todos/worker_git_guard.py:102` OPENERS/CLOSERS include zsh-only `foreach`/`end` for every shell; in bash they are plain commands, so the level counter desyncs and fails open, e.g. `bash -c 'true | { foreach; cd WT; }; git add -A'` from MAIN is ALLOWED. | also: `bash -c 'f() { true; end; cd MAIN; }; cd WT; f; git add -A'` from WT is ALLOWED; real bash stages in MAIN.
4. **medium** `scripts/todos/worker_git_guard.py:180` The function-body fix misses zsh's multi-name form `f g() { ... }`: `f g() { git add -A; }; cd MAIN; g` from WT is ALLOWED, because the body is judged at definition time in WT but runs after the cd, in MAIN.
5. **medium** `scripts/todos/worker_git_guard.py:105` CD_PROGRAMS and the plain cd tracking omit zsh's `chdir` builtin (a cd synonym in the agents' shell): `chdir MAIN; git add -A` and `f() { chdir MAIN; }; f; git add -A` from WT are both ALLOWED and stage in MAIN. | also: The new CD_PROGRAMS = {cd, pushd, popd} leaves out zsh's `chdir`. The plain-cd check at line 862 has the same gap from before this PR.
6. **medium** `scripts/todos/worker_git_guard.py:169` compound_delta counts a trailing `}` argument as a closer (zsh rule). bash treats it as data, so the finding-4 stage tracking ends a piped group early. From MAIN, `bash -c 'true | { echo }; cd WT; }; git add -A'` is allowed, but bash undoes the cd and stages MAIN. I confirmed bash keeps the old cwd.
7. **medium** `scripts/todos/worker_git_guard.py:471` compound_delta also counts reserved words in case-pattern segments (`y) ;; if)`). The piped group's level never returns, so its stage never pops and a cd inside sticks. Probed: `true | { case x in y) ;; if) ;; esac; cd WT; } | cat; git add -A` from MAIN under zsh is ALLOWED, but zsh stages in MAIN.
8. **medium** `scripts/todos/worker_git_guard.py:412` Finding-4 fix is bypassable under bash: segments() and compound_delta() treat a trailing `}` argument (`echo }`) as closing the piped group, which is zsh semantics. Verified: `bash -c 'true | { cd MAIN; echo }; git add -A; }'` from WT, and SHELL=/bin/bash `true | { cd MAIN; echo }; git add -A; }`, are ALLOWED, yet git add -A runs in MAIN.
9. **low** `scripts/todos/worker_git_guard.py:1205` Formatting slip `name =arg[2:]...` (missing space after `=`) in denied_option, introduced by the repair edit; behaviour unchanged but Black would flag it.

9 more location(s) were dropped by the cap of 10 (the most severe are kept).

Dropped by curation (fixed on main, refuted, or not a reported location):

- medium: scripts/todos/worker_git_guard.py:456 `shopt -s lastpipe` inside an uncalled function body sets CONTEXT['lastpipe'] at definition time, so `bash -c 'f() { shopt -s lastpipe; }; true | cd WT; git add -A'` from MAIN is ALLOWED although f never ran and git add runs in MAIN. (fixed on main: shopt_lastpipe on origin/main returns None when CONTEXT['deferred'] (function body); with lastpipe None, bash last_stage_cwd uses either_main(before, after), so from MAIN the cwd stays a main checkout.; the refuter agreed: function_body_start detects `f() {` and sets CONTEXT deferred=True for the body. shopt_lastpipe then returns None, and nothing restores it after the body. Under bash, last_stage_cwd with lastpipe None returns either_main(MAIN, WT), a main checkout. So it is no longer a fail-open.)

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-11 - Filed from the PR #1049 review (todo sweep run 2026-10-11-2219)

Filed by the closing step of the run from `state.py followups-md g2`.

### 2026-10-11 - Owner decision: fixed by todo 618

The owner chose todo 618's option 2 (require `-C` inside `.claude/worktrees/`). That retires the cwd tracker that
items 1–8 bypass, so they are not patched one by one. After 618 merges: check that each probe here is denied
(618 AC 2 adds them as tests), fix item 9's formatting if it is still on main, and close this todo.
