#!/usr/bin/env python3
"""Assemble `docs/rules/<domain>.md` content to fit a byte budget (todo 369).

THE PROBLEM THIS REPLACES. `inject-patterns.sh` used to concatenate the routed
domain files and `head -c 8800` the result. Three consequences, all measured:

* A **single-domain** edit truncated. `main.dart` routes to `flutter` alone and
  received 4227 of `flutter.md`'s 12127 bytes -- 34% -- cut mid-word, because
  `_discipline.md` (4426 B) always consumes half the budget first.
* A **multi-domain** edit got the first domain and nothing else.
  `settings.py` routes to `api,security,database`; `security.md` and
  `database.md` arrived as **zero bytes**.
* The rule files are append-only by convention, so the **newest** rule -- the one
  written because the mistake just happened -- was always the first to be cut.

WHAT THIS DOES INSTEAD.

1. **Budget per domain, not per concatenation.** Each routed domain gets an equal
   share, then shares unused by files smaller than their allocation are
   redistributed to the files that need them. A three-domain path gets some of
   all three.
2. **Head + tail, not head alone.** A file over its share contributes its opening
   (which carries the file's framing and its oldest, most-settled rules) AND its
   ending (the newest rules), with an explicit marker naming exactly what was
   skipped. This is the part that fixes the append-only bias: a rule appended
   yesterday is reachable today.
3. **Cut on rule boundaries.** Splits land before a top-level `- ` bullet or a
   `#` heading, never mid-sentence and never mid-word.

The result is a deliberate, documented subset rather than an arbitrary prefix,
and it says so in the output so a reader knows what they did not get.

Usage:
    budget_rules.py --budget 4000 api security database
    budget_rules.py --budget 4000 --rules-dir path/to/rules flutter
"""

from __future__ import annotations

import argparse
import pathlib
import sys

DEFAULT_RULES_DIR = (
    pathlib.Path(__file__).resolve().parents[2] / "docs" / "rules"
)

# Below this, a head/tail split produces two fragments too small to carry a
# whole rule. Fall back to TAIL only -- never head only. A head-only excerpt is
# precisely the append-only bias this module exists to remove, so if the budget
# can only carry one end it must carry the end where the newest rules are.
# (Review round 1: the old head-only branch was reachable on 48 five-domain
# files whenever any trigger fired, silently restoring the original bug.)
MIN_SPLIT = 700

# Smallest useful fragment: roughly one appended rule bullet.
MIN_TAIL = 160

# Of an over-budget file's share, how much goes to the opening. The remainder
# goes to the ending. Weighted toward the head because a rule file opens with
# the framing that makes the rest readable; weighted enough toward the tail that
# the newest rules always survive.
HEAD_FRACTION = 0.55


def boundary_before(text: str, limit: int) -> int:
    """The largest cut point <= `limit` that starts a rule, heading or blank line.

    Falls back to the last newline, then to `limit`, so this always returns
    something usable rather than raising on an unusual file.
    """
    if limit >= len(text):
        return len(text)
    window = text[:limit]
    best = -1
    for marker in ("\n- ", "\n#", "\n\n"):
        best = max(best, window.rfind(marker))
    if best > 0:
        return best + 1  # keep the newline that ends the previous line
    nl = window.rfind("\n")
    return nl + 1 if nl > 0 else limit


def boundary_after(text: str, start: int) -> int:
    """The smallest cut point >= `start` that starts a rule, heading or line."""
    if start <= 0:
        return 0
    best = len(text)
    for marker in ("\n- ", "\n#", "\n\n"):
        found = text.find(marker, start)
        if found != -1:
            best = min(best, found + 1)
    if best < len(text):
        return best
    nl = text.find("\n", start)
    return nl + 1 if nl != -1 else start


def rule_start_before(text: str, pos: int) -> int:
    """Start of the `- ` bullet enclosing `pos`, or -1 if there is none.

    `boundary_after` only searches FORWARD, so a cut landing inside the last
    bullet of a file finds no later `\n- ` and falls through to the next
    newline -- the tail then opens on a continuation line and the newest rule
    arrives without the line that states what it is. Seek backwards instead,
    and only take it when the whole rule still fits the budget.
    """
    found = text.rfind("\n- ", 0, pos)
    return found + 1 if found != -1 else -1


def nbytes(text: str) -> int:
    """UTF-8 byte length. The injection cap counts bytes; these files contain
    em dashes and arrows, so `len()` undercounts by ~2 bytes each."""
    return len(text.encode("utf-8"))


def fit_bytes(text: str, limit: int, from_end: bool = False) -> str:
    """Longest prefix (or suffix) of `text` that fits `limit` UTF-8 bytes."""
    if limit <= 0:
        return ""
    if nbytes(text) <= limit:
        return text
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        chunk = text[-mid:] if from_end else text[:mid]
        if nbytes(chunk) <= limit:
            lo = mid
        else:
            hi = mid - 1
    return text[-lo:] if lo and from_end else text[:lo]


