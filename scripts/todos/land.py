#!/usr/bin/env python3
"""Stage D helpers: make a verified group's todos archivable, exactly.

    land.py flip-acs --run RUNFILE --id 412 --repo WORKTREE --date 2026-09-27
    land.py archive  --run RUNFILE --id 412 --repo WORKTREE --date 2026-09-27

flip-acs checks a box only where the worker's ac.json says pass AND the
verifier re-ran it and agreed AND the evidence file exists under
.sweep-evidence/. It quotes the evidence tail into the Work Log, because
.sweep-evidence/ is gitignored and the Work Log is the only record that
survives the merge; `command`/`evidence_path` are flattened to one line first
so an embedded newline cannot forge a new Work Log heading, and the tail is
quoted inside a fence long enough that the tail's own content cannot close it
early. archive is split into a read-only validate phase and a write phase
(fix round 1, F1): nothing is renamed, checked off or edited until every
check -- the destination is free, the todo has an Acceptance Criteria
section, and the same bare-unchecked-box rule the CI tripwire enforces
(`check_archived_todo_status.parse`) reports none -- has already passed.
Only the validate phase may raise `LandError`. The write phase then does the
git mv, the status flip, the Work Log entry, `fix_baseline` (a filename-only
edit, never a regeneration), and the planned review check-off. A Finding
Status line is checked off by its arrow target alone (fix round 1, F2): a
`-> todo NNN` naming a DIFFERENT todo means the finding moved elsewhere
(CLAUDE.md Review Doc Tracking rule 4) and stays open; a target naming THIS
todo, or no target at all (a legacy line), is checked off regardless of
"re-pointed" wording. The review doc is renamed COMPLETED only when nothing
left in its Finding Status is open, and a planned rename is itself validated
in phase 1 (fix round 2, G3): a `-COMPLETED` destination that already exists
or a review doc git doesn't track downgrades to "checked off, no rename",
never a phase-2 `git mv` failure. `source_review` only ever resolves inside
`docs/reviews/` (fix round 2, G4) -- a path that escapes it, by `..` or
otherwise, is just another "not a review doc" value, never read or written.

Fix round 3 widens phase 1's guarantee, and reverses one earlier "not
changing" call. The planned-rename destination check is `os.path.lexists`,
not `is_file` (H1): a dangling symlink or a directory sitting where the
`-COMPLETED` twin should go both count as "something is already there", not
"go ahead". A plan carries the review doc's normalised, repo-relative POSIX
path -- derived from the file `_review_path` already resolved, not the raw
`source` string, which can contain a `..` through a directory that doesn't
exist and make a plain `open()`/`git mv` refuse even though the resolved file
is fine (H2); an absolute `source_review` is rejected outright, even one that
happens to resolve inside `docs/reviews/`, so it never gets stamped into the
archived todo's own frontmatter. Phase 1 also refuses -- before any write --
a todo with no frontmatter, one git doesn't track, one whose `status` or
`source_review` `todofile.set_fields` couldn't rewrite in place (a multi-line
value), and a missing `todos/archive/` (H3). Every quoted evidence-tail line
that would toggle `check_archived_todo_status`'s naive fence detector is
prefixed with a visible marker before quoting (H4): a single stray fence line
in a tail was shown to hide a real unchecked box for the rest of the file --
failing OPEN, not just closed -- reversing round 2's call that this was
acceptable. A duplicate Finding Status line for a finding no longer just
prefers "the first open one": every open line checkable by this todo (no
target, or a target matching todo_id) ships together, and when none is
checkable, the note prefers any line naming this todo over an arbitrary first
match (H5).

Todo 512: a quoted tail line keeps no trailing whitespace, and a blank one is
emitted empty, so the `trailing-whitespace` hook never rewrites the todo
during Land's commit.

Todo 524: the Verified entry is committed to a public repo and outlives the
worktree, so the quoted command and every quoted tail line are made
repo-relative first (`_relativize`): a leading `<repo>/`, any
`.../.claude/worktrees/<name>/` and `<main_root>/` are dropped (bare, they read
`.`), and the home directory reads `~`. The command's mention of this todo's
own pre-archive path is rewritten to its archived path, so the check can be
re-run after the merge. The `.sweep-evidence/` pointer stays but is labelled
`(not committed)`: that file is gitignored and dies with the worktree.

Todo 525 widens that: a root also starts after `file://` or a one-letter flag
(`-I<wt>/inc`), a path component never holds a separator (so a `:`-joined
list keeps its earlier entries), a root alone or with a trailing slash reads
`.` or `~` rather than nothing, any `/Users/<name>` or `/home/<name>` reads
`~`, and this machine's home is replaced wherever it is left. A leading
`cd . && ` is dropped from the command.

Todo 492 adds two things. An owner-only criterion the owner confirmed
(`state.py confirm`: a dated record on the run entry, also appended to
`owner_decision`) is ticked by flip-acs when the verifier accepted it as
`owner-confirmed`, and the owner's words are quoted into the Work Log under
their own heading; it needs no worker pass and no evidence file. And archive
refuses, in phase 1, a todo whose Work Log still names a home path
(`check_archived_todo_status.work_log_home_paths`, the CI rule's own test).

Fix round 4 closes the last phase-2 raise sites found by the round-3
re-review. The todo's own destination check is `os.path.lexists`, not
`is_file`: a directory or a dangling symlink at `todos/archive/<name>.md`
refuses in phase 1, where before `git mv` would move the todo INTO the
directory (then `set_fields` raised IsADirectoryError) or fail on the
symlink. The `-COMPLETED` twin also counts as present when git still tracks
it but it was deleted from disk, so the rename is skipped instead of
clobbering the twin's index entry. The CLI maps `yaml.YAMLError` (malformed
frontmatter) to exit 2 with a `land: ` message instead of a traceback.

Todo 552: the quoted command keeps a leading `cd <wt>/<sub> && `, which reads
`cd <sub> && `, so every later path that was under the repo, a worktree or
main_root is rewritten relative to <sub> (`../scripts/...`), and a chained
`cd` is resolved against the previous one (`_relativize_command`). A path the
command already wrote relative is left alone. Archived lines are not rewritten.

Todo 578 makes that directory tracking follow the shell more closely: a newline, `|` and a single `&`
separate commands too, quotes honour backslash escapes and an unclosed one is literal, a subshell or a
pipeline or background part keeps its `cd` to itself, `pushd`/`popd` count, a `cd` after `||` leaves either
directory possible, a rooted `cd` after an unknown one is known again, `git -C <dir>` re-roots the paths
after it, and a trailing slash and a sentence's full stop survive.
"""

