"""Compare the running interpreter's packages against ``backend/requirements.txt``.

Why this exists: a local test result is evidence about the environment that
produced it, and nothing at the moment of the run used to say what that
environment was. On 2026-09-08 a ``backend/venv`` stuck on Wagtail 7.4.3 while
``requirements.txt`` pinned 8.0 produced a plausible failure list that was read
as "local noise" twice — once hiding a real ``post_migrate`` bug that only CI
caught (todos 378/379).

Two callers share this module:

* ``backend/conftest.py`` imports it, so the report always describes the
  interpreter that actually ran the tests — not whatever lives at
  ``backend/venv`` by path.
* ``.claude/hooks/check-test-env.sh`` runs it as a script with ``--hook``.

Stdlib only, and no Django import: conftest is loaded before Django setup.
"""

from __future__ import annotations

import json
import re
import sys
from importlib.metadata import distributions
from pathlib import Path

# `name==version`, tolerating extras (`celery[redis]==5.4.0`) and trailing
# environment markers. Anything else in requirements.txt (`-e ./packages/...`,
# `-r other.txt`, bare names) is deliberately not a pin and is skipped here.
# `\s*==\s*` because a spaced pin (`wagtail == 8.0`) is pip-legal. Without it
# such a line parses as "not a pin" and the package silently drops out of the
# comparison — a false negative, which is the worse direction for a detector
# whose whole value is being believed.
PIN_RE = re.compile(r"^([A-Za-z0-9_.\-]+)(?:\[[^\]]*\])?\s*==\s*([^\s;]+)")

REQUIREMENTS = Path(__file__).resolve().parents[2] / "requirements.txt"

# Keep the drift message short; a 210-package dump helps nobody, and the
# rule-injection hook has already been bitten by unbounded context (todo 369).
MAX_LISTED = 10


def normalize(name: str) -> str:
    """PEP 503 name normalization, so `ruamel.yaml.clib` == `ruamel-yaml-clib`."""
    return re.sub(r"[-_.]+", "-", name).lower()


def read_pins(path: Path | None = None) -> dict[str, str]:
    """Parse `name==version` lines. Non-pin lines are skipped, not errors.

    `path` defaults to None and resolves `REQUIREMENTS` at call time rather
    than binding it as a default argument. A default is evaluated once at
    definition, so `REQUIREMENTS` could never be pointed elsewhere — including
    by a test, which is how this was found.
    """
    path = path if path is not None else REQUIREMENTS
    pins: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        match = PIN_RE.match(line)
        if match:
            pins[normalize(match.group(1))] = match.group(2)
    return pins


def installed_versions() -> dict[str, str]:
    """Versions visible to *this* interpreter, via importlib.metadata."""
    found: dict[str, str] = {}
    for dist in distributions():
        name = dist.metadata["Name"]
        if name:
            found[normalize(name)] = dist.version
    return found


def editable_names() -> set[str]:
    """Distributions installed in editable mode.

    `requirements.txt` carries `-e ./packages/wagtail_forum`, which is not a
    `name==version` pin — so without this, `wagtail-forum` is reported as
    installed-but-unpinned on every single run, forever. A check that ships
    with a permanent false positive is the "reader learns to discount it"
    failure this module exists to prevent.
    """
    editable: set[str] = set()
    for dist in distributions():
        name = dist.metadata["Name"]
        if not name:
            continue
        raw = dist.read_text("direct_url.json")
        if not raw:
            continue
        try:
            if json.loads(raw).get("dir_info", {}).get("editable"):
                editable.add(normalize(name))
        except (ValueError, AttributeError):
            continue
    return editable


def compare(
    pins: dict[str, str],
    installed: dict[str, str],
    editable: set[str] | None = None,
) -> tuple[list[tuple[str, str, str]], list[tuple[str, str]], list[tuple[str, str]]]:
    """Pure comparison: `(mismatched, missing, extra)`.

    `mismatched` and `missing` are reported separately on purpose. On
    2026-09-08 the tree had 3 of the former and 2 of the latter, and a naive
    "compare the versions of what's installed" check would have missed
    django-ninja and swapper entirely.
    """
    editable = editable or set()
    mismatched = sorted(
        (name, pinned, installed[name])
        for name, pinned in pins.items()
        if name in installed and installed[name] != pinned
    )
    missing = sorted(
        (name, pinned) for name, pinned in pins.items() if name not in installed
    )
    extra = sorted(
        (name, version)
        for name, version in installed.items()
        if name not in pins and name not in editable
    )
    return mismatched, missing, extra


def _truncate(items: list[str]) -> str:
    if len(items) > MAX_LISTED:
        return ", ".join(items[:MAX_LISTED]) + f", +{len(items) - MAX_LISTED} more"
    return ", ".join(items)


def format_lines(
    mismatched: list[tuple[str, str, str]],
    missing: list[tuple[str, str]],
) -> list[str]:
    """Render the drift detail. Empty list when there is no drift.

    Names the packages: "your venv is stale" gets ignored, "wagtail: pinned
    8.0, installed 7.4.3" does not.
    """
    lines: list[str] = []
    if mismatched:
        lines.append(
            "  mismatched: "
            + _truncate([f"{n} (pinned {p}, installed {i})" for n, p, i in mismatched])
        )
    if missing:
        lines.append(
            "  not installed: " + _truncate([f"{n} (pinned {p})" for n, p in missing])
        )
    return lines


def drift_report() -> list[str]:
    """Full drift detail for the current interpreter, or `[]` when clean."""
    mismatched, missing, _ = compare(
        read_pins(), installed_versions(), editable_names()
    )
    return format_lines(mismatched, missing)


def main(argv: list[str]) -> int:
    """`--hook` mode: print the drift message, or nothing when clean.

    The caller wraps this in the hook JSON, matching how every other hook here
    keeps `jq` on the bash side.
    """
    if "--hook" not in argv:
        print(__doc__.strip().splitlines()[0], file=sys.stderr)
        return 2
    try:
        lines = drift_report()
    except Exception:  # noqa: BLE001 - must never break a test run
        return 0
    if not lines:
        return 0
    print(
        "backend/venv does not match backend/requirements.txt. Test results "
        "from this environment are evidence about a tree CI does not run:"
    )
    for line in lines:
        print(line)
    print("Fix: pip install -r backend/requirements.txt (see todo 378).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
