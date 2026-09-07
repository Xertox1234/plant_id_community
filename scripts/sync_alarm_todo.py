#!/usr/bin/env python3
"""Bridge an open security-scan alarm issue into a todos/ file.

Why this is a local script rather than a CI step
------------------------------------------------
CI cannot write the todo. This repo has
``default_workflow_permissions: read`` with
``can_approve_pull_request_reviews: false``, so Actions cannot open a PR, and
branch protection forbids a direct push. Even with those relaxed, a PR created
with ``GITHUB_TOKEN`` triggers no workflow runs, so the five required checks
would never report and the PR would deadlock — the failure mode this repo has
already hit twice.

So the alarm issue prints this command, and running it locally lands the todo.

Dedupe
------
Keyed on the ``Alarm issue: #N`` line the alarm writes into the issue body and
this script copies into the todo. N only changes when the issue self-closes and
a new failure opens a fresh one, so there is one todo per *episode*, never one
per week.

Usage:
    python3 scripts/sync_alarm_todo.py [--dry-run]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
TODOS = REPO_ROOT / "todos"
LABEL = "security-scan-alarm"
ALARM_KEY = re.compile(r"^Alarm issue: #(\d+)$", re.M)


def open_alarm_issues() -> list[dict]:
    result = subprocess.run(
        ["gh", "issue", "list", "--state", "open", "--label", LABEL,
         "--json", "number,title,body,createdAt"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        sys.exit(f"gh issue list failed: {result.stderr.strip()}")
    return json.loads(result.stdout or "[]")


def todo_for_issue(number: int) -> pathlib.Path | None:
    needle = f"Alarm issue: #{number}"
    for path in list(TODOS.glob("*.md")) + list(TODOS.glob("archive/*.md")):
        if needle in path.read_text():
            return path
    return None


def next_todo_id() -> str:
    """Highest existing todo id, plus one.

    Exactly three digits, not `\\d{3,}`: todos/archive/ holds date-prefixed
    legacy files like `2025-11-05-011-completed-….md`, and a greedy match reads
    the year as the id and proposes 2026 as the next one.
    """
    ids = []
    for path in list(TODOS.glob("*.md")) + list(TODOS.glob("archive/*.md")):
        match = re.match(r"^(\d{3})-", path.name)
        if match:
            ids.append(int(match.group(1)))
    return f"{(max(ids) + 1) if ids else 1:03d}"


def render_todo(todo_id: str, issue: dict, today: str) -> str:
    return f"""---
status: pending
priority: p2
issue_id: "{todo_id}"
tags: [security, ci, dependencies]
dependencies: []
---

# Scheduled security scan is failing (alarm issue #{issue['number']})

## Problem

The weekly `security-scan.yml` run is red. The scan hard-fails on schedule by
design, but a scheduled-run failure blocks no PR and appears on no check list —
which is how it once failed 8 consecutive weeks unnoticed. This todo is the
bridge that puts the failure into the normal sweep.

Alarm issue: #{issue['number']}

## Findings

Filed from GitHub issue #{issue['number']} (opened {issue['createdAt'][:10]}) by
`scripts/sync_alarm_todo.py` on {today}. The issue body at the time:

---

{issue['body'].strip()}

---

## Recommended Action

1. Reproduce locally:
   `cd backend && pip-audit -r requirements.txt ${{=$(python3 ../scripts/check_suppressions.py --emit-flags)}}`
   and `cd web && npm audit --audit-level=moderate`.
   The `${{=...}}` matters — this project's shell is zsh, which does not
   word-split an unquoted `$VAR`, so without it pip-audit audits nothing.
   That reproduces the GATE. If it comes back clean while the scan is red,
   the failure is `--recheck`, not a new advisory: a fix has shipped for an
   advisory the gate is suppressing, and the suppressed command above cannot
   see it by construction. Re-run UNSUPPRESSED to find it:
   `cd backend && pip-audit -r requirements.txt --format json --output /tmp/a.json`
   then `python3 scripts/check_suppressions.py --recheck --report /tmp/a.json`.
2. For each advisory, **try a bump before suppressing** — an empty "Fix
   Versions" column does not mean unfixable (`docs/rules/security.md`).
3. Only if no bump clears it, add an entry to
   `.github/security-suppressions.yml` with `expires`, `owner`, `clears_when`
   and a `tracked_by` naming an OPEN todo. Never hand-add an `--ignore-vuln`
   flag to the workflow — it would bypass the expiry recheck.
4. Verify with `python3 scripts/check_suppressions.py --validate`.

## Technical Details

- Workflow: `.github/workflows/security-scan.yml` (weekly, Mondays 09:00 UTC)
- Suppression data: `.github/security-suppressions.yml`
- Checker: `scripts/check_suppressions.py`
- The alarm issue closes itself on the first green scheduled run.

## Acceptance Criteria

- [ ] The scheduled `security-scan.yml` run is green
- [ ] Alarm issue #{issue['number']} has auto-closed
- [ ] Every advisory was fixed by a bump, or suppressed with an expiry and an
      open `tracked_by` todo

## Work Log

### {today} - Filed by scripts/sync_alarm_todo.py from alarm issue #{issue['number']}

- The scheduled scan went red and the alarm opened issue #{issue['number']}.
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    issues = open_alarm_issues()
    if not issues:
        print(f"No open issues labelled {LABEL!r} — nothing to sync.")
        return 0

    today = dt.date.today().isoformat()
    for issue in issues:
        existing = todo_for_issue(issue["number"])
        if existing is not None:
            print(f"issue #{issue['number']}: already tracked by {existing.name}")
            continue

        todo_id = next_todo_id()
        path = TODOS / f"{todo_id}-pending-p2-security-scan-alarm.md"
        if args.dry_run:
            print(f"issue #{issue['number']}: would create {path.name}")
            continue
        path.write_text(render_todo(todo_id, issue, today))
        print(f"issue #{issue['number']}: created {path.name}")
        print("  Commit it on a branch and open a PR — this repo never pushes to main.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