import argparse
import datetime
import json
import os
import posixpath
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import slot_env  # noqa: E402
import state  # noqa: E402
import todofile  # noqa: E402
# todofile's own import already inserted scripts/ (its parent) onto sys.path as a
# side effect, which is what lets this resolve with no sys.path change of its own.
import check_archived_todo_status  # noqa: E402

EVIDENCE_TAIL = 5
ARROW_TARGET_RE = re.compile(r"(?:→|->)\s*todo\s*0*(\d+)", re.I)


class LandError(Exception):
    pass


def run_git(repo, *args):
    proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if proc.returncode != 0:
        raise LandError(f"git {' '.join(args)}: {proc.stderr.strip()}")
    return proc.stdout


SECRET_MIN_LEN = 8
ENV_FILES = ("backend/.env", "web/.env")


def _env_secrets(*roots):
    """Every value of at least SECRET_MIN_LEN characters in <root>/backend/.env and
    <root>/web/.env, longest first (final review m5), plus the password inside any URL value
    (todo 468): printed alone, or inside slot_env's rewritten DATABASE_URL, it matches no
    whole .env value.

    A password that is also a common word is masked everywhere on purpose (todo 475, owner
    decision 2026-09-28): with `postgres:postgres` a tail reads `django.db.backends.***ql`.
    The mask cannot tell the password from the word, so any narrowing (word boundaries, skipping
    a value equal to the DB user or scheme) leaves the password readable exactly where it is
    printed, in a tail committed to a public repo. Over-masking costs only readability."""
    values = set()
    for root in roots:
        for rel in ENV_FILES if root else ():
            path = Path(root) / rel
            if path.is_file():
                text = path.read_text(errors="replace")
                # Both readings: the comment-stripped one and python-decouple's, which the app
                # itself sees and may print (PR #870 round 1).
                for value in [*slot_env.parse_dotenv(text).values(),
                              *slot_env.parse_dotenv(text, strip_comments=False).values()]:
                    values.update([value, *_url_password(value)])
    return sorted((v for v in values if len(v) >= SECRET_MIN_LEN), key=len, reverse=True)


def _url_password(value):
    """The password of a URL value, as written and percent-decoded; [] when there is none."""
    try:
        password = urlsplit(value).password if "://" in value else None
    except ValueError:
        return []
    return [password, unquote(password)] if password else []


# pytest's closing summary, e.g. `==== 5552 passed, 8 skipped in 812.40s ====`.
PYTEST_SUMMARY_RE = re.compile(r"^=+ .*\b\d+ (passed|failed|errors?)\b.* in [\d.]+s.* =+$")


def _tail(path, secrets=()):
    """The last EVIDENCE_TAIL lines, with every .env value masked as *** -- the tail is
    committed into the Work Log of a public repo. When the last pytest summary line falls
    before the tail (shutdown logging after a full suite, todo 658), it leads the tail."""
    lines = Path(path).read_text(errors="replace").rstrip("\n").splitlines()
    tail = lines[-EVIDENCE_TAIL:]
    head = lines[:-EVIDENCE_TAIL]
    summary = next((line for line in reversed(head) if PYTEST_SUMMARY_RE.match(line.strip())), None)
    if summary is not None and not any(PYTEST_SUMMARY_RE.match(line.strip()) for line in tail):
        tail = [summary, "…"] + tail
    return [_mask(line, secrets) for line in tail]


def _mask(text, secrets):
    """`text` with every secret (longest first, as _env_secrets orders them) replaced by ***."""
    for secret in secrets:
        text = text.replace(secret, "***")
    return text


# A blank, a quote, or a separator a command line or a listing puts next to a path. None of them is
# part of a path component, so a match cannot start inside an earlier entry of a `:` or `,` joined
# list, or swallow a closing bracket (todo 525).
_SEP = r"\s'\"`;:,=|&<>()\[\]{}"
_COMPONENT = rf"[^/{_SEP}]+"
_LAST_COMPONENT = rf"[^/{_SEP}]+?"  # lazy, so a sentence's full stop after it stays outside the match
# A root starts a path: not after a character a path name is made of, where it would be the tail of a
# longer path, unless that is a one-letter flag glued to it (`-I/x`). A `file://` prefix goes with it.
_PATH_START = r"(?:(?<![\w./~-])|(?<=(?<![^\s'\"`=])-[A-Za-z]))(?:file://)?"
# The root alone: with or without its trailing slash before the end, a blank, a quote or a separator,
# or (with no slash) before a full stop that ends a sentence. `<root>/.` is left to the `<root>/` rule.
_BARE_END = r"(?:/?(?=$|[\s'\"`;:,=|&<>)\]}])|(?=\.(?:$|\s)))"
_WORKTREE = rf"(?:/{_COMPONENT})+/\.claude/worktrees/{_LAST_COMPONENT}"
_ANY_HOME = rf"/(?:Users|home)/{_LAST_COMPONENT}"


def _root_forms(*paths):
    """Each non-empty path as written and resolved (macOS: /tmp is /private/tmp), longest first."""
    forms = set()
    for path in paths:
        if path:
            forms.update(str(p).rstrip("/") for p in (Path(path), Path(path).resolve()))
    return sorted((f for f in forms if f not in ("", ".")), key=len, reverse=True)


def _strip(text, root, bare, mark=""):
    """`text` with each path under the root regex `root` made relative to it: `<root>/x` reads `x` (or
    `~/x`), and the root alone reads `bare`, never nothing (todo 525: `cd <wt>/ && ls` read `cd  && ls`).
    With `mark`, each path it rewrites starts with it, so a later pass knows which paths were rooted."""
    # A marked bare root also gets _END (todo 578 #2): `<root>.` ending a sentence reads `\x00.\x01.`, so the
    # full stop is never read as part of the path (`..`).
    text = re.sub(_PATH_START + root + _BARE_END, lambda _: mark + bare + (_END if mark else ""), text)
    return re.sub(_PATH_START + root + "/", lambda _: mark + ("" if bare == "." else bare + "/"), text)


