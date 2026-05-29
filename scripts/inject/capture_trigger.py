#!/usr/bin/env python3
"""Append a just-in-time mistake trigger to docs/rules/triggers.json.

Closes the loop: a caught mistake becomes a write-time warning for future
sessions. Two callers:
  - /codify (manual, human-curated): pass --severity warn.
  - review automation (auto): default --severity candidate (provisional,
    prunable later; still injects immediately).

Dedup is strict on `id` (idempotent: re-capturing an existing id is a no-op
unless --update). Invalid regex or a missing required field is rejected. A
pattern_ref that does not resolve to a file is dropped (with a warning) rather
than shipped dangling.

Env: INJECT_TRIGGERS_FILE overrides the index path (used by tests).
"""
import argparse
import datetime
import json
import os
import re
import sys

# Canonical key order for a trigger entry (matches the hand-written seed file).
_ORDER = [
    "id", "domains", "path_glob", "content_present", "content_absent",
    "message", "pattern_ref", "source", "added", "severity",
]


def default_root():
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def build_trigger(id, message, path_glob, *, domains=None, content_present=None,
                  content_absent=None, pattern_ref=None, source=None, added=None,
                  severity="candidate"):
    """Assemble a validated trigger dict in canonical key order. Raises ValueError."""
    if not id:
        raise ValueError("trigger id is required")
    if not message:
        raise ValueError("trigger message is required")
    if not path_glob or not isinstance(path_glob, list):
        raise ValueError("path_glob must be a non-empty list")
    for key, pat in (("content_present", content_present), ("content_absent", content_absent)):
        if pat:
            try:
                re.compile(pat)
            except re.error as e:
                raise ValueError("invalid regex in {}: {}".format(key, e))
    if severity not in ("warn", "info", "candidate"):
        raise ValueError("severity must be warn|info|candidate, got {!r}".format(severity))

    fields = {
        "id": id,
        "domains": domains or None,
        "path_glob": path_glob,
        "content_present": content_present or None,
        "content_absent": content_absent or None,
        "message": message,
        "pattern_ref": pattern_ref or None,
        "source": source or None,
        "added": added or datetime.date.today().isoformat(),
        "severity": severity,
    }
    return {k: fields[k] for k in _ORDER if fields[k] is not None}


def resolve_pattern_ref(ref, project_root):
    """Return (kept_ref_or_None, warning_or_None). Drops refs that don't resolve."""
    if not ref:
        return None, None
    if os.path.isfile(os.path.join(project_root, ref)):
        return ref, None
    return None, "pattern_ref does not resolve, dropping: {}".format(ref)


def load(path):
    try:
        with open(path) as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def save(path, triggers):
    with open(path, "w") as fh:
        json.dump(triggers, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def capture(path, trigger, update=False):
    """Append `trigger` to the index at `path`. Returns added|exists|updated."""
    triggers = load(path)
    for i, existing in enumerate(triggers):
        if existing.get("id") == trigger["id"]:
            if not update:
                return "exists"
            triggers[i] = trigger
            save(path, triggers)
            return "updated"
    triggers.append(trigger)
    save(path, triggers)
    return "added"


def _split_domains(value):
    if not value:
        return None
    return [d.strip() for d in value.split(",") if d.strip()]


def main(argv=None):
    p = argparse.ArgumentParser(description="Append a JIT mistake trigger.")
    p.add_argument("--id", required=True)
    p.add_argument("--message", required=True)
    p.add_argument("--path-glob", action="append", required=True, dest="path_glob",
                   help="repeatable; repo-relative fnmatch glob")
    p.add_argument("--domains", help="comma-separated")
    p.add_argument("--content-present", dest="content_present")
    p.add_argument("--content-absent", dest="content_absent")
    p.add_argument("--pattern-ref", dest="pattern_ref")
    p.add_argument("--source")
    p.add_argument("--added")
    p.add_argument("--severity", default="candidate", choices=["warn", "info", "candidate"])
    p.add_argument("--update", action="store_true")
    p.add_argument("--project-root", default=default_root())
    args = p.parse_args(argv)

    pattern_ref, warn = resolve_pattern_ref(args.pattern_ref, args.project_root)
    if warn:
        sys.stderr.write("warning: " + warn + "\n")

    try:
        trigger = build_trigger(
            id=args.id, message=args.message, path_glob=args.path_glob,
            domains=_split_domains(args.domains),
            content_present=args.content_present, content_absent=args.content_absent,
            pattern_ref=pattern_ref, source=args.source, added=args.added,
            severity=args.severity,
        )
    except ValueError as e:
        sys.stderr.write("error: {}\n".format(e))
        return 2

    triggers_file = os.environ.get("INJECT_TRIGGERS_FILE") or os.path.join(
        args.project_root, "docs", "rules", "triggers.json"
    )
    status = capture(triggers_file, trigger, update=args.update)
    sys.stdout.write("{}: {} ({})\n".format(status, trigger["id"], triggers_file))
    return 0


if __name__ == "__main__":
    sys.exit(main())
