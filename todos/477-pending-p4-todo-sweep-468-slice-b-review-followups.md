---
status: pending
priority: p4
issue_id: "477"
tags: [harness, todo-sweep]
dependencies: []
---

# Todo sweep: non-blocking findings from PR #872 round 1 (todo 468 slice B)

## Problem

Round 1 of PR #872 found one regression, fixed in the PR. The guard denied
`cd '<WT>' && git add -A` and `git -C "$WT" add -A` for retry and repair workers,
which run from the main session's cwd. Now a command that changes directory, or a `-C`
value built at runtime, leaves the directory unknown, and it is not checked. These
items were left for later. The guard is a mistake guard, not a security boundary.

## Findings

1. **Gaps in the main-checkout check.**
   - `git -C MAIN --work-tree=S add -A` is allowed but stages into MAIN's index.
   - `GIT_DIR=` and `GIT_WORK_TREE=` environment prefixes are not checked.
   - A `git-add` binary skips the check.
   - After a `cd`, a bare `git add` is not checked. That includes `cd MAIN && git add`.
   - In the pilot layout, the sweep's main root is itself a linked worktree (its `.git`
     is a file), so the check never fires there.
2. **A tracked file listed in `.worktreeinclude` blocks every `git add`.** If a listed
   file is tracked and not ignored, `unignored_includes` denies all staging in that tree.
   Theoretical: the file itself says only ignored files are copied.
3. **The reviewer's read-only set is narrow.** `cat-file`, `ls-tree`, `rev-list`,
   `branch --show-current` and `worktree list` are denied. The bug prompt needs only
   `diff`, so the review stage works, but a reviewer may hit a denial while exploring.
4. **Round 2 notes.**
   - A `cd` inside `$(...)`, a subshell or `eval` also leaves the outer command's
     directory unknown. That misses catches; it never adds a wrong denial.
   - An UNKNOWN `-C` stays unknown even after a later absolute literal
     (`git -C "$WT" -C MAIN add` is allowed). `_join` could restart from an absolute
     path.
   - After a `cd`, the unignored-`.env` staging check is skipped too. Land's backstop
     still refuses the `.env`.
5. **The rename message shows git's C-quoting** for a source path that has a tab or a
   quote in it. This is cosmetic.

## Acceptance Criteria

- [ ] Each gap in finding 1 is closed or recorded here as accepted, with a test for
      each one closed.
- [ ] A tracked, not-ignored `.worktreeinclude` entry does not block unrelated staging,
      with a test.
- [ ] The reviewer's read-only set is widened or recorded as enough.
- [ ] The rename message prints unquoted paths.

## Work Log

### 2026-09-28 - Filed from PR #872 round 1