def _relativize(text, repo, main_root="", todo_rel="", mark=""):
    """`text` with no absolute worktree, main-checkout or home path (todo 524): it is quoted
    into a public repo's Work Log, where `/Users/<name>/.../.claude/worktrees/wf_...` names a
    directory that is gone after the merge and leaks the local user name.

    Order matters: the worktree sits UNDER the main checkout, so `repo` and any other
    `.claude/worktrees/<name>` go before `main_root` -- stripping main_root first would leave
    `.claude/worktrees/wf_.../scripts/...`. Then the home directory reads `~`, and so does any
    other `/Users/<name>` or `/home/<name>`, from another machine or CI (todo 525). Last, this
    machine's home is replaced wherever it is left, mid-path or in the sandbox's TMPDIR spelling
    (`-Users-<name>-...`), so the user name never reaches the Work Log.

    The result is for reading. A `~` inside quotes is not expanded by a shell, so a quoted home
    path (`cat '~/.zshrc'`) no longer re-runs as written; a substitution cannot fix single quotes,
    so it is left that way (todo 525, owner decision).

    With `todo_rel`, the todo's own path becomes its archived path where a path starts (after
    any `./` or `../`), never inside a longer path (`backend/todos/...`) or one read at a
    revision (`REV:todos/...`).

    With `mark` (todo 552), every path that was under the repo, a worktree or main_root starts with
    it, so `_relativize_command` can tell a repo-root path from one the command wrote relative."""
    for form in _root_forms(repo):
        text = _strip(text, re.escape(form), ".", mark)
    text = _strip(text, _WORKTREE, ".", mark)
    for form in _root_forms(main_root):
        text = _strip(text, re.escape(form), ".", mark)
    for form in _root_forms(Path.home()):
        text = _strip(text, re.escape(form), "~")
    text = _strip(text, _ANY_HOME, "~")
    for form in _root_forms(Path.home()):
        text = text.replace(form, "~").replace(re.sub(r"[^A-Za-z0-9]", "-", form), "~")
    if todo_rel:
        text = re.sub(r"(?<![\w./:-])((?:\.\.?/)*)" + re.escape(todo_rel) + r"(?![\w.-])",
                      lambda m: m.group(1) + todofile.archived_path(todo_rel), text)
    return text


_MARK = "\x00"
_END = "\x01"  # ends a marked bare root (todo 578 #2)
# A command's separators (todo 578 #4): the two-character forms first. `(` and `)` open and close a subshell (a
# `$(` substitution is one too); `|` and `&` put the part beside them in a subshell of its own.
_OPERATORS = ("&&", "||", "|&", ";", "\n", "|", "&", "(", ")")
_DIR_RE = re.compile(r"\s*(?P<cmd>cd|pushd|popd)\b")
_CD_RE = re.compile(r"\s*(?P<cmd>cd|pushd)(?:\s+(?P<q>['\"]?)(?P<target>[^'\"\s]*)(?P=q))?\s*$")
_POPD_RE = re.compile(r"\s*popd\s*$")
_MARKED_RE = re.compile(_MARK + rf"(?P<path>[^{_SEP}{_MARK}{_END}]*)")
_GIT_RE = re.compile(r"\s*(?:[A-Za-z_]\w*=\S*\s+)*git\s")
_GIT_TOKEN_RE = re.compile(r"\s*(?P<q>['\"]?)(?P<tok>[^'\"\s]+)(?P=q)")
# git's global options that take their value as the next word. Only the words between `git` and the
# subcommand are global options: `git grep -C 3` and `git diff -C` are the subcommand's own -C (PR #1038
# review), which must not re-root anything.
_GIT_GLOBAL_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--config-env"}


def _operator(command, i):
    """The separator starting at command[i], or "". A `&` or `|` inside a redirection (`2>&1`, `&>`, `>|`) is
    not one."""
    for op in _OPERATORS:
        if command.startswith(op, i):
            if op in ("&", "|") and i and command[i - 1] in "<>":
                return ""
            if op == "&" and command[i + 1:i + 2] == ">":
                return ""
            return op
    return ""


def _split_command(command):
    """`command` cut into [part, separator, part, ...] at each separator outside quotes (`_OPERATORS`).

    A backslash outside single quotes escapes the next character, so `\'` or `\"` opens nothing (todo 578 #5).
    A quote never closed before the end of the command is read as a literal character instead (`echo it's`),
    so it does not hide every separator after it."""
    literal = set()
    while True:
        pieces, start, quote, opened, i = [], 0, "", -1, 0
        while i < len(command):
            char = command[i]
            if quote == "'":
                quote = "" if char == "'" else quote
            elif char == "\\":
                i += 2
                continue
            elif quote:
                quote = "" if char == '"' else quote
            elif char in "'\"" and i not in literal:
                quote, opened = char, i
            else:
                op = _operator(command, i)
                if op:
                    pieces += [command[start:i], op]
                    start = i = i + len(op)
                    continue
            i += 1
        if not quote:
            return pieces + [command[start:]]
        literal.add(opened)


def _resolve(base, target):
    """The repo-relative directory `target` names from `base` ("" the repo root, None unknown), or None when it
    cannot be known: a target that was not under the repo (`~`, `/opt`, `-`, `$X`) or that climbs out of it."""
    target = target.replace(_END, "")
    if target.startswith(_MARK):
        new = posixpath.normpath(target[len(_MARK):].lstrip("/") or ".")
    elif target and not re.match(r"[~/$-]", target) and _MARK not in target and base is not None:
        new = posixpath.normpath(posixpath.join(base or ".", target))
    else:
        return None
    if new == ".." or new.startswith("../"):
        return None
    return "" if new == "." else new


def _rebase(path, dirs):
    """A marked, repo-relative `path` written relative to the directory the command is in (todo 552). `dirs` is
    every directory it may be in (todo 578 #3: after a `cd` that follows `||`, either); when they disagree on
    the result, or one is unknown, the path reads repo-root-relative, as for an unknown directory. A trailing
    slash is kept (`rsync -a web/` copies the contents, todo 578 #2), and `<root>//x` is `x`."""
    trail = path.endswith("/") and path.strip("/") != ""
    path = path.lstrip("/") or "."
    if None in dirs:
        return path
    out = {posixpath.relpath(posixpath.normpath(path), d) if d else path for d in dirs}
    if len(out) != 1:
        return path
    result = out.pop()
    return result + "/" if trail and not result.endswith("/") else result


def _git_c_events(part):
    """`(end, dir)` for each `-C <dir>` among git's global options in one part: the words between `git`
    and its subcommand. Stops at the first word that is not an option or an option's value."""
    git = _GIT_RE.match(part)
    if not git:
        return []
    events, pos, takes_value = [], git.end(), None
    while (word := _GIT_TOKEN_RE.match(part, pos)) is not None:
        pos, tok = word.end(), word.group("tok")
        if takes_value is not None:
            if takes_value == "-C":
                events.append((pos, tok))
            takes_value = None
        elif tok in _GIT_GLOBAL_WITH_VALUE:
            takes_value = tok
        elif not tok.startswith("-"):
            break
    return events


