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
# whole rule, and the marker costs more than the content. Emit head only.
MIN_SPLIT = 700

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


def excerpt(text: str, share: int, path: str) -> str:
    """`text` if it fits, else head + marker + tail, cut on rule boundaries."""
    if len(text) <= share:
        return text

    if share < MIN_SPLIT:
        head_end = boundary_before(text, share)
        skipped = len(text) - head_end
        return (
            text[:head_end]
            + f"\n[... {skipped} more bytes of {path} not injected "
            f"(budget {share} B). Read the file for the rest.]\n"
        )

    head_limit = int(share * HEAD_FRACTION)
    head_end = boundary_before(text, head_limit)

    tail_bytes = share - head_end
    tail_start = boundary_after(text, max(head_end, len(text) - tail_bytes))

    if tail_start <= head_end:  # the two halves met; nothing was skipped
        return text

    skipped = tail_start - head_end
    return (
        text[:head_end]
        + f"\n[... {skipped} bytes of {path} skipped to fit the injection "
        f"budget ({share} B). The NEWEST rules follow; read the file for the "
        f"middle. ...]\n\n"
        + text[tail_start:]
    )


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
    overhead = sum(len(f"\n[RULES — {d}]\n") for d in files)
    shares = allocate({d: len(t) for d, t in files.items()}, max(budget - overhead, 0))

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
