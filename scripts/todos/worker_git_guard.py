#!/usr/bin/env python3
"""PreToolUse decision for Bash calls from todo-worker / todo-verifier agents.

Workers write and stage; only the main session commits, pushes and opens PRs
(spec §4.1). Agent frontmatter cannot say that -- `disallowedTools:
Bash(git push *)` removes Bash entirely -- so this hook does: for those two
agent types it allows a short list of git subcommands and denies every other
git subcommand and all of gh. Every other caller passes through untouched.

It reads the command text, so it sees wrappers (rtk, env, xargs), absolute
paths, compound commands, `bash -c`, `$(...)` and multi-line commands. It is a
guard against mistakes, not a sandbox: a script file that runs git inside is
not visible here.

Tests: .claude/hooks/test-guard-todo-worker-git.sh
"""

import json
import os
import shlex
import sys

GUARDED_AGENTS = {"todo-worker", "todo-verifier"}
GIT_ALLOWED = {"add", "mv", "rm", "diff", "status", "log", "show", "fetch", "write-tree", "rev-parse"}
WRAPPERS = {"rtk", "command", "env", "time", "nohup", "xargs", "exec", "sudo"}
SHELLS = {"bash", "sh", "zsh"}
GIT_OPTS_WITH_ARG = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}
PUNCTUATION = ";&|()`"


def simple_commands(command):
    lexer = shlex.shlex(command.replace("\n", ";"), posix=True, punctuation_chars=PUNCTUATION)
    lexer.whitespace_split = True
    current = []
    for token in lexer:
        if token and set(token) <= set(PUNCTUATION):
            if current:
                yield current
            current = []
        else:
            current.append(token)
    if current:
        yield current


def check_words(words):
    i = 0
    while i < len(words):
        word = words[i]
        name = word.split("=", 1)[0]
        if "=" in word and not word.startswith("-") and name.isidentifier():
            i += 1
            continue
        if os.path.basename(word) in WRAPPERS:
            i += 1
            while i < len(words) and words[i].startswith("-"):
                i += 1
            continue
        break
    if i >= len(words):
        return None
    program, rest = os.path.basename(words[i]), words[i + 1:]
    if program == "gh":
        return "gh is reserved for the main session (Land)"
    if program in SHELLS and len(rest) >= 2 and rest[0] == "-c":
        return decide_command(rest[1])
    if program == "eval":
        return decide_command(" ".join(rest))
    if program != "git":
        return None
    j = 0
    while j < len(rest) and rest[j].startswith("-"):
        j += 2 if rest[j] in GIT_OPTS_WITH_ARG else 1
    if j >= len(rest) or rest[j] in GIT_ALLOWED:
        return None
    return (f"git {rest[j]} is reserved for the main session; workers stage and stop "
            f"(allowed: {', '.join(sorted(GIT_ALLOWED))})")


def decide_command(command):
    try:
        for words in simple_commands(command):
            reason = check_words(words)
            if reason:
                return reason
    except ValueError:
        return "command could not be parsed; simplify the quoting"
    return None


def decide(event):
    if event.get("agent_type") not in GUARDED_AGENTS:
        return None
    return decide_command(str((event.get("tool_input") or {}).get("command", "")))


def main():
    try:
        event = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    if not isinstance(event, dict):
        return 0
    reason = decide(event)
    if reason:
        json.dump({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                          "permissionDecisionReason": f"todo sweep: {reason}"}}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