def _rebase_part(part, dirs):
    """Each marked path in one part, rebased against `dirs`. In a `git -C <dir>` part, a path after the `-C`
    resolves against that directory, not the shell's (todo 578 #6); repeated `-C` options compose."""
    events = _git_c_events(part)

    def sub(match):
        here = set(dirs)
        for end, target in events:
            if end <= match.start():
                here = {_resolve(d, target) for d in here}
        return _rebase(match.group("path"), here)

    return _MARKED_RE.sub(sub, part)


def _relativize_command(command, repo, main_root="", todo_rel=""):
    """`_relativize` for a quoted acceptance-criterion command, which may change directory (todo 552).

    `cd <wt>/backend && python3 <wt>/scripts/x.py` relativized whole reads `cd backend && python3
    scripts/x.py`, which no longer re-runs: the second path now resolves under backend/. So each path
    that was under the repo, a worktree or main_root is rewritten relative to the directory the
    command is in by then (`../scripts/x.py`), and a later `cd` into another rooted directory is too
    (`cd ../plant_community_mobile`), each resolved against the previous one. The leading `cd` stays
    (owner decision). A path the command already wrote relative is left alone; a `cd` to an unrelated
    place (`~`, `/opt`, `-`, `$X`, or bare) leaves the directory unknown, and later paths read
    repo-root-relative as before, until a `cd` into a rooted directory makes it known again (todo 578 #1).

    Todo 578 widens what counts as a directory change. Parts are cut at `&&`, `||`, `;`, a newline, `|` and a
    single `&` too, outside quotes and backslash escapes. A `(...)` or `$(...)` subshell keeps its `cd` to
    itself, and so does a part run in the background (`&`) or in a pipeline (`|`). `pushd <dir>` changes
    directory like `cd`, and `popd` returns to where it was. A `cd` after `||` may not have run, so the
    command may be in either directory: a later path is rebased only when both read the same. A `git -C <dir>`
    part rebases its later paths against <dir>."""
    text = _relativize(command.replace(_MARK, "").replace(_END, ""), repo, main_root, todo_rel, mark=_MARK)
    pieces = _split_command(text)
    dirs = frozenset({""})  # every directory the command may be in: repo-relative, "" the root, None unknown
    scopes, pushed = [], []  # the directories saved by each open subshell; pushd's stack
    out = []
    for index, part in enumerate(pieces):
        if index % 2:
            out.append(part)
            if part == "(":
                scopes.append((dirs, list(pushed)))
            elif part == ")" and scopes:
                dirs, pushed = scopes.pop()
            continue
        out.append(_rebase_part(part, dirs))
        if not _DIR_RE.match(part):
            continue
        before = pieces[index - 1] if index else ""
        after = pieces[index + 1] if index + 1 < len(pieces) else ""
        if before in ("|", "|&") or after in ("|", "|&", "&"):
            continue  # run in a subshell of its own: the directory change ends with the part
        cd, popd = _CD_RE.match(part), _POPD_RE.match(part)
        if popd:
            new = pushed.pop() if pushed else frozenset({None})
        elif cd and cd.group("cmd") == "pushd" and not cd.group("target"):
            new = pushed.pop() if pushed else frozenset({None})  # pushd alone swaps the top two
            pushed.append(dirs)
        elif cd:
            target = cd.group("target") or ""
            new = frozenset(_resolve(d, target) for d in dirs)
            if cd.group("cmd") == "pushd":
                pushed.append(dirs)
        else:
            new = frozenset({None})  # a cd this cannot read (quoted blanks, more arguments): the directory is unknown
        # After `||` the change runs only when what came before failed, so either directory may be current.
        dirs = dirs | new if before == "||" else new
    return "".join(out).replace(_MARK, "").replace(_END, "")


def _sanitize(value):
    """Flatten to one line so a quoted value can never forge a new heading.

    str.splitlines() (fix round 2, G5) -- not a literal \\r/\\n replace -- so
    every separator a parser might treat as a line break (\\x85, \\x0c,
    \\x1e, \\u2028, ...) is flattened too, not just the two ASCII ones."""
    return " ".join(str(value).splitlines())


_CHECKBOX_PREFIX_RE = re.compile(r"^\s*-\s\[[ xX]\]\s*")


def _normalize_ac_text(text):
    """Strip a leading checkbox marker (if any) and collapse whitespace."""
    text = _CHECKBOX_PREFIX_RE.sub("", text, count=1)
    return re.sub(r"\s+", " ", text.strip())


def _valid_evidence(repo, evidence_path):
    """The resolved Path if evidence_path is relative and inside
    <repo>/.sweep-evidence/ and names a real file, else None. A path that
    fails this is never opened -- it is treated as missing evidence."""
    if not evidence_path:
        return None
    candidate = Path(evidence_path)
    if candidate.is_absolute():
        return None
    sweep_dir = (Path(repo) / ".sweep-evidence").resolve()
    resolved = (Path(repo) / candidate).resolve()
    if not resolved.is_relative_to(sweep_dir):
        return None
    return resolved if resolved.is_file() else None


def _neutralize_fence(line):
    """Prefix a line that would toggle the CI tripwire's naive fence detector
    (fix round 3, H4) with a visible marker. check_archived_todo_status's
    FENCE_RE toggles on ANY line starting with ``` or ~~~ regardless of how
    many, so a single stray fence-looking line inside a quoted evidence tail
    can flip that toggle for the rest of the file -- hiding a real bare box
    after it (fails OPEN), or exposing a quoted line as a fake one (fails
    closed). Neither is safe, so every such line is neutralized, always."""
    return "| " + line if check_archived_todo_status.FENCE_RE.match(line) else line


def _fence_quote(lines):
    """A fence marker one backtick longer than the longest run in `lines`,
    minimum 3, so the tail's own content can never close it early (F5b).

    Each quoted line loses its trailing whitespace, and a line that is blank
    once stripped is emitted empty, not as the two-space indent (todo 512): the
    `trailing-whitespace` pre-commit hook rewrites either, which aborted Land's
    commit whenever a tail (vitest's, typically) held a spaces-only line."""
    lines = [_neutralize_fence(line.rstrip()) for line in lines]
    text = "\n".join(lines)
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    fence = "`" * max(longest + 1, 3)
    quoted = "\n".join(f"  {line}" if line else "" for line in lines)
    return fence, quoted


