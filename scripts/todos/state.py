#!/usr/bin/env python3
"""The todo sweep's run file -- the only code that writes it.

todos/.sweep-run-<run_id>.json holds one run's progress (spec §8). Every stage
change goes through transition(), which refuses moves the table does not allow,
so a todo cannot skip verification or land twice. Workflow results are read
straight from the workflow's task output file (records_from_output), so the
main session never re-types them.

    python3 scripts/todos/state.py <command> RUNFILE [options]
"""

import argparse
import copy
import datetime
import fnmatch
import json
import os
import posixpath
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import todofile  # noqa: E402
import group  # noqa: E402

TERMINAL = {"archived", "blocked", "skipped"}
ALLOWED = {
    "scanned": {"triaged"},
    "triaged": {"ready", "skipped"},
    "ready": {"executing"},
    "executing": {"staged", "failed"},
    "staged": {"verified", "failed"},
    "verified": {"pr_open", "failed"},
    "failed": {"ready"},
    "pr_open": {"reviewed"},
    "reviewed": {"merged"},
    "merged": {"archived"},
}
for _targets in ALLOWED.values():
    _targets.add("blocked")  # spec §8: any non-terminal stage may block, with a reason
# The one exit from a terminal stage (todo 469): the owner cleared the blocker. Added after the
# loop above, so blocked -> blocked stays refused. blocked is still terminal for is_complete().
ALLOWED["blocked"] = {"ready"}
MAX_RETRIES = 1
OUTCOMES = {"ready", "blocked", "skipped"}
NOT_PLANNED = {"scanned", "triaged", "blocked", "skipped"}
LANDED = {"merged", "archived"}
WORK_FIELDS = ("worktree", "branch", "tree_id", "ac_file")
# What a blocked attempt leaves on its entry; reopening moves it to `previous` (see _reopen).
ATTEMPT_FIELDS = ("reason", "group", "slot", "wave", *WORK_FIELDS, "verified_ac", "test_edits", "review_round",
                  "repoints", "reverify", "blocked_by")


class TransitionError(Exception):
    pass


def run_path(todos_dir, run_id):
    return Path(todos_dir) / f".sweep-run-{run_id}.json"


def new_run(run_id, selector, workers, todos, open_ids):
    return {
        "run_id": run_id,
        "selector": selector,
        "workers": workers,
        "open_ids": sorted(open_ids),
        "todos": {
            t["id"]: {
                "stage": "scanned",
                "path": t["path"],
                "priority": t["priority"],
                "dependencies": list(t.get("dependencies", [])),
                "stranded": bool(t.get("stranded", False)),
                "source_review": str(t.get("source_review") or ""),  # a lane (group.review_lane)
                "attempts": 0,
                "reason": "",
            }
            for t in todos
        },
        "groups": {},
        "waves": [],
        "unschedulable": {},
    }


def load(path):
    return json.loads(Path(path).read_text())


def save(run, path):
    path = Path(path)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(run, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, path)


def transition(run, todo_id, to, **fields):
    for name in {"stage", "attempts"}:
        if name in fields:
            raise TransitionError(f"{todo_id}: {name} cannot be set as a field")
    entry = run["todos"].get(todo_id)
    if entry is None:
        raise TransitionError(f"{todo_id}: not in this run")
    frm = entry["stage"]
    if to not in ALLOWED.get(frm, set()):
        raise TransitionError(f"{todo_id}: {frm} -> {to} is not allowed")
    if (to in {"blocked", "failed"} or frm == "blocked") and not fields.get("reason"):
        raise TransitionError(f"{todo_id}: {frm} -> {to} needs a reason")
    if frm == "blocked":
        _reopen(run, todo_id, entry)
    elif frm == "failed" and to == "ready":
        if entry["attempts"] >= MAX_RETRIES:
            raise TransitionError(f"{todo_id}: already retried once; block it with a reason")
        entry["attempts"] += 1
        # Regroup from scratch; never share a group with the failed attempt. Its worktree, tree, evidence and
        # re-points move to `previous` like a reopened block's (todo 494 F2/F11): a fresh worker's brief must
        # not list a re-point whose target lives in the abandoned worktree, and a later block by the retry's
        # worker must not leave the rejected tree on the entry for --reverify to re-judge.
        entry.setdefault("previous", []).append({k: entry.pop(k) for k in ATTEMPT_FIELDS if k in entry})
    entry["stage"] = to
    entry.update(fields)


def _reopen(run, todo_id, entry):
    """blocked -> ready once the blocker is cleared (todo 469; the pilot's 432 had no way back).

    Refused for a todo with a PR: the fix belongs on that PR, not in a second attempt. Refused
    without a triage record, which regrouping needs. The blocked attempt's group, worktree,
    branch and verdict move to `previous`, so its staged work stays findable while the todo is
    regrouped like a retry. attempts is not spent: a cleared blocker is not a failed attempt.
    """
    if entry.get("pr"):
        raise TransitionError(f"{todo_id}: PR #{entry['pr']} is open for it; fix it on that PR")
    if not entry.get("triage"):
        raise TransitionError(f"{todo_id}: no triage record to regroup from; triage it first")
    entry.setdefault("previous", []).append({k: entry.pop(k) for k in ATTEMPT_FIELDS if k in entry})
    run.get("unschedulable", {}).pop(todo_id, None)


def reopen_reverify(run, todo_id, reason):
    """blocked -> ready, verifying the blocked attempt's staged worktree as it is (todo 492, the 423 case).

    A worker that stopped on an owner-only criterion left finished, staged work, and no verdict. When
    the owner clears that criterion (usually a `repoint`), a plain reopen regroups the todo onto a
    fresh worker in a new worktree and throws the work away. This reopens it like `_reopen` (the
    attempt is still copied to `previous`), then puts the worktree, branch, evidence and re-points
    back on the entry and marks it `reverify`: `execute_args` re-reads the tree and briefs the
    workflow to skip the planner and the worker and run only the verifier.
    """
    entry = run["todos"].get(todo_id)
    if entry is None:
        raise TransitionError(f"{todo_id}: not in this run")
    if entry["stage"] != "blocked":
        raise TransitionError(f"{todo_id}: is {entry['stage']}; only a blocked todo is re-verified in place")
    # A tree a verifier already judged (a retry worker's, or one blocked after a failed verdict) is never
    # re-verified: that would re-judge a rejected tree without spending a retry (PR #885 review). A todo
    # that has been retried had a tree rejected already, whoever blocked it since (todo 494 F11).
    if entry.get("attempts", 0) != 0:
        raise TransitionError(f"{todo_id}: was retried after a failed verdict, so a verifier already judged its "
                              "work; reopen it without --reverify")
    if entry.get("blocked_by") != "worker":
        raise TransitionError(f"{todo_id}: only a todo its first worker blocked is re-verified in place; "
                              "reopen it without --reverify")
    missing = [k for k in WORK_FIELDS if not entry.get(k)]
    if missing:
        raise TransitionError(f"{todo_id}: no staged attempt to re-verify (missing {', '.join(missing)})")
    if run["groups"].get(entry.get("group"), {}).get("ids") != [todo_id]:
        raise TransitionError(f"{todo_id}: its blocked attempt was a group of several todos; only a one-todo "
                              "attempt is re-verified in place, so reopen it without --reverify")
    if not Path(entry["worktree"]).is_dir():
        raise TransitionError(f"{todo_id}: its worktree {entry['worktree']} is gone; reopen it without --reverify")
    _refuse_shared_worktree(run, todo_id, entry["worktree"])
    kept = {k: entry[k] for k in (*WORK_FIELDS, "repoints") if k in entry}
    transition(run, todo_id, "ready", reason=reason)
    entry.update(kept, reverify=True)


def _refuse_shared_worktree(run, todo_id, worktree, briefing=False):
    """Land commits a worktree's whole index, and the verifier checks only the todos it is given. So a
    re-verify is only for a worktree no other todo has ever recorded, live or in `previous`, at any
    stage (PR #885 round 2: a group-mate reopened the plain way or blocked later still has its work
    staged there). A multi-todo attempt is reopened the plain way. From execute-args (`briefing`) the
    todo is already ready, so the recovery is to block it first (todo 494 F13)."""
    others = sorted(i for i, e in run["todos"].items() if i != todo_id and worktree in
                    [e.get("worktree")] + [a.get("worktree") for a in e.get("previous", [])])
    if others:
        how = ("block it (`set … blocked`), then reopen it without --reverify" if briefing
               else "reopen it without --reverify")
        raise TransitionError(f"{todo_id}: its worktree also holds the work of todo {', '.join(others)}; "
                              f"only a one-todo attempt is re-verified in place, so {how}")


def summary(run):
    out = {}
    for todo_id, entry in sorted(run["todos"].items()):
        out.setdefault(entry["stage"], []).append(todo_id)
    return out


def recorded_worktrees(run):
    """{todo id: [worktree, ...]}: every todo's recorded worktree, including a reopened todo's earlier
    attempts -- `finish` deletes the run file, so the wrap-up lists these first (todo 468, F5). An archived
    todo's own worktree was removed at cleanup (pushed and merged), but a blocked attempt before it never
    is, so it stays listed for the owner (todo 473)."""
    out = {}
    for todo_id, entry in sorted(run["todos"].items()):
        current = entry.get("worktree")
        earlier = [a.get("worktree") for a in entry.get("previous", [])]
        if entry["stage"] == "archived":
            paths = [p for p in earlier if p and p != current]
        else:
            paths = [p for p in [current] + earlier if p]
        if paths:
            out[todo_id] = list(dict.fromkeys(paths))
    return out


def is_complete(run):
    return all(entry["stage"] in TERMINAL for entry in run["todos"].values())


def records_from_output(path, key):
    """Read a workflow's return value from its task output file."""
    data = json.loads(Path(path).read_text())
    if isinstance(data, dict) and key not in data and "result" in data:
        data = data["result"]
        if isinstance(data, str):
            data = json.loads(data)
    if not isinstance(data, dict) or key not in data:
        raise ValueError(f"{path}: no '{key}' in the workflow output")
    return data[key]


def triage_args(run):
    return [{"id": i, "path": e["path"]} for i, e in sorted(run["todos"].items()) if e["stage"] == "scanned"]


def record_triage(run, records, root=None):
    for record in records:
        if record["id"] not in run["todos"]:
            raise KeyError(f"triage record for {record['id']}, which is not in this run")
    for record in records:
        _normalize_predicted_files(record, root)
        run["todos"][record["id"]]["triage"] = record
        transition(run, record["id"], "triaged")
    return sorted(i for i, e in run["todos"].items() if e["stage"] == "scanned")


def _normalize_predicted_files(record, root=None):
    """Repo-relative paths only (final review m11): a leading ./ is stripped, since the
    lanes match exact repo-relative paths; an absolute path cannot be mapped onto the repo,
    so it is dropped and listed in `dropped_files` for the plan to show. A path under the
    triage root (triage-args --root) is made relative to it first: triagers searching the
    root get absolute hits back, and dropping them would drop their lanes (PR #868). A path reported
    through a symlink (/tmp is /private/tmp on macOS) is matched as reported and resolved, against the
    resolved root, so either form of either one keeps its lane (todo 473)."""
    prefix = str(Path(root).resolve()).rstrip("/") + "/" if root else None
    kept, dropped = [], []
    for path in record.get("predicted_files", []):
        path = str(path)
        if prefix and os.path.isabs(path):
            form = next((f for f in (path, os.path.realpath(path)) if f.startswith(prefix)), None)
            if form:
                path = form[len(prefix):]
        while path.startswith("./"):
            path = path[2:]
        (dropped if os.path.isabs(path) else kept).append(path)
    record["predicted_files"] = kept
    if dropped:
        record["dropped_files"] = dropped


