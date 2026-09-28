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
import fnmatch
import json
import os
import shlex
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
ATTEMPT_FIELDS = ("reason", "group", "slot", "wave", *WORK_FIELDS, "verified_ac", "test_edits", "review_round")


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
        entry.pop("group", None)  # regroup from scratch; never share a group with the failed attempt
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


def summary(run):
    out = {}
    for todo_id, entry in sorted(run["todos"].items()):
        out.setdefault(entry["stage"], []).append(todo_id)
    return out


def recorded_worktrees(run):
    """{todo id: [worktree, ...]} for every todo not archived, including a reopened todo's earlier
    attempts -- `finish` deletes the run file, so the wrap-up lists these first (todo 468, F5)."""
    out = {}
    for todo_id, entry in sorted(run["todos"].items()):
        paths = [p for p in [entry.get("worktree")] + [a.get("worktree") for a in entry.get("previous", [])] if p]
        if paths and entry["stage"] != "archived":
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
    root get absolute hits back, and dropping them would drop their lanes (PR #868)."""
    prefix = str(Path(root).resolve()).rstrip("/") + "/" if root else None
    kept, dropped = [], []
    for path in record.get("predicted_files", []):
        path = str(path)
        if prefix and path.startswith(prefix):
            path = path[len(prefix):]
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


def apply_triage(run, repo_root, today, git=run_git):
    """Write durable triage facts into each todo's frontmatter (spec §6.4)."""
    repo_root = Path(repo_root)
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
            if heading not in (repo_root / rel).read_text():
                todofile.append_work_log(
                    repo_root / rel,
                    f"{heading}\n\n"
                    "- Was `in_progress` with no branch, worktree or open PR; the owner confirmed the reset.\n",
                )
            entry["stranded"] = entry["reset_stranded"] = False
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
        todofile.set_fields(repo_root / rel, fields)
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
    result = group.plan(todos, set(run["open_ids"]) - in_run, run["workers"], busy_lanes=busy)
    offset = max((int(g[1:]) for g in run["groups"]), default=0)
    rename = {gid: f"g{offset + int(gid[1:])}" for gid in result["groups"]}
    for todo_id, reason in result["unschedulable"].items():
        transition(run, todo_id, "blocked", reason=reason)
    for gid, spec in result["groups"].items():
        run["groups"][rename[gid]] = dict(spec, deps=[rename[d] for d in spec["deps"]])
        for todo_id in spec["ids"]:
            run["todos"][todo_id]["group"] = rename[gid]
    new_waves = [[rename[g] for g in wave] for wave in result["waves"]]
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


def execute_args(run, wave, main_root):
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
    # Todo 468: wave N-1 is still in review or Land while this wave executes, so its lanes are
    # forbidden too, until every todo left in it has merged. A group that HOLDS such a lane would
    # put two PRs on it at once: refuse before anything changes (PR #869 round 1).
    previous = _unmerged(run, run["waves"][wave - 1]) if wave >= 1 else []
    for gid in gids:
        clash = set(run["groups"][gid]["lanes"]) & {lane for other in previous
                                                     for lane in run["groups"][other]["lanes"]}
        if clash and _group_entries(run, gid):
            raise TransitionError(f"{gid} holds {', '.join(sorted(clash))}, which wave {wave - 1} still holds; "
                                  "wait for that wave to merge")
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
            "evidence_dir": f".sweep-evidence/{gid}",
            "main_root": main_root,
        })
        for todo_id, _ in entries:
            transition(run, todo_id, "executing", group=gid, slot=slot, wave=wave, main_root=main_root)
    return briefs


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


def ingest_execute(run, results):
    outcome = {}
    for result in results:
        worker, verdict = result.get("worker"), result.get("verdict")
        # Final review I5: a blocked, failed or dead attempt may still have staged work in a worktree;
        # record where, so the next sweep (or the owner) can find it instead of redoing it.
        work = {k: (worker or {}).get(k) for k in WORK_FIELDS}
        work["worktree"] = work["worktree"] or result.get("worktree")
        work = {k: v for k, v in work.items() if v}
        for todo_id in result["ids"]:
            if worker is None:
                transition(run, todo_id, "failed", reason="worker returned nothing", **work)
            elif worker["status"] == "blocked":
                transition(run, todo_id, "blocked", reason=worker.get("blockers") or "worker blocked", **work)
            elif worker["status"] != "staged":
                transition(run, todo_id, "failed",
                           reason=f"worker status {worker['status']}: {worker.get('blockers', '')}", **work)
            else:
                transition(run, todo_id, "staged", worktree=worker["worktree"], branch=worker["branch"],
                           tree_id=worker["tree_id"], ac_file=worker["ac_file"])
                problem = evaluate(worker, verdict)
                if problem:
                    transition(run, todo_id, "failed", reason=_with_reasons(problem, verdict))
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