def flip_acs(repo, todo_rel, ac_entries, verdict_ac, run_id, date, main_root="", confirmed=()):
    repo = Path(repo)
    confirmed = {int(c["index"]): c for c in confirmed}
    secrets = _env_secrets(repo, main_root)
    path = repo / todo_rel
    todo_id = str((todofile.read_frontmatter(path) or {}).get("issue_id", ""))
    text = path.read_text()
    boxes = todofile.ac_lines(text)
    mine = sorted((e for e in ac_entries if str(e["todo"]) == todo_id), key=lambda e: e["index"])
    if [e["index"] for e in mine] != list(range(len(boxes))):
        raise LandError(f"{todo_rel}: ac.json has indexes {[e['index'] for e in mine]} for todo {todo_id}, "
                        f"but the file has {len(boxes)} criteria")
    for (_, _, line), entry in zip(boxes, mine):
        expected, got = _normalize_ac_text(line), _normalize_ac_text(entry.get("text", ""))
        if expected != got:
            raise LandError(f"{todo_rel}: ac.json text for index {entry['index']} ({got!r}) does not match "
                            f"the todo's AC line ({expected!r})")
    agreed = {v["index"] for v in verdict_ac if str(v["todo"]) == todo_id and v["verified"] is True}
    lines = text.splitlines(keepends=True)
    flipped, notes, owner_notes = [], [], []
    for (line_no, checked, line), entry in zip(boxes, mine):
        index = entry["index"]
        if checked or todofile.is_repoint(line):
            continue
        if index in confirmed:
            # Todo 492 AC1: ticked on the owner's dated record plus the verifier's acceptance, never on the
            # worker's word; the record is quoted, made one line, relativized and masked like a command.
            if index in agreed and _valid_date(confirmed[index].get("date", "")):
                lines[line_no] = lines[line_no].replace("[ ]", "[x]", 1)
                flipped.append(index)
                words = " ".join(_relativize(_mask(confirmed[index].get("decision", ""), secrets), repo,
                                             main_root).split())
                owner_notes.append(f"- AC {index + 1}: confirmed by the owner on {confirmed[index]['date']}: "
                                   f"\"{words}\" (`state.py confirm`; no command or evidence)\n")
            continue
        evidence = _valid_evidence(repo, entry.get("evidence_path"))
        if not (entry["pass"] is True and index in agreed and evidence):
            continue
        lines[line_no] = lines[line_no].replace("[ ]", "[x]", 1)
        flipped.append(index)
        # Mask first, as the tail is: a path-valued .env entry must still match before it is shortened.
        command = _sanitize(_relativize_command(_mask(entry["command"], secrets), repo, main_root, todo_rel))
        command = command.removeprefix("cd . && ")  # what `cd <repo> && ` reads once relativized (todo 525)
        evidence_display = _sanitize(entry["evidence_path"])
        fence, quoted = _fence_quote([_relativize(line, repo, main_root) for line in _tail(evidence, secrets)])
        notes.append(f"- AC {index + 1}: `{command}` — evidence `{evidence_display}` (not committed), "
                     f"last lines:\n\n  {fence}text\n{quoted}\n  {fence}\n")
    path.write_text("".join(lines))
    date = _log_date(path, date)
    if notes:
        todofile.append_work_log(path, f"### {date} - Verified by the todo sweep (run {run_id})\n\n" + "\n".join(notes))
    if owner_notes:
        todofile.append_work_log(path, f"### {date} - Confirmed by the owner, ticked by the todo sweep (run {run_id})"
                                       "\n\n" + "".join(owner_notes))
    remaining = [e["index"] for (_, checked, _), e in zip(boxes, mine) if not checked and e["index"] not in flipped]
    return flipped, remaining


def _valid_date(date):
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(date)))


LOG_HEADING_DATE_RE = re.compile(r"^### (\d{4}-\d{2}-\d{2}) ")


def _log_date(path, date, today=None):
    """The date for a new Work Log entry: `date`, or the latest dated Work Log heading when that is later.

    Todo 637 #7: Land's `--date` can be a day behind the worker's entry for the same run (hypothesis, not
    verified: RUN_ID is UTC and TODAY local, so a run started just after midnight UTC is still the day before
    in the US), which put the Verified and Completed entries, dated the 11th, after an Implemented entry dated
    the 12th. Entries are appended in order, so their dates must never go backwards.

    Todo 647 #4: only a heading that is a real calendar date no later than a day after today (or `date`, when
    that is later) counts, so a mistyped heading (2026-13-40, 2062-10-12) is never copied into Land's entries.
    The bound is today, not `date`: a run can stay open for days (a held group), and its worker entries are
    then legitimately days after the run's --date. The day of slack is the UTC/local skew above."""
    lines = Path(path).read_text().splitlines()
    bounds = todofile._section_bounds(lines, "Work Log")
    if bounds is None or not _calendar_date(date):
        return date
    latest = max(datetime.date.fromisoformat(date), today or datetime.date.today()) + datetime.timedelta(days=1)
    found = [d for line in lines[bounds[0]:bounds[1]] if (m := LOG_HEADING_DATE_RE.match(line))
             and (d := _calendar_date(m.group(1))) and d <= latest.isoformat()]
    return max([date, *found])


def _calendar_date(text):
    """`text` when it is a real YYYY-MM-DD date, else None."""
    try:
        return text if datetime.date.fromisoformat(text).isoformat() == text else None
    except ValueError:
        return None


def fix_baseline(repo, old_rel, new_rel):
    path = Path(repo) / ".secrets.baseline"
    if not path.is_file():
        return False
    text = path.read_text()
    if f'"{old_rel}"' not in text:
        return False
    path.write_text(text.replace(f'"{old_rel}"', f'"{new_rel}"'))
    return True


def _target_todo(line):
    """The numeric target of a '-> todo NNN' / '→ todo NNN' arrow, or None."""
    match = ARROW_TARGET_RE.search(line)
    return int(match.group(1)) if match else None


def _same_todo(a, b):
    try:
        return int(a) == int(b)
    except (TypeError, ValueError):
        return str(a) == str(b)