def accept_ready(run):
    moved = []
    for todo_id, entry in sorted(run["todos"].items()):
        record = entry.get("triage") or {}
        if (entry["stage"] == "triaged" and record.get("class") == "ready"
                and not record.get("owner_question") and not entry["stranded"]):
            transition(run, todo_id, "ready")
            moved.append(todo_id)
    return moved


def questions(run):
    out = []
    for todo_id, entry in sorted(run["todos"].items()):
        record = entry.get("triage") or {}
        if entry["stage"] != "triaged":
            continue
        if record.get("class") != "ready" or record.get("owner_question") or entry["stranded"]:
            out.append({"id": todo_id, "class": record.get("class", ""), "question": record.get("owner_question", ""),
                        "blocked_on": record.get("blocked_on", ""), "evidence": record.get("evidence", ""),
                        "stranded": entry["stranded"]})
    return out


def decide(run, todo_id, outcome, decision="", verify_only=False, reset_stranded=False):
    if outcome not in OUTCOMES:
        raise ValueError(f"outcome must be one of {sorted(OUTCOMES)}, got {outcome!r}")
    entry = run["todos"][todo_id]
    if decision:
        entry["owner_decision"] = decision
    entry["verify_only"] = bool(verify_only)
    entry["reset_stranded"] = bool(reset_stranded)
    if outcome == "blocked":
        reason = decision or (entry.get("triage") or {}).get("blocked_on") or "blocked at triage"
        transition(run, todo_id, "blocked", reason=reason)
    else:
        transition(run, todo_id, outcome)


def run_git(repo, *args):
    proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


REPOINT_MARKER = " → todo {to} (re-pointed {date})"
# The marker REPOINT_MARKER writes, found again on a line: re-running `repoint` on a later day finds the
# earlier date's marker, which is the one the verifier was told about (todo 494 F5).
REPOINT_MARKER_RE = re.compile(r"→ todo (\d+) \(re-pointed (\d{4}-\d{2}-\d{2})\)")
DATE_RE = re.compile(r"\A\d{4}-\d{2}-\d{2}\Z")


def _valid_date(date):
    """True for a real YYYY-MM-DD date: it goes into the marker and the workflows' REPOINTS line (494 F4)."""
    if not DATE_RE.match(str(date)):
        return False
    try:
        datetime.date.fromisoformat(date)
    except ValueError:
        return False
    return True


def _repoint_targets(entry):
    """Every todo number an entry re-points to, in this attempt or an earlier one."""
    attempts = [entry] + list(entry.get("previous", []))
    return {str(r["to"]) for a in attempts for r in a.get("repoints", [])}


def repoint(run, todo_id, index, to, decision, date, git=run_git):
    """Re-point one open criterion of a todo with staged work to another todo, on the owner's word.

    Re-points normally land in the triage PR, before any worker runs. This one is for a criterion
    found owner-only mid-run (todo 423's on-device walkthrough, moved to a follow-up todo). It
    appends the marker to the criterion's checkbox line in the worktree (the archive tripwire reads
    that line only), stages it, updates the criterion's `ac.json` text (flip-acs compares the two),
    and records the re-point on the entry. The verifier treats a changed criterion as edited unless
    the brief lists it, so this record is the only thing that lets the change through.
    """
    entry = run["todos"].get(todo_id)
    if entry is None:
        raise TransitionError(f"{todo_id}: not in this run")
    # Todo 494 F3: only the blocked attempt's own worktree, or the one a --reverify reopen kept. A plain
    # ready todo (a failed -> ready retry, or a plain reopen) gets a fresh worker, never that worktree.
    if not (entry["stage"] == "blocked" or (entry["stage"] == "ready" and entry.get("reverify"))):
        plain = " (not --reverify)" if entry["stage"] == "ready" else ""
        raise TransitionError(f"{todo_id}: is {entry['stage']}{plain}; re-point a blocked todo, or one reopened "
                              "with --reverify, before execute-args")
    if not decision.strip():
        raise TransitionError(f"{todo_id}: a re-point needs the owner's decision")
    if not str(to).isdigit() or str(to) == todo_id:
        raise TransitionError(f"{todo_id}: a re-point target is another todo's number, not {to!r}")
    if not _valid_date(date):
        raise TransitionError(f"{todo_id}: --date must be a YYYY-MM-DD date, not {date!r}")
    # Todo 494 F16: two unmerged PRs must not both create todo NNN as their re-point target.
    taken = sorted(i for i, e in run["todos"].items() if i != todo_id and str(to) in _repoint_targets(e))
    if taken:
        raise TransitionError(f"{todo_id}: todo {to} is already the re-point target of todo {', '.join(taken)} in "
                              "this run; pick the next free number")
    worktree, ac_file = entry.get("worktree"), entry.get("ac_file")
    if not worktree or not ac_file or not Path(worktree).is_dir():
        raise TransitionError(f"{todo_id}: no staged worktree to re-point in")
    if not Path(worktree, entry["path"]).is_file():
        raise TransitionError(f"{todo_id}: {entry['path']} is not in {worktree} (has Land already archived it?); "
                              "a re-point edits the pending todo file before Land")
    target = sorted(Path(worktree, "todos").glob(f"{to}-*.md"))
    if len(target) != 1 or not git(worktree, "ls-files", "--", f"todos/{target[0].name}").strip():
        raise TransitionError(f"{todo_id}: todo {to} must be one open todo file under todos/, staged in {worktree}")
    # A new todo made for this re-point, so the criterion can never land on a todo that is already done
    # (a stale pending copy in an old worktree, or a number origin/main has since used; PR #885 review).
    if git(worktree, "ls-tree", "--name-only", "HEAD", "--", f"todos/{target[0].name}").strip():
        raise TransitionError(f"{todo_id}: todo {to} is already on the branch; re-point to a new todo created "
                              "for it and staged in the worktree")
    try:
        on_main = git(worktree, "ls-tree", "-r", "--name-only", "origin/main", "--", "todos")
    except RuntimeError:
        on_main = ""  # no origin/main in this repo (the tests); nothing to collide with
    if any(posixpath.basename(f).startswith(f"{to}-") for f in on_main.splitlines()):
        raise TransitionError(f"{todo_id}: origin/main already has a todo {to}; pick the next free number")
    marker = REPOINT_MARKER.format(to=to, date=date)
    path = Path(worktree, entry["path"])
    text = path.read_text()
    boxes = todofile.ac_lines(text)
    if not 0 <= index < len(boxes):
        raise TransitionError(f"{todo_id}: no criterion at index {index} (it has {len(boxes)})")
    line_no, checked, _ = boxes[index]
    if checked:
        raise TransitionError(f"{todo_id}: criterion {index} is already checked")
    acp = Path(worktree, ac_file)
    ac = json.loads(acp.read_text())  # checked before the todo file changes, so a refusal leaves both alone
    mine = [e for e in ac if str(e.get("todo")) == todo_id and e.get("index") == index]
    if len(mine) != 1:
        raise TransitionError(f"{todo_id}: {ac_file} has {len(mine)} entries for criterion {index}, not one")
    lines = text.splitlines(keepends=True)
    if todofile.is_repoint(lines[line_no]):
        # Compare only `→ todo NNN` (todo 494 F5): a rerun on a later day keeps the marker already there.
        same = [m.group(0) for m in REPOINT_MARKER_RE.finditer(lines[line_no]) if m.group(1) == str(to)]
        if not same:
            raise TransitionError(f"{todo_id}: criterion {index} is already re-pointed elsewhere")
        marker = " " + same[0]
    else:
        body = lines[line_no].rstrip("\n")
        lines[line_no] = body.rstrip() + marker + lines[line_no][len(body):]
        path.write_text("".join(lines))
    mine[0].update(text=todofile.CHECKBOX_RE.sub("", todofile.ac_lines("".join(lines))[index][2], count=1).strip())
    mine[0].update(command="", evidence_path="", note="re-pointed")  # the worker's form for a re-point
    mine[0]["pass"] = False
    acp.write_text(json.dumps(ac, indent=1) + "\n")
    git(worktree, "add", "--", entry["path"])
    repoints = [r for r in entry.get("repoints", []) if r["index"] != index]
    entry["repoints"] = repoints + [{"index": index, "to": str(to), "marker": marker.strip(), "decision": decision}]
    return marker.strip()


def _triage_fields(entry, record, today):
    """The frontmatter fields apply_triage writes for one triaged todo."""
    fields = {"triage": record["class"], "triaged": today}
    if record.get("blocked_on"):
        fields["blocked_on"] = record["blocked_on"]
    # Todo 468: an owner who blocked a needs-design or stale todo has answered it. blocked-owner makes
    # the next scan skip it until the file changes, instead of asking the same question again.
    # Only the owner's own block counts (decide stores the decision as the reason): a worker that
    # blocks after an owner's "ready" answer has not been answered by the owner (PR #869 round 1).
    if (entry["stage"] == "blocked" and entry.get("owner_decision")
            and entry.get("reason") == entry["owner_decision"] and not record["class"].startswith("blocked-")):
        fields["triage"] = "blocked-owner"
        fields.setdefault("blocked_on", entry["owner_decision"])
    if entry.get("owner_decision"):
        fields["owner_decision"] = entry["owner_decision"]
    return fields


def apply_triage(run, repo_root, today, git=run_git):
    """Write durable triage facts into each todo's frontmatter (spec §6.4)."""
    repo_root = Path(repo_root)
    # Todo 474: both the in_progress file and its pending name on disk is one id twice. Skipping the rename
    # would leave the old file behind, so refuse before anything is written.
    for todo_id, entry in sorted(run["todos"].items()):
        if entry.get("triage") and entry.get("reset_stranded"):
            rel = entry["path"]
            new_rel = str(Path(rel).with_name(todofile.with_status(Path(rel).name, "pending")))
            if new_rel != rel and (repo_root / rel).exists() and (repo_root / new_rel).exists():
                raise RuntimeError(f"{todo_id}: both {rel} and {new_rel} exist, so the id is on disk twice; "
                                   "keep one (git rm the other), then rerun apply-triage")
    # Todo 519: a field set_fields would refuse (a duplicate key line, a multi-line value) is refused here,
    # before any todo is renamed or edited, not as a ValueError part-way through the loop below. A missing
    # file is left to the loop, where it fails as before and a rerun picks up from it (todo 468).
    for _, entry in sorted(run["todos"].items()):
        record = entry.get("triage")
        if not record:
            continue
        path, keys = repo_root / entry["path"], list(_triage_fields(entry, record, today))
        if entry.get("reset_stranded"):
            renamed = path.with_name(todofile.with_status(path.name, "pending"))
            path, keys = (renamed if renamed.exists() else path), ["status", *keys]
        if path.is_file():
            text = path.read_text()
            problem = next((p for p in (todofile.field_problem(text, key) for key in keys) if p), None)
            if problem:
                raise ValueError(f"{path}: {problem}; edit it by hand")
    changed = []
    for todo_id, entry in sorted(run["todos"].items()):
        record = entry.get("triage")
        if not record:
            continue
        rel = entry["path"]
        if entry.get("reset_stranded"):
            new_rel = str(Path(rel).with_name(todofile.with_status(Path(rel).name, "pending")))
            # Todo 468: a rerun after a mid-batch failure finds this rename already done (the run file
            # was not saved), or rel already the pending path; git mv would refuse either way.
            if not (repo_root / new_rel).exists():
                git(repo_root, "mv", rel, new_rel)  # rename first: git mv stages the pre-edit content
            rel = entry["path"] = new_rel
            todofile.set_fields(repo_root / rel, {"status": "pending"})
            heading = f"### {today} - Returned to pending by the todo sweep (run {run['run_id']})"
            # Todo 474: matched without the date, so a rerun on a later day does not add a second entry.
            if f" - Returned to pending by the todo sweep (run {run['run_id']})" not in (repo_root / rel).read_text():
                todofile.append_work_log(
                    repo_root / rel,
                    f"{heading}\n\n"
                    "- Was `in_progress` with no branch, worktree or open PR; the owner confirmed the reset.\n",
                )
            entry["stranded"] = entry["reset_stranded"] = False
        todofile.set_fields(repo_root / rel, _triage_fields(entry, record, today))
        changed.append(rel)
    return changed


