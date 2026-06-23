#!/usr/bin/env python3
"""Resolve repo-relative paths to docs/rules/ domain labels.

Single source of truth = docs/rules/routing.json. This is the one matcher shared
by .claude/hooks/inject-patterns.sh (edit-time), .claude/hooks/kimi-review.sh
(commit gate), and .claude/skills/codify/SKILL.md Step 1. Adding/renaming a domain
means editing routing.json only — never this script.

Input : repo-relative paths, one per line on stdin (or as argv). kimi passes the
        whole staged file list; inject passes a single path.
Output : the deduped union of matched domains, comma-joined, on one line.
        Empty output when nothing matches.

Matching (per path, then unioned):
  Rules are evaluated top-to-bottom. ORDER IS LOAD-BEARING.
    - mode "additive": if any glob matches, add its domains.
    - mode "fallback": apply only if NO domain collected yet at this position.
  This reproduces the original ordered if-blocks exactly, including the
  backend/*.py fallback stacking with a later firebase additive rule.

Fail-open: any error (missing/unparseable routing.json, bad input) prints nothing
and exits 0. Both hooks treat empty output as "no domain rules" and proceed.
"""
from __future__ import annotations

import json
import sys
from fnmatch import fnmatchcase
from pathlib import Path

ROUTING_JSON = Path(__file__).resolve().parents[2] / "docs" / "rules" / "routing.json"


def _domains_for(path: str, rules: list) -> list:
    """Ordered matcher for one path. fnmatchcase == bash [[ == ]] (case-sensitive,
    '*' spans '/'). Fallback rules fire only while the set is still empty."""
    acc: list = []
    for rule in rules:
        mode = rule.get("mode", "additive")
        if mode == "fallback" and acc:
            continue
        globs = rule.get("globs", [])
        if any(fnmatchcase(path, g) for g in globs):
            for domain in rule.get("domains", []):
                if domain not in acc:
                    acc.append(domain)
    return acc


def main() -> int:
    try:
        rules = json.loads(ROUTING_JSON.read_text(encoding="utf-8")).get("rules", [])
    except Exception:
        return 0  # fail-open: no routing → no domains

    if len(sys.argv) > 1:
        paths = sys.argv[1:]
    else:
        paths = sys.stdin.read().splitlines()

    union: list = []
    for raw in paths:
        path = raw.strip()
        if not path:
            continue
        for domain in _domains_for(path, rules):
            if domain not in union:
                union.append(domain)

    if union:
        sys.stdout.write(",".join(union))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)  # never let the matcher break a hook
