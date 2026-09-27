#!/usr/bin/env python3
"""Stage D helpers: make a verified group's todos archivable, exactly.

    land.py flip-acs --run RUNFILE --id 412 --repo WORKTREE --date 2026-09-27
    land.py archive  --run RUNFILE --id 412 --repo WORKTREE --date 2026-09-27

flip-acs checks a box only where the worker's ac.json says pass AND the
verifier re-ran it and agreed AND the evidence file exists. It quotes the
evidence tail into the Work Log, because .sweep-evidence/ is gitignored and the
Work Log is the only record that survives the merge. archive applies the
per-todo contract (completing-todos Safety Rails 4-5): status and filename move
together, a .secrets.baseline entry follows the rename (a filename-only edit,
never a regeneration), and the source review finding is checked off. The
review doc is renamed COMPLETED only when nothing in its Finding Status is open.
Re-pointed findings stay open by design (CLAUDE.md Review Doc Tracking rule 4).
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

EVIDENCE_TAIL = 5


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
    agreed = {v["index"] for v in verdict_ac if str(v["todo"]) == todo_id and v["verified"]}
    lines = text.splitlines(keepends=True)
    flipped, notes = [], []
    for (line_no, checked, _), entry in zip(boxes, mine):
        index = entry["index"]
        evidence = repo / entry["evidence_path"] if entry.get("evidence_path") else None
        if checked or not (entry["pass"] and index in agreed and evidence and evidence.is_file()):
            continue
        lines[line_no] = lines[line_no].replace("[ ]", "[x]", 1)
        flipped.append(index)
        quoted = "\n".join(f"  {line}" for line in _tail(evidence))
        notes.append(f"- AC {index + 1}: `{entry['command']}` — evidence `{entry['evidence_path']}`, "
                     f"last lines:\n\n  ```text\n{quoted}\n  ```\n")
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


def check_off_review(repo, todo_path, date, git=run_git):
    data = todofile.read_frontmatter(todo_path) or {}
    source, finding = data.get("source_review"), data.get("source_finding")
    if not source or not finding:
        return None
    review = Path(repo) / source
    if not review.is_file():
        raise LandError(f"source_review {source} not found")
    lines = review.read_text().splitlines(keepends=True)
    start = next((i for i, line in enumerate(lines) if line.rstrip("\n") == "## Finding Status"), None)
    if start is None:
        raise LandError(f"{source}: no '## Finding Status' section")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    key = re.escape(str(finding))
    open_re, done_re = re.compile(rf"^- \[ \] #{key}(?=\s|$)"), re.compile(rf"^- \[x\] #{key}(?=\s|$)")
    hit = next((i for i in range(start + 1, end) if open_re.match(lines[i])), None)
    if hit is None:
        if any(done_re.match(lines[i]) for i in range(start + 1, end)):
            return {"finding": finding, "renamed": False, "paths": [], "note": "already checked"}
        raise LandError(f"{source}: no open line for finding #{finding}")
    lines[hit] = lines[hit].rstrip("\n").replace("- [ ]", "- [x]", 1) + f" (completed {date})\n"
    review.write_text("".join(lines))
    still_open = sum(1 for i in range(start + 1, end) if lines[i].startswith("- [ ]"))
    if still_open:
        return {"finding": finding, "renamed": False, "paths": [source], "note": f"{still_open} still open"}
    completed = source[:-3] + "-COMPLETED.md" if source.endswith(".md") else source + "-COMPLETED"
    git(repo, "mv", source, completed)
    todofile.set_fields(todo_path, {"source_review": completed})
    return {"finding": finding, "renamed": True, "paths": [completed], "note": "all findings resolved"}


def archive(repo, todo_rel, run_id, date, git=run_git):
    repo = Path(repo)
    text = (repo / todo_rel).read_text()
    bare = [line for _, checked, line in todofile.ac_lines(text) if not checked and not todofile.is_repoint(line)]
    if bare:
        raise LandError(f"{todo_rel}: {len(bare)} unchecked criteria; flip them with evidence or re-point them first")
    dest_rel = f"todos/archive/{todofile.with_status(Path(todo_rel).name, 'completed')}"
    git(repo, "mv", todo_rel, dest_rel)  # rename first; the edits below are staged by the caller
    dest = repo / dest_rel
    todofile.set_fields(dest, {"status": "completed"})
    todofile.append_work_log(dest, f"### {date} - Completed by the todo sweep (run {run_id})\n\n"
                                   "- Archived by `land.py archive`; evidence is quoted above, review is on the PR.\n")
    baseline = fix_baseline(repo, todo_rel, dest_rel)
    review = check_off_review(repo, dest, date, git)
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
    run = state.load(args.run)
    entry = run["todos"][args.id]
    try:
        if args.cmd == "flip-acs":
            ac_entries = json.loads((Path(args.repo) / entry["ac_file"]).read_text())
            flipped, remaining = flip_acs(args.repo, entry["path"], ac_entries, entry.get("verified_ac", []),
                                          run["run_id"], args.date)
            print(json.dumps({"flipped": flipped, "remaining": remaining}))
        else:
            print(json.dumps(archive(args.repo, entry["path"], run["run_id"], args.date)))
    except LandError as exc:
        print(f"land: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
