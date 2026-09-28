#!/usr/bin/env python3
"""PreToolUse decision for Bash calls from todo-worker / todo-verifier / todo-reviewer agents.

Workers write and stage; only the main session commits, pushes and opens PRs
(spec §4.1). Agent frontmatter cannot say that -- `disallowedTools:
Bash(git push *)` removes Bash entirely -- so this hook does: for those agent
types it allows a short list of git subcommands (read-only ones for the
reviewer) and denies every other git subcommand and all of gh. add/mv/rm are
also denied when they would land in a main checkout rather than a worktree
(todo 468 m7). Every other caller passes through untouched.

It tokenizes the command the way a shell does -- quotes, escapes, `$(...)`,
backticks, `<(...)`, redirections, heredocs, compound commands and reserved
words -- and finds the program word of every simple command. It looks through
wrappers (rtk, env, sudo, timeout, nice, xargs, find -exec, ...), `sh -c`,
`eval` and `env -S` scripts, and `git-<sub>` binaries. When it cannot tell what
a guarded agent's command runs -- a program name built at runtime, a shell
reading stdin, an unsupported git global option, unparseable quoting -- it
denies.

This is a mistake guard, not a security boundary: a python/node/perl one-liner
or a script file that runs git inside is not visible here.

Tests: .claude/hooks/test-guard-todo-worker-git.sh
"""

import json
import os
import shlex
import subprocess
import sys

GIT_ALLOWED = {"add", "mv", "rm", "diff", "status", "log", "show", "fetch", "write-tree", "rev-parse"}
# Review-stage reviewers read the diff and report; they never stage (todo 468 m8).
GIT_READONLY = {"diff", "status", "log", "show", "rev-parse", "ls-files", "grep", "blame", "merge-base"}
ALLOWED_BY_AGENT = {"todo-worker": GIT_ALLOWED, "todo-verifier": GIT_ALLOWED, "todo-reviewer": GIT_READONLY}
GUARDED_AGENTS = set(ALLOWED_BY_AGENT)
MAIN_REASON = ("git {sub} into the main checkout ({path}) is not allowed; stage in your worktree (WT), "
               "not MAIN_ROOT")
# The calling agent's allowed set and working directory, set by decide() for one hook call.
CONTEXT = {"allowed": GIT_ALLOWED, "cwd": None}
GIT_GLOBAL_WITH_VALUE = {"-C", "--git-dir", "--work-tree"}
GIT_GLOBAL_FLAGS = {"--no-pager", "-P", "--no-optional-locks"}
# Long options that make an allowed subcommand run a program, write a file or
# read refspecs from stdin (fetch --stdin). git accepts unambiguous prefixes
# (--outp=x), so a 3+ letter prefix counts too.
OUTPUT_OPTIONS = ("output", "ext-diff", "textconv")
GIT_DENIED_OPTIONS = {"fetch": ("upload-pack", "stdin"), "diff": OUTPUT_OPTIONS, "log": OUTPUT_OPTIONS,
                      "show": OUTPUT_OPTIONS}
GIT_EXACT_OPTIONS = {"text"}  # a real option, so not a prefix of --textconv
FORCE_SUBCOMMANDS = {"add", "mv", "rm"}
FORCE_REASON = "force-staging ignored files is not allowed (git add/mv/rm -f / --force)"
SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "fish"}
SOURCES = {"source", "."}  # run a script in the current shell: same stdin risk as a shell
# Unquoted reserved words (and zsh precommand modifiers) that only prefix the
# real command. `for`, `select` and `case` start a word list or a pattern, which
# is data; `function` and zsh's `repeat` are followed by a name / count.
KEYWORDS = {"then", "do", "else", "elif", "if", "while", "until", "in", "esac", "fi", "done",
            "{", "}", "!", "coproc", "builtin", "always", "noglob", "nocorrect"}
DATA_KEYWORDS = {"for", "select", "case"}
# wrapper -> (options that take a separate value, operands before the command)
WRAPPERS = {
    "rtk": ((), 0), "command": ((), 0), "nohup": ((), 0), "exec": (("-a",), 0),
    "time": (("-o", "-f"), 0), "caffeinate": (("-t", "-w"), 0),
    "env": (("-u", "--unset", "-C", "--chdir"), 0),
    "sudo": (("-u", "-g", "-C", "-D", "-h", "-p", "-r", "-t", "-U", "-T"), 0),
    "doas": (("-u", "-C"), 0),
    "timeout": (("-s", "--signal", "-k", "--kill-after"), 1),
    "nice": (("-n", "--adjustment"), 0),
    "stdbuf": (("-i", "-o", "-e", "--input", "--output", "--error"), 0),
    "ionice": (("-c", "-n", "-p", "--class", "--classdata"), 0),
    "chrt": ((), 1), "taskset": ((), 1),
    "xargs": (("-a", "-d", "-E", "-I", "-L", "-n", "-P", "-s", "--arg-file", "--delimiter",
               "--max-args", "--max-lines", "--max-procs", "--max-chars"), 0),
}
NOT_LITERAL = set("$`*?[{<>")
OPERATORS = (";;&", ";;", ";&", "&&", "||", "|&", ";", "&", "|", "(", ")")
REDIRECTIONS = ("&>>", "&>", "<<<", "<<-", "<<", "<>", "<&", ">>", ">&", ">|", "<", ">")
CASE_ENDS = {";;", ";&", ";;&"}
MAX_DEPTH = 10
PARSE_REASON = "command could not be parsed; simplify the quoting"
STDIN_REASON = "run git directly, not through a shell reading stdin"