def _review_path(repo, rel):
    """The resolved Path for `rel` if it names a real .md file inside
    <repo>/docs/reviews/, else None (fix round 2, G4). A `source_review` that
    resolves outside docs/reviews/ -- e.g. via '../../' -- is never read or
    written; it is treated exactly like any other "not a review doc" value.
    An absolute `rel` is rejected outright (fix round 3, H2), consistent with
    `_valid_evidence` -- even one that happens to resolve inside docs/reviews/
    is not a repo-relative path, and archiving would otherwise stamp that
    absolute, machine-specific string into the todo's own frontmatter."""
    if not rel or not str(rel).endswith(".md") or Path(rel).is_absolute():
        return None
    reviews_dir = (Path(repo) / "docs" / "reviews").resolve()
    candidate = (Path(repo) / rel).resolve()
    if not candidate.is_relative_to(reviews_dir):
        return None
    return candidate if candidate.is_file() else None


def _tracked(repo, rel):
    """True when git already has `rel` staged/committed (fix round 2, G3) --
    an untracked review doc can't be `git mv`-ed, so a planned rename must
    check this before phase 2, not discover it via a failed mv."""
    proc = subprocess.run(["git", "-C", str(repo), "ls-files", "--error-unmatch", rel], capture_output=True)
    return proc.returncode == 0


def _unsettable(path, keys):
    """Why todofile.set_fields could NOT set the first such key among `keys` on
    `path` without raising, or None if all of them are settable (fix round 3,
    H3). It asks todofile.field_problem -- set_fields' own check, read-only --
    so archive() can name the exact offending key and refuse in phase 1 instead
    of discovering a pre-existing multi-line `status`/`source_review` value via
    a phase-2 ValueError after the todo has already been git-mv'd. Sharing the
    check also means a `source_review : x` line (a blank before the colon) is
    found and rewritten in place, never duplicated (todo 475)."""
    text = Path(path).read_text()
    return next((p for p in (todofile.field_problem(text, key) for key in keys) if p), None)


def plan_review(repo, todo_path, date):
    """Read-only: decide what archive's write phase should do to the source
    review doc. Never writes and never raises -- F1 is explicit that none of
    these resolutions is an error, only a no-op, a leave-open, or a checkoff,
    each carrying a note. Returns None when the todo has no source_review at
    all (no review step); source_review with no source_finding is instead a
    no-op with a note (G7), since that is an actionable data problem, not an
    absent field."""
    data = todofile.read_frontmatter(todo_path) or {}
    source, finding, todo_id = data.get("source_review"), data.get("source_finding"), data.get("issue_id")
    if not source:
        return None
    if not finding:
        return {"finding": None, "action": "noop",
                "note": f"source_review {source!r} is set but source_finding is missing"}
    review = _review_path(repo, source)
    if review is None:
        twin_rel = source[:-3] + "-COMPLETED.md" if source.endswith(".md") else None
        if twin_rel is not None and _review_path(repo, twin_rel) is not None:
            return {"finding": finding, "action": "noop", "note": f"source_review already completed: {twin_rel}"}
        return {"finding": finding, "action": "noop", "note": f"source_review is not a review doc: {source}"}
    # H2: `source` may be an un-normalised repo-relative path (an existing-but-odd
    # 'docs/reviews/sub/../r.md', or one naming a directory that doesn't exist,
    # 'docs/reviews/nope/../r.md') -- `review` is already the fully resolved,
    # real file `_review_path` found, so re-derive the clean POSIX-relative form
    # from it and use ONLY that from here on for anything that touches disk or
    # git (never the raw `source` string, which a naive open()/git mv can refuse
    # on the nonexistent 'nope' segment even though the resolved path is fine).
    norm_rel = review.relative_to(Path(repo).resolve()).as_posix()
    lines = review.read_text().splitlines(keepends=True)
    start = next((i for i, line in enumerate(lines) if line.rstrip("\n") == "## Finding Status"), None)
    if start is None:
        return {"finding": finding, "action": "noop", "note": f"{source}: no '## Finding Status' section"}
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    key = re.escape(str(finding))
    line_re = re.compile(rf"^\s*-\s\[([ xX])\]\s*#{key}(?=\s|$)")
    matches = [i for i in range(start + 1, end) if line_re.match(lines[i])]
    if not matches:
        return {"finding": finding, "action": "noop", "note": f"{source}: no line for finding #{finding}"}

    def _is_open(i):
        return line_re.match(lines[i]).group(1) == " "

    def _relevant(i):
        target = _target_todo(lines[i])
        return target is None or _same_todo(target, todo_id)

    # H5/G7: several lines can name the same finding (a stale one plus a live one,
    # or a legacy line plus its re-point). Every OPEN line that is checkable BY THIS
    # TODO (no arrow target, or a target matching todo_id) ships together -- they
    # are the same finding, shipped by the same archive. An open line targeting
    # someone else is never touched. If no line is checkable, fall back to the
    # first line that at least NAMES this todo (checked or not) over an arbitrary
    # first match, so "already checked"/"left open" describes THIS todo's own line
    # in either duplicate order, not whichever line happened to be listed first.
    checkable = [i for i in matches if _is_open(i) and _relevant(i)]
    if not checkable:
        relevant_any = next((i for i in matches if _relevant(i)), None)
        hit = relevant_any if relevant_any is not None else matches[0]
        if _is_open(hit):
            target = _target_todo(lines[hit])
            return {"finding": finding, "action": "leave_open",
                    "note": f"finding #{finding} targets todo {target}, not {todo_id}; left open"}
        return {"finding": finding, "action": "noop", "note": "already checked"}
    new_lines = list(lines)
    for i in checkable:
        new_lines[i] = new_lines[i].rstrip("\n").replace("- [ ]", "- [x]", 1) + f" (completed {date})\n"
    open_re = re.compile(r"^\s*-\s\[ \]")
    all_closed = not any(open_re.match(new_lines[i]) for i in range(start + 1, end))
    renamed, completed, note = False, None, "checked off"
    if all_closed:
        if norm_rel.endswith("-COMPLETED.md"):
            note = "checked off; already a -COMPLETED doc, no further rename"
        else:
            candidate_rel = norm_rel[:-3] + "-COMPLETED.md"
            # G3/H1: a planned rename must be fully validated here, in phase 1 -- a
            # destination collision or an untracked source only surfaces as a git
            # failure in phase 2, by which point archive() has already git-mv'd the
            # todo and rewritten the review doc, so LandError there is not an option.
            # os.path.lexists (not is_file): a dangling symlink or a directory at the
            # destination both count as "something is there" -- is_file() misses both
            # (False for a broken symlink's target, False for a directory), which let
            # git either refuse in phase 2 (symlink) or silently move the doc INTO the
            # directory instead of onto it (directory) -- H1.
            # Fix round 4: a twin git still tracks but that was deleted from disk is
            # present too -- lexists can't see the index, and a `git mv` onto it would
            # replace the twin's index entry with this doc.
            if os.path.lexists(Path(repo) / candidate_rel) or _tracked(repo, candidate_rel):
                note = f"all findings resolved, but {candidate_rel} already exists; rename skipped"
            elif not _tracked(repo, norm_rel):
                note = f"all findings resolved, but {norm_rel} is not tracked in git; rename skipped"
            else:
                renamed, completed, note = True, candidate_rel, "all findings resolved"
    siblings, skipped = _siblings(repo, review, todo_path) if renamed else ([], [])
    return {"finding": finding, "action": "checkoff", "note": note, "source": norm_rel,
            "new_lines": new_lines, "renamed": renamed, "completed": completed,
            "siblings": siblings, "skipped_siblings": skipped}


