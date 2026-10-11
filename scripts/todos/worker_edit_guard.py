#!/usr/bin/env python3
"""PreToolUse decision for Edit/Write/MultiEdit/NotebookEdit calls from a todo-worker (todo 541, #982-9).

Since todo 528, execute-args creates each group's worktree and the worker is no longer harness-isolated: its
cwd is the main checkout and it is told to work only in `WORKTREE`. guard-worktree-isolation.sh acts only when
the cwd is inside a worktree, so a mistyped relative path, or an absolute one under the main checkout, would
land in the main checkout. This hook denies, for agent_type `todo-worker` only:

  - any target under the main checkout that is not inside one of its `.claude/worktrees/<name>/` worktrees
    (a relative path resolves against the cwd, so from the main checkout it is denied too), including a plain
    file placed directly in `.claude/worktrees/`;
  - when the cwd is itself inside a worker's worktree (`sweep-*`, made by execute-args, or a harness-isolated
    one: `wf_*` from a workflow's `isolation: 'worktree'`, `agent-*` from an agent's), a target inside a
    different one;
  - otherwise (the cwd is the main checkout, or a session's own worktree that the engine ran from and the
    worker inherited, todo 546), a target in a worktree that is no worker's: neither that session's worktree
    nor a human's (`todo-543-hand-round-guards`) is a worker's to edit. A `sweep-*` worktree is allowed. A
    harness one (`wf_*`, `agent-*`) is allowed only when a sweep run file records it as a todo's `worktree`
    (todo 577 #5): a retry or a round-1 repair worker runs without isolation and edits the group's recorded
    worktree, which is a harness one when the brief had no worktree or the attempt predates todo 528 (todo
    551), but another workflow's or agent's isolated worktree, or a human's named `wf_*`, is no group's. The
    run files read are `todos/.sweep-run-*.json` in the main checkout and in the cwd's own checkout (the
    engine's session may run from a worktree); one that cannot be read records nothing.

A target outside the repository ($TMPDIR, a scratchpad, the review round's repair worktrees) is allowed. Every
other agent passes through. The hook cannot read the brief: a PreToolUse event names the subagent (`agent_id`,
`agent_type`) but carries neither its prompt nor its transcript. So from the main checkout it cannot tell the
worker's own recorded worktree from another group's recorded one; the worker's prompt names it. Fails open when the event
is unparseable or the cwd is in no git checkout (exit 2 would block every edit in the session). A mistake guard,
not a security boundary: paths are compared after realpath with `startswith`, which does not fold case, so on a
case-insensitive APFS volume a differently-cased path into the main checkout is not caught.

Tests: .claude/hooks/test-guard-todo-worker-edit.sh
"""

import glob
import json
import os
import subprocess
import sys

GUARDED = {"todo-worker"}


def main_checkout(cwd):
    """The main checkout of the repository holding cwd (a linked worktree's common dir is <main>/.git)."""
    proc = subprocess.run(["git", "-C", cwd, "rev-parse", "--path-format=absolute", "--git-common-dir"],
                          capture_output=True, text=True)
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    return os.path.realpath(os.path.dirname(os.path.normpath(proc.stdout.strip())))


# execute-args' worktrees (todo 528), and the harness's isolated ones: a workflow agent's (`wf_*`, todo 551) and
# an Agent-tool subagent's (`agent-*`).
WORKER_PREFIXES = ("sweep-", "wf_", "agent-")


def worktree_of(path, main):
    """`<main>/.claude/worktrees/<name>` when path is that worktree or inside it, else None. A plain file directly
    in `.claude/worktrees/` is in no worktree (todo 546)."""
    base = os.path.join(main, ".claude", "worktrees") + os.sep
    if not path.startswith(base):
        return None
    name = path[len(base):].split(os.sep, 1)[0]
    if not name or not os.path.isdir(base + name):
        return None
    return base + name


def _is_worker(wt):
    return os.path.basename(wt).startswith(WORKER_PREFIXES)


def _checkout_root(cwd):
    proc = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    return os.path.realpath(proc.stdout.strip()) if proc.returncode == 0 and proc.stdout.strip() else None


def _run_entries(*roots):
    """Every todo entry in the sweep run files under each root's `todos/`. An unreadable file has none."""
    for root in {r for r in roots if r}:
        for path in glob.glob(os.path.join(root, "todos", ".sweep-run-*.json")):
            try:
                with open(path, encoding="utf-8") as fh:
                    run = json.load(fh)
            except (OSError, ValueError):
                continue
            todos = run.get("todos", {}) if isinstance(run, dict) else {}
            yield from (e for e in (todos.values() if isinstance(todos, dict) else ()) if isinstance(e, dict))


def recorded_worktrees(*roots):
    """Every todo `worktree` the sweep run files under each root's `todos/` record, realpath'd (todo 577 #5)."""
    return {os.path.realpath(e["worktree"]) for e in _run_entries(*roots)
            if isinstance(e.get("worktree"), str) and e["worktree"]}


def awaiting_a_worktree(*roots):
    """Whether a run has a todo executing with no recorded worktree (PR #1038 review). Its brief named none, so
    todo-execute gave the worker a harness-isolated one, and its retry edits that from the main checkout before
    ingest-execute records it. Dormant since todo 528 (execute-args always records one), but not refused."""
    return any(e.get("stage") == "executing" and not e.get("worktree") for e in _run_entries(*roots))


def decide(event):
    if event.get("agent_type") not in GUARDED:
        return None
    tool_input = event.get("tool_input") if isinstance(event.get("tool_input"), dict) else {}
    target = tool_input.get("file_path") or tool_input.get("notebook_path")
    cwd = event.get("cwd")
    if not isinstance(target, str) or not target or not isinstance(cwd, str) or not cwd:
        return None
    main = main_checkout(cwd)
    if not main:
        return None
    path = os.path.realpath(os.path.join(cwd, target))  # an absolute target ignores cwd
    if path != main and not path.startswith(main + os.sep):
        return None  # outside the repository
    wt = worktree_of(path, main)
    if wt is None:
        return (f"a todo-worker edits only inside its worktree (the prompt's WORKTREE), but {path} is in the main "
                f"checkout {main}; use an absolute path under WORKTREE")
    own = worktree_of(os.path.realpath(cwd), main)
    if own and _is_worker(own):
        if wt != own:
            return f"a todo-worker edits only inside its own worktree {own}, not {wt}"
        return None
    # Todo 546: the cwd is the main checkout, or a non-worker worktree the engine's session ran from (the worker
    # inherits it). A worker worktree is allowed (todo 551: a retry or repair edits a recorded `wf_*`/`agent-*`
    # one too); that session's worktree and a human's are not.
    if not _is_worker(wt):
        return (f"a todo-worker edits only inside its worktree (the prompt's WORKTREE), not {wt}, which is no "
                "worker's worktree")
    # Todo 577 #5: a harness worktree is a worker's only when a run records it as a group's.
    roots = (main, _checkout_root(cwd))
    if (not os.path.basename(wt).startswith("sweep-") and wt not in recorded_worktrees(*roots)
            and not awaiting_a_worktree(*roots)):
        return (f"a todo-worker edits only inside its worktree (the prompt's WORKTREE), not {wt}: no sweep run "
                "records it as a todo's worktree")
    return None


def main():
    try:
        event = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    if not isinstance(event, dict):
        return 0
    try:
        reason = decide(event)
    except Exception:  # a guard bug fails open here: blocking every edit would stop the worker cold
        return 0
    if reason:
        json.dump({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                          "permissionDecisionReason": f"todo sweep: {reason}"}}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
