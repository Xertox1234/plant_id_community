#!/usr/bin/env python3
"""Validate that every .claude/agents/*.md frontmatter is loadable (todo 245).

Guards against the exact regression fixed by todo 229: a `description`
frontmatter field written as a multi-line block (e.g. a bare `<example>` tag
at column 0) is silently rejected by the Claude Code agent loader — the agent
just never registers, with no error anywhere in the toolchain. The loadable
shape is narrower than YAML: every frontmatter line must be a single physical
`key: value` field, no blank lines, no continuation/tag lines. Do NOT swap
this for yaml.safe_load — it also rejects the colon/quote-bearing single-line
descriptions the WORKING agents use.

Run: python3 scripts/inject/check_agent_frontmatter.py
Wired into .pre-commit-config.yaml as a local hook scoped to .claude/agents/*.md.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

AGENTS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "agents"
FIELD_RE = re.compile(r"^[a-z_][a-z0-9_]*:")
REQUIRED_KEYS = ("name", "description")


def check_frontmatter(path: Path, lines: list) -> list:
    """Return error strings for `path`'s frontmatter `lines`; empty if loadable."""
    if not lines or lines[0] != "---":
        return [f"{path}:1: frontmatter must start with a bare '---' line"]

    try:
        end = lines.index("---", 1)
    except ValueError:
        return [f"{path}:1: no closing '---' delimiter found"]

    errors = []
    seen_keys = set()
    for i, line in enumerate(lines[1:end], start=2):
        if not FIELD_RE.match(line):
            errors.append(f"{path}:{i}: not a single-line 'key: value' field: {line!r}")
            continue
        seen_keys.add(line.split(":", 1)[0])

    for key in REQUIRED_KEYS:
        if key not in seen_keys:
            errors.append(f"{path}:{end + 1}: missing required frontmatter key {key!r}")

    return errors


def main() -> int:
    if not AGENTS_DIR.is_dir():
        print(f"error: {AGENTS_DIR} not found", file=sys.stderr)
        return 1

    all_errors = []
    for path in sorted(AGENTS_DIR.glob("*.md")):
        all_errors.extend(check_frontmatter(path, path.read_text().splitlines()))

    if all_errors:
        for err in all_errors:
            print(err, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
