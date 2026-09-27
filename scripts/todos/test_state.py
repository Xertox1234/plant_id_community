#!/usr/bin/env python3
"""Tests for scripts/todos/state.py (run file, transitions, triage flow).

Run: python3 scripts/todos/test_state.py (also run by harness-ci.yml).

The transition table is the sweep's safety: a todo that could jump from
executing to pr_open would land unverified. So refused moves are tested as
carefully as allowed ones.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import state  # noqa: E402
import todofile  # noqa: E402

FAILURES = []


def check(label, condition, detail=""):
    print(f"  {'PASS' if condition else 'FAIL'}  {label}{'' if condition else f'  -- {detail}'}")
    if not condition:
        FAILURES.append(label)


def raises(fn, exc=state.TransitionError):
    try:
        fn()
    except exc:
        return True
    return False


def todo(id_, status="pending", **extra):
    return {"id": id_, "path": f"todos/{id_}-{status}-p3-x.md", "priority": "p3", **extra}


def rec(id_, cls="ready", question="", blocked_on=""):
    return {"id": id_, "class": cls, "evidence": "e", "blocked_on": blocked_on,
            "owner_question": question, "predicted_files": ["web/src/a.ts"], "size": "s",
            "needs_e2e": False, "notes_for_siblings": ""}


def git_repo(tmp):
    repo = Path(tmp) / "repo"
    (repo / "todos").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    return repo


def commit_all(repo):
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-q", "-m", "x"], check=True)


def main():
    run = state.new_run("r1", "sweep", 3, [todo("412"), todo("413", stranded=True)], ["412", "413", "500"])
    check("new todos start at scanned", run["todos"]["412"]["stage"] == "scanned")
    check("open ids are recorded sorted", run["open_ids"] == ["412", "413", "500"])

    check("scanned -> executing is refused", raises(lambda: state.transition(run, "412", "executing")))
    check("blocked without a reason is refused", raises(lambda: state.transition(run, "412", "blocked")))
    check("an unknown id is refused", raises(lambda: state.transition(run, "999", "triaged")))
    state.transition(run, "412", "triaged")
    check("scanned -> triaged is allowed", run["todos"]["412"]["stage"] == "triaged")
    check("every non-terminal stage may block",
          all("blocked" in targets for targets in state.ALLOWED.values()))
    check("terminal stages have no exits", not (state.TERMINAL & set(state.ALLOWED)))

    walk = state.new_run("r2", "sweep", 3, [todo("1")], ["1"])
    for stage in ["triaged", "ready", "executing", "failed"]:
        state.transition(walk, "1", stage, reason="r" if stage == "failed" else "")
    state.transition(walk, "1", "ready")
    check("failed -> ready retries once and counts it", walk["todos"]["1"]["attempts"] == 1)
    for stage in ["executing", "failed"]:
        state.transition(walk, "1", stage, reason="r2" if stage == "failed" else "")
    check("a second retry is refused", raises(lambda: state.transition(walk, "1", "ready")))

    with tempfile.TemporaryDirectory() as tmp:
        path = state.run_path(tmp, "r1")
        state.save(run, path)
        check("save/load round-trips", state.load(path) == run)
        check("save leaves no temp file", not list(Path(tmp).glob("*.tmp")))

        out = Path(tmp) / "wf.output"
        out.write_text(json.dumps({"records": [rec("413")]}))
        check("reads a bare workflow return value", state.records_from_output(out, "records")[0]["id"] == "413")
        out.write_text(json.dumps({"result": json.dumps({"records": [rec("413")]})}))
        check("reads a return value wrapped as a JSON string", len(state.records_from_output(out, "records")) == 1)
        out.write_text(json.dumps({"other": 1}))
        check("a missing key is an error, not an empty list",
              raises(lambda: state.records_from_output(out, "records"), ValueError))

    run = state.new_run("r3", "sweep", 3, [todo("1"), todo("2"), todo("3"), todo("4", stranded=True)],
                        ["1", "2", "3", "4"])
    check("triage_args lists scanned todos", [a["id"] for a in state.triage_args(run)] == ["1", "2", "3", "4"])
    left = state.record_triage(run, [rec("1"), rec("2", "blocked-owner", "Which API?", "needs a call"),
                                     rec("3", "ready", "Keep the old flag?")])
    check("record_triage reports ids without a record", left == ["4"])
    check("an unknown record id is refused", raises(lambda: state.record_triage(run, [rec("9")]), KeyError))
    check("accept_ready moves only question-free ready todos", state.accept_ready(run) == ["1"])
    qs = {q["id"]: q for q in state.questions(run)}
    check("questions include blocked and ready-with-question todos", set(qs) == {"2", "3"}, qs)
    state.decide(run, "2", "blocked", decision="Owner: wait for vendor")
    check("decide blocked records the reason", run["todos"]["2"]["reason"] == "Owner: wait for vendor")
    state.decide(run, "3", "ready", decision="Yes, keep it (2026-09-27)")
    check("decide ready stores the decision verbatim",
          run["todos"]["3"]["stage"] == "ready" and run["todos"]["3"]["owner_decision"].startswith("Yes"))
    check("decide rejects an unknown outcome", raises(lambda: state.decide(run, "1", "maybe"), ValueError))

    with tempfile.TemporaryDirectory() as tmp:
        repo = git_repo(tmp)
        head = '---\nstatus: {s}\npriority: p3\nissue_id: "{i}"\ndependencies: []\n---\n\n# T{i}\n\n## Work Log\n'
        (repo / "todos/1-pending-p3-x.md").write_text(head.format(s="pending", i="1"))
        (repo / "todos/4-in_progress-p3-x.md").write_text(head.format(s="in_progress", i="4"))
        commit_all(repo)
        run = state.new_run("r4", "sweep", 3,
                            [todo("1"), {"id": "4", "path": "todos/4-in_progress-p3-x.md", "priority": "p3",
                                         "stranded": True}], ["1", "4"])
        state.record_triage(run, [rec("1", "blocked-owner", "q", "vendor"), rec("4")])
        state.decide(run, "1", "blocked", decision="wait")
        state.decide(run, "4", "ready", reset_stranded=True)
        changed = state.apply_triage(run, repo, "2026-09-27")
        fm1 = todofile.read_frontmatter(repo / "todos/1-pending-p3-x.md")
        check("apply_triage writes triage fields",
              fm1["triage"] == "blocked-owner" and fm1["blocked_on"] == "vendor"
              and str(fm1["triaged"]) == "2026-09-27" and fm1["owner_decision"] == "wait", fm1)
        new4 = repo / "todos/4-pending-p3-x.md"
        check("a stranded todo is renamed back to pending",
              new4.exists() and not (repo / "todos/4-in_progress-p3-x.md").exists())
        check("its frontmatter status follows the filename", todofile.read_frontmatter(new4)["status"] == "pending")
        check("the rename is recorded in the Work Log", "Returned to pending by the todo sweep" in new4.read_text())
        check("the run file follows the rename", run["todos"]["4"]["path"] == "todos/4-pending-p3-x.md")
        check("apply_triage lists what it changed", sorted(changed) == ["todos/1-pending-p3-x.md",
                                                                       "todos/4-pending-p3-x.md"], changed)

    done = state.new_run("r5", "sweep", 3, [todo("1")], ["1"])
    state.transition(done, "1", "blocked", reason="x")
    check("is_complete when every todo is terminal", state.is_complete(done))

    run = state.new_run("r6", "sweep", 3, [todo("1")], ["1"])
    state.transition(run, "1", "triaged")
    original_stage = run["todos"]["1"]["stage"]
    check("transition refuses to set reserved field 'stage'",
          raises(lambda: state.transition(run, "1", "ready", stage="merged")))
    check("the entry's stage is unchanged after a rejected field",
          run["todos"]["1"]["stage"] == original_stage)
    check("transition refuses to set reserved field 'attempts'",
          raises(lambda: state.transition(run, "1", "ready", attempts=5)))

    with tempfile.TemporaryDirectory() as tmp:
        missing_path = Path(tmp) / "nonexistent.json"
        script_dir = os.path.dirname(os.path.abspath(__file__))
        result = subprocess.run([sys.executable, os.path.join(script_dir, "state.py"), "show", str(missing_path)],
                                capture_output=True, text=True)
        check("CLI on a missing run file exits 2", result.returncode == 2)
        check("the error is reported as 'state: <message>'", result.stderr.startswith("state: "))

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} check(s): {', '.join(FAILURES)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