def _siblings(repo, review, todo_path):
    """(rewrite, skipped) for the other todos, open or archived, whose `source_review` resolves
    to `review`: after the -COMPLETED rename their pointer would dangle (todo 468). `rewrite` is
    the repo-relative paths that can be rewritten in place; `skipped` holds a {"path", "reason"}
    for every one that can't, which archive() writes into the Work Log, so no pointer is left
    dangling silently (todo 475). Read-only and never raises, like plan_review."""
    repo = Path(repo)
    rewrite, skipped = [], []
    for path in sorted([*(repo / "todos").glob("*.md"), *(repo / "todos" / "archive").glob("*.md")]):
        if path.resolve() == Path(todo_path).resolve():
            continue
        rel = path.relative_to(repo).as_posix()
        try:  # a NUL byte in a path makes resolve() raise ValueError (PR #870 round 1)
            source = (todofile.read_frontmatter(path) or {}).get("source_review")
            if not (source and _review_path(repo, str(source)) == review):
                continue
            problem = _unsettable(path, ["source_review"])
            if problem:
                skipped.append({"path": rel, "reason": problem})
            elif not _tracked(repo, rel):  # tracked only: Stage D stages every returned path
                skipped.append({"path": rel, "reason": "not tracked in git"})
            else:
                rewrite.append(rel)
        except (yaml.YAMLError, ValueError, OSError) as exc:
            # Unreadable, so whether it names `review` is unknown: note it when its
            # `source_review` value at least holds a path that resolves to the review doc.
            if _mentions(repo, path, review):
                skipped.append({"path": rel, "reason": f"its frontmatter could not be read ({type(exc).__name__})"})
    return rewrite, skipped


# One token of a frontmatter line, read left to right: a comment (a '#' at the start or after a blank)
# runs to the end of the line; a quoted string, closed or not, or a plain run is a scalar; a flow
# indicator opens, closes or separates a flow collection.
_TOKEN_RE = re.compile(r"""(?P<comment>(?<!\S)\#.*)|"(?P<dq>[^"]*)"?|'(?P<sq>[^']*)'?|(?P<flow>[\[\]{},])"""
                       r"""|(?P<plain>[^\s"'\[\]{},]+)""")
# A `source_review` key, quoted or not, with any blanks before the colon.
_SOURCE_REVIEW_KEY_RE = re.compile(r"""[ \t]*(["']?)source_review\1[ \t]*:""")


def _key_value(line):
    """(the text after its colon, whether it sits in a flow mapping) for a `source_review` key on `line`,
    or None. The key may follow blanks -- an indented key is a common cause of the YAML error -- or a
    '{' or ',' outside quotes (todo 519)."""
    starts = [0] + [token.end() for token in _TOKEN_RE.finditer(line) if token["flow"] in ("{", ",")]
    for start in starts:
        key = _SOURCE_REVIEW_KEY_RE.match(line, start)
        if key:
            return line[key.end():], start > 0
    return None


def _scalars(lines, in_flow):
    """Each scalar of the value `lines` hold: the rest of the key's line, then its continuation lines. A
    comment ends its line. In a flow mapping the value ends at its own entry's ',' or closing brace, so a
    later key of that mapping is not read as part of it; a flow list of its own only nests."""
    depth = 0
    for line in lines:
        for token in _TOKEN_RE.finditer(line):
            if token["comment"] is not None:
                break
            flow = token["flow"]
            if flow is None:
                yield next(group for group in (token["dq"], token["sq"], token["plain"]) if group is not None)
            elif flow in "[{":
                depth += 1
            elif in_flow and depth == 0:
                return
            elif flow != ",":
                depth -= 1


def _mentions(repo, path, review):
    """True when `path` reads and a scalar in the value of a `source_review` key of its frontmatter
    resolves to `review` through `_review_path`, the rule a readable sibling's value goes through.
    Line-based, because it runs only on frontmatter YAML could not read: the value is the rest of the
    key's line plus every line indented deeper than the key, and blank or comment-only lines do not end
    it. Todo 506 replaced a bare substring test, which matched other fields and longer names. Todo 519
    replaced 506's basename match, which matched the same name in any directory and inside a trailing
    comment, and missed an indented key, a key in a flow mapping, a flow list and a value after a
    comment line."""
    try:
        match = todofile.FM_RE.match(Path(path).read_text(errors="replace"))
    except OSError:
        return False
    lines = match.group(1).splitlines() if match else []
    for i, line in enumerate(lines):
        found = _key_value(line)
        if found is None:
            continue
        rest, in_flow = found
        indent = len(line) - len(line.lstrip(" \t"))
        value = [rest]
        for more in lines[i + 1:]:
            body = more.lstrip(" \t")
            if not body or body.startswith("#"):
                continue
            if len(more) - len(body) <= indent:
                break
            value.append(more)
        for scalar in _scalars(value, in_flow):
            try:
                if _review_path(repo, scalar) == review:
                    return True
            except (ValueError, OSError):  # a NUL byte, or a name the OS refuses
                continue
    return False


