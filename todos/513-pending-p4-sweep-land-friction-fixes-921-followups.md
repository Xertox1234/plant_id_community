---
status: pending
priority: p4
issue_id: "513"
tags: [tooling, todo-sweep]
dependencies: []
triage: ready
triaged: 2026-10-01
owner_decision: "Findings 1/9: tighten — accept only when the new blob equals the fixers' output on the verified blob (rstrip per line keeping md two-space breaks, collapse EOF to one newline); refuse added whitespace, CRLF flips, dropped final newline, each with a test. Finding 6: raise the kimi-review hook timeout in .claude/settings.json to 300 s to match the pre-commit gate (2026-10-01)"
---

# Sweep Land friction fixes: non-blocking findings from PR #921 (todo 512)

## Problem

PR #921 (todo 512) merged after two review rounds in todo-sweep run 2026-10-01-1858. The findings below were rated non-blocking, so they were not repaired. Findings at the same file:line are merged; each one says which round reported it. Line numbers are as of the PR head. Re-check each finding against main before acting on it.

## Findings

1. **`scripts/todos/state.py:1165`** (medium, round 1, round 2). \_fixer\_normal is symmetric and uses bytes.rstrip(). It accepts changes that no configured fixer makes: trailing whitespace added, extra blank lines added at EOF, LF to CRLF, and trailing \\v or \\f. The docstring says it accepts only diffs 'as trailing-whitespace and end-of-file-fixer would make them'. This is contained, because it is still whitespace only.
   Suggested: Accept a path only when the actual blob equals the fixers' output on the recorded blob (strip trailing whitespace per line, then collapse EOF to a single newline). Otherwise reword the docstring to say any trailing-whitespace or EOF difference is accepted.
   Also reported: \_fixer\_only\_change compares \_fixer\_normal(before)==\_fixer\_normal(after), which works in both directions. It accepts changes no fixer makes: added trailing whitespace or EOF blank lines, a dropped final newline, removed .md hard breaks (the hook keeps those via --markdown-linebreak-ext=md), and CRLF->LF. If a whitespace-only verified change is lost, the guard passes it.
   Also reported: \_fixer\_normal uses bytes.rstrip(), which also strips \\r, so a CRLF-to-LF rewrite of a verified file is accepted as fixer-only. That is probably intended (mixed-line-ending fixer) but is neither documented nor tested.
   Also reported: \_fixer\_normal is symmetric and broader than the two hooks. It treats CRLF as LF (bytes.rstrip drops \\r, but the hook keeps EOLs), trailing \\x0b/\\x0c, added trailing whitespace and added EOF blank lines all as 'fixer' changes. So ensure-worktree accepts post-verification whitespace edits that no hook makes.

2. **`.claude/skills/completing-todos/SKILL.md:174`** (low, round 2). Stage D step 6 does not say what to do when a fixer hook aborts the Land commit. The rewritten file is left unstaged, so \_unstaged\_outside\_land refuses ensure-worktree. The new tolerance is reachable only if the operator improvises a re-add.
   Suggested: Add to step 6: if pre-commit fixers rewrote files and the commit aborted, `git add` exactly those files, re-run ensure-worktree (it now accepts a whitespace/EOF-only diff), then commit again.

3. **`.claude/skills/completing-todos/SKILL.md:264`** (low, round 1). Wedged-CI recovery commits with --allow-empty after ensure-worktree, which checks the index against tree\_id, not HEAD. A staged todos/, docs/reviews/, .secrets.baseline or whitespace-only edit passes, and the 'empty' commit then pushes it unreviewed.
   Suggested: Before the empty commit, require `/usr/bin/git -C $WT diff --cached --quiet HEAD` and stop if anything is staged. That proves the commit really is empty, so the reviews still hold.

4. **`.claude/skills/completing-todos/SKILL.md:265`** (low, round 2). In the wedged-CI recovery, `git commit --allow-empty` also commits anything staged. ensure-worktree compares the index to tree\_id with Land-path and whitespace tolerance, not to HEAD. A leftover staged todos/, docs/reviews/ or .secrets.baseline change would then be pushed after review, sandbox off, under the 'ci: restart' message.
   Suggested: Before the commit, require that `/usr/bin/git -C $WT diff --cached --quiet HEAD` succeeds. After it, check that HEAD^{tree} equals HEAD~1^{tree}, so the commit is truly empty before the push.

5. **`scripts/kimi-precommit.sh:27`** (low, round 2). The 273 s worst-case figure counts only the three draft attempts. It leaves out the engine's own setup (context gathering, building the prompt) and the deterministic verify. A slow setup past ~27 s can still cut off a third attempt at the 300 s backstop, so the gate can still print 'timed out' at times. Nothing breaks: the gate fails open.
   Suggested: Have the comment say the margin covers the API attempts only, or set KIMI\_REVIEW\_BUDGET\_SECONDS below GATE\_TIMEOUT (e.g. 280) so the engine's own deadline ends first and exits cleanly.

6. **`scripts/kimi-precommit.sh:31`** (low, round 2). GATE\_TIMEOUT is raised to 300 s, but the PreToolUse hook that runs kimi-review.sh on git commit is still capped at timeout 180 in .claude/settings.json. SKILL.md says the gate may take 300 s without saying which gate. The hook layer can still cut off a review the pre-commit layer now allows.
   Suggested: Note in SKILL.md/the comment that only the pre-commit gate gets 300 s, or raise the settings.json hook timeout to match.

