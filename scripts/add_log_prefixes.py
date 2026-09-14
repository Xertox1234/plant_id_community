#!/usr/bin/env python3
"""Prepend a bracketed subsystem prefix to unprefixed `logger.*` calls (todo 388).

WHY A SCRIPT AND NOT HAND EDITS. The sweep is 341 calls across 39 files. A
deterministic pass plus one verification is reviewable -- a reviewer reads this
table and spot-checks the output -- where 341 hand edits are not, and an agent
iterating a linter re-introduces variance on every pass.

WHAT IT DOES, AND ONLY THIS. It inserts `[TOKEN] ` at the front of the first
argument's leading string literal. It does not reword, does not convert f-strings
to lazy `%s`, does not touch `logger.exception` vs `logger.error`, and does not
reflow. Rewording is specifically unsafe: 17 assertions across 12 test files read
log content (todo 388).

WHY A TABLE AND NOT INFERENCE. The prefix names the CONCERN, not the module --
`plant_id_service.py` alone emits `[LOCK]`, `[CACHE]` and `[QUOTA]` -- which is
also why the logging `Filter` approach was rejected. Concern is not derivable
from a path, so it is stated here per file and reviewed as a table. A file whose
calls span several concerns should be split into per-line entries or done by
hand rather than forced under one token.

Idempotent: a call the checker already considers prefixed is skipped, so a second
run is a no-op.

Usage:
    add_log_prefixes.py --check     # report what would change, write nothing
    add_log_prefixes.py --apply
"""

from __future__ import annotations

import argparse
import ast
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]

# Same judgeability rules as scripts/check_log_prefixes.py, so the counts this
# prints and the counts the acceptance criteria use cannot disagree.
LEVELS = {"debug", "info", "warning", "warn", "error", "exception", "critical"}
RECEIVERS = {"logger", "log", "_logger"}
PREFIX_RE = re.compile(r"^\s*\[[A-Z0-9_-]+\]")
PREFIX_CONST_RE = re.compile(r"^LOG_PREFIX_[A-Z0-9_]+$")
LEADING_FMT_RE = re.compile(r"^\s*%s")

# --------------------------------------------------------------------------
# The table. One token per file, chosen from the ~16 already in use where one
# fits; `[NOTIFY]` and `[VALIDATION]` are new, and are named for the concern
# rather than the module for the reason above.
# --------------------------------------------------------------------------
PREFIXES = {
    # Centralised DRF exception handler: every call here reports a failed
    # request. `[ERROR]` is already the repo's most-used token after [CACHE].
    "backend/apps/core/exceptions.py": "[ERROR]",
    # Response-scanning for leaked SQL and XSS payloads.
    "backend/apps/core/sanitizers.py": "[SECURITY]",
    # Account lockout, failed logins, security events. Matches the
    # LOG_PREFIX_SECURITY calls already in this file.
    "backend/apps/core/security.py": "[SECURITY]",
    "backend/apps/core/services/email_service.py": "[EMAIL]",
    # Routes across channels (in-app, email, push), so not [EMAIL].
    "backend/apps/core/services/notification_service.py": "[NOTIFY]",
    # Only call is "Email template not found", and the service renders email
    # templates -- same subsystem as email_service.
    "backend/apps/core/services/template_service.py": "[EMAIL]",
    # File-upload and input validation outcomes.
    "backend/apps/core/validators.py": "[VALIDATION]",
}


def logger_level(call: ast.Call):
    func = call.func
    if not isinstance(func, ast.Attribute) or func.attr not in LEVELS:
        return None
    recv = func.value
    if isinstance(recv, ast.Name):
        name = recv.id
    elif isinstance(recv, ast.Attribute):
        name = recv.attr
    else:
        return None
    return func.attr if name.lower() in RECEIVERS else None