def review_args(run, round_no, wave, git=run_git, run_file=""):
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
                raise RuntimeError(f"{gid}: worktree at {first['worktree']} still holds what an earlier "
                                   f"round-{round_no} review left ({', '.join(left[:10])}); restore those "
                                   "paths, then rerun review-args")
        else:
            base = {"round": round_no, **worktree_snapshot(first["worktree"], git)}
            for _, entry in entries:
                entry["review_baseline"] = copy.deepcopy(base)
        items.append({
            "run_id": run["run_id"], "round": round_no, "group": gid, "ids": [i for i, _ in entries],
            "worktree": first["worktree"], "branch": first["branch"], "pr": first["pr"],
            "size": max((e["triage"]["size"] for _, e in entries), key=SIZE_RANK.__getitem__),
            "slot": first["slot"], "evidence_dir": f".sweep-evidence/{gid}",
            "main_root": first.get("main_root", ""),
            "test_edits": sorted({t for _, e in entries for t in e.get("test_edits", [])}),
            # Land archives before review (spec §5.3): the todo now lives at its archived path,
            # and the pending path is what the merge-base still has.
            "todo_paths": [todofile.archived_path(e["path"]) for _, e in entries],
            "origin_paths": [e["path"] for _, e in entries],
            # Todo 478: routing reads this list, not one an LLM router reports. -z: no path quoting;
            # --no-renames: a moved file lists its old path too, so the old path's reviewers still see it.
            "changed_files": [f for f in git(first["worktree"], "diff", "--name-only", "--no-renames", "-z",
                                             "origin/main...HEAD").split("\0") if f],
            # Todo 480: the workflow's check before the round-1 repair runs this and relays its output.
            "residue_check": f"python3 {shlex.quote(STATE_PY)} residue {shlex.quote(run_file)} {shlex.quote(gid)}",
        })
    return items


HELD = "held for the owner"


def _holds(line):
    # Fail closed: a refuted line without a known severity (written before todo 478) counts as critical.
    return line.startswith("critical: ") or not line.startswith("high: ")


def _group_refuted(entries):
    return list(dict.fromkeys(r for _, e in entries for r in e.get("refuted", [])))


def refuted_comment(run, gid):
    """PR comment body for the group's refuter-dismissed findings, or "" when there are none (todo 478).
    Written to a file for `gh pr comment --body-file`: the lines are LLM text and never meet a shell."""
    lines = _group_refuted(_group_entries(run, gid))
    if not lines:
        return ""
    return "\n".join([f"**Dismissed by refuters, not fixed** (todo sweep run {run['run_id']}, group {gid}). "
                      "A critical here holds the PR until the owner clears it.", ""]
                     + [f"- {r}" for r in lines]) + "\n"


def clear_hold(run, gid, decision):
    """The owner cleared a held group's dismissed criticals: blocked -> reviewed, and nothing else.
    It bypasses ALLOWED on purpose: a hold is the one blocked state that resumes at review, not at ready."""
    if not decision.strip():
        raise TransitionError(f"{gid}: clearing a hold needs the owner's decision")
    entries = _group_entries(run, gid)
    if not entries or any(e["stage"] != "blocked" or not e.get("reason", "").startswith(HELD) for _, e in entries):
        raise TransitionError(f"{gid}: not held for the owner; nothing to clear")
    for _, entry in entries:
        # Keep any triage-time decision: this one is added to it, not written over it.
        earlier = entry.get("owner_decision")
        entry.update(stage="reviewed", review_round=2, reason="",
                     owner_decision=f"{earlier}; hold cleared: {decision}" if earlier else f"hold cleared: {decision}")


def _refuted_line(f):
    line = f"{f['severity']}: {f['file']}:{f['line']} {f['summary']}"
    return line + (f" | also: {' | '.join(f['also'])}" if f.get("also") else "")


def _found_residue(run, result, round_no, git):
    """Todo 480. Without a repair, every agent of the round is done, so the worktree is compared with the
    round's baseline here, in code. A repair changes it on purpose, so then the workflow's own check,
    run before the repair, is the record; a repair without that check fails closed."""
    reported = result.get("residue")
    if result.get("repair") is None:
        return sorted(set((reported or []) + review_residue(run, result["group"], round_no, git)))
    return [] if reported == [] else (reported or ["the round-1 repair ran without a residue check"])


