---
status: completed
priority: p4
issue_id: "616"
tags: [todo-sweep, docs, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-11
owner_decision: "DIRTY-recovery merge commit skips kimi (SKIP_KIMI_REVIEW=1) and records 'kimi: skipped'; origin/main's code was already reviewed (2026-10-11)"
---

# Follow-ups from PR #1063 (todo 601, DIRTY armed-PR recovery runbook)

## Problem

Todo-sweep run 2026-10-11-2219 merged PR #1063 (todo 601, DIRTY armed-PR recovery runbook). The non-blocking review findings are below. The curator merged duplicates and checked each item against main, and the refuter dismissed what is listed as dropped. An item the curator did not return was kept as stored, unchecked. Line numbers are as of the PR head, so re-check each against main before acting on it.

Items 3 and 6 were fixed by the owner-approved round-1 hand repair on #1063 (commit e73eabc6) before merge; they were kept as stored without a check on main, so verify and close them. The cap of 10 left out 2 more locations.

## Findings

PR #1063 (todo sweep run 2026-10-11-2219, group g15, todos 601); follow-ups: verified; 3 item(s) the curator did not return were kept as stored.

1. **medium** `.claude/skills/completing-todos/SKILL.md:396` Step 6 commits the merge with the full pre-commit and kimi gate. Mid-merge the staged diff is every change origin/main brought in, so a kimi CRITICAL or timeout on peer PRs' code can block the recovery, and the runbook does not cover a failed merge commit. | also: Step 6 commits the merge with the kimi pre-commit gate on, but scripts/kimi-precommit.sh reviews `git diff --cached`, which mid-merge is every change origin/main brought in. A CRITICAL on already-merged peer code blocks the commit, and the runbook says nothing about a failed merge commit. | low: SKILL.md:386 Step 6's merge commit runs the commit-time kimi gate and pre-commit hooks on the whole staged diff against HEAD (all of origin/main's changes since the fork), not just the resolved paths; the doc does not cover a kimi CRITICAL on unrelated main code.
2. **medium** `.claude/skills/completing-todos/SKILL.md:390` Step 4 re-runs the group's gates on the merged tree but never says what to do if one fails. Auto-merge stays armed, so following steps 5-7 anyway pushes a broken merge that auto-merges with no owner looking. | also: Step 4 says to re-run 'the command of every criterion in its ac.json whose files the merge touched', but ac.json criteria do not reliably name files, so the operator cannot tell which commands this means.
3. **medium** `.claude/skills/completing-todos/SKILL.md:374` Calling `todos/` conflicts mechanical with 'keep both sides' can corrupt a todo. If both sides edit the same frontmatter (status, triage, AC ticks), the result has duplicate `status:` keys or doubled AC/Work Log lines. That breaks the status tripwire and the sweep scan, and contradicts the existing 'rebuild from main + re-apply ticks' practice.
4. **low** `.claude/skills/completing-todos/SKILL.md:377` The todo rebuild runs `git show origin/main:<path> > $WT/<path>`. If the branch archived the todo (pending to completed), the conflict path is the completed path, which is not on origin/main, so `show` fails after the redirect has already emptied the file. | also: Rebuilding a todo file with `git show origin/main:<path> > $WT/<path>` overwrites the branch's version before its changes are re-applied by hand, so a missed tick or Work Log entry is lost without a trace.
5. **low** `.claude/skills/completing-todos/SKILL.md:386` Step 6's merge commit runs the commit-time kimi gate and pre-commit hooks on the whole staged diff against HEAD, which is all of origin/main's changes since the fork, not just the resolved paths. A kimi CRITICAL on unrelated main code can block the recovery, and the doc does not cover that case.
6. **low** `scripts/todos/test_state_flow.py:1463` Formatting typo: `step6 =skill.split(...)` is missing a space after `=`. Black/pre-commit would reformat it. The edit appears accidental, since the line is otherwise unchanged from the old `step6 = ...`.

2 more location(s) were dropped by the cap of 10 (the most severe are kept).

Dropped by curation (fixed on main, refuted, or not a reported location):

- medium: .claude/skills/completing-todos/SKILL.md:373 The rule "`todos/` files: keep both sides" is wrong for a modify/modify conflict inside one todo file. Keeping both sides of a frontmatter line (status) or an AC tick leaves duplicate keys or a corrupt todo, and the archived-todo tripwire trips on it. (fixed on main: origin/main step 3 now says todos/ files are rebuilt from origin/main, 'never concatenate both sides (that leaves duplicate status: keys and doubled criteria and Work Log lines)', then the branch's ticks are re-applied by hand.; the refuter agreed: origin/main SKILL.md:375-378 now says todos/ files are rebuilt from origin/main, 'never concatenate both sides (that leaves duplicate status: keys...)', then the branch's ticks/Work Log/archive move are re-applied by hand. The keep-both rule no longer applies to todos/.)
- medium: .claude/skills/completing-todos/SKILL.md:378 The non-mechanical-conflict path moves a `reviewed` group to `blocked` but leaves auto-merge armed, so the PR can merge on its own once someone resolves it, and a blocked group can never be set merged/archived. (fixed on main: origin/main now says 'Disarm first ... `gh pr merge <n> --disable-auto`', then merge --abort and set-group blocked, and report the PR as blocked with auto-merge disarmed.; the refuter agreed: origin/main SKILL.md:385-389: 'Disarm first ... `gh pr merge <n> --repo $GH_REPO --disable-auto`', then merge --abort and set-group blocked, and report the PR as blocked with auto-merge disarmed. Auto-merge no longer stays armed.)
- low: .claude/skills/completing-todos/SKILL.md:371 Step 2 assumes `git merge origin/main` stops on conflicts. A clean local merge auto-commits, so steps 4-5 (gates, annotate tree_id) run after the fact and step 6 `commit --no-edit` fails with nothing to commit. (fixed on main: origin/main step 2 is now `merge --no-commit --no-ff origin/main`, with the note that --no-commit stops even a clean merge so steps 4-6 run before the commit exists.; the refuter agreed: origin/main SKILL.md:370-373 uses `merge --no-commit --no-ff origin/main` and says --no-commit stops even a clean merge, so steps 4-6 run before the commit exists and step 6's commit has a merge to finish.)
- low: scripts/todos/test_state_flow.py:1464 A stray edit to an existing test line: `step6 = skill...` became `step6 =skill...` (missing space, E225). It has no semantic effect, but it is an unjustified formatting regression. (fixed on main: On origin/main both occurrences (lines 1474 and 2676) read `step6 = skill.split(...)` with the space restored.; the refuter agreed: git grep on origin/main shows scripts/todos/test_state_flow.py:1474 and :2676 both read `step6 = skill.split(...)` with the space restored. The E225 typo is gone.)

## Acceptance Criteria

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-11 - Filed from the PR #1063 review (todo sweep run 2026-10-11-2219)

Filed by the closing step of the run from `state.py followups-md g15`.

### 2026-10-12 - Implemented by the todo sweep (run 2026-10-12-0349)

- #1, #5 fixed per the owner decision: step 6 of the DIRTY recovery in `.claude/skills/completing-todos/SKILL.md` commits the merge with `SKIP_KIMI_REVIEW=1` and records `kimi: skipped` (origin/main's code was reviewed in its own PRs), and now says what to do when the merge commit fails: a fixer rewrite is re-staged, re-gated and re-annotated; any other hook failure stops the group.
- #2 fixed: step 4 runs every criterion's non-empty `command` in `ac.json` (criteria do not name files) and, if any gate fails, never commits or pushes: it disarms, aborts the merge and blocks the group with the failing command as the reason.
- #4 fixed: a conflicted todo first saves the branch's side (`git show :2:<path>`), reads origin/main's version into a scratch file before overwriting anything, and names the pre-archive `pending` path when the branch archived the todo.
- #3, #6 already fixed on main: on origin/main (048736d5) step 3 already reads "rebuild from origin/main, never concatenate both sides", and `scripts/todos/test_state_flow.py` lines 1474 and 2676 read `step6 = skill.split(...)`. New checks for #1/#2/#4 are in `scripts/todos/test_state_flow.py`.

### 2026-10-11 - Verified by the todo sweep (run 2026-10-12-0349)

- AC 1: `bash -c 'cd . && python3 scripts/todos/test_state_flow.py && python3 scripts/todos/test_state.py && node scripts/todos/test_workflows.js; echo exit=$?; echo "--- 616/601 checks:"; python3 scripts/todos/test_state_flow.py | grep -E "616|601"; echo "--- #6 on main:"; git show origin/main:scripts/todos/test_state_flow.py | grep -n "step6 ="; echo "--- Work Log entry (fixed / already fixed on main):"; sed -n "/Implemented by the todo sweep (run 2026-10-12-0349)/,\$p" todos/archive/616-completed-p4-dirty-armed-pr-recovery-1063.md'` — evidence `.sweep-evidence/g12/616-ac0.txt` (not committed), last lines:

  ```text
  - #3, #6 already fixed on main: on origin/main (048736d5) step 3 already reads "rebuild from origin/main, never concatenate both sides", and `scripts/todos/test_state_flow.py` lines 1474 and 2676 read `step6 = skill.split(...)`. New checks for #1/#2/#4 are in `scripts/todos/test_state_flow.py`.
  state: --reverify takes stage ready and exactly one --field reason=...
  state: 7: --date must be a YYYY-MM-DD date, not 'tomorrow'
  state: --reverify takes stage ready and exactly one --field reason=...
  state: 7: --date must be a YYYY-MM-DD date, not 'tomorrow'
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-12-0349)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
