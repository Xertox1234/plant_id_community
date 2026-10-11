---
status: pending
priority: p4
issue_id: "578"
tags: [todo-sweep, scripts, follow-ups]
dependencies: []
---

# Follow-ups from PR #1017 (todo 552, land.py evidence-command paths)

## Problem

Todo-sweep run 2026-10-11-0401 merged PR #1017. Its two review rounds reported the non-blocking
findings below. The follow-ups curator merged duplicates and checked each one against main, and a refuter
tried to refute every one; anything dropped is listed with its reason. Line numbers are as of the PR head,
so re-check each against main before acting on it.

## Findings

PR #1017 (todo sweep run 2026-10-11-0401, group g6, todos 552); follow-ups: verified; 4 item(s) the curator did not return were kept as stored.

1. **medium** `scripts/todos/land.py:316` Once cwd is None it stays None (`elif cd and cwd is not None`), so a later cd to a rooted absolute path is ignored and every later path stays repo-root-relative: `cd ~ && cd <wt>/web && ls <wt>/web/src` gives `cd web && ls web/src` (resolves to web/web/src). | also: Once cwd is None it stays None, because of `elif cd and cwd is not None`, so a later `cd <wt>/web` (a rooted, absolute target) is ignored. Probe: `cd ~ && cd <wt>/web && ls <wt>/web/src` gives `cd ~ && cd web && ls web/src`, which resolves to web/web/src.
2. **low** `scripts/todos/land.py:311` rebase() runs posixpath.normpath on every rooted path once a cd is known, dropping a trailing slash: `cd <wt>/backend && rsync -a <wt>/web/ /tmp/y` reads `rsync -a ../web /tmp/y`, which copies the directory rather than its contents. The repo-root branch keeps the slash. | also: rebase() runs each rooted path through posixpath.normpath, so a trailing slash is lost once the command has cd'd: `cd WT/backend && rsync -a WT/web/ /tmp/x` becomes `rsync -a ../web /tmp/x`. For rsync and cp, `web/` and `web` mean different things, so the quoted command no longer reproduces what ran. | (line 307) posixpath.normpath drops a trailing slash, so `rsync -a <wt>/web/ dst` under `cd <wt>/backend` reads `rsync -a ../web dst`. For rsync and cp -r a trailing slash changes meaning. | (line 307) A marked path that starts with '/' (for example `<wt>//x`) is passed to posixpath.relpath with a relative `here`; relpath resolves it against the process cwd and the probe printed `../../../../../../../../../../x`, which varies with where land.py runs. | (line 307) The bare-root sentence-stop form (`<wt>.`, which _strip turns into `\x00..`) is captured as the path `..`; under a cd it is rebased to `../..`, so the full stop is lost and the result names the wrong directory.
3. **low** `scripts/todos/land.py:314` cwd tracking treats a `cd` after `||` as always run. In `a || cd <wt>/web && ls <wt>/x`, the cd runs only when `a` fails, but later paths are rebased against web anyway; the test passes only because ../b is the same from backend and from web.
4. **low** `scripts/todos/land.py:262` Directory tracking sees only a bare `cd` at the start of a part split on &&, || and ;. A newline, a single `&`, a pipe, a subshell `(cd <wt>/web && ls <wt>/a)` or `pushd` is missed, so later paths are rebased wrongly or not at all (e.g. `cd <wt>/backend\npython3 <wt>/scripts/x.py` still reads `python3 scripts/x.py`). | also: (line 313) Directory tracking only sees a `cd` at the start of an &&/||/; part. `(cd <wt>/web && ls <wt>/a)` gives `ls a` where `ls ../a` is needed, and `pushd <wt>/web/src && ls <wt>/a` gives `../a` where `../../a` is needed. The docstring claims every other directory change leaves the cwd unknown, which these cases do not. No worse than before the change. | (line 313) A cd inside a subshell and pushd are invisible: `(cd WT/backend && ls WT/x)` gives `ls x` (should be `ls ../x`); `pushd WT/backend && ls WT/scripts` gives `ls scripts`. | (line 263) _CMD_SPLIT_RE splits only on &&, || and ;. A subshell `(cd <wt>/backend && ls <wt>/a)`, a newline, or `&` leaves cwd unchanged, so later paths stay repo-relative and the quoted command no longer re-runs. The mixed `ls ../a\n ls ../b` case works. | (line 275)_split_command only splits on &&, || and ; and ignores a single & (background), pipes and subshells/escaped quotes, so a cd in `( cd x; ... )` or after `&` tracks the wrong cwd and later paths are rebased against it.
5. **low** `scripts/todos/land.py:268` _split_command treats any apostrophe or backslash-escaped quote as opening a quote. In `cd <wt>/backend && echo it's && cd <wt>/web && ls <wt>/backend/y` the second cd is never seen and the output is `ls y` instead of `../backend/y`.
6. **low** `scripts/todos/land.py:306` Paths are rebased against the shell cwd even when a flag like `git -C <dir>` re-roots them: `cd WT/backend && git -C WT diff WT/web` becomes `git -C .. diff ../web`, which git resolves against the repo root, outside the repo. The old output was also wrong (`-C . diff web`), so no regression.
7. **low** `scripts/todos/land.py:313` Directory tracking only sees a `cd` at the start of an &&/||/; part. `(cd <wt>/web && ls <wt>/a)` gives `ls a` where `ls ../a` is needed, and `pushd <wt>/web/src && ls <wt>/a` gives `../a` where `../../a` is needed. The docstring claims every other directory change leaves the cwd unknown, which these cases do not. This is no worse than before the change. | also: The cwd tracking only sees a bare `cd` at the start of a part. A `cd` inside a subshell (`(cd WT/a && ls WT/b)`) and `pushd` are invisible to it, so paths after them are not rebased. Probed: `(cd WT/backend && ls WT/x)` gives `ls x`, which should be `ls ../x`, and `pushd WT/backend && ls WT/scripts` gives `ls scripts`.
8. **low** `scripts/todos/land.py:263` _CMD_SPLIT_RE splits only on &&, || and ;. A subshell `(cd <wt>/backend && ls <wt>/a)`, a newline, or `&` leaves cwd unchanged, so later paths stay repo-relative and the quoted command no longer re-runs. Probed: `(cd backend && ls a)`. The mixed `ls ../a\n ls ../b` case works.
9. **low** `scripts/todos/land.py:307` posixpath.normpath drops a trailing slash, so `rsync -a <wt>/web/ dst` under `cd <wt>/backend` reads `rsync -a ../web dst`. For rsync and cp -r a trailing slash changes meaning, so the quoted command no longer re-runs the same way. | also: A marked path that starts with '/' (for example `<wt>//x`) is passed to posixpath.relpath with a relative `here`. relpath then resolves it against the process cwd, and the probe printed `../../../../../../../../../../x`, which changes with wherever land.py runs. | The bare-root sentence-stop form (`<wt>.`, which _strip turns into `\x00..`) is captured as the path `..`. Under a cd it is rebased to `../..`, so the full stop is lost and the result names the wrong directory.
10. **low** `scripts/todos/land.py:275` _split_command only splits on &&, ||, ; and ignores a single & (background), pipes and subshells/escaped quotes, so a cd in `( cd x; ... )` or after `&` tracks the wrong cwd and later paths are rebased against it.

1 more location(s) were dropped by the cap of 10 (the most severe are kept).

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log
