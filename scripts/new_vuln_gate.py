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

Which trees get audited
-----------------------
The repo carries TWO lockfile-bearing npm manifests: the root one — the
Cloudflare Workers deploy artifact, installed with `npm clean-install` and
shipped with `npx wrangler versions upload` — and `web/`. Every npm step in
security-scan.yml used to hardcode `web/`, so a PR that changed only the ROOT
lockfile audited `web/` against `web/` and printed a confident `0 advisories on
base, 0 on head, 0 new` about a tree it had never read (measured on PR #669).
A scope predicate that says "this PR is relevant" plus an action pointed at a
different tree yields a false green, not a skip.

So the manifest set lives HERE, in NPM_MANIFEST_DIRS, guarded by a drift test,
and the workflow loops over what `--list-npm-dirs` / `--scope` report rather
than over a directory name written into YAML. See todo 356.

Alias handling
--------------
An advisory is one record with several names — GHSA-g76p-4vg5-f4qh,
CVE-2026-31236 and PYSEC-2026-400 are one advisory. Base and head reports can
name it differently if the database shifts its canonical id between two audits
minutes apart. So a head advisory counts as new only when *none* of its
ids/aliases appears anywhere in the base key set. Comparing bare `id` strings
would report a rename as a new vulnerability.

Usage:
    # what the workflow asks first
    new_vuln_gate.py --list-npm-dirs
    new_vuln_gate.py --scope --changed-files <path|->

    # the gate itself
    new_vuln_gate.py --base-pip base.json --head-pip head.json
                     --npm-pair .   base-npm-root.json head-npm-root.json
                     --npm-pair web base-npm-web.json  head-npm-web.json
                     [--warn-only] [--format github]

Either ecosystem may be omitted; that ecosystem is reported as skipped. Passing
only one half of the pip pair is an error rather than a silent skip — a
half-configured gate that always passes is worse than no gate at all. Each npm
manifest is compared against ITS OWN base: merging the reports into one set
would let an advisory already present in `web/`'s base cancel the same advisory
newly appearing in the root tree.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from collections.abc import Iterable

# Every directory in this repo that carries a package-lock.json, in the order
# they are reported. "." is the Cloudflare Workers deploy artifact.
# ManifestDriftTests in scripts/test_new_vuln_gate.py fails if a third lockfile
# appears without being added here, so no manifest can go unscanned the way the
# root one did for the whole life of security-scan.yml.
NPM_MANIFEST_DIRS: tuple[str, ...] = (".", "web")

_NPM_FILENAMES = ("package.json", "package-lock.json")

# Kept identical to the predicate this replaced in security-scan.yml.
_PIP_MANIFEST_RE = re.compile(r"^backend/requirements.*\.txt$")


class GateError(Exception):
    """The gate cannot answer the question it was asked."""


def npm_dirs_from_changes(changed: Iterable[str]) -> list[str]:
    """The NPM_MANIFEST_DIRS whose manifest appears in this diff, in constant order.

    Anchored to the constant rather than to a path regex. A `package.json` with
    no lockfile beside it (`design_reference/`) cannot be audited from a
    lockfile at all, and a regex like `(^|/)package\\.json$` would scope it in
    and then crash the audit step on the missing lockfile.
    """
    paths = {p.strip() for p in changed if p.strip()}
    hit = []
    for directory in NPM_MANIFEST_DIRS:
        prefix = "" if directory == "." else f"{directory}/"
        if any(f"{prefix}{name}" in paths for name in _NPM_FILENAMES):
            hit.append(directory)
    return hit


def pip_changed(changed: Iterable[str]) -> bool:
    """Whether this diff touches a backend requirements file.

    Deliberately broader than the file the audit actually reads
    (`backend/requirements.txt`): `backend/requirements-dev.txt` is a pinless
    `-r requirements.txt` overlay, so it has the same answer by construction.
    Scoping IN a file with the same answer is harmless; scoping one OUT would be
    a silent hole. `test_requirements_dev_carries_no_pins` guards the "by
    construction" half — the day that file gains a pin of its own, it goes red
    here rather than going falsely green in CI.
    """
    return any(_PIP_MANIFEST_RE.match(p.strip()) for p in changed)


def _read_changed(source: str) -> list[str]:
    """Read a `git diff --name-only` listing from a path, or from stdin for '-'."""
    text = sys.stdin.read() if source == "-" else pathlib.Path(source).read_text()
    return [line.strip() for line in text.splitlines() if line.strip()]


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
    # nargs=3 rather than separate --base-npm/--head-npm: it makes "half a pair"
    # structurally impossible for npm, and it is the only shape that can carry
    # WHICH manifest a pair belongs to. Repeat it once per changed manifest.
    parser.add_argument(
        "--npm-pair",
        nargs=3,
        action="append",
        default=[],
        metavar=("DIR", "BASE", "HEAD"),
        help="An npm manifest directory and its base/head audit reports. "
        "Repeatable; each manifest is compared against its own base.",
    )
    parser.add_argument(
        "--list-npm-dirs",
        action="store_true",
        help="Print NPM_MANIFEST_DIRS space-separated and exit. The workflow "
        "loops over this instead of hardcoding a directory name.",
    )
    parser.add_argument(
        "--scope",
        action="store_true",
        help="Print `pip=` and `npm_dirs=` for the given diff and exit. Written "
        "straight into $GITHUB_OUTPUT by security-scan.yml.",
    )
    parser.add_argument(
        "--changed-files",
        help="Path to `git diff --name-only` output, or - for stdin. "
        "Required by --scope.",
    )
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

    if args.list_npm_dirs:
        print(" ".join(NPM_MANIFEST_DIRS))
        return 0

    if args.scope:
        if not args.changed_files:
            parser.error("--scope requires --changed-files")
        changed = _read_changed(args.changed_files)
        print(f"pip={'true' if pip_changed(changed) else 'false'}")
        print(f"npm_dirs={' '.join(npm_dirs_from_changes(changed))}")
        return 0

    try:
        pip_new, pip_status = compare(
            args.base_pip, args.head_pip, pip_advisories, "pip-audit"
        )
        npm_new: list[str] = []
        npm_statuses: list[str] = []
        if not args.npm_pair:
            _, status = compare(None, None, npm_advisories, "npm audit")
            npm_statuses.append(status)
        for directory, base, head in args.npm_pair:
            added, status = compare(
                pathlib.Path(base),
                pathlib.Path(head),
                npm_advisories,
                f"npm audit ({directory})",
            )
            # The directory rides on the label so a root advisory and a web one
            # can never be read as the same finding.
            npm_new.extend(f"{directory}: {label}" for label in added)
            npm_statuses.append(status)
    except GateError as exc:
        print(f"error: {exc}", file=sys.stderr)
        if args.format == "github":
            print(f"::error::new-vuln-gate could not run: {exc}")
        return 1

    print(pip_status)
    for status in npm_statuses:
        print(status)

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
