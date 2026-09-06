#!/usr/bin/env python3
"""Fail a pull request that ADDS a dependency advisory.

Why a merge-base diff rather than an "are there open alerts?" check
------------------------------------------------------------------
The repo carries a real advisory backlog (52 distinct GHSAs as of 2026-09-05).
A gate that reports total open alerts would be red on its first run and every
run after, which is exactly how the weekly scan became background noise. This
gate asks a strictly narrower question: *did THIS pull request introduce an
advisory that its base does not already have?*

Both sides are audited in the SAME workflow run, against the same advisory
database. That matters: a newly published CVE lands on base and head
simultaneously, so it cancels out and cannot block an unrelated branch.
Comparing against a stored baseline instead would re-create the "blocked every
open branch at once" incidents (bleach, PyJWT, pillow) that made the PR half of
security-scan.yml advisory-only in the first place.

Alias handling
--------------
An advisory is one record with several names — GHSA-g76p-4vg5-f4qh,
CVE-2026-31236 and PYSEC-2026-400 are one advisory. Base and head reports can
name it differently if the database shifts its canonical id between two audits
minutes apart. So a head advisory counts as new only when *none* of its
ids/aliases appears anywhere in the base key set. Comparing bare `id` strings
would report a rename as a new vulnerability.

Usage:
    new_vuln_gate.py --base-pip base.json --head-pip head.json
                     --base-npm base.json --head-npm head.json
                     [--warn-only] [--format github]

Either ecosystem pair may be omitted; that ecosystem is reported as skipped.
Passing only one half of a pair is an error rather than a silent skip — a
half-configured gate that always passes is worse than no gate at all.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys


class GateError(Exception):
    """The gate cannot answer the question it was asked."""


def _load(path: pathlib.Path) -> dict:
    if not path.exists():
        raise GateError(
            f"{path} does not exist — the gate cannot tell whether this PR adds "
            "an advisory, so it is failing rather than passing silently"
        )
    try:
        return json.loads(path.read_text() or "{}")
    except json.JSONDecodeError as exc:
        raise GateError(f"{path} is not valid JSON: {exc}") from exc


def pip_advisories(report: dict) -> dict[str, set[str]]:
    """Map a display label -> every id/alias naming that advisory, from pip-audit JSON."""
    found: dict[str, set[str]] = {}
    for dep in report.get("dependencies", []) or []:
        name = dep.get("name", "?")
        version = dep.get("version", "?")
        for vuln in dep.get("vulns", []) or []:
            vuln_id = vuln.get("id")
            if not vuln_id:
                continue
            keys = {vuln_id, *(a for a in (vuln.get("aliases") or []) if a)}
            found.setdefault(f"{vuln_id} ({name} {version})", set()).update(keys)
    return found


def npm_advisories(report: dict) -> dict[str, set[str]]:
    """Map a display label -> ids naming that advisory, from `npm audit --json`.

    npm nests the advisory under `vulnerabilities[pkg].via[]`, where an entry is
    either a dict (the advisory itself) or a bare string naming another package
    the vulnerability flows through. Only the dicts carry an id, so the strings
    are skipped — counting them would inflate every diff with transitive edges.
    """
    found: dict[str, set[str]] = {}
    for name, entry in (report.get("vulnerabilities") or {}).items():
        for via in entry.get("via") or []:
            if not isinstance(via, dict):
                continue
            url = via.get("url") or ""
            ghsa = url.rstrip("/").rsplit("/", 1)[-1] if "advisories/" in url else ""
            source = via.get("source")
            keys = {k for k in (ghsa, str(source) if source else "") if k}
            if not keys:
                continue
            label = f"{ghsa or source} ({name}, {via.get('severity', '?')})"
            found.setdefault(label, set()).update(keys)
    return found


def new_advisories(base: dict[str, set[str]], head: dict[str, set[str]]) -> list[str]:
    """Advisories in head whose every id/alias is absent from base."""
    base_keys: set[str] = set()
    for keys in base.values():
        base_keys |= keys
    return sorted(label for label, keys in head.items() if not (keys & base_keys))


def compare(
    base_path: pathlib.Path | None,
    head_path: pathlib.Path | None,
    extract,
    ecosystem: str,
) -> tuple[list[str], str]:
    """Return (new advisory labels, one-line status)."""
    if base_path is None and head_path is None:
        return [], f"{ecosystem}: skipped (no manifest change in this PR)"
    if base_path is None or head_path is None:
        raise GateError(
            f"{ecosystem}: got only one side of the comparison "
            f"(base={base_path}, head={head_path}). A half-configured gate "
            "would pass unconditionally, so this is an error."
        )
    base = extract(_load(base_path))
    head = extract(_load(head_path))
    added = new_advisories(base, head)
    return added, (
        f"{ecosystem}: {len(base)} advisories on base, {len(head)} on head, "
        f"{len(added)} new"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-pip", type=pathlib.Path)
    parser.add_argument("--head-pip", type=pathlib.Path)
    parser.add_argument("--base-npm", type=pathlib.Path)
    parser.add_argument("--head-npm", type=pathlib.Path)
    parser.add_argument(
        "--warn-only",
        action="store_true",
        help="Report and exit 0. For authors whose PRs exist to close "
        "advisories (Dependabot), where blocking would be backwards.",
    )
    parser.add_argument(
        "--format",
        choices=("plain", "github"),
        default="plain",
        help="`github` adds ::error/::warning workflow annotations.",
    )
    args = parser.parse_args(argv)

    try:
        pip_new, pip_status = compare(
            args.base_pip, args.head_pip, pip_advisories, "pip-audit"
        )
        npm_new, npm_status = compare(
            args.base_npm, args.head_npm, npm_advisories, "npm audit"
        )
    except GateError as exc:
        print(f"error: {exc}", file=sys.stderr)
        if args.format == "github":
            print(f"::error::new-vuln-gate could not run: {exc}")
        return 1

    print(pip_status)
    print(npm_status)

    added = pip_new + npm_new
    if not added:
        print("\nNo new dependency advisories introduced by this pull request.")
        return 0

    level = "warning" if args.warn_only else "error"
    print(f"\n{len(added)} advisory/advisories introduced by this pull request:")
    for label in added:
        print(f"  - {label}")
        if args.format == "github":
            print(f"::{level}::new dependency advisory introduced: {label}")

    if args.warn_only:
        print(
            "\nNot blocking (--warn-only). This PR exists to move dependency "
            "versions, and a bump that closes several advisories may surface a "
            "new transitive one; blocking it would be backwards."
        )
        return 0
    print(
        "\nFix the advisory or pick a version that does not carry it. If it "
        "genuinely has no fix, add an entry to .github/security-suppressions.yml "
        "(with expires/owner/tracked_by) rather than hand-adding an ignore flag."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
