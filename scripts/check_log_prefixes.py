#!/usr/bin/env python3
"""Count `logger.*` calls that lack a bracketed subsystem prefix.

Why this exists: `docs/rules/api.md:13-14` makes bracketed log prefixes
(`logger.info("[CACHE] ...")`) a binding rule so logs are greppable by
subsystem. GitHub issue #186 claimed 5% of log statements were unprefixed and
nobody ever re-measured it. On 2026-09-13 (todo 361) the real figure across
`backend/apps/` turned out to be 357 of 769 judgeable calls -- 46.4%.

That 357 was itself 16 too high, corrected 2026-09-13 (todo 388) when the first
sweep slice found the misses: 15 calls prefixed via a `LOG_PREFIX_*` constant and
1 using a hyphenated token -- then 2 more, found by spot-reading the sweep's own
diff, where the prefix arrives as the first %-format ARGUMENT. That corrected
baseline was **339 of 769 (44.1%)**, all 18 corrections in `core`.

A FOURTH shape surfaced 2026-09-13 while scoping the `users` slice: a token
containing a SPACE. `[FIREBASE AUTH]` (15) and `[FIREBASE AUTH ERROR]` (6), all
in `users/firebase_auth_views.py`, are real prefixes and the only space-tokens
in the repo -- but the pattern allowed `[A-Z0-9_-]` only, so all 21 counted as
violations. Left unfixed, the sweep would have written
`[AUTH] [FIREBASE AUTH] ...`: the same double-prefix that the %-format shape
would have produced, caught the same way -- by reading call sites before
applying, not by re-running a counter. All four shapes are recognised below.

Todo 388 sweeps that debt app by app, and its acceptance criteria are stated in
terms of counts produced by THIS script. That is the whole point of committing
it: a count is only meaningful against a fixed judgeability rule. Re-deriving a
detector from prose would produce numbers that cannot be compared to the 357
baseline, which is how the original 5% claim became worthless.

WHAT COUNTS AS A LOGGER CALL
  A call whose function is an attribute named debug/info/warning/warn/error/
  exception/critical on a receiver named (case-insensitively) logger, log or
  _logger -- so `logger.info(...)`, `LOGGER.error(...)`, `self.logger.warning(...)`
  all count. Limitation: a logger bound to any other name is invisible.

WHAT COUNTS AS PREFIXED
  The FIRST argument's leading *literal* text matches `^\\s*\\[[A-Z0-9_-]+\\]`,
  or the first argument is an f-string opening with a `LOG_PREFIX_*` constant.
  Leading text is resolved for four shapes, because a line-based regex misses
  most of them:
    - a plain string constant                  logger.info("[CACHE] hit")
    - an f-string, using its first literal     logger.info(f"[CACHE] {k}")
      chunk -- or, when it opens with an
      interpolation, the interpolated name     logger.info(
      if that name is a LOG_PREFIX_*             f"{LOG_PREFIX_AUTH} ok")
      constant (apps/core/constants.py).
      Any other opening interpolation is
      UNPREFIXED
    - "..." % (...) and "..." + x, using       logger.info("[CACHE] %s" % k)
      the left operand
    - anything else (a bare name, a call)      -> UNDETERMINABLE, not counted
      is excluded from the ratio rather           in either column
      than guessed at

  Multi-line calls are handled, because this walks the AST rather than lines.
  That matters: 3 of the 7 unprefixed calls in the file that motivated this
  script span multiple lines and a `grep` for `logger\\.\\w+\\("` misses them.

DELIBERATE EXEMPTIONS
  A call with `log-prefix: exempt` in a comment on any of its own lines, or in
  a comment-only line directly above it, is counted in a separate EXEMPT
  column, never as prefixed. A trailing comment on the line above (the end of
  another statement) does not count, and comments are found by the tokenizer,
  so a `#` inside a string is not one (todo 573). Use it only where a prefix would be wrong, and say why in the same
  comment. The one shape that needs it (todo 392): a Celery task relaying a
  management command's captured stdout line by line, where the command already
  prefixes every line it writes -- stamping a token there doubles it.

WHAT IS EXCLUDED
  Test files (`*/tests/*`, `test_*.py`, `*_test.py`) and `migrations/`. Tests
  assert ON log content rather than emitting it; see todo 388 for the 17
  assertions across 12 files that constrain any rewording during a sweep.
"""

