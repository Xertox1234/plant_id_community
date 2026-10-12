#!/usr/bin/env python3
"""PreToolUse decision for Bash calls from the todo sweep's agents.

The guarded agents (ALLOWED_BY_AGENT): todo-worker and todo-verifier, which may stage; todo-reviewer,
code-review-orchestrator and every domain reviewer that todo-review.js dispatches (REVIEW_AGENTS), which
get read-only git.

Workers write and stage; only the main session commits, pushes and opens PRs
(spec §4.1). Agent frontmatter cannot say that -- `disallowedTools:
Bash(git push *)` removes Bash entirely -- so this hook does: for those agent
types it allows a short list of git subcommands (read-only ones for the
reviewers) and denies every other git subcommand, all of gh, and any GIT_*
environment variable (GIT_DIR, GIT_EXTERNAL_DIFF, GIT_PAGER, ...). Every other
caller passes through untouched.

Staging (add/mv/rm) must name its worktree (todo 618, owner decisions 2026-10-11
and 2026-10-12): it is allowed only with a literal absolute `-C <path>` that
resolves inside a `.claude/worktrees/<name>/` worktree and is not a main checkout
(todo 468 m7, todo 477's pilot layout); a `--work-tree`, when given, must pass
the same test. A relative or runtime-built -C or --work-tree, a missing -C, and
a `git-add` binary are denied. The guard never tracks the working directory: a
`cd`, a pipeline stage or a function body cannot move where a staging git runs,
because the shell's directory is never consulted. Todo 640: when the hook event
names the agent's cwd, the worktree must be one of that repository's; a staging
git run by xargs, a staging option word built at runtime, a ( glued inside a word
(a zsh glob qualifier) and an rm/mv of a .git are denied too.

It tokenizes the command the way a shell does -- quotes, escapes, `$(...)`,
backticks, `<(...)`, redirections, heredocs and reserved words -- and finds the
program word of every simple command. It looks through wrappers (rtk, env,
sudo, timeout, nice, xargs, find -exec, ...), `sh -c`, `eval` and `env -S`
scripts, trap actions, and `git-<sub>` binaries. When it cannot tell what a
guarded agent's command runs -- a program name built at runtime, a shell
reading stdin, an unsupported git global option, unparseable quoting -- or
where a staging git would stage, it denies.

This is a mistake guard, not a security boundary: a python/node/perl one-liner
or a script file that runs git inside is not visible here.

Tests: .claude/hooks/test-guard-todo-worker-git.sh
"""

import glob
import json
import os
import re
import shlex
import subprocess
import sys

GIT_ALLOWED = {"add", "mv", "rm", "diff", "status", "log", "show", "fetch", "write-tree", "rev-parse"}
# Review-stage reviewers read the diff and report; they never stage (todo 468 m8). branch and worktree
# only list (READ_ONLY_ARGS); todo 477 widened the set for reviewers exploring the history.
GIT_READONLY = {"diff", "status", "log", "show", "rev-parse", "ls-files", "grep", "blame", "merge-base",
                "cat-file", "ls-tree", "rev-list", "branch", "worktree"}
BRANCH_LIST_FLAGS = {"--show-current", "--list", "-l", "-a", "--all", "-r", "--remotes", "-v", "-vv", "--verbose",
                     "--no-color", "--no-column"}
# git grep options whose value is the next word (or the rest of a short bundle), so an O in it is not -O.
GREP_VALUE_SHORT = set("efABCm")
GREP_VALUE_LONG = {"--regexp", "--file", "--after-context", "--before-context", "--context", "--max-count",
                   "--max-depth", "--threads"}
# zsh adds integer and float; ksh93 nameref (a declare -n) (todo 496 round 3).
DECLARERS = {"export", "declare", "typeset", "local", "readonly", "integer", "float", "nameref"}
NAMEREF_DECLARERS = {"declare", "typeset", "local"}  # -n makes a nameref (export -n un-exports)
ALLOWED_BY_AGENT = {"todo-worker": GIT_ALLOWED, "todo-verifier": GIT_ALLOWED, "todo-reviewer": GIT_READONLY}
# todo-review dispatches the orchestrator and its domain reviewers in the PR worktree (todo 472): they
# get the same read-only limit, which also covers their interactive use (they only diff, show, rev-parse).
REVIEW_AGENTS = ("code-review-orchestrator", "django-drf-reviewer", "wagtail-reviewer", "react-typescript-reviewer",
                 "flutter-dart-reviewer", "flutter-firebase-reviewer", "firebase-cloudfunction-reviewer",
                 "celery-async-reviewer", "cross-cutting-reviewer")
ALLOWED_BY_AGENT.update({a: GIT_READONLY for a in REVIEW_AGENTS})
GUARDED_AGENTS = set(ALLOWED_BY_AGENT)
MAIN_REASON = ("git {sub} would run in the main checkout at {path}; name your worktree explicitly: "
               "git -C <absolute WT> {sub} ...")
# Todo 618: staging names its worktree with a literal absolute -C; the shell's directory is never consulted.
NO_C_REASON = ("git {sub} must name its worktree: git -C <absolute path inside .claude/worktrees/> {sub} ... "
               "(a cd, a relative path or a bare git {sub} is not followed)")
NOT_ABSOLUTE_REASON = ("git {sub}: {raw} is not a literal absolute path; name the worktree literally: "
                       "git -C <absolute path inside .claude/worktrees/> {sub} ...")
OUTSIDE_REASON = ("git {sub} would stage in {path}, which is not inside a .claude/worktrees/<name>/ worktree of "
                  "this repository; name your worktree: git -C <absolute WT> {sub} ...")
# The calling agent's allowed set, set by decide() for one hook call.
CONTEXT = {"allowed": GIT_ALLOWED, "cwd": None}
GIT_GLOBAL_WITH_VALUE = {"-C", "--git-dir", "--work-tree"}
GIT_GLOBAL_FLAGS = {"--no-pager", "-P", "--no-optional-locks"}
# Long options that make an allowed subcommand run a program, write a file or
# read refspecs from stdin (fetch --stdin). git accepts unambiguous prefixes
# (--outp=x, --st), so any non-empty prefix counts too (todo 496, owner decision 2026-10-11:
# a fixed list, never derived from git's own option table). rev-list hands unknown options to the
# diff parser, so it takes --output too; grep's --textconv runs a configured driver like diff's.
OUTPUT_OPTIONS = ("output", "ext-diff", "textconv")
GIT_DENIED_OPTIONS = {"fetch": ("upload-pack", "stdin"), "diff": OUTPUT_OPTIONS, "log": OUTPUT_OPTIONS,
                      "show": OUTPUT_OPTIONS, "rev-list": OUTPUT_OPTIONS,
                      "grep": ("open-files-in-pager", "textconv"), "cat-file": ("textconv", "filters")}