def excerpt(text: str, share: int, path: str) -> str:
    """`text` if it fits, else an excerpt that ALWAYS ends with the file's tail.

    The return value never exceeds `share` bytes: the marker is charged against
    the share before any content is sliced, rather than appended on top of it.
    """
    if nbytes(text) <= share:
        return text

    total = nbytes(text)

    def split_marker(skipped: int) -> str:
        return (
            f"\n[... {skipped} bytes of {path} skipped to fit the injection "
            f"budget ({share} B). The NEWEST rules follow; read the file for "
            f"the middle. ...]\n\n"
        )

    def tail_marker(skipped: int) -> str:
        return (
            f"\n[... the first {skipped} bytes of {path} were not injected "
            f"(budget {share} B). The NEWEST rules follow; read the file for "
            f"the rest. ...]\n\n"
        )

    # Size the markers against the whole file, so the real (smaller) skipped
    # count can only make them shorter than what we reserved.
    split_cost = nbytes(split_marker(total))
    tail_cost = nbytes(tail_marker(total))

    def tail_only() -> str:
        """The file's ending alone -- or nothing. Never the head alone."""
        room = max(share - tail_cost, 0)
        body = fit_bytes(text, room, from_end=True)
        start = boundary_after(text, len(text) - len(body))
        rule_start = rule_start_before(text, start)
        if rule_start != -1 and nbytes(text[rule_start:]) <= room:
            start = rule_start
        body = fit_bytes(text[start:], room, from_end=True)
        if not body:
            return ""
        return tail_marker(total - nbytes(body)) + body

    if share - split_cost < MIN_TAIL * 2 or share < MIN_SPLIT:
        # Too tight to carry both ends. Carry the tail.
        return tail_only()

    content = share - split_cost
    head = fit_bytes(text, int(content * HEAD_FRACTION))
    head_end = boundary_before(text, len(head))
    head = text[:head_end]

    tail = fit_bytes(text, max(content - nbytes(head), 0), from_end=True)
    tail_start = boundary_after(text, len(text) - len(tail))

    # Prefer opening the tail at the start of the rule rather than mid-bullet,
    # when the whole rule still fits. Buying it back out of the head is the
    # right trade: the head is context, the tail is the rule being quoted.
    rule_start = rule_start_before(text, tail_start)
    if rule_start != -1 and rule_start > head_end and nbytes(text[rule_start:]) <= content:
        tail_start = rule_start
        head = fit_bytes(text, max(content - nbytes(text[tail_start:]), 0))
        head_end = boundary_before(text, len(head))

    if tail_start <= head_end:
        # The halves met, so nothing is actually skipped -- but the file did not
        # fit, so emitting it whole would blow the budget. Fall back to the tail.
        return tail_only()

    if not text[tail_start:].strip():
        # The tail's share landed inside the file's final line: no boundary
        # (or only trailing blank lines) follows it, so the tail is EMPTY and
        # this would emit head + marker + nothing -- head-only, the exact
        # bias this module removes. `.strip()`, not `>= len(text)`: a final
        # rule ending in a blank line left a lone "\n" tail (PR #822). Latent with
        # today's files (final lines 14-83 B against a 286-486 B tail share),
        # but nothing caps a rule's length (todo 391).
        return tail_only()

    return text[:head_end] + split_marker(tail_start - head_end) + text[tail_start:]


def allocate(sizes: dict[str, int], budget: int) -> dict[str, int]:
    """Equal shares, with the slack from small files given to large ones.

    Without redistribution a path routing to `typescript` (1224 B) and `testing`
    (41514 B) would waste most of typescript's half. Repeats until no file is
    newly satisfied, so slack cascades rather than being handed out once.
    """
    remaining = dict(sizes)
    shares: dict[str, int] = {}
    pot = budget

    while remaining:
        even = pot // len(remaining)
        satisfied = {n: s for n, s in remaining.items() if s <= even}
        if not satisfied:
            for name in remaining:
                shares[name] = even
            break
        for name, size in satisfied.items():
            shares[name] = size
            pot -= size
            del remaining[name]

    return shares


def assemble(domains: list[str], budget: int, rules_dir: pathlib.Path) -> str:
    files = {}
    for domain in domains:
        path = rules_dir / f"{domain}.md"
        if path.is_file():
            files[domain] = path.read_text(encoding="utf-8")
    if not files:
        return ""

    # The per-domain header costs bytes too; charge for it up front so the
    # assembled output actually lands under `budget` rather than just over it.
    overhead = sum(nbytes(f"\n[RULES — {d}]\n") for d in files)
    shares = allocate(
        {d: nbytes(t) for d, t in files.items()}, max(budget - overhead, 0)
    )

    out = []
    for domain in domains:
        if domain not in files:
            continue
        out.append(f"\n[RULES — {domain}]\n")
        out.append(excerpt(files[domain], shares[domain], f"docs/rules/{domain}.md"))
    return "".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("domains", nargs="*")
    parser.add_argument("--budget", type=int, required=True)
    parser.add_argument("--rules-dir", type=pathlib.Path, default=DEFAULT_RULES_DIR)
    args = parser.parse_args()

    if not args.domains or args.budget <= 0:
        return 0
    sys.stdout.write(assemble(args.domains, args.budget, args.rules_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
