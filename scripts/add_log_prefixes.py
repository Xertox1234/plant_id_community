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
    arg = call.args[0]

    node = None
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        node = arg
    elif isinstance(arg, ast.JoinedStr):
        for part in arg.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                node = part
            break
    elif isinstance(arg, ast.BinOp):
        if isinstance(arg.left, ast.Constant) and isinstance(arg.left.value, str):
            node = arg.left

    if node is None:
        return None
    if PREFIX_RE.match(node.value):
        return None  # already prefixed -- idempotent
    return node


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
        node = target_literal(call)
        if node is None:
            continue
        edits.append((node.lineno, node.col_offset))

    for lineno, col in sorted(edits, reverse=True):
        line = lines[lineno - 1]
        # col points at the opening quote (or its f/r/u/b prefix). Step past the
        # string prefix characters and the quote run to land inside the literal.
        i = col
        while i < len(line) and line[i] in "fFrRuUbB":
            i += 1
        if i >= len(line) or line[i] not in "\"'":
            continue  # not a shape we understand; leave it alone
        quote = line[i]
        run = 3 if line[i : i + 3] == quote * 3 else 1
        i += run
        lines[lineno - 1] = line[:i] + token + " " + line[i:]

    return "".join(lines), len(edits)


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
            path.write_text(new_source, encoding="utf-8")

    print(f"\n{'would prefix' if args.check else 'prefixed'} {total} call(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
