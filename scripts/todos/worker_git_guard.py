#!/usr/bin/env python3
"""PreToolUse decision for Bash calls from todo-worker / todo-verifier agents.

Workers write and stage; only the main session commits, pushes and opens PRs
(spec §4.1). Agent frontmatter cannot say that -- `disallowedTools:
Bash(git push *)` removes Bash entirely -- so this hook does: for those two
agent types it allows a short list of git subcommands and denies every other
git subcommand and all of gh. Every other caller passes through untouched.

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
import sys

GUARDED_AGENTS = {"todo-worker", "todo-verifier"}
GIT_ALLOWED = {"add", "mv", "rm", "diff", "status", "log", "show", "fetch", "write-tree", "rev-parse"}
GIT_GLOBAL_WITH_VALUE = {"-C", "--git-dir", "--work-tree"}
GIT_GLOBAL_FLAGS = {"--no-pager", "-P", "--no-optional-locks"}
# Long options that make an allowed subcommand run a program or write a file.
# git accepts unambiguous prefixes (--outp=x), so a 3+ letter prefix counts too.
OUTPUT_OPTIONS = ("output", "ext-diff", "textconv")
GIT_DENIED_OPTIONS = {"fetch": ("upload-pack",), "diff": OUTPUT_OPTIONS, "log": OUTPUT_OPTIONS,
                      "show": OUTPUT_OPTIONS}
GIT_EXACT_OPTIONS = {"text"}  # a real option, so not a prefix of --textconv
SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "fish"}
# Reserved words that only prefix the real command. `for`, `select` and `case`
# start a word list or a pattern, which is data.
KEYWORDS = {"then", "do", "else", "elif", "if", "while", "until", "in", "esac", "fi", "done",
            "{", "}", "!", "coproc", "builtin"}
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
            if c in " \t\r":
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
            elif c in " \t\r\n;&|()<>":
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
        if kind == "word":
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
        lead = next((w.value for w in seg.words if w.value not in KEYWORDS - {"esac"}), None)
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


def check_words(words, piped, stdin, depth, wrapped=False):
    i = 0
    while i < len(words):
        value = words[i].value
        if is_assignment(words[i]) or value in KEYWORDS:
            i += 1
        elif value == "function":
            i += 2
        elif value in DATA_KEYWORDS:
            return None
        else:
            break
    if i >= len(words):
        return None
    word, rest = words[i], words[i + 1:]
    if word.value in ("[", "[["):
        return None
    if NOT_LITERAL & set(word.raw):
        return f"program name must be literal (got {word.raw!r})"
    program = os.path.basename(word.value)
    if program in WRAPPERS:
        return check_wrapper(program, rest, piped, stdin, depth)
    if program == "gh":
        return "gh is reserved for the main session (Land)"
    if program in SHELLS:
        return check_shell(rest, piped, stdin, depth)
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
    if (reads_stdin or piped or stdin or operand is None or "(" in operand.raw
            or operand.value in ("/dev/stdin", "/dev/fd/0")):
        return STDIN_REASON
    return None  # a shell running a script file: out of scope


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
    j = 0
    while j < len(args):
        arg = args[j].value
        if arg in GIT_GLOBAL_WITH_VALUE:
            j += 2
        elif arg in GIT_GLOBAL_FLAGS or arg.startswith(("--git-dir=", "--work-tree=")):
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
    return check_git_subcommand(args[j].value, args[j + 1:])


def denied_option(arg, names):
    name = arg[2:].partition("=")[0] if arg.startswith("--") else ""
    return any(n == name or (len(name) >= 3 and n.startswith(name) and name not in GIT_EXACT_OPTIONS)
               for n in names)


def check_git_subcommand(sub, args):
    if sub not in GIT_ALLOWED:
        return (f"git {sub} is reserved for the main session; workers stage and stop "
                f"(allowed: {', '.join(sorted(GIT_ALLOWED))})")
    for arg in (w.value for w in args):
        if sub == "fetch" and ":" in arg:
            return f"git fetch {arg}: a ':' refspec or URL can move refs; use git fetch [origin] [<branch>]"
        if denied_option(arg, GIT_DENIED_OPTIONS.get(sub, ())):
            return f"git {sub} {arg} can run a program or write a file; drop the option"
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
