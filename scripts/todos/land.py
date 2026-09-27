#!/usr/bin/env python3
"""Stage D helpers: make a verified group's todos archivable, exactly.

    land.py flip-acs --run RUNFILE --id 412 --repo WORKTREE --date 2026-09-27
    land.py archive  --run RUNFILE --id 412 --repo WORKTREE --date 2026-09-27

flip-acs checks a box only where the worker's ac.json says pass AND the
verifier re-ran it and agreed AND the evidence file exists under
.sweep-evidence/. It quotes the evidence tail into the Work Log, because
.sweep-evidence/ is gitignored and the Work Log is the only record that
survives the merge; `command`/`evidence_path` are flattened to one line first
so an embedded newline cannot forge a new Work Log heading, and the tail is
quoted inside a fence long enough that the tail's own content cannot close it
early. archive is split into a read-only validate phase and a write phase
(fix round 1, F1): nothing is renamed, checked off or edited until every
check -- the destination is free, the todo has an Acceptance Criteria
section, and the same bare-unchecked-box rule the CI tripwire enforces
(`check_archived_todo_status.parse`) reports none -- has already passed.
Only the validate phase may raise `LandError`. The write phase then does the
git mv, the status flip, the Work Log entry, `fix_baseline` (a filename-only
edit, never a regeneration), and the planned review check-off. A Finding
Status line is checked off by its arrow target alone (fix round 1, F2): a
`-> todo NNN` naming a DIFFERENT todo means the finding moved elsewhere
(CLAUDE.md Review Doc Tracking rule 4) and stays open; a target naming THIS
todo, or no target at all (a legacy line), is checked off regardless of
"re-pointed" wording. The review doc is renamed COMPLETED only when nothing
left in its Finding Status is open, and a planned rename is itself validated
in phase 1 (fix round 2, G3): a `-COMPLETED` destination that already exists
or a review doc git doesn't track downgrades to "checked off, no rename",
never a phase-2 `git mv` failure. `source_review` only ever resolves inside
`docs/reviews/` (fix round 2, G4) -- a path that escapes it, by `..` or
otherwise, is just another "not a review doc" value, never read or written.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import state  # noqa: E402
import todofile  # noqa: E402
# todofile's own import already inserted scripts/ (its parent) onto sys.path as a
# side effect, which is what lets this resolve with no sys.path change of its own.
import check_archived_todo_status  # noqa: E402

EVIDENCE_TAIL = 5
ARROW_TARGET_RE = re.compile(r"(?:→|->)\s*todo\s*0*(\d+)", re.I)


class LandError(Exception):
    pass


def run_git(repo, *args):
    proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if proc.returncode != 0:
        raise LandError(f"git {' '.join(args)}: {proc.stderr.strip()}")
    return proc.stdout


def _tail(path):
    lines = Path(path).read_text(errors="replace").rstrip("\n").splitlines()
    return lines[-EVIDENCE_TAIL:]


def _sanitize(value):
    """Flatten to one line so a quoted value can never forge a new heading.

    str.splitlines() (fix round 2, G5) -- not a literal \\r/\\n replace -- so
    every separator a parser might treat as a line break (\\x85, \\x0c,
    \\x1e, \\u2028, ...) is flattened too, not just the two ASCII ones."""
    return " ".join(str(value).splitlines())


_CHECKBOX_PREFIX_RE = re.compile(r"^\s*-\s\[[ xX]\]\s*")


def _normalize_ac_text(text):
    """Strip a leading checkbox marker (if any) and collapse whitespace."""
    text = _CHECKBOX_PREFIX_RE.sub("", text, count=1)
    return re.sub(r"\s+", " ", text.strip())


def _valid_evidence(repo, evidence_path):
    """The resolved Path if evidence_path is relative and inside
    <repo>/.sweep-evidence/ and names a real file, else None. A path that
    fails this is never opened -- it is treated as missing evidence."""
    if not evidence_path:
        return None
    candidate = Path(evidence_path)
    if candidate.is_absolute():
        return None
    sweep_dir = (Path(repo) / ".sweep-evidence").resolve()
    resolved = (Path(repo) / candidate).resolve()
    if not resolved.is_relative_to(sweep_dir):
        return None
    return resolved if resolved.is_file() else None


def _fence_quote(lines):
    """A fence marker one backtick longer than the longest run in `lines`,
    minimum 3, so the tail's own content can never close it early (F5b)."""
    text = "\n".join(lines)
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    fence = "`" * max(longest + 1, 3)
    quoted = "\n".join(f"  {line}" for line in lines)
    return fence, quoted


