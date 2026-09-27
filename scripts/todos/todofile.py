#!/usr/bin/env python3
"""Read and minimally edit todo files without reformatting them.

Every writer here changes only the lines it owns, so a triage or archive diff
shows exactly the fields it wrote. Anything ambiguous (a multi-line value, a
filename with no status segment) raises instead of guessing.
"""

import json
import os
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from check_archived_todo_status import FENCE_RE, REPOINT_RE  # noqa: E402

FM_RE = re.compile(r"\A---\n(.*?\n)---\n", re.S)
# Written unquoted: lowercase words joined by - or _ (triage classes, statuses)
# and ISO dates. Everything else is JSON-quoted -- valid YAML -- so "yes", "412"
# or "a: b" read back as the same string instead of a bool, int or mapping.
BARE_RE = re.compile(r"[a-z]+(?:[-_][a-z]+)*|\d{4}-\d{2}-\d{2}")
YAML_WORDS = {"yes", "no", "on", "off", "true", "false", "null", "none", "y", "n"}
CHECKBOX_RE = re.compile(r"^\s*-\s\[( |x|X)\]")
FILENAME_RE = re.compile(r"^((?:\d{4}-\d{2}-\d{2}-)?\d+-)([a-z_]+)(-.+)$")


def parse_frontmatter(text):
    """Return the frontmatter mapping in `text`, or None when it has none."""
    match = FM_RE.match(text)
    if not match:
        return None
    data = yaml.safe_load(match.group(1))
    return data if isinstance(data, dict) else None


def read_frontmatter(path):
    return parse_frontmatter(Path(path).read_text())


def render(value):
    text = str(value)
    if BARE_RE.fullmatch(text) and text not in YAML_WORDS:
        return text
    return json.dumps(text, ensure_ascii=False)


def set_fields(path, fields):
    """Set top-level scalar keys in place, appending any that are missing."""
    path = Path(path)
    text = path.read_text()
    match = FM_RE.match(text)
    if not match:
        raise ValueError(f"{path}: no frontmatter block")
    lines = match.group(1).splitlines(keepends=True)
    for key, value in fields.items():
        new_line = f"{key}: {render(value)}\n"
        for i, line in enumerate(lines):
            if line.startswith(f"{key}:"):
                following = lines[i + 1] if i + 1 < len(lines) else ""
                if following[:1] in (" ", "\t", "-"):
                    raise ValueError(f"{path}: {key} has a multi-line value; edit it by hand")
                lines[i] = new_line
                break
        else:
            lines.append(new_line)
    path.write_text("---\n" + "".join(lines) + "---\n" + text[match.end():])


def title(text):
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def _section_bounds(lines, heading):
    """(start, end) line indexes of a `## heading` section body, or None."""
    start = None
    for i, line in enumerate(lines):
        if line.rstrip("\n") == f"## {heading}":
            start = i + 1
        elif start is not None and line.startswith("## "):
            return start, i
    return (start, len(lines)) if start is not None else None


def append_work_log(path, block):
    """Append a Work Log entry at the end of that section (before ## Notes)."""
    path = Path(path)
    lines = path.read_text().splitlines(keepends=True)
    bounds = _section_bounds(lines, "Work Log")
    entry = block if block.endswith("\n") else block + "\n"
    if bounds is None:
        text = "".join(lines).rstrip("\n") + "\n\n## Work Log\n\n" + entry
    else:
        _, end = bounds
        head = "".join(lines[:end]).rstrip("\n") + "\n\n" + entry
        tail = "".join(lines[end:])
        text = head + ("\n" + tail if tail else "")
    path.write_text(text)


def ac_lines(text):
    """Checkbox lines under ## Acceptance Criteria, skipping fenced examples."""
    lines = text.splitlines()
    bounds = _section_bounds([line + "\n" for line in lines], "Acceptance Criteria")
    if bounds is None:
        return []
    found, in_fence = [], False
    for i in range(*bounds):
        line = lines[i]
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        match = None if in_fence else CHECKBOX_RE.match(line)
        if match:
            found.append((i, match.group(1) != " ", line))
    return found


def is_repoint(line):
    return bool(REPOINT_RE.search(line))


def with_status(filename, status):
    match = FILENAME_RE.match(filename)
    if not match:
        raise ValueError(f"{filename}: no status segment to replace")
    return f"{match.group(1)}{status}{match.group(3)}"
