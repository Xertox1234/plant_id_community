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
import json
import os
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
MAX_RETRIES = 1
OUTCOMES = {"ready", "blocked", "skipped"}
NOT_PLANNED = {"scanned", "triaged", "blocked", "skipped"}
LANDED = {"merged", "archived"}
WORK_FIELDS = ("worktree", "branch", "tree_id", "ac_file")


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
    if to in {"blocked", "failed"} and not fields.get("reason"):
        raise TransitionError(f"{todo_id}: {to} needs a reason")
    if frm == "failed" and to == "ready":
        if entry["attempts"] >= MAX_RETRIES:
            raise TransitionError(f"{todo_id}: already retried once; block it with a reason")
        entry["attempts"] += 1
        entry.pop("group", None)  # regroup from scratch; never share a group with the failed attempt
    entry["stage"] = to
    entry.update(fields)


def summary(run):
    out = {}
    for todo_id, entry in sorted(run["todos"].items()):
        out.setdefault(entry["stage"], []).append(todo_id)
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


def record_triage(run, records):
    for record in records:
        if record["id"] not in run["todos"]:
            raise KeyError(f"triage record for {record['id']}, which is not in this run")
    for record in records:
        _normalize_predicted_files(record)
        run["todos"][record["id"]]["triage"] = record
        transition(run, record["id"], "triaged")
    return sorted(i for i, e in run["todos"].items() if e["stage"] == "scanned")


def _normalize_predicted_files(record):
    """Repo-relative paths only (final review m11): a leading ./ is stripped, since the
    lanes match exact repo-relative paths; an absolute path cannot be mapped onto the repo,
    so it is dropped and listed in `dropped_files` for the plan to show."""
    kept, dropped = [], []
    for path in record.get("predicted_files", []):
        path = str(path)
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
            git(repo_root, "mv", rel, new_rel)  # rename first: git mv stages the pre-edit content
            rel = entry["path"] = new_rel
            todofile.set_fields(repo_root / rel, {"status": "pending"})
            todofile.append_work_log(
                repo_root / rel,
                f"### {today} - Returned to pending by the todo sweep (run {run['run_id']})\n\n"
                "- Was `in_progress` with no branch, worktree or open PR; the owner confirmed the reset.\n",
            )
            entry["stranded"] = False
        fields = {"triage": record["class"], "triaged": today}
        if record.get("blocked_on"):
            fields["blocked_on"] = record["blocked_on"]
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
         "verify_only": e.get("verify_only", False), "triage": e["triage"]}
        for i, e in sorted(run["todos"].items()) if e["stage"] == "ready" and "group" not in e
    ]
    # A dependency already past triage in this run (grouped earlier, executing, pr_open, merged, ...)
    # is not "open outside the run": dropping it here lets its dependent wait at execute_args
    # instead of being blocked for good (final review I3). Blocked/skipped ones stay open.
    in_run = {i for i, e in run["todos"].items() if e["stage"] not in NOT_PLANNED}
    result = group.plan(todos, set(run["open_ids"]) - in_run, run["workers"])
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
    for todo_id, reason in to_block.items():
        transition(run, todo_id, "blocked", reason=reason)
    briefs = []
    for position, gid in enumerate(gids, start=1):
        entries = [(i, e) for i, e in _group_entries(run, gid) if i not in to_block and e["stage"] not in TERMINAL]
        if not entries:
            continue  # every todo that was here got regrouped into a later wave, or was just blocked
        held = run["groups"][gid]["lanes"]
        forbidden = sorted({lane for other in gids if other != gid for lane in run["groups"][other]["lanes"]})
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
            "lanes_held": [group.LANE_DOC[lane] for lane in held],
            "lanes_forbidden": [group.LANE_DOC[lane] for lane in forbidden],
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


def review_args(run, round_no, wave):
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
        })
    return items


def ingest_review(run, results, round_no):
    outcome = {}
    for result in results:
        gid = result["group"]
        entries = _group_entries(run, gid)
        for _, entry in entries:
            entry["checklist_skipped"] = bool(result.get("checklist_skipped"))
        if not result["reviewers_ok"]:
            outcome[gid] = "rerun"
            continue
        follow = list(dict.fromkeys(  # de-dupe within this call too, preserve order
            f"{f['file']}:{f['line']} {f['summary']}" for f in result["findings"]
            if f["severity"] not in {"critical", "high"}
        ))
        for _, entry in entries:
            existing = entry.get("followups", [])
            entry["followups"] = (existing + [f for f in follow if f not in existing])[:10]
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
            if blocking:
                set_group(run, gid, "blocked", reason=f"{len(blocking)} blocking findings after round 2")
                outcome[gid] = "blocked"
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
        branch = first["branch"]
        try:
            git(main_root, "worktree", "add", str(target), branch)
        except RuntimeError:
            # git may still have the old (now-vanished) worktree registered under this branch.
            git(main_root, "worktree", "prune")
            git(main_root, "worktree", "add", str(target), branch)
        path = str(target)
    tree_id = first.get("tree_id")
    if tree_id:
        actual = run_git(path, "write-tree").strip()
        if actual != tree_id and not _land_only_diff(path, tree_id, actual):
            raise RuntimeError(f"{gid}: worktree at {path} lost its staged work "
                               f"(has {actual[:8]}, expected {tree_id[:8]}); the group must be rerun")
    unstaged = _unstaged_outside_land(path)
    if unstaged:
        raise RuntimeError(f"{gid}: worktree at {path} has unstaged changes outside Land's paths "
                           f"({', '.join(unstaged[:5])}); the verified tree is not what is on disk")
    if not reused:
        for _, entry in entries:
            entry["worktree"] = path
    return path


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
    for name in ("show", "triage-args", "accept-ready", "questions", "finish"):
        sub.add_parser(name).add_argument("runfile")
    p = sub.add_parser("set")
    p.add_argument("runfile"), p.add_argument("id"), p.add_argument("stage")
    p.add_argument("--field", action="append", help="key=value stored on the todo entry")
    p = sub.add_parser("record-triage")
    p.add_argument("runfile"), p.add_argument("--output", required=True, help="workflow task output file")
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
            print(json.dumps({"todos": triage_args(run)}))
            return 0
        if args.cmd == "questions":
            print(json.dumps(questions(run), indent=1))
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
            left = record_triage(run, records_from_output(args.output, "records"))
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
            print(json.dumps({"round": args.round, "prs": review_args(run, args.round, args.wave)}))
        elif args.cmd == "ingest-review":
            print(json.dumps(ingest_review(run, records_from_output(args.output, "results"), args.round), indent=1))
        elif args.cmd == "set-group":
            set_group(run, args.group, args.stage, **_parse_fields(args.field))
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