def flip_acs(repo, todo_rel, ac_entries, verdict_ac, run_id, date):
    repo = Path(repo)
    path = repo / todo_rel
    todo_id = str((todofile.read_frontmatter(path) or {}).get("issue_id", ""))
    text = path.read_text()
    boxes = todofile.ac_lines(text)
    mine = sorted((e for e in ac_entries if str(e["todo"]) == todo_id), key=lambda e: e["index"])
    if [e["index"] for e in mine] != list(range(len(boxes))):
        raise LandError(f"{todo_rel}: ac.json has indexes {[e['index'] for e in mine]} for todo {todo_id}, "
                        f"but the file has {len(boxes)} criteria")
    for (_, _, line), entry in zip(boxes, mine):
        expected, got = _normalize_ac_text(line), _normalize_ac_text(entry.get("text", ""))
        if expected != got:
            raise LandError(f"{todo_rel}: ac.json text for index {entry['index']} ({got!r}) does not match "
                            f"the todo's AC line ({expected!r})")
    agreed = {v["index"] for v in verdict_ac if str(v["todo"]) == todo_id and v["verified"] is True}
    lines = text.splitlines(keepends=True)
    flipped, notes = [], []
    for (line_no, checked, line), entry in zip(boxes, mine):
        index = entry["index"]
        if checked or todofile.is_repoint(line):
            continue
        evidence = _valid_evidence(repo, entry.get("evidence_path"))
        if not (entry["pass"] is True and index in agreed and evidence):
            continue
        lines[line_no] = lines[line_no].replace("[ ]", "[x]", 1)
        flipped.append(index)
        command, evidence_display = _sanitize(entry["command"]), _sanitize(entry["evidence_path"])
        fence, quoted = _fence_quote(_tail(evidence))
        notes.append(f"- AC {index + 1}: `{command}` — evidence `{evidence_display}`, "
                     f"last lines:\n\n  {fence}text\n{quoted}\n  {fence}\n")
    path.write_text("".join(lines))
    if flipped:
        todofile.append_work_log(path, f"### {date} - Verified by the todo sweep (run {run_id})\n\n" + "\n".join(notes))
    remaining = [e["index"] for (_, checked, _), e in zip(boxes, mine) if not checked and e["index"] not in flipped]
    return flipped, remaining


def fix_baseline(repo, old_rel, new_rel):
    path = Path(repo) / ".secrets.baseline"
    if not path.is_file():
        return False
    text = path.read_text()
    if f'"{old_rel}"' not in text:
        return False
    path.write_text(text.replace(f'"{old_rel}"', f'"{new_rel}"'))
    return True


def _target_todo(line):
    """The numeric target of a '-> todo NNN' / '→ todo NNN' arrow, or None."""
    match = ARROW_TARGET_RE.search(line)
    return int(match.group(1)) if match else None


def _same_todo(a, b):
    try:
        return int(a) == int(b)
    except (TypeError, ValueError):
        return str(a) == str(b)


def _review_path(repo, rel):
    """The resolved Path for `rel` if it names a real .md file inside
    <repo>/docs/reviews/, else None (fix round 2, G4). A `source_review` that
    resolves outside docs/reviews/ -- e.g. via '../../' -- is never read or
    written; it is treated exactly like any other "not a review doc" value."""
    if not rel or not str(rel).endswith(".md"):
        return None
    reviews_dir = (Path(repo) / "docs" / "reviews").resolve()
    candidate = (Path(repo) / rel).resolve()
    if not candidate.is_relative_to(reviews_dir):
        return None
    return candidate if candidate.is_file() else None


