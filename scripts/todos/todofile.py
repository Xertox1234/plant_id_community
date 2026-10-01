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
# and ISO dates. ISO dates read back as datetime.date objects; consumers must str()
# them to get the original text. Everything else is JSON-quoted -- valid YAML -- so
# "yes", "412" or "a: b" read back as the same string instead of a bool, int or mapping.
BARE_RE = re.compile(r"[a-z]+(?:[-_][a-z]+)*|\d{4}-\d{2}-\d{2}")
YAML_WORDS = {"yes", "no", "on", "off", "true", "false", "null", "none", "y", "n"}
CHECKBOX_RE = re.compile(r"^\s*-\s\[( |x|X)\]")
INTERRUPT_RE = re.compile(r"^\s*(?:[-*+]|1[.)])\s")  # a list item that can interrupt a paragraph
HEADING_RE = re.compile(r"^\s*#{1,6}(?:\s|$)")
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


def key_line(lines, key):
    """Index of the frontmatter line that sets top-level `key`, or None. YAML allows blanks
    before the colon, so `key : value` is that key too (todo 475): a plain `key:` prefix
    match missed it, and set_fields then appended a second, duplicate `key:` line."""
    pattern = re.compile(rf"{re.escape(key)}[ \t]*:")
    return next((i for i, line in enumerate(lines) if pattern.match(line)), None)


def field_problem(text, key):
    """Why set_fields cannot set `key` in place in `text`, or None when it can. The one
    source of set_fields' refusals, so a caller can check first and write nothing."""
    match = FM_RE.match(text)
    if not match:
        return "no frontmatter block"
    lines = match.group(1).splitlines(keepends=True)
    i = key_line(lines, key)
    if i is None:
        # Set, but on no line key_line finds (a quoted or flow-style key): appending
        # would duplicate it (todo 475). Malformed YAML keeps the old append behaviour.
        try:
            data = parse_frontmatter(text) or {}
        except yaml.YAMLError:
            data = {}
        return f"'{key}' is set on a line it cannot rewrite" if key in data else None
    following = lines[i + 1] if i + 1 < len(lines) else ""
    if following[:1] in (" ", "\t", "-"):
        return f"'{key}' has a multi-line value"
    return None


def set_fields(path, fields):
    """Set top-level scalar keys in place, appending any that are missing. Refuses,
    writing nothing, when any key has a field_problem."""
    path = Path(path)
    text = path.read_text()
    for key in fields:
        problem = field_problem(text, key)
        if problem:
            raise ValueError(f"{path}: {problem}; edit it by hand")
    match = FM_RE.match(text)
    if not match:
        raise ValueError(f"{path}: no frontmatter block")
    lines = match.group(1).splitlines(keepends=True)
    for key, value in fields.items():
        new_line = f"{key}: {render(value)}\n"
        i = key_line(lines, key)
        if i is None:
            lines.append(new_line)
        else:
            lines[i] = new_line
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


def _continues(line):
    """True when `line` wraps the bullet above it: indented, non-blank, and not a
    new bullet, a heading or a fence (a fence must still reach the toggle). As in
    CommonMark, only a `1.` item can start a list inside a paragraph, and a heading
    needs a space after its #s, so a wrapped `10. …` or `#42 …` is text (todo 468 N2)."""
    return (line[:1] in (" ", "\t") and bool(line.strip()) and not INTERRUPT_RE.match(line)
            and not HEADING_RE.match(line) and not FENCE_RE.match(line))


def ac_lines(text):
    """Criteria under ## Acceptance Criteria, skipping fenced examples.

    Each is (line_no, checked, text): line_no is the checkbox line, and text is the
    whole bullet -- the checkbox line plus its indented continuation lines, joined
    by one space (29 of 47 open todos wrap a criterion onto a second line)."""
    lines = text.splitlines()
    bounds = _section_bounds([line + "\n" for line in lines], "Acceptance Criteria")
    if bounds is None:
        return []
    found, in_fence = [], False
    i, end = bounds
    while i < end:
        line = lines[i]
        if FENCE_RE.match(line):
            in_fence = not in_fence
            i += 1
            continue
        match = None if in_fence else CHECKBOX_RE.match(line)
        if not match:
            i += 1
            continue
        parts, j = [line.rstrip()], i + 1
        while j < end and _continues(lines[j]):
            parts.append(lines[j].strip())
            j += 1
        found.append((i, match.group(1) != " ", " ".join(parts)))
        i = j
    return found


def is_repoint(line):
    return bool(REPOINT_RE.search(line))


def with_status(filename, status):
    match = FILENAME_RE.match(filename)
    if not match:
        raise ValueError(f"{filename}: no status segment to replace")
    return f"{match.group(1)}{status}{match.group(3)}"


def archived_path(todo_rel):
    """Where land.archive moves a todo: todos/archive/<name with status completed>. The one source of
    this rule -- land.archive writes it, state.review_args hands it to the review prompts."""
    return f"todos/archive/{with_status(Path(todo_rel).name, 'completed')}"
