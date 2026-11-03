#!/usr/bin/env bash
# PreToolUse hook (Bash) — WARN, never block, when a command creates a branch
# from a remote ref with upstream tracking on (todo 689).
#
# `git switch -c <new> origin/main` (or `git checkout -b <new> origin/main`)
# turns on upstream tracking, which writes .git/config. The Bash sandbox refuses
# every write to that file ("could not lock config file .git/config: Operation
# not permitted"), and git then stops half-way: the branch exists and the index
# and tree have moved, but HEAD is still on the OLD branch, so the new branch's
# content looks like a large staged change on the wrong branch.
#
# Fires on `switch -c/-C/--create/--force-create` and `checkout -b/-B` when the
# start point is a remote-tracking ref (origin/..., remotes/..., refs/remotes/...)
# or --track is given, unless --no-track is present. Output is additionalContext
# plus a systemMessage; there is no permissionDecision, so the command runs as
# written. Fails open (no python3, unparseable event, unparseable command).
#
# Tests: .claude/hooks/test-warn-git-track.sh
set -uo pipefail
command -v python3 >/dev/null 2>&1 || exit 0

INPUT=$(cat)

WARN_GIT_TRACK_INPUT="$INPUT" python3 - <<'PYEOF' 2>/dev/null || exit 0
import json
import os
import shlex
import sys

try:
    event = json.loads(os.environ.get("WARN_GIT_TRACK_INPUT", ""))
except ValueError:
    sys.exit(0)
if not isinstance(event, dict) or event.get("tool_name") != "Bash":
    sys.exit(0)
command = (event.get("tool_input") or {}).get("command")
if not isinstance(command, str) or "git" not in command:
    sys.exit(0)

# A backslash-newline is a line continuation, not a separator.
command = command.replace("\\\n", " ")
SEPARATORS = ";&|()<>\n"
try:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=SEPARATORS)
    lexer.whitespace_split = True
    lexer.whitespace = " \t\r"
    lexer.commenters = ""
    tokens = list(lexer)
except ValueError:
    sys.exit(0)

# Split into simple commands on shell operators (&&, ||, ;, |) and on unquoted
# newlines, so each line of a multi-line script is checked on its own.
segments, current = [], []
for tok in tokens:
    if tok and all(ch in SEPARATORS for ch in tok):
        segments.append(current)
        current = []
    else:
        current.append(tok)
segments.append(current)

REMOTE_PREFIXES = ("origin/", "remotes/", "refs/remotes/")
# Global git options that take a separate value.
GLOBAL_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}
CREATE = {
    "switch": ("-c", "-C", "--create", "--force-create"),
    "checkout": ("-b", "-B"),
}


def creates_tracking_branch(seg):
    i = 0
    while i < len(seg):
        word = seg[i]
        if word == "git" or word.endswith("/git"):
            break
        i += 1
    else:
        return False
    i += 1
    while i < len(seg) and seg[i].startswith("-"):
        i += 2 if seg[i] in GLOBAL_WITH_VALUE else 1
    if i >= len(seg) or seg[i] not in CREATE:
        return False
    sub, rest = seg[i], seg[i + 1 :]
    flags = CREATE[sub]
    created = any(
        t in flags
        or (len(t) > 2 and t[:2] in flags and not t.startswith("--"))
        or any(t.startswith(f + "=") for f in flags if f.startswith("--"))
        for t in rest
    )
    if not created or "--no-track" in rest:
        return False
    explicit_track = any(t in ("-t", "--track") or t.startswith("--track=") for t in rest)
    from_remote = any(t.startswith(REMOTE_PREFIXES) for t in rest if not t.startswith("-"))
    return explicit_track or from_remote


if not any(creates_tracking_branch(seg) for seg in segments if seg):
    sys.exit(0)

context = (
    "GIT TRACKING WARNING (todo 689). Creating a branch from a remote ref turns on "
    "upstream tracking, which writes .git/config. The Bash sandbox refuses that write "
    "('could not lock config file .../.git/config: Operation not permitted'), and git "
    "then half-applies: the new branch exists and the index and tree have moved, but "
    "HEAD stays on the OLD branch, so the new content shows up as staged changes there.\n"
    "Safe ways:\n"
    "- Branch: add --no-track, e.g. `git switch -c <new> --no-track origin/main` "
    "(or `git checkout -b <new> --no-track origin/main`).\n"
    "- Push: `git push origin HEAD` (no -u; -u also writes .git/config).\n"
    "- Sync a worktree with main: use the host's `sync_with_base_branch` tool where it "
    "is offered, which merges outside the sandbox; a sandboxed merge or rebase can fail "
    "on the same protected paths.\n"
    "- Repair if it already half-applied: `git symbolic-ref HEAD refs/heads/<new>`. It "
    "is non-destructive (the branch, index and tree already match the start point). "
    "Never `git reset --hard` without asking."
)
print(
    json.dumps(
        {
            "hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": context},
            "systemMessage": "git: branching from a remote ref without --no-track half-applies "
            "in the sandbox (todo 689); add --no-track.",
        }
    )
)
PYEOF
exit 0