7. **`scripts/todos/state.py:1137`** (low, round 1). \_fixer\_only\_change accepts any trailing-whitespace or EOF-blank-line diff on any regular file, whether or not a fixer made it. Shipped bytes can differ from the verified tree where whitespace matters, such as Python triple-quoted strings or a shell `\` line continuation.
   Suggested: Accept as designed (owner decision), or after Land's commit record the new HEAD tree as tree\_id, so any later drift is checked against what was actually committed rather than tolerated again.

8. **`scripts/todos/state.py:1149`** (low, round 2). \_fixer\_only\_change accepts trailing-whitespace changes on any line of any non-Land file. The fixers only strip trailing whitespace. This also admits changes inside multi-line string literals or other whitespace-significant content, so the 'lost work' guard is wider than the PR #907 case needs. It is an owner-approved trade-off, and the test list has no case for it.
   Suggested: Add a test pinning the intended behavior for a whitespace-only change inside a code file, or restrict the relaxation to the end-of-file blank-line case plus .md files.

9. **`scripts/todos/state.py:1168`** (low, round 2). \_fixer\_normal accepts more than the configured fixers or the owner decision allow. It also treats removing a file's final newline ("a\\n" -> "a") as fixer-only, and end-of-file-fixer never does that. The docstring admits this ('or the final newline'). The owner decision names only trailing whitespace and EOF blank lines.
   Suggested: Accept the change only when `after` matches the fixer output: if before ends with b"\\n", require after to end with b"\\n" too. Or note in the todo's owner\_decision that final-newline removal is accepted on purpose. Add a refusing test case for b"x\\n" -> b"x".
   Also reported: \_fixer\_normal compares the two sides symmetrically, so it also accepts changes no fixer makes: trailing whitespace added, blank lines added at EOF, or CRLF/LF flipped in either direction. The docstring promises 'only as trailing-whitespace and end-of-file-fixer would make them differ'.

10. **`scripts/todos/test_state_flow.py:777`** (low, round 1). The docstring of \_fixer\_only\_change claims symlinks and submodules fail closed, but no fixer\_case covers them. Dropping the mode check for 120000/160000 would still pass the suite.
   Suggested: Add fixer\_case entries for a symlink whose target differs by trailing whitespace (expect refusal) and for a mode change to 120000.

11. **`scripts/todos/test_state_flow.py:781`** (low, round 2). The empty-commit check proves nothing. The 'land' commit has no todos/ edit and the index equals `recorded`, so ensure\_worktree hits actual == tree\_id and passes whatever the code does. It never drives the post-Land state (tree != tree\_id) that the wedged-CI recovery relies on.
   Suggested: Make the 'land' commit stage a todos/ change, so actual != tree\_id goes through \_land\_only\_diff. Assert write-tree is the same before and after the --allow-empty commit, and that ensure\_worktree still passes.

12. **`scripts/todos/test_state_flow.py:785`** (low, round 1). The wedged-CI empty-commit test proves nothing new. The index tree already equals `recorded` after fixer\_case restored it, so \_check\_worktree short-circuits on actual == tree\_id. No path added by this change runs, and the test would pass even if ensure\_worktree compared HEAD's tree.
   Suggested: Make the Land commit carry a Land-path or fixer-only change (e.g. edit todos/100-x.md) before the empty commit. Then assert that ensure\_worktree still accepts it through \_land\_only\_diff, or drop the test and keep the runbook-text check.

13. **`scripts/todos/test_state_flow.py:1333`** (low, round 1, round 2). The wave-1 negative check passes for the wrong reason. ready\_run with one group gives one wave, so execute\_args(run, 1) raises ValueError 'wave 1 does not exist' and not the 'wave 0 has not finished executing' refusal. raises(..., Exception) hides that, so the check would still pass if waves were 1-indexed.
   Suggested: Use a fixture with two groups in two waves (e.g. workers=1, two todos sharing a lane) and assert TransitionError with 'wave 0 has not finished' from execute\_args(run, 1), not any Exception.
   Also reported: The 'wave 0 is a fresh run's first wave' check uses a one-wave run, so execute\_args(run, 1) raises ValueError('wave 1 does not exist'), not the wave-ordering guard. raises(..., Exception) also accepts any error, so the 0-indexing behaviour is never tested.

14. **`scripts/todos/test_state_flow.py:1334`** (low, round 1). The 'wave 0 is a fresh run's first wave' check uses a single-group run. execute\_args(run, 1) raises ValueError only because wave 1 does not exist, not because of any wave-ordering rule, so the 0-based-wave contract is barely exercised.
   Suggested: Use a run with two waves. Assert that execute\_args(run, 1) raises TransitionError ('wave 0 has not finished executing') before wave 0 runs, and that execute\_args(run, 0) succeeds.

15. **`scripts/todos/test_state_flow.py:1335`** (low, round 2). The 'wave 0 is the first wave' check asserts raises(execute\_args(run, 1)) with a bare Exception, so any unrelated error satisfies it. Only the wave-0 half discriminates, and the SKILL.md prose ('Waves start at 0') is pinned by substring only.
   Suggested: Assert the specific RuntimeError message for wave 1 (wave 0 not yet merged/executing), or drop the raises half.

## Acceptance Criteria

- [ ] Each finding above is fixed with a test, or the Work Log records why it was left as is.

## Work Log

- 2026-10-01: Filed from todo-sweep run 2026-10-01-1858, PR #921 review rounds 1-2.
