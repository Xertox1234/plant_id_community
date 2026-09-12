#!/usr/bin/env python3
"""Fail when DEPLOYED Firebase security rules differ from the committed ones.

Why this exists: twice now a rules change was committed and never deployed — todo
224 (`firestore:rules`) and the 2026-05-23 Storage tightening that sat undeployed
for 3.5 months (todo 383 item 1). Both were found by accident. A file in git plus a
`firebase.json` entry plus an old green deploy log are all compatible with
production running something else, so the only trustworthy source is the Rules API.

Three outcomes, never two — a check that cannot tell must not report "clean":

    0  MATCH        every release's deployed source == its committed file
    1  DRIFT        at least one differs (or a release could not be mapped)
    2  INDETERMINATE credentials missing, API unreachable, config unreadable

Usage:
    python3 scripts/check_firebase_rules_drift.py [--credentials path/to/sa.json] [--quiet]

Credentials resolve in this order: --credentials, GOOGLE_APPLICATION_CREDENTIALS,
google.auth.default(). The service account needs only `roles/firebaserules.viewer`.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

EXIT_MATCH = 0
EXIT_DRIFT = 1
EXIT_INDETERMINATE = 2

API = "https://firebaserules.googleapis.com/v1"

# firebase.json key -> the release-name prefix the Rules API uses for it.
# A release whose name matches no prefix here is an ERROR, not something to skip:
# adding a bucket or a second database must not silently drop out of coverage.
RELEASE_PREFIXES = {
    "cloud.firestore": "firestore",
    "firebase.storage": "storage",
}


class Indeterminate(Exception):
    """We could not establish the deployed state. Never downgrade this to 'clean'."""


def repo_root(start: Path) -> Path:
    for d in (start, *start.parents):
        if (d / "firebase.json").is_file():
            return d
    raise Indeterminate(f"no firebase.json found at or above {start}")


def committed_rule_files(root: Path) -> dict[str, Path]:
    """Map each configured product to its committed rules file, via firebase.json."""
    try:
        config = json.loads((root / "firebase.json").read_text())
    except (OSError, ValueError) as exc:
        raise Indeterminate(f"cannot read firebase.json: {exc}") from exc

    mapping: dict[str, Path] = {}
    for product in ("firestore", "storage"):
        section = config.get(product)
        if not section:
            continue
        # firebase.json allows a list of targets as well as a single object.
        entries = section if isinstance(section, list) else [section]
        for entry in entries:
            rules = entry.get("rules")
            if not rules:
                continue
            path = root / rules
            if not path.is_file():
                raise Indeterminate(f"firebase.json points at a missing file: {rules}")
            mapping[product] = path
    if not mapping:
        raise Indeterminate("firebase.json configures no rules files")
    return mapping


def project_id(root: Path) -> str:
    try:
        rc = json.loads((root / ".firebaserc").read_text())
        return rc["projects"]["default"]
    except (OSError, ValueError, KeyError) as exc:
        raise Indeterminate(f"cannot read the default project from .firebaserc: {exc}") from exc


def build_session(credentials_path: str | None):
    try:
        import google.auth
        import google.auth.transport.requests
        from google.oauth2 import service_account
    except ImportError as exc:  # pragma: no cover - exercised only without the dep
        raise Indeterminate(f"google-auth is not installed ({exc})") from exc

    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    path = credentials_path or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    try:
        if path:
            if not Path(path).is_file():
                raise Indeterminate(f"credentials file does not exist: {path}")
            # Not every credentials file is a service-account key. Workload Identity
            # Federation — what CI uses, so that no key material exists anywhere —
            # points GOOGLE_APPLICATION_CREDENTIALS at an "external_account" config,
            # and from_service_account_file() cannot parse one. Dispatch on the
            # declared type and hand every other flavour (external_account,
            # authorized_user, impersonated_service_account) to google.auth.default(),
            # which understands them all.
            if credential_type(path) == "service_account":
                creds = service_account.Credentials.from_service_account_file(path, scopes=scopes)
            else:
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = path
                creds, _ = google.auth.default(scopes=scopes)
        else:
            creds, _ = google.auth.default(scopes=scopes)
    except Indeterminate:
        raise
    except Exception as exc:
        raise Indeterminate(f"could not load credentials: {type(exc).__name__}: {exc}") from exc
    return google.auth.transport.requests.AuthorizedSession(creds)


def credential_type(path: str) -> str:
    """The `type` field of a Google credentials file ("service_account", "external_account", ...).

    Returns "" when the file has no type field. Raises Indeterminate — never
    silently defaults — when the file cannot be read or is not JSON: guessing
    here would mean picking the wrong loader and reporting a credentials bug as
    a rules problem.
    """
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        raise Indeterminate(
            f"credentials file is not readable JSON: {path} ({type(exc).__name__}: {exc})"
        ) from exc
    if not isinstance(data, dict):
        raise Indeterminate(f"credentials file is not a JSON object: {path}")
    return data.get("type", "")


def api_get(session, url: str) -> dict:
    try:
        response = session.get(url, timeout=60)
    except Exception as exc:
        raise Indeterminate(f"request to {url} failed: {type(exc).__name__}: {exc}") from exc
    if response.status_code != 200:
        raise Indeterminate(f"{url} returned HTTP {response.status_code}: {response.text[:200]}")
    try:
        return response.json()
    except ValueError as exc:
        raise Indeterminate(f"{url} returned non-JSON: {exc}") from exc


def release_short_name(release: dict) -> str:
    name = release.get("name", "")
    _, _, short = name.partition("/releases/")
    return short or name


def classify(short_name: str) -> str | None:
    """Return the firebase.json product for a release name, or None if unmappable."""
    for prefix, product in RELEASE_PREFIXES.items():
        if short_name == prefix or short_name.startswith(prefix + "/"):
            return product
    return None


def deployed_source(session, ruleset_name: str) -> str:
    ruleset = api_get(session, f"{API}/{ruleset_name}")
    files = (ruleset.get("source") or {}).get("files") or []
    if len(files) != 1:
        # Comparing files[0] when there are two is the same silent gap as skipping
        # an unmapped release, so refuse rather than guess.
        raise Indeterminate(f"{ruleset_name} has {len(files)} source files, expected exactly 1")
    return files[0].get("content", "")


def last_commit_time(root: Path, path: Path) -> datetime | None:
    """Best-effort: when was this rules file last changed in git? Diagnostic only."""
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", str(path.relative_to(root))],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    stamp = out.stdout.strip()
    if out.returncode != 0 or not stamp:
        return None
    try:
        return datetime.fromisoformat(stamp).astimezone(timezone.utc)
    except ValueError:
        return None


def has_uncommitted_changes(root: Path, path: Path) -> bool:
    """Does the working tree hold edits to this file that no commit contains yet?

    Load-bearing for direction reporting: last_commit_time() describes the last
    COMMITTED version, so an uncommitted edit makes the repo look stale when it is
    actually ahead. Unknown (git unavailable) is treated as clean, which only
    degrades the hint back to the timestamp comparison.
    """
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain", "--", str(path.relative_to(root))],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if out.returncode != 0:
        return False
    return bool(out.stdout.strip())


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def describe_direction(
    deployed_at: datetime | None, committed_at: datetime | None, dirty: bool = False
) -> str:
    """Which side leads? Only prod-behind-repo is the incident shape."""
    if dirty:
        return (
            "PRODUCTION IS BEHIND THE WORKING TREE — this file has uncommitted changes, so "
            "the last-commit timestamp describes a different version than the one compared "
            "here. The deployed ruleset does not contain your local edit. Commit and deploy "
            "it, or discard the edit — do NOT resolve this by copying production over your "
            "work."
        )
    if deployed_at is None or committed_at is None:
        return "direction unknown (could not read both timestamps)"
    if committed_at > deployed_at:
        return (
            f"PRODUCTION IS BEHIND THE REPO — the file was committed {committed_at:%Y-%m-%d} "
            f"but the live release dates from {deployed_at:%Y-%m-%d}. This is the shape of the "
            "2026-05-23 incident: a rules change merged and never deployed. If the committed "
            "side is the tighter one, prod is running the looser policy right now."
        )
    return (
        f"repo is behind production — the live release ({deployed_at:%Y-%m-%d}) is newer than "
        f"the last commit touching the file ({committed_at:%Y-%m-%d}). Usually a deploy that "
        "has not been merged back yet."
    )


def run(root: Path, session, quiet: bool) -> int:
    project = project_id(root)
    committed = committed_rule_files(root)
    releases = api_get(session, f"{API}/projects/{project}/releases").get("releases", [])
    if not releases:
        raise Indeterminate(f"project {project} reports no rules releases at all")

    problems: list[str] = []
    lines: list[str] = []

    for release in releases:
        short = release_short_name(release)
        product = classify(short)
        if product is None:
            problems.append(
                f"release {short!r} maps to no firebase.json product — coverage gap, not a skip. "
                f"Add it to RELEASE_PREFIXES in {Path(__file__).name} and to firebase.json."
            )
            continue
        path = committed.get(product)
        if path is None:
            problems.append(
                f"release {short!r} is live but firebase.json configures no {product} rules file"
            )
            continue

        live = deployed_source(session, release["rulesetName"])
        local = path.read_text()
        rel = path.relative_to(root)

        if live == local:
            lines.append(f"  MATCH  {short}  ==  {rel}")
            continue

        direction = describe_direction(
            parse_time(release.get("updateTime")),
            last_commit_time(root, path),
            has_uncommitted_changes(root, path),
        )
        diff = "\n".join(
            difflib.unified_diff(
                live.splitlines(),
                local.splitlines(),
                fromfile=f"DEPLOYED:{short}",
                tofile=f"COMMITTED:{rel}",
                lineterm="",
            )
        )
        problems.append(f"{short} != {rel}\n    {direction}\n{diff}")

    print(f"Firebase rules drift check — project {project}")
    for line in lines:
        print(line)

    if problems:
        print("\nDRIFT DETECTED:\n")
        for problem in problems:
            print(f"  * {problem}\n")
        print(
            "Fix by deploying from a checkout that contains the committed file:\n"
            "  firebase deploy --only firestore:rules,storage\n"
            "then re-run this check. Do not resolve it by editing the repo to match prod "
            "without deciding which side is correct."
        )
        return EXIT_DRIFT

    if not quiet:
        print(f"\nAll {len(lines)} release(s) match their committed file.")
    return EXIT_MATCH


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--credentials", help="path to a service-account JSON key")
    parser.add_argument("--quiet", action="store_true", help="print nothing extra on success")
    parser.add_argument("--root", default=None, help="repo root (default: discover upwards)")
    args = parser.parse_args(argv)

    try:
        root = Path(args.root).resolve() if args.root else repo_root(Path.cwd())
        session = build_session(args.credentials)
        return run(root, session, args.quiet)
    except Indeterminate as exc:
        print(f"INDETERMINATE: {exc}", file=sys.stderr)
        print(
            "Could not establish what is deployed, so this is NOT a pass. Provide a service "
            "account with roles/firebaserules.viewer via --credentials or "
            "GOOGLE_APPLICATION_CREDENTIALS.",
            file=sys.stderr,
        )
        return EXIT_INDETERMINATE


if __name__ == "__main__":
    sys.exit(main())