GIT_EXACT_OPTIONS = {"text"}  # a real option, so not a prefix of --textconv
FORCE_SUBCOMMANDS = {"add", "mv", "rm"}
FORCE_REASON = "force-staging ignored files is not allowed (git add/mv/rm -f / --force)"
# Todo 640 #4: an option word built at runtime could be -f; after `--` every word is a path.
RUNTIME_FORCE_REASON = ("git {sub}: {raw} is built at runtime and could be -f / --force; put paths after --: "
                        "git -C <absolute WT> {sub} -- <paths>")
# Todo 640 #1/#4: xargs builds the words it adds (or puts in place of -I/-J's replstr) at runtime, so the -C or a -f
# could come from its input.
XARGS_REASON = ("git {sub} through xargs builds its arguments at runtime (a -C or a -f could come from the input); "
                "run git -C <absolute WT> {sub} -- <paths> directly")
# Todo 640 #8: with WT/.git gone, git -C WT finds the repository above it -- the main checkout.
REMOVERS = {"rm", "unlink", "rmdir", "mv"}
DOT_GIT_REASON = ("{program} on a .git is not allowed for this agent: git -C <WT> would then find the main "
                  "checkout's repository")
SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "fish"}
SOURCES = {"source", "."}  # run a script in the current shell: same stdin risk as a shell
# Unquoted reserved words (and zsh precommand modifiers) that only prefix the
# real command. `for`, `select` and `case` start a word list or a pattern, which
# is data; `function` and zsh's `repeat` are followed by a name / count.
KEYWORDS = {"then", "do", "else", "elif", "if", "while", "until", "in", "esac", "fi", "done",
            "{", "}", "!", "coproc", "builtin", "always", "noglob", "nocorrect"}
DATA_KEYWORDS = {"for", "select", "case"}
# Signals whose trap runs around every command or on any failure, so their action cannot be placed (todo 584).
EVERY_COMMAND_TRAPS = {"DEBUG", "ERR", "ZERR", "RETURN"}
# wrapper -> (options that take a separate value, operands before the command)
WRAPPERS = {
    "rtk": ((), 0), "command": ((), 0), "nohup": ((), 0), "exec": (("-a",), 0),
    "time": (("-o", "-f"), 0), "caffeinate": (("-t", "-w"), 0),
    # -P altpath is macOS env's; -a/--argv0 is GNU's. -S/--split-string is handled by env_split_string.
    "env": (("-u", "--unset", "-C", "--chdir", "-P", "-a", "--argv0"), 0),
    "sudo": (("-u", "-g", "-C", "-D", "--chdir", "-h", "-p", "-r", "-t", "-U", "-T", "--user", "--group",
              "--close-from", "--host", "--prompt", "--role", "--type", "--other-user", "--command-timeout",
              "--chroot"), 0),
    "doas": (("-u", "-C"), 0),
    "timeout": (("-s", "--signal", "-k", "--kill-after"), 1),
    "nice": (("-n", "--adjustment"), 0),
    "stdbuf": (("-i", "-o", "-e", "--input", "--output", "--error"), 0),
    "ionice": (("-c", "-n", "-p", "--class", "--classdata"), 0),
    "chrt": ((), 1), "taskset": ((), 1),
    # -J replstr, -R replacements and -S replsize are BSD/macOS xargs's (todo 640 #2).
    "xargs": (("-a", "-d", "-E", "-I", "-J", "-L", "-n", "-P", "-R", "-S", "-s", "--arg-file", "--delimiter",
               "--max-args", "--max-lines", "--max-procs", "--max-chars", "--process-slot-var"), 0),
}
NOT_LITERAL = set("$`*?[{<>")
OPERATORS = (";;&", ";;", ";&", "&&", "||", "|&", ";", "&", "|", "(", ")")
REDIRECTIONS = ("&>>", "&>", "<<<", "<<-", "<<", "<>", "<&", ">>", ">&", ">|", "<", ">")
CASE_ENDS = {";;", ";&", ";;&"}
MAX_DEPTH = 10
PARSE_REASON = "command could not be parsed; simplify the quoting"
STDIN_REASON = "run git directly, not through a shell reading stdin"
# Todo 496 G: `: ${GIT_DIR:=/x/.git}` (also = and zsh's ::=) assigns through a parameter expansion, and zsh's
# ${(P)name::=x} assigns to the variable `name` holds. Arithmetic assigns too: $((GIT_X=1)), let, (( )).
PARAM_ASSIGN = re.compile(r"\$\{GIT_\w*:{0,2}=|\$\{\([^)]*P[^)]*\)[^}]*=")
ARITH_ASSIGN = re.compile(r"\bGIT_\w*\s*(?:\*\*|<<|>>|[-+*/%&|^])?=(?!=)")
PARAM_REASON = "assigning a GIT_* variable inside an expansion is not allowed for this agent"
NAME_START = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
# Todo 496 F/D: variables that turn shell options on when a shell starts (SHELLOPTS=allexport,
# BASHOPTS=lastpipe) are refused like GIT_* ones.
SHELL_OPTION_VARS = {"SHELLOPTS", "BASHOPTS"}


class Word:
    """One shell word: `value` has the quoting removed, `raw` is the source text, `nested` the
    command substitutions inside it (todo 496: judged where the word runs, after an earlier cd)."""

    def __init__(self, value, raw, nested=None):
        self.value, self.raw, self.nested = value, raw, nested or []