def _tracked(repo, rel):
    """True when git already has `rel` staged/committed (fix round 2, G3) --
    an untracked review doc can't be `git mv`-ed, so a planned rename must
    check this before phase 2, not discover it via a failed mv."""
    proc = subprocess.run(["git", "-C", str(repo), "ls-files", "--error-unmatch", rel], capture_output=True)
    return proc.returncode == 0


def plan_review(repo, todo_path, date):
    """Read-only: decide what archive's write phase should do to the source
    review doc. Never writes and never raises -- F1 is explicit that none of
    these resolutions is an error, only a no-op, a leave-open, or a checkoff,
    each carrying a note. Returns None when the todo has no source_review at
    all (no review step); source_review with no source_finding is instead a
    no-op with a note (G7), since that is an actionable data problem, not an
    absent field."""
    data = todofile.read_frontmatter(todo_path) or {}
    source, finding, todo_id = data.get("source_review"), data.get("source_finding"), data.get("issue_id")
    if not source:
        return None
    if not finding:
        return {"finding": None, "action": "noop",
                "note": f"source_review {source!r} is set but source_finding is missing"}
    review = _review_path(repo, source)
    if review is None:
        twin_rel = source[:-3] + "-COMPLETED.md" if source.endswith(".md") else None
        if twin_rel is not None and _review_path(repo, twin_rel) is not None:
            return {"finding": finding, "action": "noop", "note": f"source_review already completed: {twin_rel}"}
        return {"finding": finding, "action": "noop", "note": f"source_review is not a review doc: {source}"}
    lines = review.read_text().splitlines(keepends=True)
    start = next((i for i, line in enumerate(lines) if line.rstrip("\n") == "## Finding Status"), None)
    if start is None:
        return {"finding": finding, "action": "noop", "note": f"{source}: no '## Finding Status' section"}
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    key = re.escape(str(finding))
    line_re = re.compile(rf"^\s*-\s\[([ xX])\]\s*#{key}(?=\s|$)")
    matches = [i for i in range(start + 1, end) if line_re.match(lines[i])]
    if not matches:
        return {"finding": finding, "action": "noop", "note": f"{source}: no line for finding #{finding}"}
    # G7: several lines can name the same finding (a stale one plus a live one).
    # Prefer the first OPEN line that is actually checkable BY THIS TODO (no arrow
    # target, or a target matching todo_id) -- an open line re-pointed to someone
    # ELSE is not "the line for this archive" even if it happens to come first among
    # the open matches (rule 4: X's own already-checked line must still read as
    # "already checked", not get shadowed by a later re-point of the same finding
    # number to a different todo). Only fall back to the first match overall (which
    # may be an already-checked line, or an open-but-irrelevant one) when no match
    # is checkable by this todo.
    def _checkable(i):
        return line_re.match(lines[i]).group(1) == " " and (
            (t := _target_todo(lines[i])) is None or _same_todo(t, todo_id))
    checkable = [i for i in matches if _checkable(i)]
    hit = checkable[0] if checkable else matches[0]
    if line_re.match(lines[hit]).group(1) != " ":
        return {"finding": finding, "action": "noop", "note": "already checked"}
    target = _target_todo(lines[hit])
    if target is not None and not _same_todo(target, todo_id):
        return {"finding": finding, "action": "leave_open",
                "note": f"finding #{finding} targets todo {target}, not {todo_id}; left open"}
    new_lines = list(lines)
    new_lines[hit] = new_lines[hit].rstrip("\n").replace("- [ ]", "- [x]", 1) + f" (completed {date})\n"
    open_re = re.compile(r"^\s*-\s\[ \]")
    all_closed = not any(open_re.match(new_lines[i]) for i in range(start + 1, end))
    renamed, completed, note = False, None, "checked off"
    if all_closed:
        if source.endswith("-COMPLETED.md"):
            note = "checked off; already a -COMPLETED doc, no further rename"
        else:
            candidate_rel = source[:-3] + "-COMPLETED.md"
            # G3: a planned rename must be fully validated here, in phase 1 -- a
            # destination collision or an untracked source only surfaces as a git
            # failure in phase 2, by which point archive() has already git-mv'd the
            # todo and rewritten the review doc, so LandError there is not an option.
            if (Path(repo) / candidate_rel).is_file():
                note = f"all findings resolved, but {candidate_rel} already exists; rename skipped"
            elif not _tracked(repo, source):
                note = f"all findings resolved, but {source} is not tracked in git; rename skipped"
            else:
                renamed, completed, note = True, candidate_rel, "all findings resolved"
    return {"finding": finding, "action": "checkoff", "note": note, "source": source,
            "new_lines": new_lines, "renamed": renamed, "completed": completed}