def target_literal(call: ast.Call):
    """The `ast.Constant` to prepend into, or None when out of scope.

    Returns None for an already-prefixed call, for a first argument that is not
    a literal, and for an f-string opening with an interpolation -- the last of
    which may be a `LOG_PREFIX_*` constant (already correct) or an arbitrary
    value (a real violation this script deliberately will not guess at).
    """
    if not call.args:
        return None

    # The prefix may arrive as the first %-format ARGUMENT rather than in the
    # literal: `logger.debug("%s extraction failed: %s", LOG_PREFIX_SECURITY, e)`
    # renders as "[SECURITY] extraction failed: ...". Prefixing that literal
    # produces "[SECURITY] [SECURITY] ...". Caught by reading the sweep's own
    # diff, not by any counter -- both counters called these calls unprefixed.
    if (
        len(call.args) >= 2
        and isinstance(call.args[0], ast.Constant)
        and isinstance(call.args[0].value, str)
        and LEADING_FMT_RE.match(call.args[0].value)
        and PREFIX_CONST_RE.match(ast.unparse(call.args[1]))
    ):
        return None

    arg = call.args[0]

    node = None
    inside = False  # does col_offset point INSIDE the literal already?
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        node = arg
    elif isinstance(arg, ast.JoinedStr):
        for part in arg.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                # An f-string CHUNK reports the position of its own text, not of
                # the enclosing quote -- unlike every other shape here. Measured,
                # not assumed: probing `logger.error(f"fstring {x}")` gives
                # col_offset pointing at `f` of `fstring`, while a plain constant
                # points at the `"`. Getting this wrong is silent: the splice
                # lands mid-word or not at all.
                node, inside = part, True
            break
    elif isinstance(arg, ast.BinOp):
        if isinstance(arg.left, ast.Constant) and isinstance(arg.left.value, str):
            node = arg.left

    if node is None:
        return None
    if PREFIX_RE.match(node.value):
        return None  # already prefixed -- idempotent
    return node, inside


def rewrite(path: pathlib.Path, token: str):
    """Return (new_source, changed_count). Edits by (line, col) from the AST.

    Text is spliced at the literal's own start offset rather than by regex, so a
    multi-line call, an implicitly concatenated literal, and a message that
    itself contains `logger.` are all handled. Edits are applied last-first so
    earlier offsets stay valid.
    """
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines(keepends=True)
    tree = ast.parse(source)

    edits = []
    for call in (n for n in ast.walk(tree) if isinstance(n, ast.Call)):
        if not logger_level(call):
            continue
        found = target_literal(call)
        if found is None:
            continue
        node, inside = found
        edits.append((node.lineno, node.col_offset, inside))

    applied = 0
    for lineno, col, inside in sorted(edits, reverse=True):
        line = lines[lineno - 1]
        if inside:
            i = col  # f-string chunk: already inside the literal
        else:
            # Step past any string-prefix letters and the quote run.
            i = col
            while i < len(line) and line[i] in "fFrRuUbB":
                i += 1
            if i >= len(line) or line[i] not in "\"'":
                # Refuse rather than skip. A silent skip is how the first run of
                # this script reported "prefixed 46" while writing 9: every
                # f-string was dropped here and still counted. A splice this
                # code cannot place is a bug in this code, not a file to ignore.
                raise RuntimeError(
                    f"{path}:{lineno}: cannot locate the literal opening at "
                    f"col {col}; refusing to write a partial sweep"
                )
            quote = line[i]
            i += 3 if line[i : i + 3] == quote * 3 else 1
        lines[lineno - 1] = line[:i] + token + " " + line[i:]
        applied += 1

    assert applied == len(edits), f"{path}: {applied} applied of {len(edits)}"
    return "".join(lines), applied


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="report, write nothing")
    group.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    total = 0
    for rel, token in sorted(PREFIXES.items()):
        path = REPO / rel
        if not path.is_file():
            print(f"MISSING: {rel}", file=sys.stderr)
            return 1
        new_source, count = rewrite(path, token)
        total += count
        print(f"  {count:3d}  {token:<12} {rel}")
        if args.apply and count:
            # Re-parse before writing. The f-string branch splices at
            # `node.col_offset`, which only points inside the literal since
            # PEP 701 (Python 3.12). On 3.11 and earlier it points at the `f`,
            # so the prefix lands OUTSIDE the quotes and the file stops
            # parsing -- and nothing notices: `rewrite()` reports success
            # (the splice "worked", just at the wrong offset), and
            # check_log_prefixes.py swallows SyntaxError with `continue`, so a
            # mangled file drops out of BOTH numerator and denominator and the
            # reported count goes DOWN. That is indistinguishable from a
            # successful sweep in the very tool that certifies it.
            try:
                ast.parse(new_source)
            except SyntaxError as exc:
                print(
                    f"REFUSING to write {rel}: the rewrite does not parse "
                    f"({exc}). This is the pre-3.12 f-string col_offset bug; "
                    f"run under Python 3.12+.",
                    file=sys.stderr,
                )
                return 1
            path.write_text(new_source, encoding="utf-8")

    print(f"\n{'would prefix' if args.check else 'prefixed'} {total} call(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