class Lexer:
    """Splits a command into ("word", Word), ("op", str) and ("redir", str) tokens.

    The text inside every `$(...)`, backtick pair and `<(...)` / `>(...)` goes to
    `nested`, to be decided as a command of its own. Heredoc bodies are data and
    are dropped; an unquoted delimiter's body is still scanned for substitutions.
    Raises ValueError on anything unterminated.
    """

    def __init__(self, text, start=0):
        self.s, self.i = text, start
        self.tokens, self.nested, self.heredocs = [], [], []
        self.tainted = False  # an expanding heredoc body assigns a GIT_* variable (todo 496 G)

    def run(self, until_close=False):
        s, depth = self.s, 0
        while self.i < len(s):
            c = s[self.i]
            if c in " \t":  # not \r: to the shell it is part of a word (<<EOF\r)
                self.i += 1
            elif s.startswith("\\\n", self.i):
                self.i += 2
            elif c == "#":
                end = s.find("\n", self.i)
                self.i = len(s) if end < 0 else end
            elif c == "\n":
                self.i += 1
                self.tokens.append(("op", "\n"))
                self.read_heredoc_bodies()
            elif (c in "<>" or s.startswith("&>", self.i)) and not s.startswith("(", self.i + 1):
                op = next(r for r in REDIRECTIONS if s.startswith(r, self.i))
                self.i += len(op)
                self.tokens.append(("redir", op))
                if op in ("<<", "<<-"):
                    self.read_heredoc_start(strip_tabs=op == "<<-")
            elif c in ";&|()":
                op = next(o for o in OPERATORS if s.startswith(o, self.i))
                if until_close and op == ")":
                    if depth == 0:
                        return
                    depth -= 1
                elif until_close and op == "(":
                    depth += 1
                self.i += len(op)
                self.tokens.append(("op", op))
            else:
                word = self.read_word()
                if word.raw.isdigit() and s[self.i:self.i + 1] in ("<", ">"):
                    continue  # the fd number of a redirection such as 2>&1
                self.tokens.append(("word", word))
        if until_close:
            raise ValueError("unclosed (")
        if self.heredocs:
            raise ValueError("unterminated heredoc")

    def read_word(self):
        s, start, value, first = self.s, self.i, [], len(self.nested)
        while self.i < len(s):
            c = s[self.i]
            if c in "<>" and s.startswith("(", self.i + 1):
                self.read_subst(value)
            elif c == "(" and self.i > start and not s.startswith("()", self.i) and s[self.i - 1] != "=":
                # Todo 640 #3: zsh reads a ( glued inside a word as a glob qualifier (MAIN(/) is MAIN) and bash's
                # extglob as a pattern, so the word is not where the ( splits it. f() and NAME=( ) still split.
                raise ValueError("a ( inside a word (a zsh glob qualifier or an extended glob)")
            elif c in " \t\n;&|()<>":
                break
            elif c == "\\":
                value.append(s[self.i + 1:self.i + 2].replace("\n", ""))
                self.i += 2
            elif c == "'":
                end = s.find("'", self.i + 1)
                if end < 0:
                    raise ValueError("unterminated '")
                value.append(s[self.i + 1:end])
                self.i = end + 1
            elif c == '"':
                self.read_double(value)
            elif c == "`":
                self.read_backtick(value)
            elif c == "$":
                self.read_dollar(value, quoted=False)
            else:
                value.append(c)
                self.i += 1
        return Word("".join(value), s[start:self.i], self.nested[first:])

    def read_double(self, value):
        s = self.s
        self.i += 1
        while self.i < len(s):
            c = s[self.i]
            if c == '"':
                self.i += 1
                return
            if c == "\\":
                nxt = s[self.i + 1:self.i + 2]
                value.append(nxt if nxt in '$`"\\' else "" if nxt == "\n" else c + nxt)
                self.i += 2
            elif c == "`":
                self.read_backtick(value)
            elif c == "$":
                self.read_dollar(value, quoted=True)
            else:
                value.append(c)
                self.i += 1
        raise ValueError('unterminated "')

    def read_backtick(self, value):
        s, j, inner = self.s, self.i + 1, []
        while j < len(s) and s[j] != "`":
            if s[j] == "\\" and s[j + 1:j + 2] in ("$", "`", "\\"):
                j += 1
            inner.append(s[j])
            j += 1
        if j >= len(s):
            raise ValueError("unterminated `")
        self.nested.append("".join(inner))
        value.append(s[self.i:j + 1])
        self.i = j + 1

    def read_dollar(self, value, quoted):
        s, nxt = self.s, self.s[self.i + 1:self.i + 2]
        if nxt == "(":
            self.read_subst(value, arithmetic=s.startswith("((", self.i + 1))
        elif nxt == "{":
            start = self.i
            self.i += 2
            while self.i < len(s) and s[self.i] != "}":
                c = s[self.i]
                if c == "\\":
                    self.i += 2
                elif c == '"':
                    self.read_double([])
                elif c == "`":
                    self.read_backtick([])
                elif c == "$":
                    self.read_dollar([], quoted=True)
                else:
                    self.i += 1
            if self.i >= len(s):
                raise ValueError("unterminated ${")
            self.i += 1
            value.append(s[start:self.i])
        elif nxt == "'" and not quoted:  # $'...' ANSI-C string: keep it raw (tainted)
            j = self.i + 2
            while j < len(s) and s[j] != "'":
                j += 2 if s[j] == "\\" else 1
            if j >= len(s):
                raise ValueError("unterminated $'")
            value.append(s[self.i:j + 1])
            self.i = j + 1
        elif nxt == '"' and not quoted:  # $"..." is a translated "..." string
            self.i += 1
        else:
            value.append("$")
            self.i += 1

    def read_subst(self, value, arithmetic=False):
        """`$(...)`, `$((...))`, `<(...)` or `>(...)` starting at self.i."""
        sub = Lexer(self.s, self.i + 2)
        sub.run(until_close=True)
        if arithmetic:  # $((...)) is not a command, but may hold substitutions
            self.nested.extend(sub.nested)
        else:
            self.nested.append(self.s[self.i + 2:sub.i])
        value.append(self.s[self.i:sub.i + 1])
        self.i = sub.i + 1

    def read_heredoc_start(self, strip_tabs):
        s = self.s
        while self.i < len(s) and s[self.i] in " \t":
            self.i += 1
        if self.i >= len(s) or s[self.i] in "\n;&|()<>":
            raise ValueError("heredoc without a delimiter")
        word = self.read_word()
        self.heredocs.append((word, word.raw == word.value, strip_tabs))
        self.tokens.append(("word", word))

    def read_heredoc_bodies(self):
        s = self.s
        for word, expand, strip_tabs in self.heredocs:
            delimiter = word.value
            while True:
                if self.i >= len(s):
                    raise ValueError("unterminated heredoc")
                end = s.find("\n", self.i)
                end = len(s) if end < 0 else end
                line, self.i = s[self.i:end], end + 1
                if (line.lstrip("\t") if strip_tabs else line) == delimiter:
                    break
                if expand:  # <<EOF (unquoted) still runs $(...) and backticks
                    self.tainted = self.tainted or assigns_git(line)
                    body = Lexer(line)
                    while body.i < len(line):
                        if line[body.i] == "\\":
                            body.i += 2
                        elif line[body.i] == "`":
                            body.read_backtick([])
                        elif line[body.i] == "$":
                            body.read_dollar([], quoted=True)
                        else:
                            body.i += 1
                    self.nested.extend(body.nested)
                    word.nested.extend(body.nested)  # the body runs with the command that reads it
        self.heredocs = []


def assigns_git(raw):
    """True when shell text assigns a GIT_* variable through an expansion or arithmetic (todo 496 G)."""
    if PARAM_ASSIGN.search(raw):
        return True
    return ("$((" in raw or "$[" in raw) and bool(ARITH_ASSIGN.search(raw))


class Segment:
    """A simple command: its words, whether stdin is redirected or piped, the operator after it, and the
    command substitutions in its words and redirection targets (`nested`)."""

    def __init__(self, words, stdin, piped, end, nested=()):
        self.words, self.stdin, self.piped, self.end = words, stdin, piped, end
        self.nested = list(nested) + [n for w in words for n in w.nested]


