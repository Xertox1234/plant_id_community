#!/usr/bin/env python3
"""PreToolUse decision for Edit/Write/MultiEdit/NotebookEdit calls from a todo-worker (todo 541, #982-9).

Since todo 528, execute-args creates each group's worktree and the worker is no longer harness-isolated: its
cwd is the main checkout and it is told to work only in `WORKTREE`. guard-worktree-isolation.sh acts only when
the cwd is inside a worktree, so a mistyped relative path, or an absolute one under the main checkout, would
land in the main checkout. This hook denies, for agent_type `todo-worker` only:

  - any target under the main checkout that is not inside one of its `.claude/worktrees/<name>/` worktrees
    (a relative path resolves against the cwd, so from the main checkout it is denied too);
  - when the cwd is itself inside such a worktree (a harness-isolated or retry worker), a target inside a
    different one.

A target outside the repository ($TMPDIR, a scratchpad) is allowed. Every other agent passes through. The hook
cannot read the brief, so it cannot tell the worker's own sweep worktree from another group's when the cwd is
the main checkout; the worker's prompt names it. Fails open when the event is unparseable or the cwd is in no
git checkout (exit 2 would block every edit in the session). A mistake guard, not a security boundary.

Tests: .claude/hooks/test-guard-todo-worker-edit.sh
"""

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


def worktree_of(path, main):
    """`<main>/.claude/worktrees/<name>` when path is inside it, else None."""
    base = os.path.join(main, ".claude", "worktrees") + os.sep
    if not path.startswith(base):
        return None
    name = path[len(base):].split(os.sep, 1)[0]
    return base + name if name else None


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
    if own and wt != own:
        return f"a todo-worker edits only inside its own worktree {own}, not {wt}"
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