def apply_review(repo, plan, todo_path, git=run_git):
    """Write phase for plan_review's plan. Never raises: any error in the
    plan already surfaced in plan_review, before any write happened."""
    if plan is None:
        return None
    if plan["action"] != "checkoff":
        return {"finding": plan["finding"], "renamed": False, "paths": [], "note": plan["note"]}
    source = plan["source"]
    (Path(repo) / source).write_text("".join(plan["new_lines"]))
    if plan["renamed"]:
        completed = plan["completed"]
        git(repo, "mv", source, completed)
        todofile.set_fields(todo_path, {"source_review": completed})
        return {"finding": plan["finding"], "renamed": True, "paths": [completed], "note": plan["note"]}
    return {"finding": plan["finding"], "renamed": False, "paths": [source], "note": plan["note"]}


def archive(repo, todo_rel, run_id, date, git=run_git):
    repo = Path(repo)
    src = repo / todo_rel
    dest_rel = f"todos/archive/{todofile.with_status(Path(todo_rel).name, 'completed')}"
    dest = repo / dest_rel

    # Phase 1: validate; write nothing. LandError may be raised only here.
    if not src.is_file():
        if dest.is_file():
            raise LandError(f"{todo_rel}: already archived at {dest_rel}")
        raise LandError(f"{todo_rel}: source todo not found")
    if dest.is_file():
        raise LandError(f"{todo_rel}: destination already exists: {dest_rel}")
    text = src.read_text()
    if not any(line.rstrip("\n") == "## Acceptance Criteria" for line in text.splitlines()):
        raise LandError(f"{todo_rel}: no '## Acceptance Criteria' section; nothing verified to archive")
    _, _, _, bare_acs = check_archived_todo_status.parse(str(src))
    if bare_acs:
        raise LandError(f"{todo_rel}: {len(bare_acs)} unchecked criteria; "
                        "flip them with evidence or re-point them first")
    review_plan = plan_review(repo, src, date)
    # G1: whether THIS land wrote a Verified note with evidence for this run_id --
    # not merely whether some box happens to be [x], which is also true for a box
    # that was already checked (by hand, or a past run) with no evidence ever quoted.
    has_verified_note = f"Verified by the todo sweep (run {run_id})" in text

    # Phase 2: write.
    git(repo, "mv", todo_rel, dest_rel)
    todofile.set_fields(dest, {"status": "completed"})
    tail_note = "evidence is quoted above, review is on the PR." if has_verified_note else "review is on the PR."
    todofile.append_work_log(dest, f"### {date} - Completed by the todo sweep (run {run_id})\n\n"
                                   f"- Archived by `land.py archive`; {tail_note}\n")
    baseline = fix_baseline(repo, todo_rel, dest_rel)
    review = apply_review(repo, review_plan, dest, git)
    paths = [dest_rel] + ([".secrets.baseline"] if baseline else []) + (review["paths"] if review else [])
    return {"archived": dest_rel, "paths": paths, "baseline_updated": baseline, "review": review}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("cmd", choices=["flip-acs", "archive"])
    parser.add_argument("--run", required=True)
    parser.add_argument("--id", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--date", required=True)
    args = parser.parse_args(argv)
    try:
        run = state.load(args.run)
        entry = run["todos"][args.id]
        if args.cmd == "flip-acs":
            ac_entries = json.loads((Path(args.repo) / entry["ac_file"]).read_text())
            flipped, remaining = flip_acs(args.repo, entry["path"], ac_entries, entry.get("verified_ac", []),
                                          run["run_id"], args.date)
            print(json.dumps({"flipped": flipped, "remaining": remaining}))
        else:
            print(json.dumps(archive(args.repo, entry["path"], run["run_id"], args.date)))
    except (LandError, KeyError, ValueError, FileNotFoundError) as exc:
        print(f"land: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
