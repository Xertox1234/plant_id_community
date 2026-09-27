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
        run["todos"][record["id"]]["triage"] = record
        transition(run, record["id"], "triaged")
    return sorted(i for i, e in run["todos"].items() if e["stage"] == "scanned")


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


def _cmd_decide(run, args):
    decide(run, args.id, args.outcome, decision=args.decision or "",
           verify_only=args.verify_only, reset_stranded=args.reset_stranded)


def _parse_fields(pairs):
    fields = {}
    for pair in pairs or []:
        key, _, value = pair.partition("=")
        fields[key] = int(value) if value.isdigit() else value
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
    except (TransitionError, KeyError, ValueError, RuntimeError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"state: {exc}", file=sys.stderr)
        return 2
    save(run, args.runfile)
    return 0


if __name__ == "__main__":
    sys.exit(main())