import argparse
import ast
import io
import os
import re
import sys
import tokenize
from collections import Counter

LEVELS = {"debug", "info", "warning", "warn", "error", "exception", "critical"}
RECEIVERS = {"logger", "log", "_logger"}
# A hyphen and a SPACE are both allowed in the token. `[RATELIMIT-RESOLVE]`
# (apps/core/ratelimit.py) and `[FIREBASE AUTH]` / `[FIREBASE AUTH ERROR]`
# (users/firebase_auth_views.py, 21 calls) are real, greppable subsystem
# prefixes; rejecting either counted compliant calls as violations and would
# have invited someone to "fix" a working diagnostic -- or, worse, invited this
# repo's own sweep to prepend a second prefix in front of the first.
PREFIX_RE = re.compile(r"^\s*\[[A-Z0-9_ -]+\]")
# An f-string may open with a named constant that IS the prefix:
#   logger.warning(f"{LOG_PREFIX_RATELIMIT} Rate limit violation: ...")
# apps/core/constants.py:74-83 defines ten of these and they hold real bracketed
# values. Treating "opens with an interpolation" as unprefixed marked 15 already-
# compliant calls as violations -- every one of them in `core`, which is why that
# app read as 92.5% non-compliant instead of its true 68.7%.
PREFIX_CONST_RE = re.compile(r"^LOG_PREFIX_[A-Z0-9_]+$")
# A third shape: the prefix arrives as the first %-format ARGUMENT rather than in
# the literal -- `logger.debug("%s extraction failed: %s", LOG_PREFIX_SECURITY, e)`.
# The RENDERED line is prefixed, so the call is compliant. Two such calls exist
# (apps/core/security.py:646,653); counting them as violations would have made a
# sweep double-prefix them to "[SECURITY] [SECURITY] ...".
LEADING_FMT_RE = re.compile(r"^\s*%s")
EXEMPT_MARK = "log-prefix: exempt"
SKIP_DIRS = {"venv", ".venv", "node_modules", "migrations", "__pycache__", ".git"}


def prefix_comes_from_a_format_arg(call: ast.Call) -> bool:
    """True when the literal opens with `%s` and that arg is a LOG_PREFIX_*."""
    if len(call.args) < 2:
        return False
    first = call.args[0]
    if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
        return False
    if not LEADING_FMT_RE.match(first.value):
        return False
    return bool(PREFIX_CONST_RE.match(ast.unparse(call.args[1])))


def leading_literal(call: ast.Call) -> "str | None":
    """The first argument's literal leading text, or None if undeterminable."""
    if not call.args:
        return None
    if prefix_comes_from_a_format_arg(call):
        return "[ARG_PREFIX]"
    arg = call.args[0]
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return arg.value
    if isinstance(arg, ast.JoinedStr):
        for part in arg.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                return part.value
            if isinstance(part, ast.FormattedValue):
                # Opens with an interpolation. That is a prefix only when the
                # interpolated name is one of the LOG_PREFIX_* constants; any
                # other expression is a value, not a subsystem tag.
                if PREFIX_CONST_RE.match(ast.unparse(part.value)):
                    return "[CONST_PREFIX]"
                return ""
            return ""
        return ""
    if isinstance(arg, ast.BinOp):
        left = arg.left
        if isinstance(left, ast.Constant) and isinstance(left.value, str):
            return left.value
    return None


def logger_level(call: ast.Call) -> "str | None":
    """The log level if this call is a logger call, else None."""
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


def exempt_marks(source: str) -> "dict[int, bool]":
    """Lines whose comment holds EXEMPT_MARK -> whether the comment is alone
    on its line.

    Comments come from the tokenizer, not from splitting on `#`: a `#` inside
    a string literal (`"#%s"`) is not a comment, and must neither hide nor
    fake the mark (todo 573).
    """
    marks: "dict[int, bool]" = {}
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.COMMENT and EXEMPT_MARK in tok.string:
                row, col = tok.start
                marks[row] = not tok.line[:col].strip()
    except (tokenize.TokenError, SyntaxError):
        return {}
    return marks