SIZE_RANK = {"xs": 0, "s": 1, "m": 2, "l": 3}


def apply_grouping(run):
    """Group the ready todos and APPEND their groups and waves.

    Appending (never replacing) is what lets a retried todo be regrouped
    without erasing the groups and waves that already have PRs.
    """
    _ungroup_stale_deps(run)
    todos = [
        {"id": i, "priority": e["priority"], "dependencies": e["dependencies"],
         "verify_only": e.get("verify_only", False), "triage": e["triage"],
         "source_review": e.get("source_review", "")}
        for i, e in sorted(run["todos"].items()) if e["stage"] == "ready" and "group" not in e
    ]
    # A dependency already past triage in this run (grouped earlier, executing, pr_open, merged, ...)
    # is not "open outside the run": dropping it here lets its dependent wait at execute_args
    # instead of being blocked for good (final review I3). Blocked/skipped ones stay open.
    in_run = {i for i, e in run["todos"].items() if e["stage"] not in NOT_PLANNED}
    # The new waves are appended after the run's last wave, which may still be executing or in
    # review; its lanes are busy for the first new wave (PR #869 round 1).
    busy = set().union(*(run["groups"][g]["lanes"] for g in _unmerged(run, run["waves"][-1] if run["waves"] else [])))
    # Todo 492: a re-verified todo is the worktree it was staged in: a group of its own, never bundled or
    # merged by file, in a wave of its own BEFORE the planned ones. It needs no worker, and a planned
    # dependent then waits in execute_args for it to merge instead of running first (PR #885 round 2).
    again = sorted((t for t in todos if run["todos"][t["id"]].get("reverify")), key=group._rank)
    todos = [t for t in todos if t not in again]
    again_lanes = [set(group.lanes_for(t["triage"]) | group.review_lane(t)) for t in again]
    result = group.plan(todos, set(run["open_ids"]) - in_run, run["workers"],
                        busy_lanes=again_lanes[-1] if again else busy)
    offset = max((int(g[1:]) for g in run["groups"]), default=0)
    rename = {gid: f"g{offset + int(gid[1:])}" for gid in result["groups"]}
    for todo_id, reason in result["unschedulable"].items():
        transition(run, todo_id, "blocked", reason=reason)
    for gid, spec in result["groups"].items():
        run["groups"][rename[gid]] = dict(spec, deps=[rename[d] for d in spec["deps"]])
        for todo_id in spec["ids"]:
            run["todos"][todo_id]["group"] = rename[gid]
    new_waves = [[rename[g] for g in wave] for wave in result["waves"]]
    offset = max((int(g[1:]) for g in run["groups"]), default=0)
    first = []
    for n, (t, lanes) in enumerate(zip(again, again_lanes), start=offset + 1):
        run["groups"][f"g{n}"] = {"ids": [t["id"]], "lanes": sorted(lanes), "deps": []}
        run["todos"][t["id"]]["group"] = f"g{n}"
        first.append([f"g{n}"])
    new_waves = first + new_waves
    run["waves"].extend(new_waves)
    run["unschedulable"].update(result["unschedulable"])
    return {"waves": new_waves, "unschedulable": result["unschedulable"]}


def slot_for(wave, position, workers):
    return (wave % 2) * workers + position


def _group_entries(run, gid):
    """The todos currently in group gid (a retried todo moves to a new group)."""
    return [(i, run["todos"][i]) for i in run["groups"][gid]["ids"] if run["todos"][i].get("group") == gid]


def _unmerged(run, gids):
    """The groups in gids with a todo that has not merged yet (still holding their lanes)."""
    return [g for g in gids if any(e["stage"] not in LANDED | TERMINAL for _, e in _group_entries(run, g))]


def _group_is_stale(run, gid):
    """True when any todo originally placed in gid no longer belongs to it
    (spec S1): a group that lost SOME of its members to a retry is just as
    stale as one that lost all of them -- its wave was placed assuming every
    original member would run there together, and that assumption is gone
    the moment even one has moved elsewhere. A fully emptied group (every id
    moved) is the special case where this is also true.
    """
    return any(run["todos"][i].get("group") != gid for i in run["groups"][gid]["ids"])


def _being_regrouped(run, todo_id):
    """True for an in-run todo that is ready with no group: this apply_grouping plans it."""
    entry = run["todos"].get(todo_id)
    return entry is not None and entry["stage"] == "ready" and "group" not in entry


def _ungroup_stale_deps(run):
    """Drop the group of any ready todo whose group depends, directly or
    transitively, on a group a retry has emptied or partly emptied (spec R2,
    S1): its wave was placed relative to a dependency that has since moved
    to a later wave, so its own placement can no longer be trusted and must
    be recomputed.
    """
    changed = True
    while changed:
        changed = False
        for todo_id, entry in sorted(run["todos"].items()):
            gid = entry.get("group")
            if entry["stage"] != "ready" or gid is None:
                continue
            if (any(_group_is_stale(run, dep) for dep in run["groups"][gid]["deps"])
                    or any(_being_regrouped(run, dep) for dep in entry["dependencies"])):
                entry.pop("group", None)
                changed = True


def _dependencies_of(run, gid, todo_id, entry):
    """Every in-run todo that must be merged or archived before todo_id is handed out (final
    review I3): its own in-run dependencies, read by stage -- a retried dependency has left its
    group, so _group_entries would hide it -- plus every todo ever placed in a dependency group
    of gid that holds one of them (one group is one PR). Current members of gid ship with it."""
    members = {i for i, _ in _group_entries(run, gid)}
    direct = {d for d in entry["dependencies"] if d in run["todos"] and d not in members}
    related = set(direct)
    for dep_gid in run["groups"][gid]["deps"]:
        recorded = set(run["groups"][dep_gid]["ids"])
        if recorded & direct:
            related |= recorded
    return sorted(related - members - {todo_id})


def _repoints(entries):
    """{todo id: [{index, to, marker}]} -- the owner-authorized re-points the verifier may accept."""
    return {i: [{k: r[k] for k in ("index", "to", "marker")} for r in e["repoints"]]
            for i, e in entries if e.get("repoints")}


def _evidence_dir(ac_file, gid):
    """The evidence dir a group's ac_file sits in, or the group's default (todo 494 F15). Only a relative
    path under .sweep-evidence/ counts: an absolute or bare ac_file from a worker would otherwise turn a
    repair worker's EVIDENCE_DIR into an absolute path or the worktree root."""
    ac_file = str(ac_file or "")
    if ac_file and not posixpath.isabs(ac_file):
        parent = posixpath.dirname(posixpath.normpath(ac_file))
        if parent.startswith(".sweep-evidence/"):
            return parent
    return f".sweep-evidence/{gid}"


def _reverify_tree(todo_id, entry, git):
    """The tree a re-verify brief records: the worktree's index now. It must still exist (todo 494 F13),
    and the only paths that may have changed since the worker's block are the todo file and each
    re-point's new target todo (494 F9): anything else staged since then would become the verified tree."""
    worktree = entry.get("worktree")
    if not worktree or not Path(worktree).is_dir():
        raise TransitionError(f"{todo_id}: its worktree {worktree} is gone, so there is nothing to re-verify; "
                              "block it (`set … blocked`), then reopen it without --reverify")
    tree = git(worktree, "write-tree").strip()
    if entry.get("tree_id") and tree != entry["tree_id"]:
        changed = [p for p in git(worktree, "diff-tree", "-r", "--name-only", "--no-renames", "-z",
                                  entry["tree_id"], tree).split("\0") if p]
        targets = {str(r["to"]) for r in entry.get("repoints", [])}
        stray = [p for p in changed if p != entry["path"] and not (
            p.startswith("todos/") and "/" not in p[len("todos/"):] and p.endswith(".md")
            and p[len("todos/"):].split("-", 1)[0] in targets)]
        if stray:
            raise TransitionError(f"{todo_id}: its worktree changed outside the re-point since the block "
                                  f"({', '.join(stray[:5])}); unstage those, or block it and reopen it without "
                                  "--reverify")
    return tree


def execute_args(run, wave, main_root, git=run_git):
    if wave >= len(run["waves"]):
        raise ValueError(f"wave {wave} does not exist ({len(run['waves'])} waves)")
    if wave >= 1:
        for gid in run["waves"][wave - 1]:
            for todo_id, entry in _group_entries(run, gid):
                if entry["stage"] in {"ready", "executing"}:
                    raise TransitionError(f"wave {wave - 1} has not finished executing ({todo_id})")
    for w in range(wave - 1):  # every earlier wave, not just wave-2: it may hold a same-parity slot
        for gid in run["waves"][w]:
            for todo_id, entry in _group_entries(run, gid):
                if entry["stage"] not in TERMINAL | {"merged"}:
                    raise TransitionError(f"wave {w} is not merged yet ({todo_id} is {entry['stage']})")
    gids = run["waves"][wave]
    # Todo 492: a re-verified todo is its own group and the only todo its worktree ever held. Checked
    # again here, before anything changes: grouping or a later reopen must not have broken either.
    trees = {}
    for gid in gids:
        members = _group_entries(run, gid)
        again = [(i, e) for i, e in members if e["stage"] == "ready" and e.get("reverify")]
        if again and len(members) != 1:
            raise TransitionError(f"{gid}: a re-verified todo shares its group with other work; block them "
                                  "and reopen each the plain way")
        for todo_id, entry in again:
            _refuse_shared_worktree(run, todo_id, entry.get("worktree"), briefing=True)
            trees[todo_id] = _reverify_tree(todo_id, entry, git)
    # Todo 468: wave N-1 is still in review or Land while this wave executes, so its lanes are
    # forbidden too, until every todo left in it has merged. A group that HOLDS such a lane would
    # put two PRs on it at once: refuse before anything changes (PR #869 round 1).
    previous = _unmerged(run, run["waves"][wave - 1]) if wave >= 1 else []
    for gid in gids:
        holders = [other for other in previous if set(run["groups"][gid]["lanes"]) & set(run["groups"][other]["lanes"])]
        clash = set(run["groups"][gid]["lanes"]) & {lane for other in holders for lane in run["groups"][other]["lanes"]}
        if clash and _group_entries(run, gid):
            # Todo 494 F10: a failed group never merges by itself; waiting for it would wait forever.
            failed = [other for other in holders if any(e["stage"] == "failed" for _, e in _group_entries(run, other))]
            how = (f"{', '.join(failed)} failed and never merges until its todos are retried (`set … ready`, then "
                   "`group`) or blocked" if failed else "wait for that wave to merge")
            raise TransitionError(f"{gid} holds {', '.join(sorted(clash))}, which wave {wave - 1} still holds; {how}")
    # Todo 468: a member blocked or skipped after grouping (decide or `set`, not the gate below) never
    # ran in this wave -- a retried one still carries its first attempt's `wave` (PR #869 round 1). It
    # leaves its group like a gate-blocked one, and its in-group dependents block with it.
    gone = {i for gid in gids for i, e in _group_entries(run, gid)
            if e["stage"] in {"blocked", "skipped"} and e.get("wave") != wave}
    to_block = {}
    for gid in gids:
        for todo_id, entry in _group_entries(run, gid):
            if entry["stage"] != "ready":
                continue
            for dep in _dependencies_of(run, gid, todo_id, entry):
                stage = run["todos"][dep]["stage"]
                if stage in {"blocked", "skipped"}:
                    to_block.setdefault(todo_id, f"dependency {dep} {stage}")
                elif stage not in LANDED:
                    raise TransitionError(f"{todo_id}: dependency {dep} is {stage}, not merged; wait for it to merge "
                                          "(run `group` first if it was retried)")
    # PR #861 B-1: a member depending (directly or transitively) on a member blocked above cannot
    # run either -- it would ship without the code it depends on. Block it too, naming that member.
    changed = True
    while changed:
        changed = False
        for gid in gids:
            for todo_id, entry in _group_entries(run, gid):
                if entry["stage"] != "ready" or todo_id in to_block:
                    continue
                blocked_dep = next((d for d in entry["dependencies"] if d in to_block or d in gone), None)
                if blocked_dep:
                    how = "blocked" if blocked_dep in to_block else run["todos"][blocked_dep]["stage"]
                    to_block[todo_id] = f"dependency {blocked_dep} {how}"
                    changed = True
    for todo_id, reason in to_block.items():
        transition(run, todo_id, "blocked", reason=reason)
    for todo_id in gone | set(to_block):
        # N1: a gate-blocked todo never ran, so it leaves its group entirely -- both the entry's
        # group and the recorded ids -- or set_group/ensure_worktree/review_args would read it as
        # the group's first member, and _dependencies_of would count it against the group's dependents.
        gid = run["todos"][todo_id].pop("group")
        run["groups"][gid]["ids"] = [i for i in run["groups"][gid]["ids"] if i != todo_id]
    briefs = []
    for position, gid in enumerate(gids, start=1):
        entries = [(i, e) for i, e in _group_entries(run, gid) if i not in to_block and e["stage"] not in TERMINAL]
        if not entries:
            continue  # every todo that was here got regrouped into a later wave, or was just blocked
        held = run["groups"][gid]["lanes"]
        forbidden = sorted({lane for other in gids + previous if other != gid
                            for lane in run["groups"][other]["lanes"]})
        slot = slot_for(wave, position, run["workers"])
        reverify = None
        if all(e.get("reverify") for _, e in entries):
            first = entries[0][1]
            tree = trees[entries[0][0]]  # a re-point since the block moved it
            for _, e in entries:
                e["tree_id"] = tree
            reverify = {"worktree": first["worktree"], "branch": first["branch"], "tree_id": tree,
                        "ac_file": first["ac_file"]}
        briefs.append({
            "run_id": run["run_id"],
            "group": gid,
            "ids": [i for i, _ in entries],
            "todo_paths": [e["path"] for _, e in entries],
            "owner_decisions": {i: e.get("owner_decision", "") for i, e in entries},
            "plan_needed": any(e["triage"]["class"] == "needs-research" for _, e in entries),
            "verify_only": all(e.get("verify_only") for _, e in entries),
            "in_scope_files": sorted({f for _, e in entries for f in e["triage"]["predicted_files"]}),
            "lanes_held": [group.lane_doc(lane) for lane in held],
            "lanes_forbidden": [group.lane_doc(lane) for lane in forbidden],
            "slot": slot,
            "evidence_dir": _evidence_dir(reverify["ac_file"] if reverify else "", gid),
            "main_root": main_root,
            "repoints": _repoints(entries),
            "reverify": reverify,
        })
        for todo_id, entry in entries:
            entry.pop("reverify", None)  # one re-verify: a failed one is retried by a worker, as usual
            transition(run, todo_id, "executing", group=gid, slot=slot, wave=wave, main_root=main_root)
    return briefs