class Word:
    """One shell word: `value` has the quoting removed, `raw` is the source text."""

    def __init__(self, value, raw):
        self.value, self.raw = value, raw


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
        s, start, value = self.s, self.i, []
        while self.i < len(s):
            c = s[self.i]
            if c in "<>" and s.startswith("(", self.i + 1):
                self.read_subst(value)
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
        return Word("".join(value), s[start:self.i])

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
        self.heredocs.append((word.value, word.raw == word.value, strip_tabs))
        self.tokens.append(("word", word))

    def read_heredoc_bodies(self):
        s = self.s
        for delimiter, expand, strip_tabs in self.heredocs:
            while True:
                if self.i >= len(s):
                    raise ValueError("unterminated heredoc")
                end = s.find("\n", self.i)
                end = len(s) if end < 0 else end
                line, self.i = s[self.i:end], end + 1
                if (line.lstrip("\t") if strip_tabs else line) == delimiter:
                    break
                if expand:  # <<EOF (unquoted) still runs $(...) and backticks
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
        self.heredocs = []


class Segment:
    """A simple command: its words, whether stdin is redirected or piped, and the operator after it."""

    def __init__(self, words, stdin, piped, end):
        self.words, self.stdin, self.piped, self.end = words, stdin, piped, end


def segments(tokens):
    words, stdin, piped = [], False, False
    tokens = iter(tokens)
    for kind, val in tokens:
        if kind == "word" and val.raw == "}":  # zsh ends a group at `}` alone: { true } always { … }
            yield Segment(words + [val], stdin, piped, "}")
            words, stdin, piped = [], False, False
        elif kind == "word":
            words.append(val)
        elif kind == "redir":
            target = next(tokens, None)
            if target is None or target[0] != "word":
                raise ValueError("redirection without a target")
            stdin = stdin or val.startswith("<")
        else:
            yield Segment(words, stdin, piped, val)
            piped = val in ("|", "|&") or (piped and not words and val == "(")
            words, stdin = [], False
    yield Segment(words, stdin, piped, None)


def check_segments(segs, depth):
    cases, pattern = 0, False
    for seg in segs:
        first = next((w for w in seg.words if keyword(w) not in KEYWORDS - {"esac"}), None)
        lead = keyword(first) if first else None
        if pattern:  # a case pattern such as `*)` is data
            if lead != "esac":
                pattern = seg.end != ")"
                continue
            cases, pattern = cases - 1, False
        elif lead == "case":
            cases, pattern = cases + 1, seg.end != ")"
            continue
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


def check_words(words, piped, stdin, depth, wrapped=False):
    i = 0
    while i < len(words):
        bare = keyword(words[i])
        if is_assignment(words[i]) or bare in KEYWORDS:
            i += 1
        elif bare in ("function", "repeat"):  # function NAME / zsh repeat COUNT
            i += 2
        elif bare in DATA_KEYWORDS:
            return None
        else:
            break
    if i >= len(words):
        return None
    word, rest = words[i], words[i + 1:]
    if word.value in ("[", "[["):
        return None
    if NOT_LITERAL & set(word.raw) or word.raw.startswith("="):  # zsh: =git is a PATH lookup
        return f"program name must be literal (got {word.raw!r})"
    program = os.path.basename(word.value)
    if program in WRAPPERS:
        return check_wrapper(program, rest, piped, stdin, depth)
    if program == "gh":
        return "gh is reserved for the main session (Land)"
    if program in SHELLS:
        return check_shell(rest, piped, stdin, depth)
    if program in SOURCES:
        return shell_reads_stdin(rest[0] if rest else None, False, piped, stdin)
    if program == "eval":
        return decide_command(" ".join(w.value for w in rest), depth + 1)
    if program == "find":
        return check_find(rest, depth)
    if program == "git":
        return check_git(rest, wrapped)
    if program.startswith("git-"):
        return check_git_subcommand(program[4:], rest)
    return None


def check_wrapper(name, args, piped, stdin, depth):
    value_options, operands = WRAPPERS[name]
    j = 1 if name == "rtk" and args[:1] and args[0].value == "proxy" else 0
    while j < len(args) and args[j].value.startswith("-"):
        option = args[j].value
        if option == "--":
            j += 1
            break
        if name == "command" and not option.startswith("--") and set(option) & {"v", "V"}:
            return None  # command -v only looks the name up
        if name == "env" and option.startswith(("-S", "--split-string")):
            if option in ("-S", "--split-string"):
                script, args = (args[j + 1].value if j + 1 < len(args) else ""), args[j + 2:]
            else:
                script, args = option[2:] if option[1] == "S" else option.partition("=")[2], args[j + 1:]
            try:
                parts = [Word(p, p) for p in shlex.split(script)]
            except ValueError:
                return PARSE_REASON
            return check_words(parts + args, piped, stdin, depth, wrapped=True)
        j += 2 if option in value_options else 1
    return check_words(args[j + operands:], piped, stdin, depth, wrapped=True)