def segments(tokens):
    words, stdin, piped, targets = [], False, False, []
    tokens = iter(tokens)
    for kind, val in tokens:
        if kind == "word" and val.raw == "}":  # zsh ends a group at `}` alone: { true } always { … }
            yield Segment(words + [val], stdin, piped, "}", (n for t in targets for n in t.nested))
            words, stdin, piped, targets = [], False, False, []
        elif kind == "word":
            words.append(val)
        elif kind == "redir":
            target = next(tokens, None)
            if target is None or target[0] != "word":
                raise ValueError("redirection without a target")
            stdin = stdin or val.startswith("<")
            targets.append(target[1])
        else:
            yield Segment(words, stdin, piped, val, (n for t in targets for n in t.nested))
            piped = val in ("|", "|&") or (piped and not words and val == "(")
            words, stdin, targets = [], False, []
    yield Segment(words, stdin, piped, None, (n for t in targets for n in t.nested))


def check_segments(segs, depth):
    cases, pattern, opens = 0, False, 0
    for seg in segs:
        # Todo 496 G: `(( GIT_X = 1 ))` is two ( operators, then words; it assigns like $((...)).
        if opens >= 2 and ARITH_ASSIGN.search(" ".join(w.raw for w in seg.words)):
            return PARAM_REASON
        opens = opens + 1 if seg.end == "(" and not seg.words else 0
        # Todo 496 finding 3: a case or for word's $(...) still runs, though the words are data.
        for inner in seg.nested:
            reason = decide_command(inner, depth + 1)
            if reason:
                return reason
        first = next((w for w in seg.words if keyword(w) not in KEYWORDS - {"esac"}), None)
        lead = keyword(first) if first else None
        skip = False
        if pattern:  # a case pattern such as `*)` is data
            if lead != "esac":
                pattern, skip = seg.end != ")", True
            else:
                cases, pattern = cases - 1, False
        elif lead == "case":
            cases, pattern, skip = cases + 1, seg.end != ")", True
        if not skip:
            reason = check_words(seg.words, seg.piped, seg.stdin, depth)
            if reason:
                return reason
        if cases and seg.end in CASE_ENDS:
            pattern = True
    return None


def is_assignment(word):
    name, eq, _ = word.raw.partition("=")
    return bool(eq) and name.rstrip("+").isidentifier()


def keyword(word):
    """The word's text if it could be a reserved word (unquoted), else None."""
    return word.value if word.raw == word.value else None


def git_env(word):
    """True for an assignment to a GIT_* variable: GIT_DIR or GIT_WORK_TREE move where git stages,
    GIT_EXTERNAL_DIFF or GIT_PAGER make an allowed read run a program (todos 477, 478)."""
    return is_assignment(word) and git_name(word.raw)


def git_name(text):
    """True when `text` starts with a GIT_* variable name, bare or with a subscript or value (GIT_DIR,
    GIT_DIR=x, GIT_DIR+=x, GIT_DIR[1]=x, zsh's read 'GIT_DIR?prompt'), or names SHELLOPTS / BASHOPTS."""
    match = NAME_START.match(text)
    return bool(match) and (match.group().startswith("GIT_") or match.group() in SHELL_OPTION_VARS)


def var_name(text):
    match = NAME_START.match(text)
    return match.group() if match else text


def runtime(raw):
    """True when a word's source text is built at runtime ($x, ${x}, $(...), backticks)."""
    return "$" in raw or "`" in raw


# Todo 496 finding 5: builtins that set a variable named by an operand (read GIT_DIR <<< x), and the
# ones that take the name after -v (printf -v GIT_DIR x; zsh print -v).
VAR_SETTERS = {"read", "mapfile", "readarray", "vared", "getopts"}
VAR_OPTION_SETTERS = {"printf", "print"}
# Their options that take a value (the next word, or the rest of a short bundle). bash read -a NAME names
# an array; mapfile -C runs a callback (todo 496 round 3).
SETTER_VALUE_LETTERS = {"read": set("adinNptu"), "mapfile": set("dnOsuCc"), "readarray": set("dnOsuCc"),
                        "vared": set("prMmift")}
# zsh builtins and modules that store into a variable named by an operand or an option value: any GIT_
# word in them is refused (fail closed).
ZSH_NAME_SETTERS = {"zparseopts", "zstyle", "strftime", "zformat", "getln", "sysread", "zregexparse", "zstat",
                    "ztcp", "zsocket", "zselect", "zsystem", "let"}
NAME_REASON = ("a variable name built at runtime ({raw}) is not allowed for {program} here; "
               "name the variable literally")


def check_setters(program, rest, depth):
    """The reason to deny a declarer, read-like builtin, printf -v or let: a GIT_* (or SHELLOPTS/BASHOPTS)
    name, a name built at runtime (`export ${p}DIR=x`), or a nameref to a GIT_* name (todo 496 H)."""
    names, built = [], []

    def name(word):
        if runtime(word.raw):
            built.append(word.raw)
        elif git_name(word.value):
            names.append(var_name(word.value))

    if program in DECLARERS:
        nameref = program == "nameref"
        for w in rest:
            v = w.value
            if v[:1] in ("-", "+") and len(v) > 1:
                nameref = nameref or (program in NAMEREF_DECLARERS and v[0] == "-" and "n" in v[1:])
                if runtime(w.raw):
                    built.append(w.raw)
                continue
            name_raw, eq, target_raw = w.raw.partition("=")
            name(Word(v.partition("=")[0], name_raw))
            if nameref:  # declare -n r=GIT_DIR; an unset nameref takes its target from the next r=GIT_DIR
                target = v.partition("=")[2]
                if not eq or runtime(target_raw) or git_name(target):
                    names.append(f"{var_name(v)} -> {target or '?'}")
    elif program in VAR_SETTERS:
        letters, operands, k = SETTER_VALUE_LETTERS.get(program, set()), [], 0
        while k < len(rest):
            w, v = rest[k], rest[k].value
            k += 1
            if v == "--":
                operands += rest[k:]
                break
            if program != "getopts" and v.startswith("-") and len(v) > 1:
                if "GIT_" in v:  # a glued name such as read -aGIT_X (fail closed)
                    names.append(v)
                for n, c in enumerate(v[1:], start=1):
                    if c not in letters:
                        continue
                    value = rest[k] if n == len(v) - 1 and k < len(rest) else Word(v[n + 1:], w.raw)
                    k += 1 if n == len(v) - 1 else 0
                    if c == "a" and program == "read":
                        operands.append(value)
                    elif c == "C" and program in ("mapfile", "readarray"):
                        reason = decide_command(value.value, depth + 1)  # the callback runs as a command
                        if reason:
                            return reason
                    elif git_name(value.value):
                        names.append(var_name(value.value))
                    break
                continue
            operands.append(w)
        for w in operands[1:2] if program == "getopts" else operands:
            name(w)
    elif program in VAR_OPTION_SETTERS:
        # Options come before the first operand; zsh print bundles them (-rv NAME) and -f/-C/-u/-x/-X take a
        # value too, so the walk skips those values rather than stopping at them.
        letters, k = set("fCuxXv") if program == "print" else {"v"}, 0
        while k < len(rest):
            w, v = rest[k], rest[k].value
            k += 1
            if v == "--" or not v.startswith("-") or len(v) == 1:
                break
            for n, c in enumerate(v[1:], start=1):
                if c not in letters:
                    continue
                glued = n < len(v) - 1
                value = Word(v[n + 1:], w.raw) if glued else (rest[k] if k < len(rest) else Word("", ""))
                k += 0 if glued else 1
                if c == "v":
                    name(value)
                break
    elif program in ZSH_NAME_SETTERS:
        for w in rest:
            if "GIT_" in w.value or (program == "let" and ARITH_ASSIGN.search(w.value)):
                names.append(w.value)
    if built:
        return NAME_REASON.format(raw=", ".join(built), program=program)
    if names:
        return GIT_ENV_REASON.format(names=", ".join(names))
    return None