def add_worktrees(run, briefs, root, git=run_git):
    """Create each worker brief's worktree before the workflow runs, and put its path and branch on the
    brief and on every todo of the group (todo 528, owner decision 2026-10-10). The workflow used to let
    `isolation: 'worktree'` make it; a worker that died then left a worktree nobody recorded, because
    agent() reports nothing for a null result. Now the path is known before any agent runs.

    Cut from origin/main with --no-track (tracking config is a .git/config write the sandbox denies),
    then the main checkout's .worktreeinclude files are copied in, as the harness did. A rerun after a
    failure part-way reuses a worktree this function already made (same branch, nothing changed in it);
    anything else at the path is refused. A re-verify brief already names its worktree and is skipped."""
    root = Path(root)
    for brief in briefs:
        if brief.get("reverify"):
            continue
        main_root = brief["main_root"]
        name = f"sweep-{run['run_id']}-{brief['group']}"
        path, branch = root / name, f"worktree-{name}"
        if path.exists():
            try:
                same = (git(path, "rev-parse", "--abbrev-ref", "HEAD").strip() == branch
                        and not git(path, "status", "--porcelain").strip())
            except RuntimeError:
                same = False
            if not same:
                raise RuntimeError(f"{brief['group']}: {path} already exists and is not this group's fresh "
                                   "worktree; move it aside, then rerun execute-args")
        else:
            root.mkdir(parents=True, exist_ok=True)
            git(main_root, "worktree", "add", "--no-track", "-b", branch, str(path), "origin/main")
        _copy_worktreeinclude(main_root, path, git)
        brief.update(worktree=str(path), branch=branch)
        for todo_id in brief["ids"]:
            run["todos"][todo_id].update(worktree=str(path), branch=branch)
    return briefs


def _copy_worktreeinclude(main_root, worktree, git):
    """Copy each file the main checkout's .worktreeinclude lists that is gitignored there (backend/.env,
    web/.env) into the new worktree, unless it already has one. A missing source is skipped: slot_env.py
    falls back to the main checkout's .env (todo 479)."""
    include = Path(main_root, ".worktreeinclude")
    if not include.is_file():
        return
    for line in include.read_text().splitlines():
        pattern = line.strip()
        if not pattern or pattern.startswith("#"):
            continue
        for src in sorted(Path(main_root).glob(pattern)):
            rel = src.relative_to(main_root).as_posix()
            dest = Path(worktree, rel)
            if not src.is_file() or dest.exists():
                continue
            try:
                git(main_root, "check-ignore", "-q", "--", rel)
            except RuntimeError:
                continue  # not ignored: a tracked file arrives with the checkout, and copying it would dirty it
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)


def evaluate(worker, verdict):
    """None when the verdict can be trusted, else why not (spec §5.2)."""
    if verdict is None:
        return "no verdict"
    if verdict["verdict"] != "pass":
        return "verifier: fail"
    if len({worker["tree_id"], verdict["tree_id_before"], verdict["tree_id_after"]}) != 1:
        return "staged tree changed during verification"
    if not verdict["clean_after"]:
        return "working tree not clean after verification"
    if "ids" in verdict and sorted(verdict["ids"]) != sorted(worker["ids"]):
        return "verdict covers different todos than the worker"
    ac_ids = {item["todo"] for item in verdict["ac"]}
    if not verdict["ac"] or any(i not in ac_ids for i in worker["ids"]):
        return "verifier passed without acceptance-criteria coverage for every todo"
    if not all(item["verified"] for item in verdict["ac"]):
        return "verifier passed with an unverified criterion"
    return None


def _ac_text(box):
    """A criterion's text as land._normalize_ac_text compares it: no checkbox, whitespace collapsed."""
    return " ".join(todofile.CHECKBOX_RE.sub("", box[2], count=1).split())


def criteria_problem(base_text, current_text, repoints=(), ignore_boxes=False):
    """Why the current Acceptance Criteria are not the merge-base ones, or None (todo 494 F1). The verifier's
    step 4 in code: the same count, text and order, and (unless Land already flipped boxes) the same box
    state. The one allowed change is an owner-authorized re-point: a listed criterion whose text, with its
    marker removed exactly once, is the merge-base text. An unlisted marker is an edit."""
    base, now = todofile.ac_lines(base_text), todofile.ac_lines(current_text)
    if len(base) != len(now):
        return f"{len(base)} criteria at the merge-base, {len(now)} now"
    markers = {r["index"]: " ".join(str(r["marker"]).split()) for r in repoints}
    for index, (old, new) in enumerate(zip(base, now)):
        was, text = _ac_text(old), _ac_text(new)
        marker = markers.get(index)
        if marker and text != was and text.count(marker) == 1:
            text = " ".join(text.replace(marker, "", 1).split())
        if text != was:
            return f"criterion {index} was edited"
        if not ignore_boxes and old[1] != new[1]:
            return f"criterion {index}'s box changed"
    return None


def git_criteria(run, todo_id, worktree, current_path, ignore_boxes, git=run_git):
    """criteria_problem for one todo of a worktree: its merge-base file (origin/main...HEAD, at the pending
    path) against the file in the worktree now (`current_path`: the archived one after Land). A file
    either side cannot be read is itself a problem, so the check fails closed."""
    entry = run["todos"][todo_id]
    try:
        base = git(worktree, "merge-base", "origin/main", "HEAD").strip()
        base_text = git(worktree, "show", f"{base}:{entry['path']}")
        current = Path(worktree, current_path).read_text()
    except (RuntimeError, OSError) as exc:
        return f"could not read the criteria to compare: {exc}"[:300]
    return criteria_problem(base_text, current, entry.get("repoints", []), ignore_boxes)


def execute_criteria(run, todo_id, worktree, git=run_git):
    """Before Land: the pending file, and box state must match too."""
    return git_criteria(run, todo_id, worktree, run["todos"][todo_id]["path"], False, git)


def review_criteria(run, todo_id, worktree, git=run_git):
    """After Land: the archived file, whose verified boxes Land already flipped."""
    return git_criteria(run, todo_id, worktree, todofile.archived_path(run["todos"][todo_id]["path"]), True, git)


def _same_path(a, b):
    return os.path.realpath(str(a)) == os.path.realpath(str(b))


def ingest_execute(run, results, criteria=None):
    """Record a todo-execute output. `criteria(run, todo_id, worktree)` returns why a staged worktree's
    Acceptance Criteria differ from the merge-base ones, or None; the CLI always passes git_criteria (todo
    494 F1). A worker that reports a worktree other than the one it was given fails (todo 528)."""
    outcome = {}
    for result in results:
        worker, verdict = result.get("worker"), result.get("verdict")
        # Final review I5: a blocked, failed or dead attempt may still have staged work in a worktree;
        # record where, so the next sweep (or the owner) can find it instead of redoing it.
        work = {k: (worker or {}).get(k) for k in WORK_FIELDS}
        work["worktree"] = work["worktree"] or result.get("worktree")
        work = {k: v for k, v in work.items() if v}
        # One worktree, one index: an edit to any todo's criteria fails the whole group, or Land would
        # commit the edited file with the group-mates that passed (round-2 review of PR #982).
        edited = None
        if criteria and worker is not None and worker.get("status") == "staged" and not evaluate(worker, verdict):
            for todo_id in result["ids"]:
                problem = criteria(run, todo_id, worker["worktree"])
                if problem:
                    edited = f"todo {todo_id}: {problem}"
                    break
        for todo_id in result["ids"]:
            given = run["todos"][todo_id].get("worktree")
            if worker is not None and given and worker.get("worktree") and not _same_path(worker["worktree"], given):
                transition(run, todo_id, "failed", reason=f"the worker reported worktree {worker['worktree']}, "
                                                          f"not the one it was given ({given})"[:500])
                outcome[todo_id] = run["todos"][todo_id]["stage"]
                continue
            if worker is None:
                transition(run, todo_id, "failed", reason="worker returned nothing", **work)
            elif worker["status"] == "blocked":
                # Todo 492: only a first worker's block leaves a tree no verifier has judged yet.
                transition(run, todo_id, "blocked", reason=worker.get("blockers") or "worker blocked", **work,
                           blocked_by="retry worker" if result.get("retried") else "worker")
            elif worker["status"] != "staged":
                transition(run, todo_id, "failed",
                           reason=f"worker status {worker['status']}: {worker.get('blockers', '')}", **work)
            else:
                transition(run, todo_id, "staged", worktree=worker["worktree"], branch=worker["branch"],
                           tree_id=worker["tree_id"], ac_file=worker["ac_file"])
                problem = evaluate(worker, verdict)
                if problem:
                    transition(run, todo_id, "failed", reason=_with_reasons(problem, verdict))
                elif edited:
                    transition(run, todo_id, "failed", reason=f"acceptance criteria were edited: {edited}"[:500])
                else:
                    transition(run, todo_id, "verified", test_edits=verdict["test_edits_flagged"],
                               verified_ac=verdict["ac"])
            outcome[todo_id] = run["todos"][todo_id]["stage"]
    return outcome