def is_exempt(marks: "dict[int, bool]", call: ast.Call) -> bool:
    """True when EXEMPT_MARK is in a comment on one of the call's own lines,
    or in a comment-only line directly above it.

    The line above counts only when it holds nothing but the comment: a
    trailing mark there belongs to the statement on that line, and must not
    excuse an unprefixed call on the next (todo 573).
    """
    last = call.end_lineno or call.lineno
    if any(row in marks for row in range(call.lineno, last + 1)):
        return True
    return marks.get(call.lineno - 1, False)


def is_test(path: str, filename: str) -> bool:
    return (
        "/tests/" in path
        or "/tests" in path.rstrip("/")
        or filename.startswith("test_")
        or filename.endswith("_test.py")
    )


def scan(root: str):
    """Yield (relpath, lineno, level, leading_text_or_None, exempt) per logger call."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for filename in sorted(filenames):
            if not filename.endswith(".py"):
                continue
            full = os.path.join(dirpath, filename)
            if is_test(full, filename):
                continue
            try:
                source = open(full, encoding="utf-8").read()
                tree = ast.parse(source)
            except (SyntaxError, UnicodeDecodeError):
                continue
            marks = exempt_marks(source)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                level = logger_level(node)
                if level is None:
                    continue
                yield full, node.lineno, level, leading_literal(node), is_exempt(
                    marks, node
                )


def app_of(relpath: str, root: str) -> str:
    rest = os.path.relpath(relpath, root)
    return rest.split(os.sep)[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root",
        default="backend/apps",
        help="directory to scan (default: backend/apps)",
    )
    parser.add_argument("--app", help="only report this top-level app")
    parser.add_argument(
        "--list",
        action="store_true",
        help="list every unprefixed and exempt call site",
    )
    parser.add_argument(
        "--fail-over",
        type=int,
        metavar="N",
        help="exit 1 if the unprefixed count exceeds N (use 0 to require a clean app)",
    )
    args = parser.parse_args()

    if not os.path.isdir(args.root):
        print(f"error: no such directory: {args.root}", file=sys.stderr)
        return 2

    prefixed, unprefixed, undeterminable = Counter(), Counter(), Counter()
    exempt = Counter()
    sites, exempt_sites = [], []
    for path, lineno, level, text, is_marked in scan(args.root):
        app = app_of(path, args.root)
        if args.app and app != args.app:
            continue
        if text is None:
            undeterminable[app] += 1
        elif PREFIX_RE.match(text):
            prefixed[app] += 1
        elif is_marked:
            exempt[app] += 1
            exempt_sites.append((path, lineno, level, text[:60]))
        else:
            unprefixed[app] += 1
            sites.append((path, lineno, level, text[:60]))

    apps = sorted(set(prefixed) | set(unprefixed) | set(undeterminable) | set(exempt))
    total_u = sum(unprefixed.values())
    total_p = sum(prefixed.values())
    total_d = sum(undeterminable.values())
    total_e = sum(exempt.values())

    width = max((len(a) for a in apps), default=10)
    print(f"{'app'.ljust(width)}  unprefixed  prefixed  exempt")
    for app in apps:
        print(
            f"{app.ljust(width)}  {unprefixed[app]:10d}  {prefixed[app]:8d}"
            f"  {exempt[app]:6d}"
        )
    print(f"{'TOTAL'.ljust(width)}  {total_u:10d}  {total_p:8d}  {total_e:6d}")

    # Exempt calls stay in the denominator: they are judgeable, just excused.
    judgeable = total_u + total_p + total_e
    share = (100.0 * total_u / judgeable) if judgeable else 0.0
    print(
        f"\n{total_u} unprefixed of {judgeable} judgeable ({share:.1f}%), "
        f"{len(set(s[0] for s in sites))} files"
    )
    if total_d:
        print(f"{total_d} call(s) undeterminable (first arg not a literal), excluded")
    if total_e:
        print(f"{total_e} call(s) marked `# {EXEMPT_MARK}`, not counted as unprefixed")

    if args.list:
        print()
        for path, lineno, level, text in sorted(sites):
            print(f"{path}:{lineno}  {level:<9} {text}")
        for path, lineno, level, text in sorted(exempt_sites):
            print(f"{path}:{lineno}  {level:<9} {text}  [exempt]")

    if args.fail_over is not None and total_u > args.fail_over:
        print(
            f"\nFAIL: {total_u} unprefixed exceeds the allowed {args.fail_over}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