GIT_ENV_REASON = ("environment variables ({names}) are not allowed for this agent (GIT_* ones move or run git, "
                  "SHELLOPTS/BASHOPTS turn on shell options); use git -C <WT> and --no-pager instead")
ALLEXPORT_REASON = "turning on allexport (set -a, set -o allexport, setopt allexport) is not allowed for this agent"
OPTION_REASON = "a shell option name built at runtime ({raw}) is not allowed here; name the option literally"
DEFINE_REASON = "{program} definitions are not allowed for this agent; run the command by its name"
TRAP_REASON = "a {signal} trap runs around every command or on any failure; not allowed for this agent"
KEYWORD_REASON = ("turning on keyword (set -k, set -o keyword, bash -k) exports every NAME=value argument, so a "
                  "GIT_* one would reach git; not allowed for this agent")


def option_is(text, name):
    """zsh option names ignore case and underscores, and a leading `no` negates (no_allexport)."""
    norm = text.lower().replace("_", "").replace("-", "")
    return norm in (name, "no" + name)


def check_shell_options(program, rest, depth):
    """set / setopt / unsetopt / shopt / emulate: deny allexport in every spelling (todo 496 F). Names built at
    runtime are denied, except a bash `shopt -s/-u` operand (bash's own option list holds no allexport).
    keyword (set -k) is denied like allexport (todo 584). Also zsh's `set -A NAME` and fish's `set NAME` set
    a variable."""
    flags, k = "", 0
    while k < len(rest):
        w, v = rest[k], rest[k].value
        k += 1
        if v == "--" and program == "set":
            return None  # the rest are positional parameters
        if v[:1] in ("-", "+") and len(v) > 1 and not v.startswith("--"):
            if runtime(w.raw):
                return OPTION_REASON.format(raw=w.raw)
            letters = v[1:]
            flags += letters
            if v[0] == "-" and "a" in letters and program in ("set", "setopt", "unsetopt"):
                return ALLEXPORT_REASON  # set -a; zsh's single-letter -a is ALL_EXPORT too
            if v[0] == "-" and "k" in letters and program in ("set", "setopt", "unsetopt"):
                return KEYWORD_REASON  # todo 584 finding 3: set -k (zsh's -k is another option: fail closed)
            if program in ("setopt", "unsetopt") and "m" in letters:
                return ALLEXPORT_REASON  # setopt -m 'all*' sets every option matching a pattern
            if program == "emulate" and "c" in letters and k < len(rest):
                reason = decide_command(rest[k].value, depth + 1)  # emulate sh -c CMD
                if reason:
                    return reason
                k += 1
                continue
            if program == "set" and "A" in letters:  # zsh: set -A NAME values...
                if k < len(rest) and (runtime(rest[k].raw) or git_name(rest[k].value)):
                    return GIT_ENV_REASON.format(names=rest[k].raw)
                return None
            if "o" in letters and program != "shopt" and k < len(rest):
                opt = rest[k]
                k += 1
                if runtime(opt.raw):
                    return OPTION_REASON.format(raw=opt.raw)
                if option_is(opt.value, "allexport"):
                    return ALLEXPORT_REASON
                if option_is(opt.value, "keyword"):
                    return KEYWORD_REASON
            continue
        if v.startswith("--") and program == "set":
            continue
        if program == "set":  # the first positional parameter (or fish: set NAME value)
            if runtime(w.raw):
                return OPTION_REASON.format(raw=w.raw)
            return GIT_ENV_REASON.format(names=w.value) if git_name(w.value) else None
        if program == "emulate":
            continue
        if runtime(w.raw):
            if program == "shopt" and "o" not in flags:
                continue
            return OPTION_REASON.format(raw=w.raw)
        if option_is(v, "allexport"):
            return ALLEXPORT_REASON
        if option_is(v, "keyword"):
            return KEYWORD_REASON
    return None


def check_definitions(program, rest, depth):
    """alias NAME=..., hash -p PATH NAME / hash NAME=PATH (and zsh hash -d) make a name run something
    else; trap ACTION SIG runs ACTION as a command (todo 496 round 3, fail closed)."""
    values = [w.value for w in rest]
    if program == "alias" and any("=" in v for v in values if not v.startswith("-")):
        return DEFINE_REASON.format(program="alias")
    if program == "hash" and any("=" in v or (v.startswith("-") and set(v[1:]) & {"p", "d"}) for v in values):
        return DEFINE_REASON.format(program="hash")
    if program == "trap":
        operands = list(rest)
        while operands and operands[0].value.startswith("-") and operands[0].value != "-":
            stop = operands[0].value == "--"
            operands = operands[1:]
            if stop:
                break
        if len(operands) >= 2 and operands[0].value not in ("", "-"):
            for sig in operands[1:]:  # todo 584: DEBUG / ERR / ZERR / RETURN (also SIGDEBUG, debug) run anywhere
                name = sig.value.upper()
                if runtime(sig.raw) or (name[3:] if name.startswith("SIG") else name) in EVERY_COMMAND_TRAPS:
                    return TRAP_REASON.format(signal=sig.value)
            return decide_command(operands[0].value, depth + 1)  # the action runs as a command
    return None