def set_group(run, gid, stage, **fields):
    for todo_id, _ in _group_entries(run, gid):
        transition(run, todo_id, stage, **fields)


def annotate(run, gid, **fields):
    """Record fields on every todo of a group without a stage change (e.g. a renamed branch)."""
    for name in ("stage", "attempts", "group"):
        if name in fields:
            raise TransitionError(f"{gid}: {name} cannot be set via annotate")
    for _, entry in _group_entries(run, gid):
        entry.update(fields)


def _with_reasons(problem, verdict):
    """Append the verifier's group-level reasons (VERDICT.reasons) to a failure reason."""
    reasons = [r for r in ((verdict or {}).get("reasons") or []) if r]
    return f"{problem}: {'; '.join(reasons)}" if reasons else problem


STATE_PY = os.path.abspath(__file__)
RESIDUE_SHOWN = 50


def worktree_snapshot(worktree, git=run_git):
    """HEAD, plus every path `git add -A` would pick up in the worktree, with its status and content
    hash (todo 480). Untracked files are listed one by one; ignored ones never, as `add -A` skips them
    too. The git guard stops reviewers staging or committing, so what a review leaves shows up here.
    The hash catches a further edit to a file that was already modified at the baseline."""
    head = git(worktree, "rev-parse", "HEAD").strip()
    fields = git(worktree, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--no-renames").split("\0")
    status, i = {}, 0
    while i < len(fields):
        item = fields[i]
        i += 1
        if len(item) < 4:
            continue
        if item[0] in "RC":
            i += 1  # the rename/copy source path follows as its own field
        status[item[3:]] = item[:2]
    # A deleted path has no content to hash; a trailing / is a nested repository, which git lists whole.
    present = [p for p, xy in status.items() if "D" not in xy and not p.endswith("/")]
    hashes = git(worktree, "hash-object", "--", *present).split() if present else []
    if len(hashes) != len(present):
        raise RuntimeError(f"git hash-object returned {len(hashes)} hashes for {len(present)} paths in {worktree}")
    content = dict(zip(present, hashes))
    return {"head": head, "files": {p: f"{xy} {content.get(p, '-')}" for p, xy in status.items()}}


def snapshot_changes(before, worktree, git=run_git):
    """The paths whose status or content differ from the `before` snapshot, sorted."""
    now = worktree_snapshot(worktree, git)
    old, new = before["files"], now["files"]
    changed = {p for p in set(old) | set(new) if old.get(p) != new.get(p)}
    if now["head"] != before["head"]:
        changed.add(f"(HEAD moved from {before['head'][:12]} to {now['head'][:12]})")
        changed.update(p for p in git(worktree, "diff", "--name-only", "--no-renames", "-z", before["head"],
                                      now["head"]).split("\0") if p)
    return sorted(changed)


def review_residue(run, gid, round_no, git=run_git):
    """What the review changed in the group's PR worktree since review-args took the round's baseline
    (todo 480). Fails closed: no baseline for this round, or a git error, is itself a finding."""
    entries = _group_entries(run, gid)
    if not entries:
        raise KeyError(f"{gid}: no such group")
    first = entries[0][1]
    base = first.get("review_baseline")
    if not base or base.get("round") != round_no:
        return [f"no round-{round_no} review baseline recorded; review-args takes it"]
    try:
        return snapshot_changes(base, first["worktree"], git)
    except RuntimeError as exc:
        return [f"residue check failed: {exc}"[:300]]


def review_args(run, round_no, wave, git=run_git, run_file="", held=None):
    """The workflow args for the wave's open PRs due this round. A group whose worktree still holds what an
    earlier attempt at the round left is skipped and put in `held` (group -> paths), so it never stalls
    the rest of the wave (todo 480)."""
    if round_no not in (1, 2):
        raise ValueError("round must be 1 or 2")
    items = []
    for gid in run["waves"][wave]:
        entries = _group_entries(run, gid)
        if not entries:
            continue
        first = entries[0][1]
        if first["stage"] != "pr_open" or first.get("review_round", 0) != round_no - 1:
            continue
        # Todo 480: the baseline is taken once per round. A rerun keeps it, because retaking it would
        # absorb whatever the failed attempt left, and the round-1 repair's `git add -A` would commit it.
        base = first.get("review_baseline")
        if base and base.get("round") == round_no:
            left = snapshot_changes(base, first["worktree"], git)
            if left:
                if held is None:  # a caller that cannot report a held group must not lose it silently
                    raise RuntimeError(f"{gid}: worktree at {first['worktree']} still holds what an earlier "
                                       f"round-{round_no} review left ({', '.join(left[:10])})")
                held[gid] = left
                continue
        else:
            base = {"round": round_no, **worktree_snapshot(first["worktree"], git)}
            for _, entry in entries:
                entry["review_baseline"] = copy.deepcopy(base)
        items.append({
            "run_id": run["run_id"], "round": round_no, "group": gid, "ids": [i for i, _ in entries],
            "worktree": first["worktree"], "branch": first["branch"], "pr": first["pr"],
            "size": max((e["triage"]["size"] for _, e in entries), key=SIZE_RANK.__getitem__),
            "slot": first["slot"],
            # A re-verified todo's evidence stays where its first attempt's group wrote it (todo 492).
            "evidence_dir": _evidence_dir(first.get("ac_file"), gid),
            "main_root": first.get("main_root", ""),
            "test_edits": sorted({t for _, e in entries for t in e.get("test_edits", [])}),
            # Land archives before review (spec §5.3): the todo now lives at its archived path,
            # and the pending path is what the merge-base still has.
            "todo_paths": [todofile.archived_path(e["path"]) for _, e in entries],
            "origin_paths": [e["path"] for _, e in entries],
            "repoints": _repoints(entries),
            # Todo 478: routing reads this list, not one an LLM router reports. -z: no path quoting;
            # --no-renames: a moved file lists its old path too, so the old path's reviewers still see it.
            "changed_files": [f for f in git(first["worktree"], "diff", "--name-only", "--no-renames", "-z",
                                             "origin/main...HEAD").split("\0") if f],
            # Todo 480: the workflow's check before the round-1 repair runs this and relays its output.
            "residue_check": f"python3 {shlex.quote(STATE_PY)} residue {shlex.quote(run_file)} {shlex.quote(gid)}",
            # Todo 483: untracked when the round started. The repair stages only what it changed and leaves
            # these alone, the verifier's clean checks ignore them, and ingest refuses a repair that staged one.
            "untracked_before": sorted(p for p, v in base["files"].items() if v.startswith("?? ")),
        })
    return items


HELD = "held for the owner"
# The runbook's "one rerun per round", kept in the run file so it survives a resume (todo 478): the second
# incomplete review (rerun or residue) in one round blocks the group.
MAX_INCOMPLETE = 2


def _holds(line):
    # Fail closed: a refuted line without a known severity (written before todo 478) counts as critical.
    return line.startswith("critical: ") or not line.startswith("high: ")


def _group_refuted(entries):
    return list(dict.fromkeys(r for _, e in entries for r in e.get("refuted", [])))


LOCATION = re.compile(r"(?:critical|high|medium|low): .+?:\d+(?= )")


def _location(line):
    """A refuted line's `severity: file:line`, the key _merge_refuted merges on. A line without one (written
    before todo 478) is its own key."""
    m = LOCATION.match(line)
    return m.group(0) if m else line


def _open_criticals(entries):
    """The group's dismissed criticals the owner has not cleared (todo 482: a round-1 hold is cleared
    before round 2, which must not hold again for the same lines). Matched by location, not by text:
    _merge_refuted rewrites a location's line when a later round adds a phrasing, and a cleared critical
    reworded in round 2 must not hold again."""
    cleared = {_location(r) for _, e in entries for r in e.get("hold_cleared", [])}
    return [r for r in _group_refuted(entries) if _holds(r) and _location(r) not in cleared]


def held_groups(run):
    """The groups blocked and held for the owner's decision on a dismissed critical."""
    return sorted({e["group"] for e in run["todos"].values()
                   if e["stage"] == "blocked" and e.get("group") and e.get("reason", "").startswith(HELD)})


def refuted_comment(run, gid):
    """PR comment body for the group's refuter-dismissed findings, or "" when there are none (todo 478).
    Written to a file for `gh pr comment --body-file`: the lines are LLM text and never meet a shell."""
    lines = _group_refuted(_group_entries(run, gid))
    if not lines:
        return ""
    return "\n".join([f"**Dismissed by refuters, not fixed** (todo sweep run {run['run_id']}, group {gid}). "
                      "A critical here holds the PR until the owner clears it.", ""]
                     + [f"- {r}" for r in lines]) + "\n"


# Curation reads origin/main, so a group is curated only once its PR is on it (todo 529 repair): a reviewed,
# unmerged PR's code is not on main yet, and every item it added would read as `fixed` and be dropped.
FOLLOWUP_STAGES = LANDED


def _group_followups(run, gid):
    """The group's stored follow-ups, plus any a run file written before todo 529 left on its todos."""
    record = run["groups"][gid]
    lines = list(record.get("followups", []))
    for _, entry in _group_entries(run, gid):
        lines += [line for line in entry.get("followups", []) if line not in lines]
    return sorted(lines, key=_followup_rank)


def followups_args(run, main_root):
    """The todo-followups workflow args (todo 529 item 3): one item per merged or archived group that has
    follow-ups and has not been curated yet. A reviewed group waits for its merge: the curator checks each
    item on origin/main, which does not have the PR's code until then. A held or blocked group is an owner
    hand-off, not a follow-up. Refuted lines are listed for the record only: the workflow never curates them."""
    items = []
    for gid in sorted(run["groups"], key=lambda g: int(g[1:]) if g[1:].isdigit() else 0):
        entries = _group_entries(run, gid)
        if not entries or any(e["stage"] not in FOLLOWUP_STAGES for _, e in entries):
            continue
        record = run["groups"][gid]
        followups = _group_followups(run, gid)
        if not followups or "curation" in record:
            continue
        items.append({"run_id": run["run_id"], "group": gid, "ids": [i for i, _ in entries],
                      "pr": entries[0][1].get("pr"), "main_root": main_root, "followups": followups})
    return items


def ingest_followups(run, results):
    """Record each group's curated follow-ups. A curated item is kept only at a file:line the review
    reported (a curator cannot invent one), as a medium or a low. A dead curator leaves the stored list
    as it is, marked uncurated. Refuted lines are never touched here: the owner re-judges those."""
    outcome = {}
    for result in results:
        gid = result["group"]
        record = run["groups"][gid]
        raw = _group_followups(run, gid)
        if result.get("kept") is None:
            record["curation"] = f"uncurated: {result.get('why') or 'the curator returned nothing'}"[:300]
            outcome[gid] = "uncurated"
            continue
        known = {_followup_key(line) for line in raw}
        kept, dropped = [], list(result.get("dropped") or [])
        for item in result["kept"]:
            line = _refuted_line(item)
            if f"{item['file']}:{item['line']}" not in known or item["severity"] not in {"medium", "low"}:
                dropped.append({"line": line, "why": "not a location or severity the review reported"})
            else:
                kept.append(line)
        record["curated"] = sorted(dict.fromkeys(kept), key=_followup_rank)
        record["curation_dropped"] = dropped
        record["curation"] = "verified" if result.get("refuter_ok") else "curated; the refuter returned nothing"
        outcome[gid] = record["curation"]
    return outcome


def followups_md(run, gid):
    """The follow-up todo's Findings for one group (todo 529 AC3): every item with its severity, the curated
    list when there is one, what the cap dropped, and the refuted lines under their own heading."""
    entries = _group_entries(run, gid)
    if not entries:
        raise KeyError(f"{gid}: no such group")
    record = run["groups"][gid]
    lines = record["curated"] if "curated" in record else _group_followups(run, gid)
    pr = entries[0][1].get("pr")
    out = [f"PR #{pr} (todo sweep run {run['run_id']}, group {gid}, todos {', '.join(i for i, _ in entries)}); "
           f"follow-ups: {record.get('curation', 'uncurated')}.", ""]
    for n, line in enumerate(lines, start=1):
        m = FOLLOWUP_LINE.match(line)
        out.append(f"{n}. **{m.group(1)}** `{m.group(2)}` {m.group(3)}" if m else f"{n}. **unknown severity** {line}")
    if record.get("followups_dropped"):
        out.append(f"\n{record['followups_dropped']} more location(s) were dropped by the cap of {FOLLOWUP_CAP} "
                   "(the most severe are kept).")
    refuted = _group_refuted(entries)
    if refuted:
        out += ["", "Dismissed by refuters, not fixed (re-judge each):", ""] + [f"- {r}" for r in refuted]
    return "\n".join(out) + "\n"


def clear_hold(run, gid, decision):
    """The owner cleared a held group's dismissed criticals, and nothing else. It bypasses ALLOWED on purpose:
    a hold is the one blocked state that resumes at review, not at ready. A round-2 hold goes to reviewed; a
    round-1 hold (todo 482) goes back to pr_open with round 1 done, so round 2 still runs, and the criticals
    cleared here stop holding (a new one in round 2 holds again)."""
    if not decision.strip():
        raise TransitionError(f"{gid}: clearing a hold needs the owner's decision")
    entries = _group_entries(run, gid)
    if not entries or any(e["stage"] != "blocked" or not e.get("reason", "").startswith(HELD) for _, e in entries):
        raise TransitionError(f"{gid}: not held for the owner; nothing to clear")
    cleared = _open_criticals(entries)
    for _, entry in entries:
        # Keep any triage-time decision: this one is added to it, not written over it.
        earlier = entry.get("owner_decision")
        if entry.pop("held_round", 2) == 1:
            resume = {"stage": "pr_open", "review_round": 1}
        else:
            resume = {"stage": "reviewed", "review_round": 2}
        entry.update(reason="", hold_cleared=list(dict.fromkeys(entry.get("hold_cleared", []) + cleared)),
                     owner_decision=f"{earlier}; hold cleared: {decision}" if earlier else f"hold cleared: {decision}",
                     **resume)


def _hold(run, gid, entries, criticals, round_no, note=""):
    set_group(run, gid, "blocked", reason=f"{HELD}: {len(criticals)} critical finding(s) dismissed only by "
                                          f"refuters (round {round_no}){note}; first: {criticals[0]}"[:500])
    for _, entry in entries:
        entry["held_round"] = round_no


def _refuted_line(f):
    line = f"{f['severity']}: {f['file']}:{f['line']} {f['summary']}"
    return line + (f" | also: {' | '.join(f['also'])}" if f.get("also") else "")


def _merged_phrasings(body, f):
    """(summary, also) for a stored line's body (`summary | also: a | b`) with f's phrasings added."""
    head, _, also = body.partition(" | also: ")
    have = [head] + (also.split(" | ") if also else [])
    merged = have + [p for p in dict.fromkeys([f["summary"], *f.get("also", [])]) if p not in have]
    return merged[0], merged[1:]


def _merge_refuted(kept, findings):
    """Todo 482: one line per severity and file:line across both rounds. A later round's new phrasings of the
    same location join its line, so one dismissed bug is counted once and posted once."""
    out = list(kept)
    for f in findings:
        prefix = f"{f['severity']}: {f['file']}:{f['line']} "
        at = next((n for n, line in enumerate(out) if line.startswith(prefix)), None)
        if at is None:
            out.append(_refuted_line(f))
            continue
        summary, also = _merged_phrasings(out[at][len(prefix):], f)
        out[at] = _refuted_line({**f, "summary": summary, "also": also})
    return out


SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
FOLLOWUP_CAP = 10
FOLLOWUP_LINE = re.compile(r"(critical|high|medium|low): (.+?:\d+) (.*)\Z", re.S)


def _followup_key(line):
    """A follow-up's file:line, the one key it merges on (todo 529); a line written before todo 529
    (`file:line summary`, no severity) is its own key."""
    m = FOLLOWUP_LINE.match(line)
    return m.group(2) if m else line


def _followup_rank(line):
    m = FOLLOWUP_LINE.match(line)
    return SEVERITY_RANK[m.group(1)] if m else len(SEVERITY_RANK)  # a pre-529 line, severity unknown, ranks last


def _merge_followups(kept, findings):
    """Todo 529: one line per file:line, whatever its severity. A new phrasing joins the line (as
    _merge_refuted's do), and the line takes the more severe of the two severities."""
    out = list(kept)
    for f in findings:
        key = f"{f['file']}:{f['line']}"
        at = next((n for n, line in enumerate(out) if _followup_key(line) == key), None)
        if at is None:
            out.append(_refuted_line(f))
            continue
        m = FOLLOWUP_LINE.match(out[at])
        summary, also = _merged_phrasings(m.group(3), f)
        severity = min(m.group(1), f["severity"], key=SEVERITY_RANK.__getitem__)
        out[at] = _refuted_line({**f, "severity": severity, "summary": summary, "also": also})
    return out


def _store_followups(run, gid, entries, findings):
    """Store a round's non-blocking findings ONCE for the group, which is one PR and one follow-up todo
    (todo 529, from todo 537 engine finding 3): copying them to each todo made a group's findings count
    once per todo. Ranked by severity on every ingest (medium before low; a pre-529 line last), capped
    at FOLLOWUP_CAP, with `followups_dropped` = the distinct locations ever seen minus those kept, so
    a dropped location reported again in round 2 is not counted twice. A run file written before todo
    529 kept the lists on each todo: they are moved here first."""
    record = run["groups"][gid]
    kept = list(record.get("followups", []))
    for _, entry in entries:
        kept += [line for line in entry.pop("followups", []) if line not in kept]
    merged = _merge_followups(kept, findings)
    ranked = sorted(merged, key=_followup_rank)  # stable: arrival order within a severity
    seen = list(dict.fromkeys(record.get("followups_seen", []) + [_followup_key(line) for line in ranked]))
    record["followups"] = ranked[:FOLLOWUP_CAP]
    record["followups_seen"] = seen
    record["followups_dropped"] = len(seen) - len(record["followups"])


ALIASES = (("/tmp/", "/private/tmp/"), ("/var/", "/private/var/"))


def _rel_file(path, worktree):
    """A reviewer's file as a repo-relative path (todo 478): the PR worktree's prefix is stripped in any of
    its forms (macOS /tmp is /private/tmp), and so is a leading ./, so one location is one follow-up."""
    path = str(path)
    if worktree and os.path.isabs(path):
        roots = {str(worktree).rstrip("/"), os.path.realpath(worktree)}
        for root in list(roots):
            for alias, real in ALIASES:
                if root.startswith(alias):
                    roots.add(real + root[len(alias):])
                elif root.startswith(real):
                    roots.add(alias + root[len(real):])
        for form in dict.fromkeys((path, os.path.realpath(path))):
            hit = next((r for r in sorted(roots, key=len, reverse=True) if form.startswith(r + "/")), None)
            if hit:
                path = form[len(hit) + 1:]
                break
    while path.startswith("./"):
        path = path[2:]
    return path


def _found_residue(run, result, round_no, git):
    """Todo 480. Without a repair, every agent of the round is done, so the worktree is compared with the
    round's baseline here, in code. A repair changes it on purpose, so then the workflow's own check,
    run before the repair, is the record; a repair without that check fails closed."""
    reported = result.get("residue")
    if result.get("repair") is None:
        return sorted(set((reported or []) + review_residue(run, result["group"], round_no, git)))
    return [] if reported == [] else (reported or ["the round-1 repair ran without a residue check"])


def _incomplete(run, gid, entries, round_no, outcome, why):
    """Count a rerun or residue outcome in the run file (todo 478); the second one in a round blocks."""
    n = entries[0][1].get("review_reruns", {}).get(str(round_no), 0) + 1
    for _, entry in entries:
        entry["review_reruns"] = {**entry.get("review_reruns", {}), str(round_no): n}
    if n < MAX_INCOMPLETE:
        return outcome
    set_group(run, gid, "blocked",
              reason=f"review round {round_no} was incomplete twice (last: {outcome}, {why})"[:500])
    return "blocked"


def _staged_untracked_before(entries, git):
    """Todo 483: paths that were untracked when the round started and that the round-1 repair staged. The
    repair stages only what it changed; these were already there (a worker's artifact that Land never
    committed), so staging one would put it in the PR."""
    first = entries[0][1]
    before = {p for p, v in (first.get("review_baseline") or {}).get("files", {}).items() if v.startswith("?? ")}
    if not before:
        return []
    staged = git(first["worktree"], "diff", "--cached", "--name-only", "--no-renames", "-z", "HEAD").split("\0")
    return sorted(before & set(staged))


def _repair_problem(result, entries, git):
    """Why a round-1 repair cannot be kept, or None."""
    repair = result["repair"]
    if not repair:
        return "no repair"
    if repair["status"] != "staged":
        blockers = result.get("repair_blockers") or repair.get("blockers") or ""
        return f"repair {repair['status']}: {blockers}" if blockers else f"repair {repair['status']}"
    problem = evaluate(repair, result["verdict"])
    if problem:
        return _with_reasons(problem, result["verdict"])
    try:
        swept = _staged_untracked_before(entries, git)
    except RuntimeError as exc:
        swept = [f"(the check failed: {exc})"[:300]]
    if swept:
        return (f"the repair staged files that were untracked before the round ({', '.join(swept[:5])}); "
                "it must stage only the paths it changed")
    return None


def ingest_review(run, results, round_no, git=run_git, criteria=None):
    """Record a todo-review output. `criteria` is ingest_execute's check, run on a kept round-1 repair; the
    CLI always passes review_criteria (todo 494 F1)."""
    # Todo 468: checked for every group before anything is written, so a stale output (a round-1
    # file re-ingested after round 1) cannot overwrite tree_id and verified_ac, even in part.
    for result in results:
        for _, entry in _group_entries(run, result["group"]):
            if entry["stage"] != "pr_open" or entry.get("review_round", 0) != round_no - 1:
                raise TransitionError(f"{result['group']}: a round-{round_no} output does not follow this group "
                                      f"({entry['stage']}, review round {entry.get('review_round', 0)}); "
                                      "is it a stale output file?")
    outcome = {}
    for result in results:
        gid = result["group"]
        entries = _group_entries(run, gid)
        # A review that changed the PR worktree reviewed something other than the PR, and a repair's
        # `git add -A` would commit what it left: nothing from this round is kept (todo 480).
        found = _found_residue(run, result, round_no, git)
        for _, entry in entries:
            entry.pop("review_residue", None)
            if found:
                entry["review_residue"] = found
        if found:
            outcome[gid] = _incomplete(run, gid, entries, round_no, "residue", ", ".join(found[:5]))
            continue
        if not result["reviewers_ok"]:
            outcome[gid] = _incomplete(run, gid, entries, round_no, "rerun",
                                       "a reviewer or the router returned nothing")
            continue
        worktree = entries[0][1].get("worktree", "")
        follow = [{**f, "file": _rel_file(f["file"], worktree)} for f in result["findings"]
                  if f["severity"] not in {"critical", "high"}]
        _store_followups(run, gid, entries, follow)
        # Blocking findings both refuters dismissed are kept whole (severity, every phrasing, no cap): the
        # PR comment before arming, the follow-up todos and the critical hold below all read them (todo 478).
        dismissed = [{**f, "file": _rel_file(f["file"], worktree)} for f in result.get("refuted", [])]
        for _, entry in entries:
            entry["refuted"] = _merge_refuted(entry.get("refuted", []), dismissed)
        blocking = result["blocking"]
        # An LLM refutation alone never clears a critical, from either round: hold the PR for the owner.
        criticals = _open_criticals(entries)
        also = (f"; also {len(criticals)} critical finding(s) dismissed only by refuters, which the owner "
                "must clear") if criticals else ""
        if round_no == 1:
            if blocking:
                problem = _repair_problem(result, entries, git)
                if not problem and criteria:
                    edited = next((f"todo {i}: {p}" for i, _ in entries
                                   for p in [criteria(run, i, result["repair"]["worktree"])] if p), None)
                    problem = f"acceptance criteria were edited: {edited}" if edited else None
                if problem:
                    set_group(run, gid, "blocked", reason=f"round-1 repair failed: {problem}{also}")
                    outcome[gid] = "blocked"
                    continue
                for _, entry in entries:
                    entry["tree_id"] = result["repair"]["tree_id"]
                    entry["verified_ac"] = result["verdict"]["ac"]
                    entry["test_edits"] = sorted(set(entry.get("test_edits", []))
                                                  | set(result["verdict"]["test_edits_flagged"]))
            # Todo 482: a dismissed critical would hold the PR at round 2 anyway, so hold it now and save the
            # commit, push and round 2. A verified repair stays staged, uncommitted, for the owner.
            if criticals:
                note = "; a verified repair waits staged, uncommitted" if blocking else ""
                _hold(run, gid, entries, criticals, 1, note)
                outcome[gid] = "held"
                continue
            outcome[gid] = "repair-staged" if blocking else "clean"
            for _, entry in entries:
                entry["review_round"] = 1
        elif blocking:
            set_group(run, gid, "blocked", reason=f"{len(blocking)} blocking findings after round 2{also}")
            outcome[gid] = "blocked"
        elif criticals:
            _hold(run, gid, entries, criticals, 2)
            outcome[gid] = "held"
        else:
            set_group(run, gid, "reviewed", review_round=2)
            outcome[gid] = "clean"
    return outcome


def _land_only_diff(path, tree_id, actual):
    """True when every path git diff reports between tree_id and actual is one
    Land itself writes (todos/, docs/reviews/, .secrets.baseline) -- R3: a
    resumed Land staging and committing its own edits must not read as lost
    work -- or one a pre-commit fixer rewrote (todo 512, owner decision
    2026-10-01): its new contents are exactly what `trailing-whitespace` and
    `end-of-file-fixer` make of the recorded ones (todo 513). An empty current
    tree against a non-empty recorded one is never accepted, whatever the diff
    says.
    """
    if not run_git(path, "ls-tree", "-r", "--name-only", actual).strip():
        return False
    changed = [p for p in run_git(path, "diff", "--no-renames", "--name-only", "-z", tree_id, actual).split("\0")
               if p]
    return bool(changed) and all(_is_land_path(p) or _fixer_only_change(path, tree_id, actual, p)
                                 for p in changed)


def _fixer_only_change(path, tree_id, actual, rel):
    """True when `rel` is a regular file in both trees, with the same mode, whose new contents are
    exactly the configured fixers' output on the recorded ones (todo 512; tightened by todo 513,
    owner decision 2026-10-01). On PR #907 end-of-file-fixer dropped one trailing blank line from a
    verified .md during the Land commit, and the next ensure-worktree read that as lost work.
    Anything a fixer would not have produced from the verified bytes still fails closed: trailing
    whitespace or end-of-file blank lines added, a final newline dropped, a .md two-space hard break
    removed, a line ending flipped either way (CRLF to LF included, although mixed-line-ending
    --fix=lf makes that one: the owner chose to refuse it), whitespace inside a line, a blank line
    anywhere but the end, an added, deleted or re-moded file, a file the fixers treat as binary
    (_is_text: todo 514), a symlink or a submodule.

    Only trailing-whitespace + end-of-file-fixer output is modelled; mixed-line-ending is not (todo 514
    F7, owner decision 2026-10-10). So the two fixers' CRLF-preserving output on a CRLF file is
    accepted, although the configured chain would also turn it into LF: those bytes differ from the
    verified ones by trailing whitespace only."""
    modes = []
    for tree in (tree_id, actual):
        listing = run_git(path, "--literal-pathspecs", "ls-tree", "-z", tree, "--", rel).split("\0")[0]
        modes.append(listing.split(" ", 1)[0] if listing else None)
    if modes[0] != modes[1] or modes[0] not in ("100644", "100755"):
        return False
    before, after = _blob(path, tree_id, rel), _blob(path, actual, rel)
    if not (_is_text(rel, before) and _is_text(rel, after)):
        return False
    return after == _fixer_output(before, rel)


# pre-commit runs both fixers only on files `identify` tags `text` (todo 514 F3/F4). identify decides by a
# known extension first, else by the first 1 KB: any byte outside _TEXTCHARS makes the file binary. This
# port refuses a binary extension OR such a byte, a little stricter than identify (which trusts a text
# extension like .py even with a control byte): a refusal only stops the group, so it fails closed.
_TEXTCHARS = bytes(sorted({7, 8, 9, 10, 11, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7F}))
BINARY_EXTENSIONS = {
    "7z", "a", "avif", "bin", "bmp", "bz2", "class", "db", "dll", "dylib", "eot", "exe", "gif", "gz", "heic",
    "icns", "ico", "jar", "jks", "jpeg", "jpg", "keystore", "mov", "mp3", "mp4", "o", "ogg", "otf", "p12",
    "pdf", "png", "psd", "pyc", "so", "sqlite", "sqlite3", "tar", "tgz", "tif", "tiff", "ttf", "wav", "webm",
    "webp", "woff", "woff2", "xz", "zip",
}


def _is_text(rel, data):
    """True when identify would tag `rel` with `data` as text: a NUL byte or any other control byte
    outside _TEXTCHARS (0x01-0x06, 0x0e-0x1a, 0x1c-0x1f, 0x7f) in the first 1024 bytes, or a binary
    extension, makes it binary, and the fixers never touch it."""
    if posixpath.splitext(rel.lower())[1].lstrip(".") in BINARY_EXTENSIONS:
        return False
    return not data[:1024].translate(None, _TEXTCHARS)


def _blob(path, tree, rel):
    proc = subprocess.run(["git", "-C", str(path), "cat-file", "blob", f"{tree}:{rel}"], capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(f"git cat-file blob {tree}:{rel} failed: {proc.stderr.decode(errors='replace').strip()}")
    return proc.stdout


def _fixer_output(data, rel):
    """What `trailing-whitespace --markdown-linebreak-ext=md` and then `end-of-file-fixer` (the
    order .pre-commit-config.yaml runs them in; pre-commit-hooks v4.5.0) write for `data` at `rel`."""
    markdown = posixpath.splitext(rel.lower())[1] == ".md"  # the hook's own test, so ".md" alone is not one
    out, lines = [], data.split(b"\n")  # readlines() splits on \n only, never on a lone \r
    for i, line in enumerate(lines):
        eol = b"\n" if i < len(lines) - 1 else b""
        if eol and line.endswith(b"\r"):
            line, eol = line[:-1], b"\r\n"
        if markdown and not line.isspace() and line.endswith(b"  "):
            line = line[:-2].rstrip() + b"  "  # a .md hard break keeps exactly two spaces
        else:
            line = line.rstrip()  # ASCII whitespace only, as the hook strips it
        out.append(line + eol)
    text = b"".join(out)
    if text[-1:] not in (b"\n", b"\r"):
        return text + b"\n" if text else text  # an empty file stays empty
    body = text.rstrip(b"\r\n")
    if not body:
        return b""  # a file of nothing but line breaks is emptied
    tail = text[len(body):]
    return body + next(seq for seq in (b"\n", b"\r\n", b"\r") if tail.startswith(seq))


def _is_land_path(p):
    return p.startswith("todos/") or p.startswith("docs/reviews/") or p == ".secrets.baseline"


def _unstaged_outside_land(path):
    """Tracked paths with an unstaged change (the Y column of `status --porcelain
    --untracked-files=no`) outside Land's own paths -- spec §5.2's clean check before Land
    (final review m2). Staged entries (the verified work itself) are expected; untracked
    test artifacts don't count, because Land commits only the index."""
    fields = run_git(path, "status", "--porcelain", "-z", "--untracked-files=no").split("\0")
    dirty, i = [], 0
    while i < len(fields):
        item = fields[i]
        i += 1
        if len(item) < 4:
            continue
        if item[0] in "RC":
            i += 1  # the rename/copy source path follows as its own field
        if item[1] != " " and not _is_land_path(item[3:]):
            dirty.append(item[3:])
    return dirty


def _force_staged_ignored(path, base="origin/main"):
    """(paths, renamed): the paths the branch ADDED (against the merge-base with `base`, renames
    split into delete + add) that an ignore rule matches or that `base`'s .worktreeinclude lists --
    a force-staged backend/.env or web/.env, which .worktreeinclude copies into every worktree
    (PR #861 B-3). The .worktreeinclude list is read from `base`, so a worker that deletes the .env
    rule from its own .gitignore and stages the file with a plain `git add -A` is still caught
    (todo 468). `renamed` maps each flagged path that is a rename destination to its source, so the
    error can name the real cause. Limited to added paths, so a file already tracked at the base
    that happens to match an ignore rule never trips it. A missing base makes git fail, and run_git
    raises: the check fails closed."""
    # -z everywhere: git C-quotes a path with a tab, a quote or a non-ASCII byte otherwise, and the error
    # would name "a\tb" instead of the file (todo 477).
    ignored = {p for p in run_git(path, "ls-files", "-z", "--cached", "--ignored", "--exclude-standard").split("\0")
               if p}
    include = _worktreeinclude(path, base)
    if not ignored and not include:
        return [], {}
    added = [p for p in run_git(path, "diff", "--cached", "--name-only", "-z", "--no-renames", "--diff-filter=A",
                                "--merge-base", base).split("\0") if p]
    flagged = sorted(p for p in added if p in ignored or any(fnmatch.fnmatch(p, pat) for pat in include))
    renamed = {}
    if flagged:
        # With -z, each rename is three fields: status (R<score>), source, destination.
        fields = run_git(path, "diff", "--cached", "--name-status", "-z", "-M", "--diff-filter=R",
                         "--merge-base", base).split("\0")
        for i in range(0, len(fields) - 2, 3):
            if fields[i].startswith("R") and fields[i + 2] in flagged:
                renamed[fields[i + 2]] = fields[i + 1]
    return flagged, renamed


def _worktreeinclude(path, base):
    """The patterns in `base`'s .worktreeinclude (none when it has no such file)."""
    try:
        text = run_git(path, "show", f"{base}:.worktreeinclude")
    except RuntimeError:
        return []
    return [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]


def _add_worktree(git, main_root, target, branch):
    """Re-add a group's worktree at `target` on `branch`. When the local branch is gone but it was
    pushed, recover it from origin/<branch> with --no-track, because the sandbox denies the
    .git/config write that tracking needs (todo 468 m6)."""
    try:
        git(main_root, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}")
    except RuntimeError:
        git(main_root, "worktree", "add", "--no-track", "-b", branch, str(target), f"origin/{branch}")
        return
    try:
        git(main_root, "worktree", "add", str(target), branch)
    except RuntimeError:
        # git may still have the old (now-vanished) worktree registered under this branch.
        git(main_root, "worktree", "prune")
        git(main_root, "worktree", "add", str(target), branch)


def ensure_worktree(run, gid, scratch, git=run_git):
    entries = _group_entries(run, gid)
    first = entries[0][1]
    main_root = first.get("main_root") or "."
    current = first.get("worktree", "")
    reused = bool(current) and Path(current).is_dir()
    if reused:
        path = current
    else:
        target = Path(scratch) / gid
        if target.exists() and any(target.iterdir()):
            raise RuntimeError(f"{target} already exists and is not empty; refusing to touch it")
        target.parent.mkdir(parents=True, exist_ok=True)
        _add_worktree(git, main_root, target, first["branch"])
        path = str(target)
    try:
        _check_worktree(gid, path, first.get("tree_id"))
    except RuntimeError as exc:
        if reused:
            raise
        # Todo 468: the worktree this call re-added holds only the branch's committed state -- the
        # staged work it was meant to find is gone either way -- so it leaves nothing new behind.
        try:
            git(main_root, "worktree", "remove", path)
        except RuntimeError:
            raise RuntimeError(f"{exc}; the re-added worktree {path} could not be removed") from exc
        raise RuntimeError(f"{exc} (the re-added worktree was removed again)") from exc
    if not reused:
        for _, entry in entries:
            entry["worktree"] = path
    return path


def _check_worktree(gid, path, tree_id):
    """spec §5.2's checks before Land commits from `path`; raises RuntimeError naming the problem."""
    if tree_id:
        actual = run_git(path, "write-tree").strip()
        if actual != tree_id and not _land_only_diff(path, tree_id, actual):
            raise RuntimeError(f"{gid}: worktree at {path} lost its staged work "
                               f"(has {actual[:8]}, expected {tree_id[:8]}); the group must be rerun")
    unstaged = _unstaged_outside_land(path)
    if unstaged:
        raise RuntimeError(f"{gid}: worktree at {path} has unstaged changes outside Land's paths "
                           f"({', '.join(unstaged[:5])}); the verified tree is not what is on disk")
    forced, renamed = _force_staged_ignored(path)
    added = [p for p in forced if p not in renamed]
    moved = [f"{p} (renamed from {renamed[p]})" for p in forced if p in renamed]
    problems = []
    if added:
        problems.append(f"stages files the branch added that are ignored or listed in .worktreeinclude "
                        f"({', '.join(added)}); a .env must never be committed -- unstage them (git rm --cached)")
    if moved:
        # Todo 468: refused on purpose -- a rename is how a copied-in .env would slip past an add-only check.
        problems.append(f"moves tracked files onto ignored paths ({', '.join(moved)}); Land will not commit "
                        "that -- land the rename by hand, or change the ignore rule on main first")
    if problems:
        raise RuntimeError(f"{gid}: worktree at {path} " + "; it also ".join(problems) + ", then rerun the group")


def _cmd_decide(run, args):
    decide(run, args.id, args.outcome, decision=args.decision or "",
           verify_only=args.verify_only, reset_stranded=args.reset_stranded)


def _parse_fields(pairs):
    fields = {}
    for pair in pairs or []:
        key, _, value = pair.partition("=")
        fields[key] = int(value) if key == "pr" and value.isdigit() else value  # only a PR number is an int
    return fields


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("show", "accept-ready", "questions", "finish", "worktrees"):
        sub.add_parser(name).add_argument("runfile")
    p = sub.add_parser("triage-args")
    p.add_argument("runfile")
    p.add_argument("--root", help="absolute path of a fresh origin/main checkout for the triagers to read (todo 468)")
    p = sub.add_parser("set")
    p.add_argument("runfile"), p.add_argument("id"), p.add_argument("stage")
    p.add_argument("--field", action="append", help="key=value stored on the todo entry")
    p.add_argument("--reverify", action="store_true",
                   help="blocked -> ready, verifying the blocked attempt's staged worktree as it is (todo 492)")
    p = sub.add_parser("repoint", help="owner-authorized re-point of one criterion in a todo's staged worktree")
    p.add_argument("runfile"), p.add_argument("id")
    p.add_argument("--index", type=int, required=True, help="0-based criterion index")
    p.add_argument("--to", required=True, help="the open todo the criterion moves to")
    p.add_argument("--decision", required=True, help="the owner's decision, dated")
    p.add_argument("--date", required=True)
    p = sub.add_parser("record-triage")
    p.add_argument("runfile"), p.add_argument("--output", required=True, help="workflow task output file")
    p.add_argument("--root", help="the triage-args --root, stripped from predicted_files")
    p = sub.add_parser("decide")
    p.add_argument("runfile"), p.add_argument("id"), p.add_argument("outcome", choices=sorted(OUTCOMES))
    p.add_argument("--decision"), p.add_argument("--verify-only", action="store_true")
    p.add_argument("--reset-stranded", action="store_true")
    p = sub.add_parser("apply-triage")
    p.add_argument("runfile"), p.add_argument("--repo", default="."), p.add_argument("--today", required=True)
    p = sub.add_parser("group")
    p.add_argument("runfile")
    p = sub.add_parser("execute-args")
    p.add_argument("runfile"), p.add_argument("--wave", type=int, required=True)
    p.add_argument("--main-root", required=True)
    p.add_argument("--worktree-root", help="where each worker's worktree is created (todo 528); default "
                                           "<main-root>/.claude/worktrees")
    p = sub.add_parser("followups-args")
    p.add_argument("runfile"), p.add_argument("--main-root", required=True)
    p = sub.add_parser("ingest-followups")
    p.add_argument("runfile"), p.add_argument("--output", required=True)
    p = sub.add_parser("followups-md")
    p.add_argument("runfile"), p.add_argument("group"), p.add_argument("--out", required=True)
    p = sub.add_parser("ingest-execute")
    p.add_argument("runfile"), p.add_argument("--output", required=True)
    p = sub.add_parser("review-args")
    p.add_argument("runfile"), p.add_argument("--round", type=int, required=True)
    p.add_argument("--wave", type=int, required=True)
    p = sub.add_parser("ingest-review")
    p.add_argument("runfile"), p.add_argument("--output", required=True)
    p.add_argument("--round", type=int, required=True)
    p = sub.add_parser("set-group")
    p.add_argument("runfile"), p.add_argument("group"), p.add_argument("stage")
    p.add_argument("--field", action="append")
    p = sub.add_parser("refuted-comment")
    p.add_argument("runfile"), p.add_argument("group"), p.add_argument("--out", required=True)
    p = sub.add_parser("residue")
    p.add_argument("runfile"), p.add_argument("group")
    p = sub.add_parser("clear-hold")
    p.add_argument("runfile"), p.add_argument("group"), p.add_argument("--decision", required=True)
    p = sub.add_parser("ensure-worktree")
    p.add_argument("runfile"), p.add_argument("group"), p.add_argument("--scratch", required=True)
    p = sub.add_parser("annotate")
    p.add_argument("runfile"), p.add_argument("group"), p.add_argument("--field", action="append")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        run = load(args.runfile)
        if args.cmd == "show":
            print(json.dumps(summary(run), indent=1))
            return 0
        if args.cmd == "triage-args":
            root = {"root": str(Path(args.root).resolve())} if args.root else {}
            print(json.dumps({"todos": triage_args(run), **root}))
            return 0
        if args.cmd == "questions":
            print(json.dumps(questions(run), indent=1))
            return 0
        if args.cmd == "refuted-comment":
            body = refuted_comment(run, args.group)
            if body:
                Path(args.out).write_text(body)
            print(args.out if body else "none")
            return 0
        if args.cmd == "residue":
            # Read-only, run by the workflow's check agent before a round-1 repair: never saves the run.
            entries = _group_entries(run, args.group)
            round_no = (entries[0][1].get("review_round", 0) + 1) if entries else 1
            changed = review_residue(run, args.group, round_no)
            more = [f"(and {len(changed) - RESIDUE_SHOWN} more)"] if len(changed) > RESIDUE_SHOWN else []
            print(json.dumps({"changed": changed[:RESIDUE_SHOWN] + more}))
            return 0
        if args.cmd == "worktrees":
            print(json.dumps(recorded_worktrees(run), indent=1))
            return 0
        if args.cmd == "finish":
            held = held_groups(run)
            if held:
                # Todo 482: clear-hold needs the run file, and the owner must not have to merge by hand.
                print(f"state: {', '.join(held)} held for the owner (a dismissed critical); keep the run file until "
                      f"`clear-hold` resolves each", file=sys.stderr)
                return 1
            if is_complete(run):
                Path(args.runfile).unlink()
                print("run complete; run file removed")
                return 0
            print(json.dumps({k: v for k, v in summary(run).items() if k not in TERMINAL}, indent=1))
            return 1
        if args.cmd == "set":
            fields = _parse_fields(args.field)
            if args.reverify:
                if args.stage != "ready" or set(fields) != {"reason"}:
                    raise TransitionError("--reverify takes stage ready and exactly one --field reason=...")
                reopen_reverify(run, args.id, fields["reason"])
            else:
                transition(run, args.id, args.stage, **fields)
        elif args.cmd == "repoint":
            print(json.dumps({"marker": repoint(run, args.id, args.index, args.to, args.decision, args.date)}))
        elif args.cmd == "record-triage":
            left = record_triage(run, records_from_output(args.output, "records"), args.root)
            print(json.dumps({"without_record": left}))
        elif args.cmd == "accept-ready":
            print(json.dumps({"ready": accept_ready(run)}))
        elif args.cmd == "decide":
            _cmd_decide(run, args)
        elif args.cmd == "apply-triage":
            print("\n".join(apply_triage(run, args.repo, args.today)))
        elif args.cmd == "group":
            result = apply_grouping(run)
            print(json.dumps({"waves": result["waves"], "unschedulable": result["unschedulable"]}, indent=1))
        elif args.cmd == "execute-args":
            briefs = execute_args(run, args.wave, args.main_root)
            add_worktrees(run, briefs, args.worktree_root or Path(args.main_root, ".claude", "worktrees"))
            print(json.dumps({"run_id": run["run_id"], "briefs": briefs}))
        elif args.cmd == "ingest-execute":
            print(json.dumps(ingest_execute(run, records_from_output(args.output, "results"),
                                            criteria=execute_criteria), indent=1))
        elif args.cmd == "followups-args":
            print(json.dumps({"run_id": run["run_id"], "groups": followups_args(run, args.main_root)}))
            return 0
        elif args.cmd == "ingest-followups":
            print(json.dumps(ingest_followups(run, records_from_output(args.output, "results")), indent=1))
        elif args.cmd == "followups-md":
            Path(args.out).write_text(followups_md(run, args.group))
            print(args.out)
            return 0
        elif args.cmd == "review-args":
            held = {}
            prs = review_args(run, args.round, args.wave, run_file=str(Path(args.runfile).resolve()), held=held)
            print(json.dumps({"round": args.round, "prs": prs, "residue": held}))
        elif args.cmd == "ingest-review":
            print(json.dumps(ingest_review(run, records_from_output(args.output, "results"), args.round,
                                           criteria=review_criteria), indent=1))
        elif args.cmd == "set-group":
            set_group(run, args.group, args.stage, **_parse_fields(args.field))
        elif args.cmd == "clear-hold":
            clear_hold(run, args.group, args.decision)
        elif args.cmd == "ensure-worktree":
            print(ensure_worktree(run, args.group, args.scratch))
        elif args.cmd == "annotate":
            annotate(run, args.group, **_parse_fields(args.field))
    except (TransitionError, KeyError, ValueError, RuntimeError, FileNotFoundError, json.JSONDecodeError,
            IndexError, group.CycleError) as exc:
        print(f"state: {exc}", file=sys.stderr)
        return 2
    save(run, args.runfile)
    return 0


if __name__ == "__main__":
    sys.exit(main())