def apply_review(repo, plan, todo_path, git=run_git):
    """Write phase for plan_review's plan. Never raises: any error in the
    plan already surfaced in plan_review, before any write happened."""
    if plan is None:
        return None
    # Todo 506: every result carries skipped_siblings, so callers see one shape.
    if plan["action"] != "checkoff":
        return {"finding": plan["finding"], "renamed": False, "paths": [], "note": plan["note"],
                "skipped_siblings": []}
    source = plan["source"]
    (Path(repo) / source).write_text("".join(plan["new_lines"]))
    if plan["renamed"]:
        completed = plan["completed"]
        git(repo, "mv", source, completed)
        todofile.set_fields(todo_path, {"source_review": completed})
        for rel in plan.get("siblings", []):
            todofile.set_fields(Path(repo) / rel, {"source_review": completed})
        skipped = plan.get("skipped_siblings", [])
        note = plan["note"] + (f"; {len(skipped)} sibling todo(s) not rewritten" if skipped else "")
        return {"finding": plan["finding"], "renamed": True, "paths": [completed, *plan.get("siblings", [])],
                "note": note, "skipped_siblings": skipped}
    return {"finding": plan["finding"], "renamed": False, "paths": [source], "note": plan["note"],
            "skipped_siblings": []}


def _skipped_notes(review_plan):
    """Work Log bullets naming each sibling whose pointer the -COMPLETED rename leaves
    dangling, so it is in the committed record, not only in the JSON output (todo 475).
    Every interpolated value goes through _sanitize -- the review paths too (todo 506) --
    so no file name can start a new line, and with it a forged heading."""
    plan = review_plan or {}
    return "".join(
        f"- Sibling `{_sanitize(s['path'])}` still names `{_sanitize(plan['source'])}` ({_sanitize(s['reason'])}); "
        f"point its `source_review` at `{_sanitize(plan['completed'])}` by hand.\n"
        for s in plan.get("skipped_siblings", []))


def has_verified_note_for(text, run_id):
    """True when flip_acs wrote its evidence-quoting Work Log heading for run_id. A
    worker never writes "Verified by" (a verify-only worker writes "Checked by"), so
    this cannot be satisfied by a note that quoted nothing (final review m9)."""
    return f"Verified by the todo sweep (run {run_id})" in text


def archive(repo, todo_rel, run_id, date, git=run_git):
    repo = Path(repo)
    src = repo / todo_rel
    dest_rel = todofile.archived_path(todo_rel)
    dest = repo / dest_rel

    # Phase 1: validate; write nothing. LandError may be raised only here.
    if not src.is_file():
        if dest.is_file():
            raise LandError(f"{todo_rel}: already archived at {dest_rel}")
        raise LandError(f"{todo_rel}: source todo not found")
    if not dest.parent.is_dir():
        raise LandError(f"{dest.parent}: does not exist")
    # Fix round 4: lexists, not is_file -- a directory at dest would have `git mv`
    # move the todo INTO it (then set_fields raises IsADirectoryError), and a
    # dangling symlink would fail the `git mv`; both must refuse here, before any write.
    if os.path.lexists(dest):
        raise LandError(f"{todo_rel}: destination already exists: {dest_rel}")
    # H3: each of these would otherwise surface as an exception mid-phase-2 -- a
    # ValueError from set_fields (no frontmatter, or a multi-line status/source_review
    # that can't be rewritten in place), or a git failure from mv-ing an untracked
    # path -- by which point the todo or the review doc may already have moved.
    if todofile.read_frontmatter(src) is None:
        raise LandError(f"{todo_rel}: no frontmatter block")
    if not _tracked(repo, todo_rel):
        raise LandError(f"{todo_rel}: not tracked in git")
    text = src.read_text()
    if not any(line.rstrip("\n") == "## Acceptance Criteria" for line in text.splitlines()):
        raise LandError(f"{todo_rel}: no '## Acceptance Criteria' section; nothing verified to archive")
    _, _, _, bare_acs = check_archived_todo_status.parse(str(src))
    if bare_acs:
        raise LandError(f"{todo_rel}: {len(bare_acs)} unchecked criteria; "
                        "flip them with evidence or re-point them first")
    # Todo 492 AC2: CI refuses an archived todo whose Work Log names a home path, so Land refuses first.
    home = check_archived_todo_status.work_log_home_paths(text)
    if home:
        raise LandError(f"{todo_rel}: its Work Log names a home path on {len(home)} line(s); make each repo-relative "
                        "(or `~`) by hand, then archive again")
    # Todo 647 #4: one date for the Completed entry and the review-doc check-off alike.
    date = _log_date(src, date)
    review_plan = plan_review(repo, src, date)
    settable = ["status"]
    if review_plan and review_plan["action"] == "checkoff" and review_plan["renamed"]:
        settable.append("source_review")
    problem = _unsettable(src, settable)
    if problem:
        raise LandError(f"{todo_rel}: {problem}; edit it by hand")
    # G1: whether THIS land wrote a Verified note with evidence for this run_id --
    # not merely whether some box happens to be [x], which is also true for a box
    # that was already checked (by hand, or a past run) with no evidence ever quoted.
    has_verified_note = has_verified_note_for(text, run_id)

    # Phase 2: write.
    git(repo, "mv", todo_rel, dest_rel)
    todofile.set_fields(dest, {"status": "completed"})
    tail_note = "evidence is quoted above, review is on the PR." if has_verified_note else "review is on the PR."
    todofile.append_work_log(dest, f"### {date} - Completed by the todo sweep (run {run_id})\n\n"
                                   f"- Archived by `land.py archive`; {tail_note}\n" + _skipped_notes(review_plan))
    baseline = fix_baseline(repo, todo_rel, dest_rel)
    review = apply_review(repo, review_plan, dest, git)
    paths = [dest_rel] + ([".secrets.baseline"] if baseline else []) + (review["paths"] if review else [])
    return {"archived": dest_rel, "paths": paths, "baseline_updated": baseline, "review": review}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("cmd", choices=["flip-acs", "archive"])
    parser.add_argument("--run", required=True)
    parser.add_argument("--id", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--date", required=True)
    args = parser.parse_args(argv)
    try:
        run = state.load(args.run)
        entry = run["todos"][args.id]
        if args.cmd == "flip-acs":
            ac_entries = json.loads((Path(args.repo) / entry["ac_file"]).read_text())
            flipped, remaining = flip_acs(args.repo, entry["path"], ac_entries, entry.get("verified_ac", []),
                                          run["run_id"], args.date, main_root=entry.get("main_root", ""),
                                          confirmed=entry.get("confirmed", []))
            print(json.dumps({"flipped": flipped, "remaining": remaining}))
        else:
            print(json.dumps(archive(args.repo, entry["path"], run["run_id"], args.date)))
    except (LandError, KeyError, ValueError, FileNotFoundError, yaml.YAMLError) as exc:
        print(f"land: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