def ingest_review(run, results, round_no, git=run_git):
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
            outcome[gid] = "residue"
            continue
        if not result["reviewers_ok"]:
            outcome[gid] = "rerun"
            continue
        follow = list(dict.fromkeys(  # de-dupe within this call too, preserve order
            f"{f['file']}:{f['line']} {f['summary']}" for f in result["findings"]
            if f["severity"] not in {"critical", "high"}
        ))
        # Blocking findings both refuters dismissed are kept whole (severity, every phrasing, no cap): the
        # PR comment before arming, the follow-up todos and the critical hold below all read them (todo 478).
        dismissed = [_refuted_line(f) for f in result.get("refuted", [])]
        for _, entry in entries:
            existing = entry.get("followups", [])
            entry["followups"] = (existing + [f for f in follow if f not in existing])[:10]
            kept = entry.get("refuted", [])
            entry["refuted"] = kept + [f for f in dismissed if f not in kept]
        blocking = result["blocking"]
        if round_no == 1:
            if blocking:
                repair = result["repair"]
                if not repair:
                    problem = "no repair"
                elif repair["status"] != "staged":
                    blockers = result.get("repair_blockers") or repair.get("blockers") or ""
                    problem = f"repair {repair['status']}: {blockers}" if blockers else f"repair {repair['status']}"
                else:
                    problem = evaluate(repair, result["verdict"])
                    problem = problem and _with_reasons(problem, result["verdict"])
                if problem:
                    set_group(run, gid, "blocked", reason=f"round-1 repair failed: {problem}")
                    outcome[gid] = "blocked"
                    continue
                for _, entry in entries:
                    entry["tree_id"] = result["repair"]["tree_id"]
                    entry["verified_ac"] = result["verdict"]["ac"]
                    entry["test_edits"] = sorted(set(entry.get("test_edits", []))
                                                  | set(result["verdict"]["test_edits_flagged"]))
                outcome[gid] = "repair-staged"
            else:
                outcome[gid] = "clean"
            for _, entry in entries:
                entry["review_round"] = 1
        else:
            # An LLM refutation alone never clears a critical, from either round: hold the PR for the owner.
            criticals = [r for r in _group_refuted(entries) if _holds(r)]
            if blocking:
                also = (f"; also {len(criticals)} critical finding(s) dismissed only by refuters, which the "
                        "owner must clear") if criticals else ""
                set_group(run, gid, "blocked", reason=f"{len(blocking)} blocking findings after round 2{also}")
                outcome[gid] = "blocked"
            elif criticals:
                set_group(run, gid, "blocked", reason=f"{HELD}: {len(criticals)} critical finding(s) "
                                                      f"dismissed only by refuters; first: {criticals[0]}"[:500])
                outcome[gid] = "held"
            else:
                set_group(run, gid, "reviewed", review_round=2)
                outcome[gid] = "clean"
    return outcome


def _land_only_diff(path, tree_id, actual):
    """True when every path git diff reports between tree_id and actual is one
    Land itself writes (todos/, docs/reviews/, .secrets.baseline) -- R3: a
    resumed Land staging and committing its own edits must not read as lost
    work. An empty current tree against a non-empty recorded one is never
    accepted, whatever the diff says.
    """
    if not run_git(path, "ls-tree", "-r", "--name-only", actual).strip():
        return False
    changed = [p for p in run_git(path, "diff", "--no-renames", "--name-only", tree_id, actual).splitlines() if p]
    return bool(changed) and all(_is_land_path(p) for p in changed)


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
    ignored = set(run_git(path, "ls-files", "--cached", "--ignored", "--exclude-standard").splitlines())
    include = _worktreeinclude(path, base)
    if not ignored and not include:
        return [], {}
    added = run_git(path, "diff", "--cached", "--name-only", "--no-renames", "--diff-filter=A",
                    "--merge-base", base).splitlines()
    flagged = sorted(p for p in added if p in ignored or any(fnmatch.fnmatch(p, pat) for pat in include))
    renamed = {}
    if flagged:
        for line in run_git(path, "diff", "--cached", "--name-status", "-M", "--diff-filter=R",
                            "--merge-base", base).splitlines():
            parts = line.split("\t")
            if len(parts) == 3 and parts[2] in flagged:
                renamed[parts[2]] = parts[1]
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
            if is_complete(run):
                Path(args.runfile).unlink()
                print("run complete; run file removed")
                return 0
            print(json.dumps({k: v for k, v in summary(run).items() if k not in TERMINAL}, indent=1))
            return 1
        if args.cmd == "set":
            transition(run, args.id, args.stage, **_parse_fields(args.field))
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
            print(json.dumps({"run_id": run["run_id"], "briefs": execute_args(run, args.wave, args.main_root)}))
        elif args.cmd == "ingest-execute":
            print(json.dumps(ingest_execute(run, records_from_output(args.output, "results")), indent=1))
        elif args.cmd == "review-args":
            print(json.dumps({"round": args.round, "prs": review_args(run, args.round, args.wave,
                                                                       run_file=str(Path(args.runfile).resolve()))}))
        elif args.cmd == "ingest-review":
            print(json.dumps(ingest_review(run, records_from_output(args.output, "results"), args.round), indent=1))
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