def check_words(words, piped, stdin, depth, wrapped=False):
    i = 0
    while i < len(words):
        bare = keyword(words[i])
        if is_assignment(words[i]) or bare in KEYWORDS:
            i += 1
        elif bare in ("function", "repeat"):  # function NAME / zsh repeat COUNT
            i += 2
        elif bare in DATA_KEYWORDS or bare == "foreach":
            if bare == "case":
                return None
            # Todo 496 I: zsh takes several loop variables (for a GIT_DIR in x y; foreach a b (x y)).
            for w in words[i + 1:]:
                if keyword(w) in ("in", "do"):
                    break
                if runtime(w.raw) or git_name(w.value):
                    return GIT_ENV_REASON.format(names=w.raw)
            return None
        else:
            break
    program = os.path.basename(words[i].value) if i < len(words) else ""
    names = [var_name(w.raw) for w in words[:i] if git_env(w)]
    if names:
        return GIT_ENV_REASON.format(names=", ".join(names))
    if i >= len(words):
        return None
    word, rest = words[i], words[i + 1:]
    if word.value in ("[", "[["):
        return None
    if NOT_LITERAL & set(word.raw) or word.raw.startswith("="):  # zsh: =git is a PATH lookup
        return f"program name must be literal (got {word.raw!r})"
    if git_name(program):  # (( GIT_X = 1 )) reads as a command named GIT_X
        return GIT_ENV_REASON.format(names=program)
    reason = (check_setters(program, rest, depth)
              or (check_shell_options(program, rest, depth)
                  if program in ("set", "setopt", "unsetopt", "shopt", "emulate") else None)
              or check_definitions(program, rest, depth))
    if reason:
        return reason
    if program in WRAPPERS:
        return check_wrapper(program, rest, piped, stdin, depth)
    if program == "gh":
        return "gh is reserved for the main session (Land)"
    if program in SHELLS:
        return check_shell(program, rest, piped, stdin, depth)
    if program in SOURCES:
        return shell_reads_stdin(rest[0] if rest else None, False, piped, stdin)
    if program == "eval":
        return decide_command(" ".join(w.value for w in rest), depth + 1)
    if program == "find":
        return check_find(rest, depth)
    if program in REMOVERS and any(os.path.basename(w.value.rstrip("/")) == ".git" for w in rest):
        return DOT_GIT_REASON.format(program=program)
    if program == "git":
        return check_git(rest, wrapped)
    if program.startswith("git-"):
        # Todo 477: a git-add binary stages exactly like `git add`; it takes no -C, so todo 618 denies it.
        return check_git_subcommand(program[4:], rest) or check_staging(program[4:], None, None, False, [])
    return None


def long_spelling(name, spelling):
    """A long option as the wrapper reads it: getopt_long takes any unambiguous prefix (sudo --chd=DIR is
    --chdir), so a prefix of one of its value options takes a value (todo 496 J)."""
    longs = [o for o in WRAPPERS[name][0] if o.startswith("--")]
    if spelling in longs or len(spelling) < 3:
        return spelling
    matches = [o for o in longs if o.startswith(spelling)]
    return (matches or [spelling])[0]


def option_span(name, args, j):
    """How many words the wrapper option at args[j] spans. Short options may be bundled (-iC DIR, -CDIR); a
    long option may carry =VALUE or be abbreviated."""
    value_options = WRAPPERS[name][0]
    option = args[j].value
    if option.startswith("--"):
        spelling, eq, _ = option.partition("=")
        return 2 if not eq and long_spelling(name, spelling) in value_options else 1
    letters = {o[1] for o in value_options if len(o) == 2}
    for n, c in enumerate(option[1:], start=1):
        if c in letters:
            return 1 if n < len(option) - 1 else 2  # the value is glued on (-C/tmp, -n5) or the next word
    return 1


def env_split_string(args, j):
    """(script, the words after it) when env's option word args[j] is -S / --split-string (also bundled
    after flags, -iS, -0S, and glued, -S'...'), else None. A value option before the S (-uS) takes it."""
    option = args[j].value
    if option.startswith("--"):
        spelling, eq, glued = option.partition("=")
        if len(spelling) < 3 or not "--split-string".startswith(spelling):
            return None
        if eq:
            return glued, args[j + 1:]
        return (args[j + 1].value if j + 1 < len(args) else ""), args[j + 2:]
    letters = {o[1] for o in WRAPPERS["env"][0] if len(o) == 2}
    for n, c in enumerate(option[1:], start=1):
        if c in letters:
            return None
        if c == "S":
            if n < len(option) - 1:
                return option[n + 1:], args[j + 1:]
            return (args[j + 1].value if j + 1 < len(args) else ""), args[j + 2:]
    return None


def check_wrapper(name, args, piped, stdin, depth):
    """Judge the command a wrapper runs, past its options (a chdir option such as env -C or sudo -D only takes
    a value: todo 618 never follows the directory)."""
    value_options, operands = WRAPPERS[name]
    j = 1 if name == "rtk" and args[:1] and args[0].value == "proxy" else 0
    while j < len(args) and args[j].value.startswith("-"):
        option = args[j].value
        if option == "--":
            j += 1
            break
        if name == "command" and not option.startswith("--") and set(option) & {"v", "V"}:
            return None  # command -v only looks the name up
        split = env_split_string(args, j) if name == "env" else None
        if split is not None:
            # Todo 496 A/B: the string is split into words that env parses again as its own options, so
            # -i, -0, -u and -P inside it apply: re-enter this parser, not check_words.
            script, after = split
            try:
                parts = [Word(p, p) for p in shlex.split(script)]
            except ValueError:
                return PARSE_REASON
            return check_wrapper("env", parts + after, piped, stdin, depth)
        j += option_span(name, args, j)
    return check_words(args[j + operands:], piped, stdin, depth, wrapped=name)


def check_shell(program, args, piped, stdin, depth):
    j, has_script, reads_stdin = 0, False, False
    while j < len(args):
        arg = args[j].value
        if arg in ("--", "-"):
            reads_stdin = reads_stdin or arg == "-"
            j += 1
            break
        if arg == "--command":  # fish
            has_script = True
            j += 1
        elif arg.startswith("--"):
            if option_is(arg[2:], "allexport"):  # zsh --allexport / --all-export (todo 496 F)
                return ALLEXPORT_REASON
            if option_is(arg[2:], "keyword"):  # zsh --keyword (todo 584 finding 3)
                return KEYWORD_REASON
            j += 2 if arg in ("--rcfile", "--init-file") else 1
        elif arg[:1] in ("-", "+") and len(arg) > 1:
            if runtime(args[j].raw):
                return OPTION_REASON.format(raw=args[j].raw)
            if arg[0] == "-" and "a" in arg:  # bash -a / zsh -a: allexport (todo 496 F)
                return ALLEXPORT_REASON
            if arg[0] == "-" and "k" in arg:  # bash -k: keyword (todo 584 finding 3)
                return KEYWORD_REASON
            has_script = has_script or (arg[0] == "-" and "c" in arg)
            reads_stdin = reads_stdin or (arg[0] == "-" and "s" in arg)
            if set(arg) & {"o", "O"}:
                # -o NAME / -O NAME (bash's shopt): allexport and keyword are refused (todo 496 F).
                opt = args[j + 1] if j + 1 < len(args) else Word("", "")
                if runtime(opt.raw):
                    return OPTION_REASON.format(raw=opt.raw)
                if option_is(opt.value, "allexport"):
                    return ALLEXPORT_REASON
                if option_is(opt.value, "keyword"):
                    return KEYWORD_REASON
                j += 2
            else:
                j += 1
        else:
            break
    operand = args[j] if j < len(args) else None
    if has_script:
        if not operand:
            return "sh -c without a script"
        return decide_command(operand.value, depth + 1)
    return shell_reads_stdin(operand, reads_stdin, piped, stdin)


