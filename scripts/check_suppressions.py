#!/usr/bin/env python3
"""Validate .github/security-suppressions.yml and expire stale suppressions.

Background
----------
pip-audit's ``--ignore-vuln`` hides an advisory unconditionally — including
after a fix ships. That is how eight advisories stayed invisible for two
months while the weekly scan kept "passing" the parts it could still see.
The list also pointed at "todo 089" for tracking; that todo was real, and
completed, and archived. A pointer to a closed artifact reads as live
tracking forever.

This script makes both failures loud:

--emit-flags   Print the ``--ignore-vuln`` flags for the scan job. The
               workflow no longer hardcodes them, so data and flags cannot
               drift apart.

--validate     Schema and policy only. Never fails from the passage of
               time, so it is safe to run on every pull request.

--recheck      Reads the UNSUPPRESSED pip-audit JSON report the scan job
               already writes, and fails when a suppression has outlived
               its reason. Intended for schedule/dispatch runs.

Why --recheck consults fix_versions rather than "is there a newer release":
docs/rules/security.md already warns that an empty Fix Versions column does
not mean unfixable. The inverse holds too — nltk 3.10.3 merely *existing*
does not prove PYSEC-2026-597 is fixed, and in the real report it still
carries no fix version. The audit report is the authoritative answer, and
the job generates it for free.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import sys

try:
    import yaml
except ImportError:  # pragma: no cover - dependency is present in CI
    sys.exit("check_suppressions: PyYAML is required (pip install pyyaml)")

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SUPPRESSIONS = REPO_ROOT / ".github" / "security-suppressions.yml"
TODOS = REPO_ROOT / "todos"

# Also the shell-injection guard: these ids are interpolated into a command line.
VULN_ID = re.compile(r"^[A-Za-z0-9._-]+$")

REQUIRED_FIELDS = (
    "id",
    "package",
    "pinned",
    "reason",
    "clears_when",
    "added",
    "expires",
    "owner",
    "tracked_by",
)


class SuppressionError(Exception):
    """A suppression entry is malformed or has outlived its reason."""


def load(path: pathlib.Path = SUPPRESSIONS) -> dict:
    if not path.exists():
        raise SuppressionError(f"{path} does not exist")
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        raise SuppressionError(f"{path} is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise SuppressionError(f"{path} must contain a mapping at the top level")
    return data


def entries(data: dict) -> list[dict]:
    got = data.get("pip_audit") or []
    if not isinstance(got, list):
        raise SuppressionError("`pip_audit:` must be a list of entries")
    return got


def _parse_date(value, field: str, vuln_id: str) -> dt.date:
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise SuppressionError(
            f"{vuln_id}: `{field}` must be an ISO date (YYYY-MM-DD), got {value!r}"
        ) from exc


def resolve_todo(issue_id: str) -> pathlib.Path | None:
    """Find a todo by id in either todos/ or todos/archive/.

    Deliberately id-based rather than path-based: a path breaks the moment
    `completing-todos` runs `git mv` into archive/, which is the failure this
    field exists to prevent.
    """
    for pattern in (f"{issue_id}-*.md", f"archive/{issue_id}-*.md"):
        matches = sorted(TODOS.glob(pattern))
        if matches:
            return matches[0]
    return None


# `completed` is the live convention; the rest are legacy drift found in
# todos/archive/ (ready, resolved, complete, closed, skipped). Any of them means
# the todo is not tracking anything any more.
TERMINAL_STATUSES = {"completed", "complete", "resolved", "closed", "skipped"}


def todo_is_closed(path: pathlib.Path) -> bool:
    """A todo stops being live tracking when it is archived or terminal.

    Location is checked first and is decisive: `completing-todos` archives by
    `git mv` into todos/archive/, and 13 archived files still say
    `status: pending` — trusting the status string alone would call those live.
    """
    try:
        if path.resolve().parent.name == "archive":
            return True
    except OSError:
        pass
    for line in path.read_text().splitlines()[:20]:
        if line.startswith("status:"):
            return line.split(":", 1)[1].strip().lower() in TERMINAL_STATUSES
    return False


def validate(data: dict) -> list[str]:
    """Schema + policy. Returns problems; never time-dependent."""
    problems: list[str] = []
    policy = data.get("policy") or {}
    max_days = int(policy.get("max_expiry_days", 180))

    seen: set[str] = set()
    for entry in entries(data):
        vuln_id = str(entry.get("id", "<missing id>"))

        for field in REQUIRED_FIELDS:
            value = entry.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                problems.append(f"{vuln_id}: missing or empty `{field}`")

        if not VULN_ID.match(vuln_id):
            problems.append(
                f"{vuln_id!r}: id must match {VULN_ID.pattern} "
                "(it is interpolated into a command line)"
            )
        if vuln_id in seen:
            problems.append(f"{vuln_id}: duplicate entry")
        seen.add(vuln_id)

        if entry.get("added") and entry.get("expires"):
            try:
                added = _parse_date(entry["added"], "added", vuln_id)
                expires = _parse_date(entry["expires"], "expires", vuln_id)
            except SuppressionError as exc:
                problems.append(str(exc))
            else:
                if expires <= added:
                    problems.append(f"{vuln_id}: `expires` must be after `added`")
                elif (expires - added).days > max_days:
                    problems.append(
                        f"{vuln_id}: window of {(expires - added).days}d exceeds "
                        f"policy.max_expiry_days ({max_days}d)"
                    )

        tracked_by = entry.get("tracked_by")
        if tracked_by and resolve_todo(str(tracked_by)) is None:
            problems.append(
                f"{vuln_id}: `tracked_by: {tracked_by}` resolves to no todo in "
                "todos/ or todos/archive/ — a suppression must point at an "
                "artifact a script can find"
            )

    return problems


def load_report(path: pathlib.Path) -> dict[str, list[str]]:
    """Map every advisory id/alias in an unsuppressed pip-audit report to its fix versions."""
    report = json.loads(path.read_text())
    fixes: dict[str, list[str]] = {}
    for dep in report.get("dependencies", []):
        for vuln in dep.get("vulns", []):
            fix_versions = [v for v in (vuln.get("fix_versions") or []) if v]
            for key in {vuln.get("id"), *(vuln.get("aliases") or [])}:
                if not key:
                    continue
                # Union, not replace. A real report lists the same advisory more
                # than once with different fix sets — Twisted PYSEC-2026-160
                # appears with ["26.4.0"] and with ["26.4.0rc2"]. Replacing would
                # let the message show only the release candidate, and "still
                # RC-only" is exactly the stale reasoning that kept this
                # suppression alive after 26.4.0 stable shipped.
                merged = fixes.setdefault(key, [])
                for version in fix_versions:
                    if version not in merged:
                        merged.append(version)
    return fixes


def recheck(data: dict, report_path: pathlib.Path | None, today: dt.date) -> list[str]:
    """Time- and fix-dependent checks. Schedule/dispatch only."""
    problems: list[str] = []
    fixes = load_report(report_path) if report_path and report_path.exists() else {}
    if report_path and not report_path.exists():
        problems.append(
            f"pip-audit report not found at {report_path} — the recheck cannot "
            "tell whether a fix has shipped, so it is failing rather than "
            "passing silently"
        )

    for entry in entries(data):
        vuln_id = str(entry.get("id", "<missing id>"))

        if entry.get("expires"):
            try:
                expires = _parse_date(entry["expires"], "expires", vuln_id)
            except SuppressionError as exc:
                problems.append(str(exc))
            else:
                if expires < today:
                    problems.append(
                        f"{vuln_id} ({entry.get('package')}): suppression expired "
                        f"{expires.isoformat()}. Re-assess it and either fix the "
                        "advisory or renew the entry with a fresh rationale."
                    )

        if vuln_id in fixes and fixes[vuln_id]:
            problems.append(
                f"{vuln_id} ({entry.get('package')} {entry.get('pinned')}): a fix "
                f"has shipped — pip-audit reports fix_versions="
                f"{','.join(fixes[vuln_id])}. Suppression rationale was: "
                f"{str(entry.get('clears_when', '')).strip()}"
            )

        tracked_by = entry.get("tracked_by")
        if tracked_by:
            todo = resolve_todo(str(tracked_by))
            if todo is not None and todo_is_closed(todo):
                problems.append(
                    f"{vuln_id}: `tracked_by: {tracked_by}` points at {todo.name}, "
                    "which is COMPLETED. A closed todo cannot track anything — "
                    "repoint it at an open todo or drop the suppression. "
                    "(This is the todo-089 failure, caught mechanically.)"
                )

    return problems


def emit_flags(data: dict) -> str:
    flags: list[str] = []
    for entry in entries(data):
        vuln_id = str(entry.get("id", ""))
        if not VULN_ID.match(vuln_id):
            raise SuppressionError(f"refusing to emit unsafe vuln id {vuln_id!r}")
        flags += ["--ignore-vuln", vuln_id]
    return " ".join(flags)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--emit-flags", action="store_true")
    mode.add_argument("--validate", action="store_true")
    mode.add_argument("--recheck", action="store_true")
    parser.add_argument("--report", type=pathlib.Path, default=None)
    parser.add_argument(
        "--warn-only",
        action="store_true",
        help="Print problems and exit 0 (advisory-only PR runs).",
    )
    parser.add_argument("--file", type=pathlib.Path, default=SUPPRESSIONS)
    args = parser.parse_args(argv)

    try:
        data = load(args.file)
    except SuppressionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.emit_flags:
        try:
            print(emit_flags(data))
        except SuppressionError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        return 0

    if args.recheck:
        problems = recheck(data, args.report, dt.date.today())
        label = "recheck"
    else:  # --validate is the default
        problems = validate(data)
        label = "validate"

    if not problems:
        print(f"check_suppressions {label}: OK ({len(entries(data))} entries)")
        return 0

    stream = sys.stdout if args.warn_only else sys.stderr
    print(f"check_suppressions {label}: {len(problems)} problem(s)", file=stream)
    for problem in problems:
        print(f"  - {problem}", file=stream)
    if args.warn_only:
        print("::warning::suppression drift detected (advisory-only on this run)")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
