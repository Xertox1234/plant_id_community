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
          all("blocked" in targets for name, targets in state.ALLOWED.items() if name not in state.TERMINAL))
    check("only blocked leaves a terminal stage, and only to ready",
          state.TERMINAL & set(state.ALLOWED) == {"blocked"} and state.ALLOWED["blocked"] == {"ready"})

    walk = state.new_run("r2", "sweep", 3, [todo("1")], ["1"])
    for stage in ["triaged", "ready", "executing", "failed"]:
        state.transition(walk, "1", stage, reason="r" if stage == "failed" else "")
    walk["todos"]["1"]["group"] = "g1"
    state.transition(walk, "1", "ready")
    check("failed -> ready retries once and counts it", walk["todos"]["1"]["attempts"] == 1)
    check("failed -> ready drops the todo's group so it can be regrouped",
          "group" not in walk["todos"]["1"])
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

        # Todo 468: apply-triage saves the run file only on success, so a rerun after a mid-batch
        # failure sees the old in_progress path while the disk already has the pending one.
        (repo / "todos/6-in_progress-p3-x.md").write_text(head.format(s="in_progress", i="6"))
        (repo / "todos/7-pending-p3-x.md").write_text(head.format(s="pending", i="7"))
        commit_all(repo)
        mid = state.new_run("r4b", "sweep", 3,
                            [{"id": "6", "path": "todos/6-in_progress-p3-x.md", "priority": "p3", "stranded": True},
                             todo("7")], ["6", "7"])
        state.record_triage(mid, [rec("6"), rec("7")])
        state.decide(mid, "6", "ready", reset_stranded=True)
        state.decide(mid, "7", "ready")
        saved = json.loads(json.dumps(mid))  # what the run file still holds after a failed run
        (repo / "todos/7-pending-p3-x.md").rename(repo / "todos/7-moved-away.md")
        check("468 setup: the first apply-triage fails part-way (todo 7's file is missing)",
              raises(lambda: state.apply_triage(mid, repo, "2026-09-28"), FileNotFoundError)
              and (repo / "todos/6-pending-p3-x.md").exists())
        (repo / "todos/7-moved-away.md").rename(repo / "todos/7-pending-p3-x.md")
        rerun, err = None, None
        try:
            rerun = state.apply_triage(saved, repo, "2026-09-28")
        except Exception as exc:  # noqa: BLE001 -- the check reports it
            err = exc
        new6 = repo / "todos/6-pending-p3-x.md"
        check("468: re-running apply-triage after a mid-batch failure succeeds",
              err is None and sorted(rerun) == ["todos/6-pending-p3-x.md", "todos/7-pending-p3-x.md"]
              and saved["todos"]["6"]["path"] == "todos/6-pending-p3-x.md", err or rerun)
        check("468: the rerun does not repeat the Work Log entry",
              new6.read_text().count("Returned to pending by the todo sweep") == 1, new6.read_text())
        err = None
        saved["todos"]["6"]["reset_stranded"] = True  # PR #861 round 1: path already pending, flag still set
        try:
            state.apply_triage(saved, repo, "2026-09-28")
        except Exception as exc:  # noqa: BLE001
            err = exc
        check("468: re-running apply-triage after a successful run succeeds (no git mv onto itself)",
              err is None and new6.read_text().count("Returned to pending by the todo sweep") == 1, err)

        # Todo 468: an owner who blocks a needs-design or stale todo has answered it; the next scan
        # must not ask again, so the frontmatter says blocked-owner (scan skips blocked-* unchanged).
        (repo / "todos/8-pending-p3-x.md").write_text(head.format(s="pending", i="8"))
        (repo / "todos/9-pending-p3-x.md").write_text(head.format(s="pending", i="9"))
        answered = state.new_run("r4c", "sweep", 3, [todo("8"), todo("9")], ["8", "9"])
        state.record_triage(answered, [rec("8", "needs-design", "Which layout?"), rec("9", "stale", "Keep it?")])
        state.decide(answered, "8", "blocked", decision="Owner: wait for the redesign (2026-09-28)")
        state.decide(answered, "9", "skipped")
        state.apply_triage(answered, repo, "2026-09-28")
        fm8 = todofile.read_frontmatter(repo / "todos/8-pending-p3-x.md")
        fm9 = todofile.read_frontmatter(repo / "todos/9-pending-p3-x.md")
        check("468: an owner-blocked needs-design todo is written as blocked-owner with the owner's answer",
              fm8["triage"] == "blocked-owner" and fm8["blocked_on"] == "Owner: wait for the redesign (2026-09-28)",
              fm8)
        check("468: a todo skipped for this run keeps its class (asked again next sweep)", fm9["triage"] == "stale",
              fm9)
        # PR #869 round 1: an owner's "ready" answer, then a worker block, is not an owner block.
        (repo / "todos/10-pending-p3-x.md").write_text(head.format(s="pending", i="10"))
        worked = state.new_run("r4d", "sweep", 3, [todo("10")], ["10"])
        state.record_triage(worked, [rec("10", "needs-design", "Which layout?")])
        state.decide(worked, "10", "ready", decision="Use the two-column layout")
        state.transition(worked, "10", "executing")
        state.transition(worked, "10", "blocked", reason="worker: needs the design file")
        state.apply_triage(worked, repo, "2026-09-28")
        check("PR #869: a worker block after an owner's ready answer keeps the triage class",
              todofile.read_frontmatter(repo / "todos/10-pending-p3-x.md")["triage"] == "needs-design")

        import scan  # noqa: E402 -- scan imports state, so only here
        picked, _ = scan.select(scan.load_todos(repo / "todos"), selector="sweep", inflight=set(),
                                changed_since=lambda p, d: False)
        check("468: the next sweep does not re-ask the answered todo, and does re-ask the skipped one",
              "8" not in [t["id"] for t in picked] and "9" in [t["id"] for t in picked], [t["id"] for t in picked])

    done = state.new_run("r5", "sweep", 3, [todo("1")], ["1"])
    state.transition(done, "1", "blocked", reason="x")
    check("is_complete when every todo is terminal", state.is_complete(done))

    # todo 469: the pilot's 432 blocked on a missing .env; once #864 cleared it, nothing could re-brief it.
    run = state.new_run("r7", "sweep", 3, [todo("1"), todo("2"), todo("3")], ["1", "2", "3"])
    state.record_triage(run, [rec("1"), rec("2")])
    state.accept_ready(run)
    for stage, fields in [("executing", {}), ("blocked", {"reason": "no backend/.env"})]:
        state.transition(run, "1", stage, **fields)
    run["todos"]["1"].update(group="g1", worktree="/wt/g1", branch="worktree-g1", tree_id="T1")
    run["unschedulable"]["1"] = "stale reason"
    check("blocked -> ready needs a reason", raises(lambda: state.transition(run, "1", "ready")))
    check("blocked -> blocked stays refused", raises(lambda: state.transition(run, "1", "blocked", reason="again")))
    state.transition(run, "1", "ready", reason="blocker cleared by #864")
    one = run["todos"]["1"]
    check("blocked -> ready reopens the todo", one["stage"] == "ready" and one["reason"] == "blocker cleared by #864")
    check("reopening drops the group so the todo is regrouped", "group" not in one)
    check("the blocked attempt's worktree, branch and reason move to previous",
          one["previous"] == [{"reason": "no backend/.env", "group": "g1", "worktree": "/wt/g1",
                               "branch": "worktree-g1", "tree_id": "T1"}], one.get("previous"))
    check("reopening does not spend the retry", one["attempts"] == 0)
    check("reopening clears a stale unschedulable reason", "1" not in run["unschedulable"])
    check("a reopened todo makes the run incomplete again", not state.is_complete(run))
    state.transition(run, "2", "blocked", reason="review round 2", pr=870)
    check("a blocked todo with a PR is not reopened",
          raises(lambda: state.transition(run, "2", "ready", reason="fixed")) and run["todos"]["2"]["stage"] == "blocked")
    state.transition(run, "3", "blocked", reason="set by hand")
    check("a blocked todo with no triage record is not reopened",
          raises(lambda: state.transition(run, "3", "ready", reason="fixed")))
    run["todos"]["1"]["worktree"] = "/wt/g4"
    run["todos"]["2"]["worktree"] = "/wt/g2"
    run["todos"]["3"].update(stage="archived", worktree="/wt/g3")
    check("worktrees lists every unarchived todo's worktrees, earlier attempts included (todo 468 F5)",
          state.recorded_worktrees(run) == {"1": ["/wt/g4", "/wt/g1"], "2": ["/wt/g2"]}, state.recorded_worktrees(run))

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

        runfile = state.run_path(tmp, "r8")
        state.save(state.new_run("r8", "sweep", 3, [todo("1")], ["1"]), runfile)
        cli = [sys.executable, os.path.join(script_dir, "state.py"), "triage-args", str(runfile)]
        plain = json.loads(subprocess.run(cli, capture_output=True, text=True).stdout)
        rooted = json.loads(subprocess.run(cli + ["--root", tmp], capture_output=True, text=True).stdout)
        check("triage-args adds no root unless asked", "root" not in plain and plain["todos"][0]["id"] == "1", plain)
        check("triage-args --root passes an absolute origin/main tree to the triagers (todo 468)",
              rooted["root"] == str(Path(tmp).resolve()), rooted)

    # PR #868 round 1: a triager searching the root returns absolute paths; they keep their lanes.
    run = state.new_run("r9", "sweep", 3, [todo("1")], ["1"])
    root = Path("/scratch/triage-r9").resolve()
    record = rec("1") | {"predicted_files": [f"{root}/backend/plant_community_backend/settings.py", "/elsewhere/x.py",
                                             "web/src/a.ts"]}
    state.record_triage(run, [record], root=str(root))
    triaged = run["todos"]["1"]["triage"]
    check("record_triage makes paths under the triage root repo-relative",
          triaged["predicted_files"] == ["backend/plant_community_backend/settings.py", "web/src/a.ts"]
          and triaged["dropped_files"] == ["/elsewhere/x.py"], triaged)

    # Todo 473: a symlinked root (macOS /tmp is /private/tmp) in either form, reported in either form.
    with tempfile.TemporaryDirectory() as tmp:
        real = Path(tmp).resolve() / "real-root"
        (real / "backend").mkdir(parents=True)
        link = Path(tmp) / "link-root"
        link.symlink_to(real)
        for label, root, reported in (("resolved root, path reported through the link", real, link),
                                      ("linked root, path reported resolved", link, real)):
            run = state.new_run("r10", "sweep", 3, [todo("1")], ["1"])
            state.record_triage(run, [rec("1") | {"predicted_files": [f"{reported}/backend/a.py",
                                                                       f"{reported}/web/new_file.ts"]}],
                                root=str(root))
            triaged = run["todos"]["1"]["triage"]
            check(f"473 AC4: record-triage keeps both paths ({label})",
                  triaged["predicted_files"] == ["backend/a.py", "web/new_file.ts"] and "dropped_files" not in triaged,
                  triaged)

    # Todo 474: apply-triage and a stranded todo.
    with tempfile.TemporaryDirectory() as tmp:
        repo = git_repo(tmp)
        head = '---\nstatus: {s}\npriority: p3\nissue_id: "{i}"\ndependencies: []\n---\n\n# T{i}\n\n## Work Log\n'
        (repo / "todos/11-in_progress-p3-x.md").write_text(head.format(s="in_progress", i="11"))
        (repo / "todos/11-pending-p3-x.md").write_text(head.format(s="pending", i="11"))
        (repo / "todos/12-pending-p3-x.md").write_text(head.format(s="pending", i="12"))
        commit_all(repo)
        both = state.new_run("r11", "sweep", 3, [{"id": "11", "path": "todos/11-in_progress-p3-x.md", "priority": "p3",
                                                  "stranded": True}, todo("12")], ["11", "12"])
        state.record_triage(both, [rec("11"), rec("12")])
        state.decide(both, "11", "ready", reset_stranded=True)
        state.decide(both, "12", "ready")
        before12 = (repo / "todos/12-pending-p3-x.md").read_text()
        err = None
        try:
            state.apply_triage(both, repo, "2026-09-28")
        except RuntimeError as exc:
            err = exc
        check("474 AC3: apply-triage refuses a stranded todo whose old and new paths both exist, naming both",
              err is not None and "todos/11-in_progress-p3-x.md" in str(err) and "todos/11-pending-p3-x.md" in str(err),
              err)
        check("474: the refusal comes before anything is written (the other todo is untouched)",
              (repo / "todos/12-pending-p3-x.md").read_text() == before12
              and (repo / "todos/11-in_progress-p3-x.md").exists())

        (repo / "todos/13-in_progress-p3-x.md").write_text(head.format(s="in_progress", i="13"))
        commit_all(repo)
        later = state.new_run("r12", "sweep", 3, [{"id": "13", "path": "todos/13-in_progress-p3-x.md",
                                                   "priority": "p3", "stranded": True}], ["13"])
        state.record_triage(later, [rec("13")])
        state.decide(later, "13", "ready", reset_stranded=True)
        saved = json.loads(json.dumps(later))  # the run file as it was, before a failed save
        state.apply_triage(later, repo, "2026-09-28")
        state.apply_triage(saved, repo, "2026-09-29")
        text = (repo / "todos/13-pending-p3-x.md").read_text()
        check("474 AC4: a rerun of apply-triage on a later day adds no second 'Returned to pending' entry",
              text.count("Returned to pending by the todo sweep") == 1 and "2026-09-29 - Returned" not in text, text)

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} check(s): {', '.join(FAILURES)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