def shell_reads_stdin(operand, reads_stdin, piped, stdin):
    """Deny a shell or `source` fed by stdin, a pipe or `<(...)`; a plain script file is out of scope."""
    if (reads_stdin or piped or stdin or operand is None or "(" in operand.raw
            or operand.value in ("-", "/dev/stdin", "/dev/fd/0")):
        return STDIN_REASON
    return None


def check_find(args, depth):
    k = 0
    while k < len(args):
        if args[k].value in ("-exec", "-execdir", "-ok", "-okdir"):
            end = k + 1
            while end < len(args) and args[end].value not in (";", "+"):
                end += 1
            reason = check_words(args[k + 1:end], False, False, depth, wrapped=True)
            if reason:
                return reason
            k = end
        k += 1
    return None


def check_git(args, wrapped):
    """`wrapped` is the wrapper that runs this git (its name, True for find -exec), or False."""
    # Todo 477: -C moves where git finds the repository (and so the index it stages into); --work-tree only
    # names the tree. Both are checked: `git -C MAIN --work-tree=S add` still stages into MAIN's index.
    # Todo 618: each must be a literal absolute path; anything else is collected in `bad` (fail closed).
    j, where, tree, git_dir, bad = 0, None, None, False, []
    while j < len(args):
        arg = args[j].value
        if arg in GIT_GLOBAL_WITH_VALUE:
            value = args[j + 1] if j + 1 < len(args) else Word("", "")
            if arg == "--git-dir":
                git_dir = True
            elif arg == "-C":
                where = _absolute(value, bad)
            else:
                tree = _absolute(value, bad)
            j += 2
        elif arg in GIT_GLOBAL_FLAGS or arg.startswith(("--git-dir=", "--work-tree=")):
            git_dir = git_dir or arg.startswith("--git-dir=")
            if arg.startswith("--work-tree="):
                raw = args[j].raw.partition("=")[2]
                tree = _absolute(Word(arg.partition("=")[2], raw), bad)
            j += 1
        elif arg == "--version":
            return None
        elif arg.startswith("-"):
            return (f"unsupported git global option {arg} (allowed: -C, --git-dir, --work-tree, "
                    f"--no-pager, -P, --no-optional-locks)")
        else:
            break
    if j >= len(args):
        return "bare git after a wrapper or xargs; run git <subcommand> directly" if wrapped else None
    sub = args[j].value
    reason = check_git_subcommand(sub, args[j + 1:])
    if reason:
        return reason
    if wrapped == "xargs" and sub in FORCE_SUBCOMMANDS and sub in CONTEXT["allowed"]:
        return XARGS_REASON.format(sub=sub)
    return check_staging(sub, where, tree, git_dir, bad)


def check_staging(sub, where, tree, git_dir, bad):
    """Todo 618 (owner decisions 2026-10-11, 2026-10-12): add/mv/rm stage only through a literal absolute -C
    inside a `.claude/worktrees/<name>/` worktree; a --work-tree, when given, must pass the same test. The
    shell's directory is never consulted, so a missing -C is denied -- --work-tree alone is not enough,
    because git still finds the repository (and the index it stages into) from the directory it runs in
    (todo 477). Todo 468 m7: a main checkout is refused by name, the pilot main root included."""
    if sub not in FORCE_SUBCOMMANDS or sub not in CONTEXT["allowed"]:
        return None
    if git_dir:
        return f"git --git-dir with {sub} is not allowed; use git -C <absolute WT> {sub}"
    if bad:
        return NOT_ABSOLUTE_REASON.format(sub=sub, raw=", ".join(bad))
    paths = [p for p in (where, tree) if p is not None]
    for path in paths:
        main = main_checkout(path)
        if main:
            return MAIN_REASON.format(sub=sub, path=main)
    if where is None:
        return NO_C_REASON.format(sub=sub)
    for path in paths:
        if not in_worktrees(path):
            return OUTSIDE_REASON.format(sub=sub, path=path)
    exposed = sub == "add" and unignored_includes(tree or where)
    if exposed:
        return (f"{', '.join(exposed)} is no longer ignored in this worktree, so git add would stage it; "
                "restore its .gitignore rule first (todo 468)")
    return None


def _absolute(word, bad):
    """The path a -C / --work-tree operand names when it is a literal absolute path (an unquoted `~` or `~/...`
    is the home directory, todo 496), else None with its source text appended to `bad` (todo 618)."""
    if not (NOT_LITERAL & set(word.raw)):
        if word.raw == "~" or word.raw.startswith("~/"):
            return os.path.expanduser(word.value)
        if os.path.isabs(word.value):
            return word.value
    bad.append(word.raw or "''")
    return None


def in_worktrees(path):
    """True when `path`, with symlinks and `..` resolved, is a `.claude/worktrees/<name>` directory or inside
    one (the same layout worker_edit_guard.worktree_of accepts). Todo 640 #7: when the hook event names the
    agent's cwd, the directory must be under THIS repository's `.claude/worktrees/` (the main root of the
    cwd's repository), not another project's."""
    real = os.path.realpath(path)
    parts = real.split(os.sep)
    if not any(parts[i:i + 2] == [".claude", "worktrees"] and parts[i + 2] for i in range(len(parts) - 2)):
        return False
    root = repo_main_root(CONTEXT.get("cwd"))
    if root is None:
        return True
    rel = os.path.relpath(real, os.path.join(root, ".claude", "worktrees"))
    return rel != "." and not rel.startswith("..")


def repo_main_root(cwd):
    """The main root of the repository holding `cwd` (the parent of its common .git directory, so a linked
    worktree's cwd -- the pilot main root, a harness-isolated worker -- anchors to the same root), or None when
    there is no cwd or it is not in a repository (todo 640 #7: then nothing is anchored, as before)."""
    if not isinstance(cwd, str) or not cwd or not os.path.isdir(cwd):
        return None
    proc = subprocess.run(["git", "-C", cwd, "rev-parse", "--path-format=absolute", "--git-common-dir"],
                          capture_output=True, text=True)
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    return os.path.dirname(os.path.realpath(proc.stdout.strip()))


