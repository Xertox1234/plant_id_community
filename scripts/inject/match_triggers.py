#!/usr/bin/env python3
"""Just-in-time mistake-injection matcher.

Reads a Claude Code PreToolUse event (JSON) on stdin and prints the recurring
mistake warnings whose trigger matches *the code being written*. Prints nothing
when no trigger matches. Always exits 0 — the injection layer must never block
or malform an edit (see the design spec).

Matching is asymmetric:
  - content_present is matched against the NEW edit fragment ("are you
    introducing this?").
  - content_absent is matched against the RESULTING file ("...and is the
    mitigation missing from the file?"). Testing absence on the fragment alone
    is unsound (absence-in-a-fragment != absence-in-the-file).

Env overrides (used by tests / the hook):
  INJECT_PROJECT_ROOT   repo root used to relativise file paths (default: repo
                        root inferred from this file's location)
  INJECT_TRIGGERS_FILE  path to the trigger index (default:
                        <root>/docs/rules/triggers.json)
"""
import datetime
import fnmatch
import json
import os
import re
import sys

EDIT_TOOLS = ("Edit", "Write", "MultiEdit")


def default_root():
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def to_rel(file_path, project_root):
    """Normalise an absolute-or-relative file path to a repo-relative path."""
    if not file_path:
        return ""
    if project_root:
        root = project_root.rstrip("/") + "/"
        if file_path.startswith(root):
            return file_path[len(root):]
    return file_path.lstrip("/") if file_path.startswith("/") else file_path


def extract_fragment(tool_name, tool_input):
    """The newly-introduced text for this edit."""
    if tool_name == "Write":
        return tool_input.get("content") or ""
    if tool_name == "Edit":
        return tool_input.get("new_string") or ""
    if tool_name == "MultiEdit":
        edits = tool_input.get("edits")
        if isinstance(edits, list):
            return "\n".join(
                (e.get("new_string") or "") for e in edits if isinstance(e, dict)
            )
    return ""


def compute_resulting_file(tool_name, tool_input, disk_content):
    """Reconstruct post-edit content for absence checks.

    Falls back to (disk + fragment) when the precise result can't be computed,
    which over-approximates presence and therefore errs toward SUPPRESSION
    (fewer false positives).
    """
    if tool_name == "Write":
        return tool_input.get("content") or ""

    if tool_name == "Edit":
        new = tool_input.get("new_string") or ""
        if disk_content is None:
            return new
        old = tool_input.get("old_string") or ""
        if old and old in disk_content:
            if tool_input.get("replace_all"):
                return disk_content.replace(old, new)
            return disk_content.replace(old, new, 1)
        return disk_content + "\n" + new

    if tool_name == "MultiEdit":
        content = disk_content if disk_content is not None else ""
        edits = tool_input.get("edits")
        if not isinstance(edits, list):
            return content + "\n" + extract_fragment(tool_name, tool_input)
        for e in edits:
            if not isinstance(e, dict):
                continue
            old = e.get("old_string") or ""
            new = e.get("new_string") or ""
            if old and old in content:
                content = content.replace(old, new, 1)
            else:
                content = content + "\n" + new
        return content

    return disk_content or ""


def _fires(trigger, rel_path, fragment, resulting_file):
    globs = trigger.get("path_glob") or []
    if not any(fnmatch.fnmatch(rel_path, g) for g in globs):
        return False
    present = trigger.get("content_present")
    if present and not re.search(present, fragment):
        return False
    absent = trigger.get("content_absent")
    if absent and re.search(absent, resulting_file):
        return False
    return True


def _safe_fires(trigger, rel_path, fragment, resulting_file):
    try:
        return _fires(trigger, rel_path, fragment, resulting_file)
    except re.error:
        return False
    except Exception:
        return False


def find_matches(tool_name, tool_input, triggers, disk_content, project_root=""):
    """Return the triggers that fire for this edit. Pure; safe on bad input."""
    if tool_name not in EDIT_TOOLS or not isinstance(tool_input, dict):
        return []
    file_path = tool_input.get("file_path")
    if not file_path:
        return []
    rel = to_rel(file_path, project_root)
    fragment = extract_fragment(tool_name, tool_input)
    resulting = compute_resulting_file(tool_name, tool_input, disk_content)
    return [t for t in triggers if _safe_fires(t, rel, fragment, resulting)]


def format_hits(hits):
    lines = []
    for t in hits:
        sev = str(t.get("severity", "warn")).upper()
        line = "- [{}] {}".format(sev, t.get("message", ""))
        ref = t.get("pattern_ref")
        if ref:
            line += "\n  -> see {}".format(ref)
        lines.append(line)
    return "\n".join(lines)


def load_triggers(project_root):
    path = os.environ.get("INJECT_TRIGGERS_FILE") or os.path.join(
        project_root, "docs", "rules", "triggers.json"
    )
    try:
        with open(path) as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def read_disk(file_path, project_root):
    try:
        path = file_path
        if not os.path.isabs(path):
            path = os.path.join(project_root, file_path)
        with open(path) as fh:
            return fh.read()
    except Exception:
        return None


def _log_fires(hits, rel_path):
    """Append fired trigger IDs to INJECT_FIRES_LOG. Fail-open — never blocks."""
    if not hits:
        return
    try:
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        _default_log = os.path.join(os.path.expanduser("~"), ".claude", "inject-fires.log")
        log_path = os.environ.get("INJECT_FIRES_LOG", _default_log)
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a") as fh:
            for t in hits:
                fh.write("{}\t{}\t{}\n".format(ts, rel_path, t.get("id", "unknown")))
    except Exception:
        pass


def main():
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        return 0
    if not isinstance(payload, dict):
        return 0
    tool_name = payload.get("tool_name")
    if tool_name not in EDIT_TOOLS:
        return 0
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict) or not tool_input.get("file_path"):
        return 0

    project_root = os.environ.get("INJECT_PROJECT_ROOT") or default_root()
    triggers = load_triggers(project_root)
    if not triggers:
        return 0
    disk = read_disk(tool_input["file_path"], project_root)
    hits = find_matches(tool_name, tool_input, triggers, disk, project_root)
    _log_fires(hits, to_rel(tool_input["file_path"], project_root))
    out = format_hits(hits)
    if out:
        sys.stdout.write(out + "\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
