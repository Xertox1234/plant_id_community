---
status: completed
priority: p4
issue_id: "525"
tags: [tooling, todo-sweep]
dependencies: []
triage: ready
triaged: 2026-10-02
owner_decision: "Findings 6-7: implement the generic /Users/<name>/ and /home/<name>/ to ~/ fallback; document the quoted-'~' limit in the docstring (2026-10-02)"
---

# Verified-entry path rewrite edge cases: non-blocking findings from PR #938 (todo 524)

## Problem

PR #938 (todo 524) merged after two review rounds in todo-sweep run 2026-10-02-0255. The findings below were rated non-blocking, so they were not repaired. Findings at the same file:line are merged; each one says which round reported it. Line numbers are as of the PR head. Re-check each finding against main before acting on it.

## Findings

1. **`scripts/todos/land.py:171`** (medium, round 1, round 2). \_NOT\_IN\_PATH excludes a preceding '/', so a file:// URL (Node ESM stack traces) or a flag-glued path (-I/Users/...) skips every strip. Probe: 'at file://\<wt>/web/x.ts' passes through unchanged, so the username and worktree name still reach the public Work Log, which breaks the todo's AC.
   Suggested: Let the root and worktree patterns match after a 'file://' prefix, e.g. lookbehind (?\<![\\w.~-])(?\<![^:]/), or pre-strip 'file://'. Then do a plain str.replace(home, '~') as a backstop. Add a file:// case to the 524 tests.
   Also reported: The lookbehind (?\<![\\w./~-]) blocks any root that follows '/' or a word character, so file:// URLs (Node ESM stack traces) and flag-glued paths like -I\<wt>/inc keep the full /Users/\<name>/.../worktrees/wf\_* path. Probed: 'file://\<wt>/web/x.js:1:2' comes back unchanged.
   Also reported: The home strip misses some forms and leaks the username: after a word char or '/' ('-I/Users/x/inc', 'file:///Users/x/...'), before '.' ('/Users/x.'), and the sandbox TMPDIR form '/private/tmp/claude-501/-Users-\<name>-projects-...'. All probed unchanged. The AC says 'no /Users/'.