def unignored_includes(path):
    """The .worktreeinclude files (backend/.env, web/.env: copied into every worktree) that exist in
    the checkout holding `path` but that no ignore rule covers any more -- a worker that deleted the
    rule from .gitignore would stage one with a plain `git add -A` (todo 468). Literal paths only; a
    git error means "cannot tell" and is left to Land's own backstop (state.ensure_worktree)."""
    top = os.path.realpath(path)
    while not os.path.exists(os.path.join(top, ".git")):
        if os.path.dirname(top) == top:
            return []
        top = os.path.dirname(top)
    try:
        with open(os.path.join(top, ".worktreeinclude")) as f:
            rels = [line.strip() for line in f if line.strip() and not line.lstrip().startswith("#")]
    except OSError:
        return []
    out = []
    for rel in rels:
        if set(rel) & set("*?[") or not os.path.isfile(os.path.join(top, rel)):
            continue
        proc = subprocess.run(["git", "-C", top, "check-ignore", "-q", "--no-index", rel], capture_output=True)
        if proc.returncode != 1:  # 0 = ignored, 128 = error
            continue
        # Todo 477: a TRACKED listed file is ordinary content (the repo already has it), not a copied-in
        # secret, so it must not block every `git add` in the tree.
        tracked = subprocess.run(["git", "-C", top, "ls-files", "--error-unmatch", "--", rel], capture_output=True)
        if tracked.returncode != 0:
            out.append(rel)
    return out


def main_checkout(path):
    """The top of the checkout holding `path` when it is a MAIN checkout, else None. A main checkout's
    .git is a directory; a linked worktree's is a file. In the pilot layout the sweep's own main root is a
    linked worktree (todo 477), so a checkout holding the sweep's run file (todos/.sweep-run-*.json, which
    only REPO has) counts as main too. A path that does not exist is left to git."""
    here = os.path.realpath(path)
    while True:
        dot_git = os.path.join(here, ".git")
        if os.path.isdir(dot_git):
            return here
        if os.path.exists(dot_git):
            return here if glob.glob(os.path.join(glob.escape(here), "todos", ".sweep-run-*.json")) else None
        parent = os.path.dirname(here)
        if parent == here:
            return None
        here = parent


def denied_option(arg, names):
    # Any non-empty prefix counts, one letter included (`git cat-file --t` is --textconv): the round-1 repair of
    # PR #1023, owner-approved 2026-10-11, which widened the "2+ letters" in the todo 496 owner decision (todo 584).
    name = arg[2:].partition("=")[0] if arg.startswith("--") else ""
    return any(n == name or (name and n.startswith(name) and name not in GIT_EXACT_OPTIONS)
               for n in names)


def force_reason(sub, args):
    """The reason to deny add/mv/rm whose options include -f / --force (PR #861 B-3): `.worktreeinclude`
    copies backend/.env and web/.env into every worktree, and `add -f` would stage one for
    Land to commit into a public repo. Any long option that is a prefix of --force counts (git
    takes unambiguous prefixes), and so does any short-option bundle holding an f (-fA, -nf).
    A word built at runtime ($(printf -- -f), "$F") could be either, so it is denied too (todo 640 #4).
    Operands after `--` are paths, so a file named -f is fine."""
    for word in args:
        arg = word.value
        if arg == "--":
            return None
        if runtime(word.raw):
            return RUNTIME_FORCE_REASON.format(sub=sub, raw=word.raw)
        if arg.startswith("--"):
            name = arg[2:].partition("=")[0]
            if name and "force".startswith(name):
                return FORCE_REASON
        elif arg.startswith("-") and len(arg) > 1 and "f" in arg[1:]:
            return FORCE_REASON
    return None


def check_git_subcommand(sub, args):
    allowed = CONTEXT["allowed"]
    if sub not in allowed:
        return (f"git {sub} is reserved for the main session "
                f"(allowed for this agent: {', '.join(sorted(allowed))})")
    if sub in FORCE_SUBCOMMANDS:
        reason = force_reason(sub, args)
        if reason:
            return reason
    values = [w.value for w in args]
    # Todo 477: reviewers may list branches and worktrees, never create, move or delete one.
    if sub == "branch" and any(v not in BRANCH_LIST_FLAGS for v in values):
        return f"git branch may only list here (allowed: {', '.join(sorted(BRANCH_LIST_FLAGS))})"
    if sub == "worktree" and values[:1] != ["list"]:
        return "git worktree may only list here (git worktree list)"
    if sub == "grep" and grep_opens_pager(values):
        return "git grep -O runs a program on the matching files; drop the option"
    for arg in values:
        if sub == "fetch" and ":" in arg:
            return f"git fetch {arg}: a ':' refspec or URL can move refs; use git fetch [origin] [<branch>]"
        if denied_option(arg, GIT_DENIED_OPTIONS.get(sub, ())):
            return f"git {sub} {arg} can run a program, write a file or take refspecs from stdin; drop the option"
    return None


def grep_opens_pager(values):
    """True when git grep's options hold -O (--open-files-in-pager takes the long-option route), alone or in
    a short bundle such as -lO<cmd>. A value (the pattern after -e, a count after -A) is skipped (todo 478)."""
    k = 0
    while k < len(values):
        arg = values[k]
        k += 1
        if arg == "--":
            return False
        if arg in GREP_VALUE_LONG:
            k += 1
        elif arg.startswith("-") and not arg.startswith("--") and len(arg) > 1:
            for n, c in enumerate(arg[1:], start=1):
                if c == "O":
                    return True
                if c in GREP_VALUE_SHORT:
                    k += 1 if n == len(arg) - 1 else 0  # a value glued on (-efoo) or the next word (-e foo)
                    break
    return False


def decide_command(command, depth=0):
    """The reason to deny `command`, or None. Nested commands ($(...), `sh -c`, eval, trap actions) are
    judged the same way, one level deeper."""
    if depth > MAX_DEPTH:
        return "command nests too deeply; simplify it"
    try:
        lexer = Lexer(command)
        lexer.run()
        segs = list(segments(lexer.tokens))
    except (ValueError, RecursionError):
        return PARSE_REASON
    if lexer.tainted or any(kind == "word" and assigns_git(val.raw) for kind, val in lexer.tokens):
        return PARAM_REASON
    # Each segment judges its own substitutions (todo 496). Should any substitution not belong to a word
    # the segments carry, judge them all up front, as before.
    if sum(len(seg.nested) for seg in segs) != len(lexer.nested):
        for inner in lexer.nested:
            reason = decide_command(inner, depth + 1)
            if reason:
                return reason
    return check_segments(segs, depth)


def decide(event):
    agent = event.get("agent_type")
    if not isinstance(agent, str) or agent not in GUARDED_AGENTS:
        return None
    tool_input = event.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str):
        return "unexpected hook input; tool_input.command is not a string"
    CONTEXT.update(allowed=ALLOWED_BY_AGENT[agent], cwd=event.get("cwd"))
    try:
        return decide_command(command)
    except Exception:  # a guard bug must not wave a guarded agent through
        return "the guard failed on this command; simplify it"


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
