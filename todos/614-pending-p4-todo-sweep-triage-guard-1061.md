---
status: pending
priority: p4
issue_id: "614"
tags: [todo-sweep, harness, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-11
owner_decision: "#4: widen REPOINT_RE to accept the CLAUDE.md form 're-pointed DATE; ... todo N' again, keeping the loose forms the tightening meant to exclude out (2026-10-11)"
---

# Follow-ups from PR #1061 (todos 596 and 600, apply-triage ready answer and worker edit guard)

## Problem

Todo-sweep run 2026-10-11-2219 merged PR #1061 (todos 596 and 600, apply-triage ready answer and worker edit guard). The non-blocking review findings are below. The curator merged duplicates and checked each item against main, and the refuter dismissed what is listed as dropped. An item the curator did not return was kept as stored, unchecked. Line numbers are as of the PR head, so re-check each against main before acting on it.

Item 3 (stray_worktree allowlisted) was fixed by the owner-approved round-1 hand repair on #1061 (commit 245486d7) before merge; it was kept as stored without a check on main, so verify and close it. The cap of 10 left out 1 more location.

## Findings

PR #1061 (todo sweep run 2026-10-11-2219, group g13, todos 596, 600); follow-ups: verified; 1 item(s) the curator did not return were kept as stored.

1. **medium** `scripts/todos/state.py:500` The todo-600 override only fires when stage is `ready`. For selector `next`, SKILL.md runs apply-triage later (in the worker's worktree, after execute), when stage is verified or later, so an owner-answered needs-design todo still gets the triager's class and blocked_on. | also: Todo 600's unblock only fires when stage == 'ready'. For selector `next`, SKILL.md has apply-triage run during Land, when the todo is already `verified`, so an owner-answered needs-design/blocked-* todo is still written with the triager's class and blocked_on. | Any owner_decision on a ready entry triggers the rewrite, including one written only by `confirm` (criterion confirmation). A needs-research or already-done todo that has a confirmed criterion then gets triage: ready and its blocked_on removed, though the owner never answered a blocking question. | The todo 600 override depends on stage == 'ready'. In the `next` selector, SKILL.md runs apply-triage during Land, after execution, when the stage is no longer 'ready'. An owner-answered needs-design todo still gets the triager's class and blocked_on written and committed. | The todo-600 override only fires when the entry's stage is exactly `ready`. For selector `next`, SKILL.md runs apply-triage during Land, when the stage is `verified`. So a needs-design todo the owner answered `ready` still gets the triager's class and a stale blocked_on written. | Any owner_decision triggers the override, including the one `confirm` writes ('criterion N confirmed by the owner'). A needs-research or already-done todo decided plain `ready` (no words, per the Decide table) and then confirmed before apply-triage gets triage: ready, and its class is lost.
2. **medium** `.claude/workflows/todo-followups.js:169` Refuted text spreads across identical copies, so conflicting verdicts end in a drop. A refuted also copy (refuted=false on the summary) sets summaryGone, and with on_main 'fixed' the drop reads 'the refuter agreed', which it did not. | also: summaryGone can now be true only because an identical `also` copy was refuted while the refuter set refuted:false on the summary. With on_main 'fixed', the drop then reads 'fixed on main ... the refuter agreed', which is a verdict the refuter never gave on the summary.
3. **medium** `scripts/todos/worker_edit_guard.py:100` recorded_worktrees now allowlists every `stray_worktree`, on the current entry and in `previous`. A stray is by definition a path the worker reported that is NOT the worktree it was given (state.py:1077), possibly another agent's harness worktree. Any todo-worker may now edit it.
4. **low** `scripts/check_archived_todo_status.py:211` The narrowed REPOINT_RE drops the 'todo N ... re-pointed' form and caps 're-pointed ... todo N' at 30 chars with no .;!?|/. todo-worker.md:88 and todo-verifier.md:59 still describe 're-pointed … todo NNN' loosely, so agents and the checker can disagree. | also: REPOINT_RE no longer accepts the 'todo N ... re-pointed' order, or more than 30 characters between 're-pointed' and 'todo N'. This tightens the tripwire as intended. The current repo passes (checker rc=0), but a future hand-written re-point in those forms is flagged. | REPOINT_RE no longer accepts the 'todo N ... re-pointed' order. The checker passes today, but a future archived AC worded that way will fail. A 30-char window also rejects longer re-point clauses. The tests pin only the accepted arrow and re-pointed-to forms. | REPOINT_RE drops the 'todo N ... re-pointed' ordering and bounds the gap to 30 non-punctuation chars. A legitimate re-point such as 're-pointed 2026-07-26; promoted to todo 283' (the CLAUDE.md convention form) no longer exempts, so a valid re-pointed criterion is reported as unchecked.
5. **low** `scripts/todos/test_state.py:220` The 600 test covers only needs-design answered at stage ready. Nothing covers a blocked-*class, a stale/ready triager record, or apply_triage running later in the flow (the `next` Land path). | also: The todo-600 branch fires on stage=='ready' with any owner_decision. The tests cover needs-design only; no test shows that a blocked-* class or a stale/ready triager record is also overridden to triage: ready.

1 more location(s) were dropped by the cap of 10 (the most severe are kept).

Dropped by curation (fixed on main, refuted, or not a reported location):

- medium: scripts/todos/worker_edit_guard.py:97 recorded_worktrees now admits every entry's stray_worktree (current entry's too, not only `previous`). That field is the worktree a worker wrongly reported (state.py:1077), so the guard allows edits in the stray wf_*/agent-* tree 577 #5 meant to deny. (fixed on main: origin/main recorded_worktrees collects only a.get("worktree") from each entry and its previous[]; docstring says never a stray_worktree, top-level or in previous (PR #1061 review).; the refuter agreed: origin/main worker_edit_guard.recorded_worktrees collects only a.get("worktree") from each entry and its previous[] list. stray_worktree is never read, top-level or in previous, so stray trees are not allowlisted.)
- medium: .claude/workflows/todo-followups.js:104 The curator must now repeat a phrasing once per merged item, but the CURATED schema caps `also` at maxItems 10. Merging more than 10 identical items plus the kept item's own also list fails validation or truncates, leaving items uncovered and refiled. (fixed on main: origin/main ITEM schema has also maxItems: 50 (also_refuted 50, items 40). Refute step now builds refutedText and drops every identical copy of a refuted text, so unlisted identical copies no longer survive.; the refuter agreed: The ITEM schema on origin/main caps also at maxItems 50 and also_refuted at 50, with items capped at 40. The refute step (lines 167-168) adds every identical copy of a refuted text to alsoGone, so an unlisted identical copy cannot survive in stay.)
- low: .claude/hooks/test-guard-todo-worker-edit.sh:140 The guard now also allows an entry's own top-level `stray_worktree`, not only those under `previous`, but the new tests cover only `previous[].stray_worktree`, so the top-level path is untested. (fixed on main: origin/main test file lines 145-147 add assert_deny for an entry's top-level stray_worktree, alongside the previous[] case at 141-143; the guard now denies both.; the refuter agreed: The origin/main guard no longer allows any stray_worktree. test-guard-todo-worker-edit.sh has assert_deny for both previous[].stray_worktree and an entry's top-level stray_worktree, so the top-level path is tested.)

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-11 - Filed from the PR #1061 review (todo sweep run 2026-10-11-2219)

Filed by the closing step of the run from `state.py followups-md g13`.
