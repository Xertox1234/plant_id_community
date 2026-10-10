---
status: pending
priority: p4
issue_id: "541"
tags: [todo-sweep, follow-ups]
dependencies: []
---

# Todo sweep run 2026-10-10-1537: follow-ups from PRs #982 and #983

## Problem

Todo-sweep run 2026-10-10-1537 merged two PRs: #982 (todos 494, 514, 528, 529, the sweep engine) and #983
(todo 537, mail-gate follow-ups). Their review rounds reported non-blocking findings. As in the last two runs,
there is one consolidated follow-up todo for the whole run. Duplicate reports are merged below, and the refuters
dismissed nothing.
PR #982 had three rounds. Round 2 sustained one high (one todo's edited criteria could split a group), which
was fixed by hand in round 3 (owner-approved), and round 3 was clean. Line numbers are as of each PR's head, so
re-check each finding against main before acting on it.

## Findings

### PR #982: sweep engine (494, 514, 528, 529)

1. **`scripts/todos/state.py` `ingest_followups`** (medium, reported by about 8 reviewers across all three
   rounds). Nothing checks that every stored follow-up comes back from the curator as kept, merged (`also`) or
   dropped. A curator that omits items, or returns `items: []`, loses them while the group is still marked
   `verified`. `followups_md` prints only `curated` and never shows `curation_dropped`. Suggested: put any raw
   `file:line` not covered back into `curated` (or mark the group uncurated), and list `curation_dropped` under its
   own heading.
2. **`state.py` `_followup_key`** (medium). A pre-529 line (`a.py:2 nit`, no severity) is keyed by the whole line,
   so curation drops every legacy item as "not a location the review reported", and a new finding at the same
   `file:line` never merges with it. Suggested: fall back to a leading `(.+?:\d+)` key, and add a test that
   curates a legacy line.
3. **`.claude/workflows/todo-followups.js:112`** (medium). Items the curator marks `fixed` on main skip the refuter
   and are dropped, so a wrong "fixed" verdict deletes a real follow-up unchecked. Suggested: send them to the
   refuter with the "fixed" claim, or keep them as unclear.
4. **`state.py` `followups_args`** (low). Any `curation` key excludes a group for good, including
   `uncurated: …` from a dead curator or an unfetched origin/main, so a transient failure can never be retried.
   Suggested: skip only `verified`/curated groups.
5. **`state.py` `git_criteria`** (low). It reads the todo file from the working tree, but what ships is the index
   (`tree_id`). Suggested: `git show :<path>` before Land, or `git show <tree_id>:<path>` after.
6. **`state.py` `ingest_review`, round-1 repair criteria check** (low/medium). It runs against the worktree the
   repair worker reports, not the group's recorded worktree, unlike `ingest_execute` (528). Suggested: pass the
   recorded worktree, or refuse a mismatched report. Related: the criteria pre-pass in `ingest_execute` reads
   `worker["worktree"]` before the mismatch check runs (the todo still fails).
7. **`state.py` `add_worktrees`** (low/medium). The "move it aside, then rerun" recovery cannot work: the branch
   `worktree-sweep-…` and the registered path still exist, so `git worktree add -b` fails. Also, a relative
   `--main-root`/`--worktree-root` records a relative worktree path. Suggested: name the real recovery
   (`git worktree remove`/`prune` + delete the branch), and resolve both roots.
8. **`state.py:800`, branch name `worktree-sweep-<RUN_ID>-<group>`** (low). `scan.ids_in` does not skip it, so its
   `2026` and HHMM runs read as in-flight todo ids while the branch exists. Suggested: add the prefix to scan's skip
   list.
9. **`.claude/workflows/todo-execute.js:122`** (low). Implement workers are no longer harness-isolated, and their
   cwd is the main checkout. `guard-worktree-isolation.sh` acts only when cwd is inside a worktree, so a mistyped
   relative Edit/Write path lands in the main checkout. Suggested: a hook that denies Edit/Write outside the
   brief's worktree for `todo-worker`.
10. **`state.py` `_copy_worktreeinclude`** (low). A `..` or anchored (`/backend/.env`) pattern raises after
    `git worktree add` has already run, and `copy2` follows symlinks. Suggested: strip a leading `/`, skip
    negations, skip sources outside `main_root` and symlinks.
11. **`state.py` `ingest_execute`, worktree mismatch** (low). A worker that reports another worktree fails without
    that path being recorded, so `state.py worktrees` cannot list it. Suggested: record it (`stray_worktree`, or
    under `previous`).
12. **`state.py` criteria checks after Land** (low). `review_criteria` ignores box state, so a round-1 repair can
    tick an unverified box. `criteria_problem` also accepts a criterion whose re-point marker was removed.
    Suggested: allow box changes only on Land-flipped indexes, and require each recorded marker exactly once.
13. **`state.py` `_reverify_tree`** (low). It fails open when the entry has no `tree_id`. Suggested: refuse a
    `--reverify` brief without one.
14. **`scripts/todos/test_workflows.js:742/796`** (low). The F8 negative checks use an unparenthesised `A && B || C`,
    so `errors` is never asserted, and a null result throws instead of failing. Suggested: assert both explicitly.

### PR #983: mail-gate follow-ups (537)

1. **`backend/packages/wagtail_forum/wagtail_forum/management/commands/send_forum_digest.py:124`** (low, reported
   by 5 reviewers across both rounds). `except BaseException` now gives the claim back on a
   `SoftTimeLimitExceeded` too. On main the claim was kept. A soft limit after SMTP accepted the mail now means a
   duplicate digest on the next run. Only the `Warning` arm is tested. Suggested: release only on `Warning`, or
   accept at-least-once (as `send_blog_newsletter` does), say so in the comment, and test the soft-limit path.
2. **`backend/apps/forum_host/tasks.py:421`** (low, 6 reports). The docstring edit left one ~120-character line
   ("This ordering is load-bearing: …"). Re-wrap it.
3. **`backend/apps/blog/newsletter.py:213`** (low). `_release_confirmation_stamp` has untyped `now`/`previous`.
   Annotate `now: datetime, previous: datetime | None`.
4. **`backend/apps/core/checks.py:57`** (low). The rebuild passes Django's private `_ignore_unknown_kwargs`. A
   Django upgrade that renames it would surface as a misleading `core.E364`. Keep the test that runs against the
   installed Django, and name the Django version it mirrors in the comment.

## Acceptance Criteria

- [ ] Each finding above is fixed, or closed with a dated reason, or promoted to its own todo.

## Work Log

- 2026-10-10: Filed from run 2026-10-10-1537's review rounds (#982 rounds 1–3, #983 rounds 1–2).