def check_shell(args, piped, stdin, depth):
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
            j += 2 if arg in ("--rcfile", "--init-file") else 1
        elif arg[:1] in ("-", "+") and len(arg) > 1:
            has_script = has_script or (arg[0] == "-" and "c" in arg)
            reads_stdin = reads_stdin or (arg[0] == "-" and "s" in arg)
            j += 2 if set(arg) & {"o", "O"} else 1
        else:
            break
    operand = args[j] if j < len(args) else None
    if has_script:
        return decide_command(operand.value, depth + 1) if operand else "sh -c without a script"
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
    j, where, git_dir = 0, CONTEXT["cwd"], False
    while j < len(args):
        arg = args[j].value
        if arg in GIT_GLOBAL_WITH_VALUE:
            value = args[j + 1].value if j + 1 < len(args) else ""
            if arg == "--git-dir":
                git_dir = True
            else:  # -C composes like cd; --work-tree names the tree directly
                where = os.path.join(where or "", value)
            j += 2
        elif arg in GIT_GLOBAL_FLAGS or arg.startswith(("--git-dir=", "--work-tree=")):
            git_dir = git_dir or arg.startswith("--git-dir=")
            if arg.startswith("--work-tree="):
                where = os.path.join(where or "", arg.partition("=")[2])
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
    if sub in FORCE_SUBCOMMANDS and sub in CONTEXT["allowed"]:
        # Todo 468 m7: a worker that confuses MAIN_ROOT with WT would stage into the owner's checkout.
        if git_dir:
            return f"git --git-dir with {sub} is not allowed; use git -C WT {sub}"
        main = where and main_checkout(where)
        if main:
            return MAIN_REASON.format(sub=sub, path=main)
        exposed = where and sub == "add" and unignored_includes(where)
        if exposed:
            return (f"{', '.join(exposed)} is no longer ignored in this worktree, so git add would stage it; "
                    "restore its .gitignore rule first (todo 468)")
    return check_git_subcommand(sub, args[j + 1:])


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
        if proc.returncode == 1:  # 0 = ignored, 128 = error
            out.append(rel)
    return out


def main_checkout(path):
    """The top of the checkout holding `path` when it is a MAIN checkout (its .git is a directory;
    a linked worktree's .git is a file), else None. A path that does not exist is left to git."""
    here = os.path.realpath(path)
    while True:
        dot_git = os.path.join(here, ".git")
        if os.path.isdir(dot_git):
            return here
        if os.path.exists(dot_git):
            return None
        parent = os.path.dirname(here)
        if parent == here:
            return None
        here = parent


def denied_option(arg, names):
    name = arg[2:].partition("=")[0] if arg.startswith("--") else ""
    return any(n == name or (len(name) >= 3 and n.startswith(name) and name not in GIT_EXACT_OPTIONS)
               for n in names)


def forces(args):
    """True when add/mv/rm options include -f / --force (PR #861 B-3): `.worktreeinclude`
    copies backend/.env and web/.env into every worktree, and `add -f` would stage one for
    Land to commit into a public repo. Any long option that is a prefix of --force counts (git
    takes unambiguous prefixes), and so does any short-option bundle holding an f (-fA, -nf).
    Operands after `--` are paths, so a file named -f is fine."""
    for arg in (w.value for w in args):
        if arg == "--":
            return False
        if arg.startswith("--"):
            name = arg[2:].partition("=")[0]
            if name and "force".startswith(name):
                return True
        elif arg.startswith("-") and len(arg) > 1 and "f" in arg[1:]:
            return True
    return False


def check_git_subcommand(sub, args):
    allowed = CONTEXT["allowed"]
    if sub not in allowed:
        return (f"git {sub} is reserved for the main session; workers stage and stop "
                f"(allowed: {', '.join(sorted(allowed))})")
    if sub in FORCE_SUBCOMMANDS and forces(args):
        return FORCE_REASON
    for arg in (w.value for w in args):
        if sub == "fetch" and ":" in arg:
            return f"git fetch {arg}: a ':' refspec or URL can move refs; use git fetch [origin] [<branch>]"
        if denied_option(arg, GIT_DENIED_OPTIONS.get(sub, ())):
            return f"git {sub} {arg} can run a program, write a file or take refspecs from stdin; drop the option"
    return None


def decide_command(command, depth=0):
    if depth > MAX_DEPTH:
        return "command nests too deeply; simplify it"
    try:
        lexer = Lexer(command)
        lexer.run()
        segs = list(segments(lexer.tokens))
    except (ValueError, RecursionError):
        return PARSE_REASON
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
    cwd = event.get("cwd")
    CONTEXT.update(allowed=ALLOWED_BY_AGENT[agent], cwd=cwd if isinstance(cwd, str) and cwd else None)
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
