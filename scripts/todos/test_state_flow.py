#!/usr/bin/env python3
"""Tests for the execute/review half of scripts/todos/state.py.

Run: python3 scripts/todos/test_state_flow.py (also run by harness-ci.yml).

evaluate() is where "a different agent re-ran the evidence" becomes a rule
instead of a hope (spec §5.2): a verifier that passes while the staged tree
moved, or leaves the working tree dirty, must void the verdict.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import state  # noqa: E402

FAILURES = []


def check(label, condition, detail=""):
    print(f"  {'PASS' if condition else 'FAIL'}  {label}{'' if condition else f'  -- {detail}'}")
    if not condition:
        FAILURES.append(label)


def rec(id_, files, cls="ready", size="s"):
    return {"id": id_, "class": cls, "evidence": "e", "blocked_on": "", "owner_question": "",
            "predicted_files": files, "size": size, "needs_e2e": False, "notes_for_siblings": ""}


def ready_run(specs, workers=3):
    todos = [{"id": i, "path": f"todos/{i}-pending-p3-x.md", "priority": "p3"} for i, _ in specs]
    run = state.new_run("r", "sweep", workers, todos, [i for i, _ in specs])
    state.record_triage(run, [rec(i, f) for i, f in specs])
    state.accept_ready(run)
    return run


def worker(ids, tree="T1", status="staged"):
    return {"ids": ids, "status": status, "worktree": "/wt/g1", "branch": "worktree-g1", "tree_id": tree,
            "files_changed": ["a.py"], "ac_file": ".sweep-evidence/g1/ac.json", "tests_run": ["pytest a"],
            "blockers": "", "discoveries": "", "summary": "done"}


def verdict(ids, before="T1", after="T1", clean=True, result="pass", ac_ok=True, edits=()):
    return {"ids": ids, "verdict": result, "ac": [{"todo": ids[0], "index": 0, "verified": ac_ok, "note": ""}],
            "test_edits_flagged": list(edits), "commands_rerun": 1,
            "tree_id_before": before, "tree_id_after": after, "clean_after": clean}


def worktree_run(todo_id, gid, branch, worktree="", tree_id=None, main_root=""):
    entry = {"stage": "staged", "group": gid, "worktree": worktree, "branch": branch, "main_root": main_root}
    if tree_id is not None:
        entry["tree_id"] = tree_id
    return {"todos": {todo_id: entry}, "groups": {gid: {"ids": [todo_id]}}}


def main():
    check("evaluate passes a clean, matching verdict", state.evaluate(worker(["1"]), verdict(["1"])) is None)
    check("no verdict is a problem", state.evaluate(worker(["1"]), None) == "no verdict")
    check("a failing verdict is a problem", "fail" in state.evaluate(worker(["1"]), verdict(["1"], result="fail")))
    check("a tree that moved during verification voids the verdict",
          "tree changed" in state.evaluate(worker(["1"]), verdict(["1"], after="T2")))
    check("a verifier that starts on a different tree voids it",
          "tree changed" in state.evaluate(worker(["1"]), verdict(["1"], before="T0")))
    check("a dirty working tree after verification voids it",
          "not clean" in state.evaluate(worker(["1"]), verdict(["1"], clean=False)))
    check("a pass with an unverified criterion is a problem",
          "unverified" in state.evaluate(worker(["1"]), verdict(["1"], ac_ok=False)))
    empty_ac = verdict(["1"])
    empty_ac["ac"] = []
    check("a pass with an empty ac list is a problem", "coverage" in state.evaluate(worker(["1"]), empty_ac))
    check("a pass whose ac covers only one of two todos is a problem",
          "coverage" in state.evaluate(worker(["1", "2"]), verdict(["1", "2"])))
    mismatched = verdict(["1"])
    mismatched["ids"] = ["2"]
    check("a verdict naming different todos than the worker is a problem",
          "different todos" in state.evaluate(worker(["1"]), mismatched))

    check("slots alternate between two banks", [state.slot_for(w, p, 3) for w, p in [(0, 1), (0, 3), (1, 1), (2, 2)]]
          == [1, 3, 4, 2])

    run = ready_run([("1", ["a.py"]), ("2", ["b.py"]), ("3", ["c.py"]), ("4", ["d.py"])], workers=2)
    state.apply_grouping(run)
    check("grouping stores waves no wider than the worker count",
          all(len(w) <= 2 for w in run["waves"]) and sum(len(w) for w in run["waves"]) == 4, run["waves"])
    briefs = state.execute_args(run, 0, "/main")
    check("execute_args marks the wave executing",
          all(run["todos"][i]["stage"] == "executing" for b in briefs for i in b["ids"]))
    check("briefs carry slots 1..workers for wave 0", [b["slot"] for b in briefs] == [1, 2])
    check("briefs are self-contained", set(briefs[0]) >= {"run_id", "group", "ids", "todo_paths", "owner_decisions",
                                                           "plan_needed", "verify_only", "in_scope_files",
                                                           "lanes_held", "lanes_forbidden", "slot", "evidence_dir",
                                                           "main_root"}, briefs[0])
    check("a wave cannot start before the previous wave has executed",
          raises(lambda: state.execute_args(run, 1, "/main")))

    g_ok, g_bad = briefs[0]["group"], briefs[1]["group"]
    ids_ok, ids_bad = briefs[0]["ids"], briefs[1]["ids"]
    outcome = state.ingest_execute(run, [
        {"group": g_ok, "ids": ids_ok, "worker": worker(ids_ok), "verdict": verdict(ids_ok), "retried": False},
        {"group": g_bad, "ids": ids_bad, "worker": worker(ids_bad), "verdict": verdict(ids_bad, after="T9"),
         "retried": True},
    ])
    check("a verified group moves to verified", all(run["todos"][i]["stage"] == "verified" for i in ids_ok), outcome)
    check("a voided verdict moves to failed with the reason",
          all(run["todos"][i]["stage"] == "failed" and "tree changed" in run["todos"][i]["reason"] for i in ids_bad))
    check("worktree and branch are recorded", run["todos"][ids_ok[0]]["worktree"] == "/wt/g1")

    briefs1 = state.execute_args(run, 1, "/main")
    check("wave 1 uses the second slot bank", [b["slot"] for b in briefs1] == [3, 4][:len(briefs1)], briefs1)
    ids_w = briefs1[0]["ids"]
    state.ingest_execute(run, [{"group": briefs1[0]["group"], "ids": ids_w, "worker": None, "verdict": None,
                                "retried": False}] + [
        {"group": b["group"], "ids": b["ids"], "worker": worker(b["ids"], status="blocked") | {"blockers": "needs key"},
         "verdict": None, "retried": False} for b in briefs1[1:]])
    check("a worker that returned nothing fails", run["todos"][ids_w[0]]["stage"] == "failed")
    if len(briefs1) > 1:
        check("a blocked worker blocks with its blocker", run["todos"][briefs1[1]["ids"][0]]["reason"] == "needs key")

    state.set_group(run, g_ok, "pr_open", pr=861)
    items = state.review_args(run, 1, 0)
    check("review_args lists open PRs in the wave", [i["group"] for i in items] == [g_ok] and items[0]["pr"] == 861)
    rerun_finding = [{"severity": "low", "file": "a.py", "line": 9, "summary": "should not land", "suggested_fix": ""}]
    res = state.ingest_review(run, [{"group": g_ok, "ids": ids_ok, "findings": rerun_finding, "blocking": [],
                                     "reviewers_ok": False, "repair": None, "verdict": None}], 1)
    check("an incomplete review asks for a rerun and adds no followups",
          res[g_ok] == "rerun" and run["todos"][ids_ok[0]].get("review_round", 0) == 0
          and run["todos"][ids_ok[0]].get("followups", []) == [])
    blocking = [{"severity": "high", "file": "a.py", "line": 1, "summary": "bug", "suggested_fix": ""}]
    res = state.ingest_review(run, [{"group": g_ok, "ids": ids_ok, "findings": blocking, "blocking": blocking,
                                     "reviewers_ok": True, "repair": worker(ids_ok, tree="T5"),
                                     "verdict": verdict(ids_ok, before="T5", after="T5", edits=["tests/test_a.py"])}],
                              1)
    check("a verified round-1 repair is staged for the main session to commit", res[g_ok] == "repair-staged")
    check("a round-1 repair's flagged test edits carry into round 2",
          "tests/test_a.py" in state.review_args(run, 2, 0)[0]["test_edits"])
    check("an invalid round number is refused", raises(lambda: state.review_args(run, 3, 0), ValueError))
    low = [{"severity": "low", "file": "a.py", "line": 2, "summary": "nit", "suggested_fix": ""}]
    res = state.ingest_review(run, [{"group": g_ok, "ids": ids_ok, "findings": low, "blocking": [],
                                     "reviewers_ok": True, "checklist_skipped": True, "repair": None,
                                     "verdict": None}], 2)
    check("a skipped checklist review is recorded", run["todos"][ids_ok[0]]["checklist_skipped"] is True)
    check("a clean round 2 moves to reviewed", res[g_ok] == "clean"
          and all(run["todos"][i]["stage"] == "reviewed" for i in ids_ok))
    check("non-blocking findings are kept as follow-ups", run["todos"][ids_ok[0]]["followups"] == ["a.py:2 nit"])

    state.annotate(run, g_ok, branch="feat/1-x")
    check("annotate records a field without a stage change",
          run["todos"][ids_ok[0]]["branch"] == "feat/1-x" and run["todos"][ids_ok[0]]["stage"] == "reviewed")
    stage_before = run["todos"][ids_ok[0]]["stage"]
    check("annotate refuses to set 'stage'", raises(lambda: state.annotate(run, g_ok, stage="archived")))
    check("the stage is unchanged after the rejected annotate", run["todos"][ids_ok[0]]["stage"] == stage_before)

    for i in ids_bad:
        state.transition(run, i, "ready")
    waves_before = len(run["waves"])
    state.apply_grouping(run)
    new_gid = run["todos"][ids_bad[0]]["group"]
    check("a retried todo is regrouped into a new, appended wave",
          len(run["waves"]) == waves_before + 1 and run["waves"][-1] == [new_gid] and new_gid not in (g_ok, g_bad),
          run["waves"])
    check("regrouping keeps the earlier groups", g_ok in run["groups"] and g_bad in run["groups"])
    check("the old group no longer counts the retried todo", state._group_entries(run, g_bad) == [])
    # F1: regrouping a failed-and-retried todo must not empty other waves, and the
    # execute_args gate must see past an emptied same-parity wave to an earlier one.
    run1 = ready_run([("f1", ["e1.py"]), ("f2", ["e2.py"]), ("f3", ["e3.py"]), ("f4", ["e4.py"])], workers=1)
    state.apply_grouping(run1)
    check("f1 setup: four singleton waves", len(run1["waves"]) == 4 and all(len(w) == 1 for w in run1["waves"]))
    fb0 = state.execute_args(run1, 0, "/m")
    fg0, fid0 = fb0[0]["group"], fb0[0]["ids"]
    state.ingest_execute(run1, [{"group": fg0, "ids": fid0, "worker": worker(fid0), "verdict": verdict(fid0),
                                 "retried": False}])
    state.set_group(run1, fg0, "pr_open", pr=1)
    fb1 = state.execute_args(run1, 1, "/m")
    fg1, fid1 = fb1[0]["group"], fb1[0]["ids"]
    state.ingest_execute(run1, [{"group": fg1, "ids": fid1, "worker": None, "verdict": None, "retried": False}])
    for i in fid1:
        state.transition(run1, i, "ready")
    wave2_before, wave3_before = list(run1["waves"][2]), list(run1["waves"][3])
    state.apply_grouping(run1)
    check("waves 2 and 3 keep their original groups after an earlier wave regroups",
          run1["waves"][2] == wave2_before and run1["waves"][3] == wave3_before, run1["waves"])
    new_g = run1["todos"][fid1[0]]["group"]
    check("the retried todo goes into a new, appended wave",
          len(run1["waves"]) == 5 and new_g not in (fg0, fg1) and run1["waves"][4] == [new_g], run1["waves"])
    check("execute_args refuses a wave whose earlier same-parity wave is still pr_open",
          raises(lambda: state.execute_args(run1, 2, "/m"), state.TransitionError))

    # F6: followups are capped at 10 in total across review rounds, not per call.
    run6 = ready_run([("f6", ["z.py"])], workers=1)
    state.apply_grouping(run6)
    g6 = run6["waves"][0][0]
    state.execute_args(run6, 0, "/m")
    state.ingest_execute(run6, [{"group": g6, "ids": ["f6"], "worker": worker(["f6"]), "verdict": verdict(["f6"]),
                                 "retried": False}])
    state.set_group(run6, g6, "pr_open", pr=42)
    many = [{"severity": "low", "file": "f.py", "line": n, "summary": "n", "suggested_fix": ""} for n in range(15)]
    state.ingest_review(run6, [{"group": g6, "ids": ["f6"], "findings": many, "blocking": [],
                                "reviewers_ok": True, "repair": None, "verdict": None}], 1)
    state.ingest_review(run6, [{"group": g6, "ids": ["f6"], "findings": many, "blocking": [],
                                "reviewers_ok": True, "repair": None, "verdict": None}], 2)
    check("followups are capped at 10 total across rounds, not per call",
          len(run6["todos"]["f6"]["followups"]) <= 10, run6["todos"]["f6"]["followups"])

    # F3: ensure_worktree must run git against the real repo, recover a worktree whose
    # directory vanished but whose branch still holds the commit, and refuse to trust
    # a re-add that silently lost uncommitted (staged-only) work.
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q",
                        "--allow-empty", "-m", "init"], check=True)
        git = lambda *a: state.run_git(repo, *a[1:])

        wt = Path(tmp) / "worker-wt"
        subprocess.run(["git", "-C", str(repo), "worktree", "add", "-q", "-b", "worktree-g1", str(wt)], check=True)
        (wt / "a.py").write_text("x = 1\n")
        subprocess.run(["git", "-C", str(wt), "add", "a.py"], check=True)
        subprocess.run(["git", "-C", str(wt), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q",
                        "-m", "work"], check=True)
        committed_tree = subprocess.run(["git", "-C", str(wt), "write-tree"], capture_output=True,
                                         text=True).stdout.strip()
        shutil.rmtree(wt)
        run_c = worktree_run("c1", "gc", "worktree-g1", worktree=str(wt), tree_id=committed_tree)
        path = state.ensure_worktree(run_c, "gc", Path(tmp) / "scratch", git=git)
        check("a missing worktree with committed work is re-added from its branch",
              Path(path).is_dir() and path.endswith("gc"), path)
        check("the run file points at the new worktree", run_c["todos"]["c1"]["worktree"] == path)
        check("an existing worktree whose tree still matches is left alone",
              state.ensure_worktree(run_c, "gc", Path(tmp) / "scratch") == path)

        wt2 = Path(tmp) / "worker-wt2"
        subprocess.run(["git", "-C", str(repo), "worktree", "add", "-q", "-b", "worktree-g2", str(wt2)], check=True)
        (wt2 / "b.py").write_text("y = 2\n")
        subprocess.run(["git", "-C", str(wt2), "add", "b.py"], check=True)
        staged_tree = subprocess.run(["git", "-C", str(wt2), "write-tree"], capture_output=True,
                                      text=True).stdout.strip()
        shutil.rmtree(wt2)
        run_s = worktree_run("s1", "gs", "worktree-g2", worktree=str(wt2), tree_id=staged_tree)
        check("a worktree that lost its only (uncommitted) staged work raises",
              raises(lambda: state.ensure_worktree(run_s, "gs", Path(tmp) / "scratch", git=git), RuntimeError))

        existing = Path(tmp) / "scratch3" / "gd"
        existing.mkdir(parents=True)
        (existing / "keep.txt").write_text("mine")
        run_d = worktree_run("d1", "gd", "worktree-g1", worktree=str(Path(tmp) / "gone3"))
        check("a non-empty target directory is never touched",
              raises(lambda: state.ensure_worktree(run_d, "gd", Path(tmp) / "scratch3", git=git), RuntimeError)
              and (existing / "keep.txt").exists())

    # F6 (CLI): an out-of-range wave must exit 2 with a message, not an uncaught traceback.
    with tempfile.TemporaryDirectory() as tmp:
        run9 = ready_run([("z1", ["zz.py"])], workers=1)
        state.apply_grouping(run9)
        runfile = Path(tmp) / "run.json"
        state.save(run9, runfile)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        result = subprocess.run([sys.executable, os.path.join(script_dir, "state.py"), "review-args", str(runfile),
                                  "--round", "1", "--wave", "9"], capture_output=True, text=True)
        check("review-args on an out-of-range wave exits 2, not a traceback", result.returncode == 2)
        check("the error is reported as 'state: <message>'", result.stderr.startswith("state: "))

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} check(s): {', '.join(FAILURES)}")
        return 1
    print("All checks passed.")
    return 0


def raises(fn, exc=state.TransitionError):
    try:
        fn()
    except exc:
        return True
    return False


if __name__ == "__main__":
    sys.exit(main())