2. **`scripts/todos/land.py:172`** (medium, round 1, round 2). \_WORKTREE\_RE path components accept ':', ',', '=', ';'. A list entry glued to another worktree's path is swallowed: 'PYTHONPATH=/opt/lib:\<main>/.claude/worktrees/wf\_zz-2/backend' becomes 'PYTHONPATH=backend', and '--ignore=/opt/a,\<wt2>/b' becomes '--ignore=b'. Confirmed by an in-memory probe.
   Suggested: Exclude shell separators from the prefix component class, e.g. (?:/[^\\s'"\`/:;,=|&\<>)]+)+, so the match can only start at the real start of the worktree path. Add a test case with a ':'-joined list.
   Also reported: \_WORKTREE\_RE segments ([^\\s'"\`/]+) allow ':', ',', ';', '='. A sibling-worktree path in a joined list eats the entries before it: 'PYTHONPATH=/opt/lib:\<main>/.claude/worktrees/wf\_o/backend x' becomes 'PYTHONPATH=backend x'. The recorded command is silently wrong. Probed; untested.
   Also reported: In \_WORKTREE\_RE, the path-segment class [^\\s'"\`/] allows ':', ',', '=' and ';', so earlier list entries get swallowed. 'PYTHONPATH=/opt/lib:\<main>/.claude/worktrees/wf\_o-2/backend' becomes 'PYTHONPATH=backend'. The name class also swallows a closing '}' or ']': '{\<otherwt>}' becomes '{.'.
   Also reported: \_WORKTREE\_RE segments allow ':' and ',', so a worktree path after a separator also eats the elements before it. Probed: 'PYTHONPATH=/opt/lib:\<main>/.claude/worktrees/wf\_o-2/backend x' becomes 'PYTHONPATH=backend x', and 'a /x/y,/z/.claude/worktrees/q/r' becomes 'a r'. The archived command is then wrong.
   Also reported: \_WORKTREE\_RE's leading segments allow ':;,=|&)\<>', so a path list gets swallowed. Probed: 'PYTHONPATH=/opt/lib:\<main>/.claude/worktrees/wf\_x/backend x' becomes 'PYTHONPATH=backend x', which silently changes the archived command. This hits when Land runs in a re-added scratch worktree.

3. **`scripts/todos/land.py:170`** (low, round 1, round 2). A bare root followed by a character outside \_PATH\_END ('.', ']', '}') is not stripped, so the absolute path and user name leak: 'see /Users/williamtower.' and 'path [\<main>]' stay as written. 'file://\<wt>/x' and '-C\<wt>' leak too, because of the lookbehind. This breaks the AC's 'no /Users/' for such tails.
   Suggested: Add '.', ']' and '}' to \_PATH\_END when followed by end of text or whitespace. Consider allowing a 'file://' prefix. Alternatively, add a final guard that flags any remaining '/Users/' or home path in the note.
   Also reported: \_NOT\_IN\_PATH/\_PATH\_END miss some common contexts, so absolute home or worktree paths still leak. Probed: 'file:///Users/u/.../.claude/worktrees/wf\_x/a' is left as is. A path followed by '.', ']' or '}' (prose or pytest tails) is also not stripped.

4. **`scripts/todos/land.py:185`** (low, round 1). \_strip\_roots replaces '\<root>/' with '' even when nothing follows the slash. 'git -C \<wt>/ status' becomes 'git -C  status', and 'cd \<wt>/ && ls' becomes 'cd  && ls'. Re-run as quoted, the latter changes to the home directory.
   Suggested: Strip '\<root>/' to '' only when a path character follows (lookahead (?![\\s'"\`;:,)|&\<>=]|$)). Otherwise replace '\<root>/' with '.' (or '~' for home).

5. **`scripts/todos/land.py:186`** (low, round 1, round 2). \_strip\_roots (and \_WORKTREE\_RE when group(1) is '/') turn '\<root>/' followed by a path end into nothing, not '.'. 'git -C \<wt>/ status' becomes 'git -C  status' and 'ls \<other\_wt>/ -la' becomes 'ls  -la' (probed), so the quoted command changes meaning when re-run.
   Suggested: Before the '\<root>/' rule, rewrite '\<root>/' followed by \_PATH\_END to the bare form ('.' or '~'). In \_WORKTREE\_RE, return '.' when the trailing '/' is followed by \_PATH\_END. Add a 'git -C {wt}/ status' case.
   Also reported: When a root ends in a slash and nothing follows it, `root/` is replaced with an empty string. 'cd \<wt>/ && pytest' becomes 'cd  && pytest', which re-runs in $HOME, and 'ls \<wt>/' becomes 'ls '. The same happens in the \_WORKTREE\_RE lambda, which returns '' when group(1) is '/'.

6. **`scripts/todos/land.py:199`** (low, round 1). \_relativize only strips the worktree, main checkout and Path.home(). Any other absolute path with a username, such as a /Users/\<other>/ or /home/\<u>/ path in evidence tails from a different machine or CI, still reaches the public Work Log. Tail lines are also not run through the todo\_rel rewrite.
   Suggested: Optionally add a generic /Users/\<name>/ and /home/\<name>/ -> ~/ fallback; otherwise state the home-only scope in the docstring.

7. **`scripts/todos/land.py:204`** (low, round 1). The home directory becomes '~' even inside quotes: "cat '/Users/x/.zshrc'" becomes "cat '~/.zshrc'" (probed). The shell does not expand a quoted '~', so the recorded check no longer re-runs, against the todo's re-runnable intent.
   Suggested: Accept this and say so in the \_relativize docstring as display-only, or write "$HOME" for an occurrence inside double quotes. Single quotes cannot be fixed by substitution, so document it.

8. **`scripts/todos/land.py:205`** (low, round 1). The todo\_rel lookbehind (?\<![\\w.:-]) does not exclude '/', so a deeper path ending in the todo's path is rewritten too. 'backend/todos/524-pending-p3-x.md' becomes 'backend/todos/archive/524-completed-p3-x.md', which never exists.
   Suggested: Rewrite only at a path start: (?:(?\<=^)|(?\<=[\\s'"\`=])|(?\<=\\./))todos/..., or add '/' to the lookbehind with a separate allowance for './'.

9. **`scripts/todos/land.py:296`** (low, round 2). The evidence tail is relativized without todo\_rel, and tail lines get no worktree-regex test with a different worktree name. Output of a test run that prints another worktree's path is covered only by the command cases.
   Suggested: Add one test case where an evidence tail line contains a foreign .claude/worktrees/\<name>/ path; no code change needed if it passes.

10. **`scripts/todos/test_land.py:451`** (low, round 1, round 2). The \_relativize table has no case for `.claude/worktrees/<name>` as the last path segment followed by a separator (e.g. `wf_x:` or `wf_x)`), nor for a worktree-like name with a trailing dot. Those \_PATH\_END branches in \_WORKTREE\_RE are not pinned.
   Suggested: Add one or two cases such as f"cd {wt};ls" and f"({wt})" to the table.
   Also reported: The verifier flagged test\_land.py edits. Every hunk is additive: one docstring paragraph and a new todo-524 block. No existing assertion or case was changed or weakened, so the edits are justified.

11. **`todos/archive/524-completed-p3-sweep-verified-entry-absolute-paths.md:1`** (low, round 2). Archived AC 2 command was rewritten to `cd . && ...` (from `cd <worktree> && ...`), a harmless artifact of relativizing; it re-runs fine but reads oddly.
   Suggested: Optionally drop a leading `cd . &&` prefix in \_relativize; not blocking.

## Acceptance Criteria

- [x] Each finding above is fixed with a test, or the Work Log records why it was left as is.

## Work Log

- 2026-10-01: Filed from todo-sweep run 2026-10-02-0255, PR #938 review rounds 1-2.

### 2026-10-02 - Implemented by the todo sweep (run 2026-10-02-2343)

- Findings 1-5 and 10 (`land._relativize`): a root also starts after `file://` (dropped with it) or after a one-letter flag glued to it (`-I<wt>/inc`, `'-I<wt>/x'`, `CFLAGS=-I...`). A path component never holds a blank, quote, bracket or separator, so `PYTHONPATH=/opt/lib:<wt2>/backend` keeps `/opt/lib:` and `{<wt2>}` keeps its brace. `]` and `}` end a path. A root alone, with a trailing slash, or before a full stop that ends a sentence reads `.` or `~`, never nothing: `git -C <wt>/ status` is `git -C . status`, and `see <main>.` reads `see ..`. Last, this machine's home is replaced wherever it is left, mid-path or in the sandbox TMPDIR spelling `-Users-<name>-...`.
- Findings 6-7 (owner decision): any other `/Users/<name>` or `/home/<name>` reads `~`. The `_relativize` docstring now says the result is for reading and a quoted `~` does not re-run as written, and a table row pins that. One existing 524 expectation changes with the fallback: `{main}-old/x` now reads `~/projects/pic-old/x`. It is still not stripped as main_root; only the user name goes.
- Finding 8: the todo's own path is rewritten only where a path starts (after any `./` or `../`), so `backend/todos/524-...` is left alone.
- Findings 9 and 11: a tail line naming another worktree already read repo-relative; a `flip_acs` test now pins it. Tail lines keep the todo's pre-archive path on purpose, because they record what the command printed. A leading `cd . && `, which is what `cd <repo> && ` becomes, is dropped from the quoted command.
- `test_land.py` has `525 #N` rows for every finding: 32 `_relativize` cases and two `flip_acs` checks. Every probe a finding reported as wrong was red at BASE; the exceptions are 7, kept and documented, and 9, which was already right. A mutant turns each new rule red. Run over every todo-file line that holds `/Users/` or `/home/`, the new `_relativize` leaves no user name.

### 2026-10-02 - Verified by the todo sweep (run 2026-10-02-2343)

- AC 1: `( python3 scripts/todos/test_land.py | grep -E "525 #|pic-old|check\(s\)|All checks passed" && grep -n "inside quotes is not expanded" scripts/todos/land.py && grep -n "Implemented by the todo sweep (run 2026-10-02-2343)" todos/archive/525-completed-p4-verified-entry-path-rewrite-edge-cases-938-followups.md )` — evidence `.sweep-evidence/g2/525-ac0.txt` (not committed), last lines:

  ```text
    PASS  525 #9: a tail line naming another worktree reads repo-relative
    PASS  525 #11: the command's leading `cd <repo> && ` is dropped, not quoted as `cd . && `
  All checks passed.
  219:    The result is for reading. A `~` inside quotes is not expanded by a shell, so a quoted home
  70:### 2026-10-02 - Implemented by the todo sweep (run 2026-10-02-2343)
  ```

### 2026-10-02 - Completed by the todo sweep (run 2026-10-02-2343)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
