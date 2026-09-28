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


def verdict(ids, before="T1", after="T1", clean=True, result="pass", ac_ok=True, edits=(), note=""):
    return {"ids": ids, "verdict": result, "ac": [{"todo": ids[0], "index": 0, "verified": ac_ok, "note": note}],
            "test_edits_flagged": list(edits), "commands_rerun": 1,
            "tree_id_before": before, "tree_id_after": after, "clean_after": clean, "reasons": []}


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
    # F9: land.py's flip_acs reads verified_ac off the run entry (state.py, not tested until now).
    check("ingest_execute stores the verdict's ac list as verified_ac",
          run["todos"][ids_ok[0]]["verified_ac"] == verdict(ids_ok)["ac"], run["todos"][ids_ok[0]])

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
    # B2: Land archived the todo before review, so the prompts need both paths.
    check("review_args gives the archived todo paths, as land.archive writes them",
          items[0]["todo_paths"] == [f"todos/archive/{i}-completed-p3-x.md" for i in ids_ok], items[0])
    check("review_args gives the pending (merge-base) paths as origin_paths",
          items[0]["origin_paths"] == [run["todos"][i]["path"] for i in ids_ok], items[0])
    rerun_finding = [{"severity": "low", "file": "a.py", "line": 9, "summary": "should not land", "suggested_fix": ""}]
    res = state.ingest_review(run, [{"group": g_ok, "ids": ids_ok, "findings": rerun_finding, "blocking": [],
                                     "reviewers_ok": False, "repair": None, "verdict": None}], 1)
    check("an incomplete review asks for a rerun and adds no followups",
          res[g_ok] == "rerun" and run["todos"][ids_ok[0]].get("review_round", 0) == 0
          and run["todos"][ids_ok[0]].get("followups", []) == [])
    blocking = [{"severity": "high", "file": "a.py", "line": 1, "summary": "bug", "suggested_fix": ""}]
    # G2: the repair verdict's ac carries a distinct note from the original ingest_execute
    # verdict (which used the default note=""), so this can tell "updated from the repair"
    # apart from "still holding the value the first ingest_execute call set" -- the same
    # ids/ac_ok would otherwise make an identical ac list either way, proving nothing.
    repair_verdict = verdict(ids_ok, before="T5", after="T5", edits=["tests/test_a.py"], note="repair")
    res = state.ingest_review(run, [{"group": g_ok, "ids": ids_ok, "findings": blocking, "blocking": blocking,
                                     "reviewers_ok": True, "repair": worker(ids_ok, tree="T5"),
                                     "verdict": repair_verdict}],
                              1)
    check("a verified round-1 repair is staged for the main session to commit", res[g_ok] == "repair-staged")
    check("a round-1 repair updates verified_ac from the repair's (distinct) verdict",
          run["todos"][ids_ok[0]]["verified_ac"] == repair_verdict["ac"], run["todos"][ids_ok[0]])
    check("a round-1 repair's flagged test edits carry into round 2",
          "tests/test_a.py" in state.review_args(run, 2, 0)[0]["test_edits"])
    check("an invalid round number is refused", raises(lambda: state.review_args(run, 3, 0), ValueError))
    low = [{"severity": "low", "file": "a.py", "line": 2, "summary": "nit", "suggested_fix": ""}]
    res = state.ingest_review(run, [{"group": g_ok, "ids": ids_ok, "findings": low, "blocking": [],
                                     "reviewers_ok": True, "repair": None, "verdict": None,
                                     "refuted": [{"severity": "high", "file": "b.py", "line": 3, "summary": "maybe",
                                                  "suggested_fix": "", "also": [], "refutations": ["no", "no"]}]}], 2)
    check("a finding both refuters dismissed is kept for the wrap-up",
          run["todos"][ids_ok[0]]["refuted"] == ["b.py:3 maybe"], run["todos"][ids_ok[0]])
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
    # R1(d): the emptied wave 1 (W-2 for wave 3) must not hide wave 0, still further back and unresolved.
    check("execute_args refuses a wave even further out while an emptied wave hides an earlier blocker",
          raises(lambda: state.execute_args(run1, 3, "/m"), state.TransitionError))
    # R1(d), isolated from R4's W-1 check: wave 0 stuck at pr_open, wave 1 emptied, wave
    # 2 independently resolved past ready/executing (so R4's own W-1 check is satisfied)
    # -- only the "waves 0..W-2" range check can still catch wave 0 here.
    run1d = ready_run([("d0", ["dd0.py"]), ("d1", ["dd1.py"]), ("d2", ["dd2.py"]), ("d3", ["dd3.py"])], workers=1)
    state.apply_grouping(run1d)
    g0d, g1d, g2d = (run1d["waves"][w][0] for w in (0, 1, 2))
    state.transition(run1d, "d0", "executing", group=g0d, slot=1, wave=0, main_root="/m")
    state.transition(run1d, "d0", "staged", worktree="/wt0", branch="b0", tree_id="T0", ac_file="a0")
    state.transition(run1d, "d0", "verified", test_edits=[], verified_ac=[])
    state.transition(run1d, "d0", "pr_open", pr=1)  # left unresolved
    run1d["todos"]["d1"].pop("group", None)  # simulates: d1 retried, its group now empty
    state.transition(run1d, "d2", "executing", group=g2d, slot=1, wave=2, main_root="/m")
    state.transition(run1d, "d2", "staged", worktree="/wt2", branch="b2", tree_id="T2", ac_file="a2")
    state.transition(run1d, "d2", "verified", test_edits=[], verified_ac=[])
    state.transition(run1d, "d2", "pr_open", pr=2)
    state.transition(run1d, "d2", "reviewed", review_round=2)
    state.transition(run1d, "d2", "merged")  # past ready/executing, so R4's W-1 check is quiet
    check("R1(d) isolated: a far-earlier unresolved wave still blocks past an emptied, resolved one",
          raises(lambda: state.execute_args(run1d, 3, "/m"), state.TransitionError))
    # R1(c): once wave 0 clears, the emptied wave 1 must dispatch nothing (not raise, not include fid1).
    state.set_group(run1, fg0, "reviewed")
    state.set_group(run1, fg0, "merged")
    check("an emptied wave dispatches nothing once its blocker clears",
          state.execute_args(run1, 1, "/m") == [])

    # R2: a retry must not let a dependent group keep running in the wrong order.
    # X (g1) <- Y (g2, independent) <- Z (g3, depends on X). X fails and retries;
    # Z's group must be dropped too (its dep group is now empty) and rescheduled
    # at least 2 waves after X's new placement.
    run2 = ready_run([("x1", ["dep_x.py"]), ("y1", ["dep_y.py"]), ("z1", ["dep_z.py"])], workers=1)
    run2["todos"]["z1"]["dependencies"] = ["x1"]
    state.apply_grouping(run2)
    check("r2 setup: 3 waves, Z's group depends on X's group",
          len(run2["waves"]) == 3
          and run2["groups"][run2["waves"][2][0]]["deps"] == [run2["waves"][0][0]], run2["waves"])
    bx = state.execute_args(run2, 0, "/m")
    gx, idx = bx[0]["group"], bx[0]["ids"]
    state.ingest_execute(run2, [{"group": gx, "ids": idx, "worker": None, "verdict": None, "retried": False}])
    for i in idx:
        state.transition(run2, i, "ready")
    by = state.execute_args(run2, 1, "/m")
    gy, idy = by[0]["group"], by[0]["ids"]
    state.ingest_execute(run2, [{"group": gy, "ids": idy, "worker": worker(idy), "verdict": verdict(idy),
                                 "retried": False}])
    old_z_group = run2["todos"]["z1"]["group"]
    state.apply_grouping(run2)
    check("R2: Z's group is dropped once its dependency's group is empty",
          run2["todos"]["z1"]["group"] != old_z_group)
    new_x_wave = next(w for w, gids in enumerate(run2["waves"]) if run2["todos"][idx[0]]["group"] in gids)
    new_z_wave = next(w for w, gids in enumerate(run2["waves"]) if run2["todos"]["z1"]["group"] in gids)
    check("R2: Z's new wave comes at least 2 waves after X's new wave",
          new_z_wave >= new_x_wave + 2, (new_x_wave, new_z_wave))
    check("R2: execute_args for Z's old wave no longer dispatches Z",
          "z1" not in [i for b in state.execute_args(run2, 2, "/m") for i in b["ids"]])
    check("R2: Y (no dependency) is untouched by the ungrouping",
          run2["todos"]["y1"]["group"] == gy)

    # S1 (probe P4): a PARTLY emptied dependency group must also release its
    # dependents. x1 and x2 share a group (same predicted file); z depends on
    # x1. x1 is retried (ungrouped) but x2 is separately blocked, so the
    # group still lists x2 -- it must still count as stale.
    run4 = ready_run([("x1", ["shared4.py"]), ("x2", ["shared4.py"]), ("z1", ["depz4.py"])], workers=1)
    run4["todos"]["z1"]["dependencies"] = ["x1"]
    state.apply_grouping(run4)
    g1_4 = run4["todos"]["x1"]["group"]
    check("s1 setup: x1 and x2 share a group; z's group depends on it",
          run4["todos"]["x2"]["group"] == g1_4
          and run4["groups"][run4["todos"]["z1"]["group"]]["deps"] == [g1_4])
    # Drive x1 to failed-then-ready (retried) and x2 to blocked directly via transition(),
    # rather than through execute_args/ingest_execute: the two must diverge, and a single
    # shared-group worker result cannot express that (one worker, one outcome, one PR).
    state.transition(run4, "x1", "executing", group=g1_4, slot=1, wave=0, main_root="/m")
    state.transition(run4, "x1", "staged", worktree="/wtx1", branch="bx1", tree_id="Tx1", ac_file="ax1")
    state.transition(run4, "x1", "failed", reason="verifier disagreed")
    state.transition(run4, "x1", "ready")
    state.transition(run4, "x2", "blocked", reason="owner decision")
    old_z4_group = run4["todos"]["z1"]["group"]
    state.apply_grouping(run4)
    check("S1: a partly emptied dependency group (x2 still present, blocked) still releases its dependent",
          run4["todos"]["z1"]["group"] != old_z4_group)
    new_x1_wave = next(w for w, gids in enumerate(run4["waves"]) if run4["todos"]["x1"]["group"] in gids)
    new_z4_wave = next(w for w, gids in enumerate(run4["waves"]) if run4["todos"]["z1"]["group"] in gids)
    check("S1: z's new wave comes at least 2 waves after x1's new wave",
          new_z4_wave >= new_x1_wave + 2, (new_x1_wave, new_z4_wave))

    # S2: the ungrouping fixpoint must be transitive, not a single pass. Chain
    # x1 <- m1 <- a1 (a1 depends on m1, m1 depends on x1). x1 retries; both m1
    # and a1 must be ungrouped and re-placed >= 2 waves after their dependency
    # -- ids are chosen ("a1" sorts before "m1") so a single, non-repeating
    # pass would ungroup m1 but miss a1 (a1 is visited before m1 in that pass).
    run_chain = ready_run([("x1", ["chx.py"]), ("m1", ["chm.py"]), ("a1", ["cha.py"])], workers=1)
    run_chain["todos"]["m1"]["dependencies"] = ["x1"]
    run_chain["todos"]["a1"]["dependencies"] = ["m1"]
    state.apply_grouping(run_chain)
    bxc = state.execute_args(run_chain, 0, "/m")
    gxc, idxc = bxc[0]["group"], bxc[0]["ids"]
    state.ingest_execute(run_chain, [{"group": gxc, "ids": idxc, "worker": None, "verdict": None,
                                      "retried": False}])
    for i in idxc:
        state.transition(run_chain, i, "ready")
    old_m_group, old_a_group = run_chain["todos"]["m1"]["group"], run_chain["todos"]["a1"]["group"]
    state.apply_grouping(run_chain)
    check("S2: the transitive fixpoint ungroups both M and A, not just M",
          run_chain["todos"]["m1"]["group"] != old_m_group and run_chain["todos"]["a1"]["group"] != old_a_group,
          (run_chain["todos"]["m1"]["group"], run_chain["todos"]["a1"]["group"]))
    new_x_wave_c = next(w for w, gids in enumerate(run_chain["waves"]) if run_chain["todos"]["x1"]["group"] in gids)
    new_m_wave_c = next(w for w, gids in enumerate(run_chain["waves"]) if run_chain["todos"]["m1"]["group"] in gids)
    new_a_wave_c = next(w for w, gids in enumerate(run_chain["waves"]) if run_chain["todos"]["a1"]["group"] in gids)
    check("S2: M's new wave is at least 2 waves after X's new wave", new_m_wave_c >= new_x_wave_c + 2)
    check("S2: A's new wave is at least 2 waves after M's new wave", new_a_wave_c >= new_m_wave_c + 2)

    # R4: evaluate() compares verdict/worker ids order-insensitively.
    reordered = verdict(["1", "2"])
    reordered["ids"] = ["2", "1"]
    reordered["ac"] = [{"todo": "1", "index": 0, "verified": True, "note": ""},
                        {"todo": "2", "index": 0, "verified": True, "note": ""}]
    check("evaluate compares verdict/worker ids order-insensitively",
          state.evaluate(worker(["1", "2"]), reordered) is None)

    # R4: dispatch order restored -- W-1 still "ready" (never executed) refuses the next wave.
    run_order = ready_run([("o1", ["oo1.py"]), ("o2", ["oo2.py"])], workers=1)
    state.apply_grouping(run_order)
    check("execute_args refuses a wave while the previous wave is still ready, not just executing",
          raises(lambda: state.execute_args(run_order, 1, "/m"), state.TransitionError))

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

    # R4: within-call duplicate findings are stored once, and two rounds with the
    # same 3 findings store 3 (not 6).
    run_dup = ready_run([("fd", ["dup.py"])], workers=1)
    state.apply_grouping(run_dup)
    gd = run_dup["waves"][0][0]
    state.execute_args(run_dup, 0, "/m")
    state.ingest_execute(run_dup, [{"group": gd, "ids": ["fd"], "worker": worker(["fd"]), "verdict": verdict(["fd"]),
                                    "retried": False}])
    state.set_group(run_dup, gd, "pr_open", pr=7)
    within_call_dup = [{"severity": "low", "file": "a.py", "line": 5, "summary": "dup", "suggested_fix": ""}] * 2
    state.ingest_review(run_dup, [{"group": gd, "ids": ["fd"], "findings": within_call_dup, "blocking": [],
                                   "reviewers_ok": True, "repair": None, "verdict": None}], 1)
    check("within-call duplicate findings are stored once",
          run_dup["todos"]["fd"]["followups"] == ["a.py:5 dup"], run_dup["todos"]["fd"]["followups"])
    three = [{"severity": "low", "file": f"f{n}.py", "line": n, "summary": "x", "suggested_fix": ""}
             for n in range(3)]
    run_dup["todos"]["fd"]["followups"] = []
    run_dup["todos"]["fd"]["review_round"] = 0  # a fresh round 1 (todo 468 refuses a round-1 re-ingest)
    state.ingest_review(run_dup, [{"group": gd, "ids": ["fd"], "findings": three, "blocking": [],
                                   "reviewers_ok": True, "repair": None, "verdict": None}], 1)
    state.ingest_review(run_dup, [{"group": gd, "ids": ["fd"], "findings": three, "blocking": [],
                                   "reviewers_ok": True, "repair": None, "verdict": None}], 2)
    check("two rounds with the same 3 findings store 3, not 6",
          len(run_dup["todos"]["fd"]["followups"]) == 3, run_dup["todos"]["fd"]["followups"])

    # B5: the verifier's group-level reasons reach the recorded fail reason.
    run_rs = ready_run([("rs", ["rs.py"])], workers=1)
    state.apply_grouping(run_rs)
    grs = run_rs["waves"][0][0]
    state.execute_args(run_rs, 0, "/m")
    edited = verdict(["rs"], result="fail") | {"reasons": ["acceptance criteria were edited"]}
    state.ingest_execute(run_rs, [{"group": grs, "ids": ["rs"], "worker": worker(["rs"]), "verdict": edited,
                                   "retried": True}])
    check("ingest_execute appends the verdict's reasons to the fail reason",
          run_rs["todos"]["rs"]["stage"] == "failed"
          and run_rs["todos"]["rs"]["reason"] == "verifier: fail: acceptance criteria were edited",
          run_rs["todos"]["rs"])
    run_nr = ready_run([("nr", ["nr.py"])], workers=1)
    state.apply_grouping(run_nr)
    gnr = run_nr["waves"][0][0]
    state.execute_args(run_nr, 0, "/m")
    state.ingest_execute(run_nr, [{"group": gnr, "ids": ["nr"], "worker": worker(["nr"]),
                                   "verdict": verdict(["nr"], after="T9") | {"reasons": []}, "retried": False}])
    check("an empty reasons list leaves the fail reason unchanged",
          run_nr["todos"]["nr"]["reason"] == "staged tree changed during verification", run_nr["todos"]["nr"])

    # B5/B7: round-1 repair failures name their cause.
    def review_run(todo_id):
        rr = ready_run([(todo_id, [f"{todo_id}.py"])], workers=1)
        state.apply_grouping(rr)
        gid = rr["waves"][0][0]
        state.execute_args(rr, 0, "/m")
        state.ingest_execute(rr, [{"group": gid, "ids": [todo_id], "worker": worker([todo_id]),
                                   "verdict": verdict([todo_id]), "retried": False}])
        state.set_group(rr, gid, "pr_open", pr=5)
        return rr, gid

    high = [{"severity": "high", "file": "a.py", "line": 1, "summary": "bug", "suggested_fix": ""}]
    run_rb, grb = review_run("rb")
    res = state.ingest_review(run_rb, [{"group": grb, "ids": ["rb"], "findings": high, "blocking": high,
                                        "reviewers_ok": True, "repair": worker(["rb"], status="blocked")
                                        | {"blockers": "needs the deps lane"},
                                        "repair_blockers": "needs the deps lane", "verdict": None}], 1)
    check("a blocked round-1 repair records its blockers, not 'no verdict'",
          res[grb] == "blocked" and run_rb["todos"]["rb"]["reason"]
          == "round-1 repair failed: repair blocked: needs the deps lane", run_rb["todos"]["rb"])
    run_rv, grv = review_run("rv")
    state.ingest_review(run_rv, [{"group": grv, "ids": ["rv"], "findings": high, "blocking": high,
                                  "reviewers_ok": True, "repair": worker(["rv"], tree="T5"),
                                  "verdict": verdict(["rv"], before="T5", after="T5", result="fail")
                                  | {"reasons": ["tree not clean before verification"]}}], 1)
    check("a failed repair verdict's reasons reach the blocked reason",
          run_rv["todos"]["rv"]["reason"]
          == "round-1 repair failed: verifier: fail: tree not clean before verification", run_rv["todos"]["rv"])

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
        path, err = expect(lambda: state.ensure_worktree(run_c, "gc", Path(tmp) / "scratch", git=git))
        check("a missing worktree with committed work is re-added from its branch",
              err is None and path is not None and Path(path).is_dir() and path.endswith("gc"), err or path)
        check("the run file points at the new worktree", err is None and run_c["todos"]["c1"]["worktree"] == path)
        path2, err2 = expect(lambda: state.ensure_worktree(run_c, "gc", Path(tmp) / "scratch"))
        check("an existing worktree whose tree still matches is left alone", err2 is None and path2 == path, err2)

        # R3: a resumed Land stages and commits its own edits (todos/, docs/reviews/,
        # .secrets.baseline) on top of the recorded tree_id -- that must be accepted,
        # not read as lost work; any other changed path must still raise.
        land_wt = Path(tmp) / "scratch" / "gc"
        (land_wt / "todos").mkdir(exist_ok=True)
        (land_wt / "todos" / "100-completed-p3-x.md").write_text("archived by land\n")
        subprocess.run(["git", "-C", str(land_wt), "add", "-A"], check=True)
        land_path, err3 = expect(lambda: state.ensure_worktree(run_c, "gc", Path(tmp) / "scratch"))
        check("a resumed Land's todos/ edit is accepted, not read as lost work",
              err3 is None and land_path == str(land_wt), err3)

        source_wt = Path(tmp) / "worker-wt3"
        subprocess.run(["git", "-C", str(repo), "worktree", "add", "-q", "-b", "worktree-g1-src", str(source_wt),
                        "worktree-g1"], check=True)
        (source_wt / "a.py").write_text("x = 2\n")
        subprocess.run(["git", "-C", str(source_wt), "add", "-A"], check=True)
        run_src = worktree_run("src1", "gsrc", "worktree-g1-src", worktree=str(source_wt), tree_id=committed_tree)
        check("a change to a source file outside Land's write-set still raises",
              raises(lambda: state.ensure_worktree(run_src, "gsrc", Path(tmp) / "scratch"), RuntimeError))

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
        # R4: a failed tree check must not leave a changed worktree path recorded.
        check("a failed tree check leaves the entry's worktree unchanged",
              run_s["todos"]["s1"]["worktree"] == str(wt2))

        existing = Path(tmp) / "scratch3" / "gd"
        existing.mkdir(parents=True)
        (existing / "keep.txt").write_text("mine")
        run_d = worktree_run("d1", "gd", "worktree-g1", worktree=str(Path(tmp) / "gone3"))
        check("a non-empty target directory is never touched",
              raises(lambda: state.ensure_worktree(run_d, "gd", Path(tmp) / "scratch3", git=git), RuntimeError)
              and (existing / "keep.txt").exists())

        # S3: an empty current tree must be rejected even when the recorded tree held
        # only todos/ files -- the ls-tree emptiness guard, not just the path allowlist
        # (a diff from a todos/-only tree to nothing would otherwise pass the allowlist).
        todos_only_wt = Path(tmp) / "worker-wt4"
        subprocess.run(["git", "-C", str(repo), "worktree", "add", "-q", "-b", "worktree-g4", str(todos_only_wt)],
                       check=True)
        (todos_only_wt / "todos").mkdir()
        (todos_only_wt / "todos" / "100-x.md").write_text("hello\n")
        subprocess.run(["git", "-C", str(todos_only_wt), "add", "-A"], check=True)
        todos_only_tree = subprocess.run(["git", "-C", str(todos_only_wt), "write-tree"], capture_output=True,
                                          text=True).stdout.strip()
        (todos_only_wt / "todos" / "100-x.md").unlink()
        subprocess.run(["git", "-C", str(todos_only_wt), "add", "-A"], check=True)
        run_empty = worktree_run("e1", "ge", "worktree-g4", worktree=str(todos_only_wt), tree_id=todos_only_tree)
        check("an empty current tree is rejected even though the recorded tree held only todos/ files",
              raises(lambda: state.ensure_worktree(run_empty, "ge", Path(tmp) / "scratch"), RuntimeError))

        # S4: a path that merely starts with the same letters (no slash) must still be
        # rejected -- proves the prefix check's trailing slash is load-bearing.
        slash_wt = Path(tmp) / "worker-wt5"
        subprocess.run(["git", "-C", str(repo), "worktree", "add", "-q", "-b", "worktree-g5", str(slash_wt)],
                       check=True)
        slash_baseline = subprocess.run(["git", "-C", str(slash_wt), "write-tree"], capture_output=True,
                                         text=True).stdout.strip()
        (slash_wt / "todos_x").mkdir()
        (slash_wt / "todos_x" / "f.md").write_text("not really todos/\n")
        (slash_wt / "docs" / "reviews-old").mkdir(parents=True)
        (slash_wt / "docs" / "reviews-old" / "r.md").write_text("not really docs/reviews/\n")
        subprocess.run(["git", "-C", str(slash_wt), "add", "-A"], check=True)
        run_slash = worktree_run("sl1", "gslash", "worktree-g5", worktree=str(slash_wt), tree_id=slash_baseline)
        check("todos_x/ and docs/reviews-old/ are rejected -- the prefix check's trailing slash matters",
              raises(lambda: state.ensure_worktree(run_slash, "gslash", Path(tmp) / "scratch"), RuntimeError))

    # R4: ensure_worktree must use the entry's main_root for -C, not the process cwd.
    # Uses the real run_git (no override) and runs from a cwd outside the repo, so a
    # regression to a hardcoded "." would fail (that cwd is not a git repo at all).
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q",
                        "--allow-empty", "-m", "init"], check=True)
        subprocess.run(["git", "-C", str(repo), "branch", "worktree-mr"], check=True)
        run_mr = worktree_run("m1", "gmr", "worktree-mr", worktree=str(Path(tmp) / "gone-mr"), main_root=str(repo))
        elsewhere = Path(tmp) / "elsewhere"
        elsewhere.mkdir()
        prev_cwd = os.getcwd()
        os.chdir(elsewhere)
        try:
            path_mr, err_mr = expect(lambda: state.ensure_worktree(run_mr, "gmr", Path(tmp) / "scratch-mr"))
        finally:
            os.chdir(prev_cwd)
        check("ensure_worktree uses the entry's main_root for -C, not the process cwd",
              err_mr is None and path_mr is not None and Path(path_mr).is_dir() and path_mr.endswith("gmr"),
              err_mr)

    # Final review I3: the execute gate reads every in-run dependency by stage. The reviewer's
    # probe: 401 <- 402, one worker, waves [[g1], [], [g2]].
    def dep_run():
        rd = ready_run([("401", ["dep401.py"]), ("402", ["dep402.py"])], workers=1)
        rd["todos"]["402"]["dependencies"] = ["401"]
        state.apply_grouping(rd)
        b0 = state.execute_args(rd, 0, "/m")
        state.ingest_execute(rd, [{"group": b0[0]["group"], "ids": ["401"], "worker": None, "verdict": None,
                                   "retried": False}])
        return rd, next(w for w, gids in enumerate(rd["waves"]) if rd["todos"]["402"]["group"] in gids)

    run_b, w402 = dep_run()
    state.transition(run_b, "401", "blocked", reason="owner said no")
    for w in range(1, w402):
        state.execute_args(run_b, w, "/m")
    briefs_b, err_b = expect(lambda: state.execute_args(run_b, w402, "/m"))
    check("I3: a blocked dependency blocks its dependent instead of handing it out",
          err_b is None and briefs_b == [] and run_b["todos"]["402"]["stage"] == "blocked"
          and run_b["todos"]["402"]["reason"] == "dependency 401 blocked", err_b or run_b["todos"]["402"])

    run_r, w402 = dep_run()
    state.transition(run_r, "401", "ready")  # retried: its group is popped, so _group_entries hides it
    for w in range(1, w402):
        state.execute_args(run_r, w, "/m")
    check("I3: a retried dependency holds its dependent (execute_args refuses, nothing is handed out)",
          raises(lambda: state.execute_args(run_r, w402, "/m")) and run_r["todos"]["402"]["stage"] == "ready",
          run_r["todos"]["402"])

    # The gate itself, isolated from the wave gate: a dependency with no group edge at all (the
    # fold-in below drops edges to in-run todos past ready) still holds its dependent.
    run_e = ready_run([("501", ["e501.py"]), ("502", ["e502.py"])], workers=2)
    state.apply_grouping(run_e)
    run_e["todos"]["502"]["dependencies"] = ["501"]
    check("I3: a same-wave dependency with no group edge holds its dependent",
          len(run_e["waves"][0]) == 2 and raises(lambda: state.execute_args(run_e, 0, "/m"))
          and run_e["todos"]["501"]["stage"] == "ready", run_e["waves"])

    # Fold-in (T7 P5): 403 depends on 401 and 402. 401 reaches pr_open, 402 fails and is retried.
    # 403 is regrouped with 402, and must wait for 401 -- not be blocked for good.
    run_p = ready_run([("401", ["p401.py"]), ("402", ["p402.py"]), ("403", ["p403.py"])], workers=2)
    run_p["todos"]["403"]["dependencies"] = ["401", "402"]
    state.apply_grouping(run_p)
    bp = state.execute_args(run_p, 0, "/m")
    by_id = {b["ids"][0]: b for b in bp}
    state.ingest_execute(run_p, [
        {"group": by_id["401"]["group"], "ids": ["401"], "worker": worker(["401"]), "verdict": verdict(["401"]),
         "retried": False},
        {"group": by_id["402"]["group"], "ids": ["402"], "worker": None, "verdict": None, "retried": False}])
    state.set_group(run_p, by_id["401"]["group"], "pr_open", pr=9)
    state.transition(run_p, "402", "ready")
    result_p = state.apply_grouping(run_p)
    check("I3: a regrouped todo whose other dependency is pr_open waits, it is not blocked",
          run_p["todos"]["403"]["stage"] == "ready" and "group" in run_p["todos"]["403"]
          and "403" not in result_p["unschedulable"], (run_p["todos"]["403"], result_p))

    # Fold-in, deadlock guard: a dependent placed earlier must be regrouped when its dependency
    # is retried later, or its wave would wait forever on a dependency placed after it.
    run_d = ready_run([("601", ["d601.py"]), ("602", ["d602.py"])], workers=2)
    run_d["todos"]["602"]["dependencies"] = ["601"]
    state.apply_grouping(run_d)
    g602 = run_d["todos"]["602"]["group"]
    state.transition(run_d, "601", "executing", group=run_d["todos"]["601"]["group"], slot=1, wave=0, main_root="/m")
    state.transition(run_d, "601", "failed", reason="x")
    state.transition(run_d, "601", "ready")
    run_d["groups"][g602]["deps"] = []  # as if placed with the edge dropped (dependency was past ready)
    state.apply_grouping(run_d)
    w601 = next(w for w, gids in enumerate(run_d["waves"]) if run_d["todos"]["601"]["group"] in gids)
    w602 = next(w for w, gids in enumerate(run_d["waves"]) if run_d["todos"]["602"]["group"] in gids)
    check("I3: a dependent is regrouped with its retried dependency and placed after it",
          run_d["todos"]["602"]["group"] != g602 and w602 >= w601 + 2, (w601, w602, run_d["waves"]))

    # Re-review N1: the gate blocks ONE member of a two-member group (402, sharing a file with 403;
    # since B-2 an xs todo with a dependency edge is never bundled, so the group is a shared-file one).
    # The blocked member must leave the group entirely, or Land and review read it as the group's
    # first member, and a dependent of the member that ran (404 <- 403) is blocked on it.
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q",
                        "--allow-empty", "-m", "init"], check=True)
        wt = Path(tmp) / "wt403"
        subprocess.run(["git", "-C", str(repo), "worktree", "add", "-q", "-b", "worktree-n1", str(wt)], check=True)
        (wt / "backend").mkdir()
        (wt / "backend" / "n403.py").write_text("x = 1\n")
        subprocess.run(["git", "-C", str(wt), "add", "-A"], check=True)
        tree403 = subprocess.run(["git", "-C", str(wt), "write-tree"], capture_output=True, text=True).stdout.strip()

        todos_n1 = [{"id": i, "path": f"todos/{i}-pending-p3-x.md", "priority": "p3"} for i in ("401", "402", "403",
                                                                                                "404")]
        run_n1 = state.new_run("r", "sweep", 1, todos_n1, ["401", "402", "403", "404"])
        state.record_triage(run_n1, [rec("401", ["n401.py"]), rec("402", ["backend/n402.py", "backend/n1-shared.py"]),
                                     rec("403", ["backend/n403.py", "backend/n1-shared.py"]), rec("404", ["n404.py"])])
        state.accept_ready(run_n1)
        run_n1["todos"]["402"]["dependencies"] = ["401"]
        run_n1["todos"]["404"]["dependencies"] = ["403"]
        state.apply_grouping(run_n1)
        g2 = run_n1["todos"]["403"]["group"]
        check("N1 setup: 402 and 403 share one group", run_n1["todos"]["402"].get("group") == g2
              and sorted(run_n1["groups"][g2]["ids"]) == ["402", "403"], run_n1["groups"])
        wave_of_n1 = {i: next(w for w, gids in enumerate(run_n1["waves"]) if run_n1["todos"][i]["group"] in gids)
                      for i in ("401", "403", "404")}
        b0 = state.execute_args(run_n1, 0, "/m")
        state.ingest_execute(run_n1, [{"group": b0[0]["group"], "ids": ["401"], "retried": False, "verdict": None,
                                       "worker": worker(["401"], status="blocked") | {"blockers": "owner"}}])
        briefs_n1 = []
        for w in range(1, wave_of_n1["403"] + 1):
            briefs_n1 = state.execute_args(run_n1, w, "/m")
        check("N1: the gate blocks 402 and dispatches only 403",
              [b["ids"] for b in briefs_n1] == [["403"]] and run_n1["todos"]["402"]["stage"] == "blocked", briefs_n1)
        check("N1: the gate-blocked member leaves the group (entry and recorded ids)",
              "group" not in run_n1["todos"]["402"] and run_n1["groups"][g2]["ids"] == ["403"],
              (run_n1["todos"]["402"].get("group"), run_n1["groups"][g2]["ids"]))
        state.ingest_execute(run_n1, [{"group": g2, "ids": ["403"], "retried": False,
                                       "worker": worker(["403"], tree=tree403) | {"worktree": str(wt),
                                                                                  "branch": "worktree-n1"},
                                       "verdict": verdict(["403"], before=tree403, after=tree403)}])
        _, err = expect(lambda: state.set_group(run_n1, g2, "pr_open", pr=9))
        check("N1: set_group moves the group that ran to pr_open", err is None
              and run_n1["todos"]["403"]["stage"] == "pr_open", err)
        path_n1, err = expect(lambda: state.ensure_worktree(run_n1, g2, Path(tmp) / "scratch"))
        check("N1: ensure_worktree finds the member that ran", err is None and path_n1 == str(wt), err)
        items, err = expect(lambda: state.review_args(run_n1, 1, wave_of_n1["403"]))
        check("N1: review_args lists the group", err is None and [i["group"] for i in (items or [])] == [g2]
              and items[0]["ids"] == ["403"], err or items)
        _, err = expect(lambda: (state.set_group(run_n1, g2, "reviewed"), state.set_group(run_n1, g2, "merged")))
        briefs_404 = []
        for w in range(wave_of_n1["403"] + 1, wave_of_n1["404"] + 1):
            got, err = expect(lambda: state.execute_args(run_n1, w, "/m"))
            briefs_404 = got or []
        check("N1: a dependent of the member that ran is dispatched, not blocked on the gate-blocked member",
              err is None and [b["ids"] for b in briefs_404] == [["404"]]
              and run_n1["todos"]["404"]["stage"] == "executing", err or run_n1["todos"]["404"])

    # PR #861 B-1: a member that depends on a gate-blocked member of the SAME group (directly or
    # through a chain inside the group) is blocked too, never handed out alone.
    def intra_group_run(chain):
        ids = ["x1"] + chain
        rb1 = ready_run([("x1", ["bx.py"])] + [(i, ["b1-shared.py"]) for i in chain], workers=1)
        rb1["todos"][chain[0]]["dependencies"] = ["x1"]
        for dependent, dependency in zip(chain[1:], chain):
            rb1["todos"][dependent]["dependencies"] = [dependency]
        state.apply_grouping(rb1)
        gid = rb1["todos"][chain[0]]["group"]
        wave = next(w for w, gids in enumerate(rb1["waves"]) if gid in gids)
        b0 = state.execute_args(rb1, 0, "/m")
        state.ingest_execute(rb1, [{"group": b0[0]["group"], "ids": ["x1"], "retried": False, "verdict": None,
                                    "worker": worker(["x1"], status="blocked") | {"blockers": "owner"}}])
        out = []
        for w in range(1, wave + 1):
            got, err = expect(lambda: state.execute_args(rb1, w, "/m"))
            out = got if err is None else [err]
        return rb1, gid, ids, out

    rb1, gb1, _, out = intra_group_run(["a1", "b1"])
    check("B-1: A (dep X blocked) and B (dep A, same group) are both blocked; nothing is handed out",
          out == [] and [rb1["todos"][i]["stage"] for i in ("a1", "b1")] == ["blocked", "blocked"]
          and rb1["todos"]["b1"]["reason"] == "dependency a1 blocked" and rb1["groups"][gb1]["ids"] == [],
          (out, {i: rb1["todos"][i].get("reason") for i in ("a1", "b1")}, rb1["groups"][gb1]["ids"]))
    rb1, gb1, _, out = intra_group_run(["a1", "b1", "c1"])
    check("B-1: a chain inside the group (C <- B <- A <- X) blocks all three, each naming its blocked dependency",
          out == [] and [rb1["todos"][i]["reason"] for i in ("a1", "b1", "c1")]
          == ["dependency x1 blocked", "dependency a1 blocked", "dependency b1 blocked"]
          and "group" not in rb1["todos"]["c1"],
          (out, {i: (rb1["todos"][i]["stage"], rb1["todos"][i].get("reason")) for i in ("a1", "b1", "c1")}))

    # Final review I5: a worker that stops short still has a worktree; record it.
    run_w = ready_run([("701", ["w701.py"]), ("702", ["w702.py"]), ("703", ["w703.py"])], workers=3)
    state.apply_grouping(run_w)
    bw = {b["ids"][0]: b for b in state.execute_args(run_w, 0, "/m")}
    blocked_worker = worker(["701"], status="blocked") | {"worktree": "/wt/a1", "branch": "worktree-agent-a1",
                                                          "tree_id": "TB", "blockers": "device check"}
    state.ingest_execute(run_w, [
        {"group": bw["701"]["group"], "ids": ["701"], "worker": blocked_worker, "verdict": None, "retried": False},
        {"group": bw["702"]["group"], "ids": ["702"], "worker": worker(["702"], status="failed")
         | {"worktree": "/wt/a2", "branch": "worktree-agent-a2"}, "verdict": None, "retried": False},
        {"group": bw["703"]["group"], "ids": ["703"], "worker": None, "verdict": None, "retried": True,
         "worktree": "/wt/a3"}])
    e701, e702, e703 = (run_w["todos"][i] for i in ("701", "702", "703"))
    check("I5: a blocked worker's worktree, branch, tree and ac file are recorded",
          e701["stage"] == "blocked" and (e701.get("worktree"), e701.get("branch"), e701.get("tree_id"),
                                          e701.get("ac_file")) == ("/wt/a1", "worktree-agent-a1", "TB",
                                                                   ".sweep-evidence/g1/ac.json"), e701)
    check("I5: a failed worker's worktree is recorded", e702["stage"] == "failed" and e702.get("worktree") == "/wt/a2",
          e702)
    check("I5: a dead retry keeps the first attempt's worktree from the result",
          e703["stage"] == "failed" and e703.get("worktree") == "/wt/a3", e703)

    # Final review m10: only a PR number is coerced to an int.
    check("m10: _parse_fields coerces only pr",
          state._parse_fields(["pr=861", "tree_id=0123", "reason=404", "branch=412"])
          == {"pr": 861, "tree_id": "0123", "reason": "404", "branch": "412"})

    # Final review m11: predicted files are repo-relative, or they silently miss a lane.
    run_n = state.new_run("r", "sweep", 1, [{"id": "801", "path": "todos/801-pending-p3-x.md", "priority": "p3"}],
                          ["801"])
    state.record_triage(run_n, [rec("801", ["./backend/plant_community_backend/settings.py",
                                            "/abs/elsewhere.py", "web/a.ts"])])
    t801 = run_n["todos"]["801"]["triage"]
    check("m11: a leading ./ is stripped, so the settings lane is found",
          t801["predicted_files"] == ["backend/plant_community_backend/settings.py", "web/a.ts"]
          and state.group.lanes_for(t801) == {"settings"}, t801)
    check("m11: an absolute path is dropped and noted on the record", t801.get("dropped_files") == ["/abs/elsewhere.py"],
          t801)

    # Final review m2: spec §5.2's clean check -- an unstaged change outside Land's paths refuses.
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        (repo / "todos").mkdir()
        (repo / "a.py").write_text("x = 1\n")
        (repo / "todos" / "t.md").write_text("t\n")
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q",
                        "-m", "init"], check=True)
        wt = Path(tmp) / "wt-clean"
        subprocess.run(["git", "-C", str(repo), "worktree", "add", "-q", "-b", "worktree-m2", str(wt)], check=True)
        (wt / "b.py").write_text("y = 2\n")
        subprocess.run(["git", "-C", str(wt), "add", "b.py"], check=True)
        staged = subprocess.run(["git", "-C", str(wt), "write-tree"], capture_output=True, text=True).stdout.strip()
        run_m2 = worktree_run("m2", "gm2", "worktree-m2", worktree=str(wt), tree_id=staged)
        path_m2, err_m2 = expect(lambda: state.ensure_worktree(run_m2, "gm2", Path(tmp) / "scratch"))
        check("m2: staged work alone is clean", err_m2 is None and path_m2 == str(wt), err_m2)
        (wt / "todos" / "t.md").write_text("edited by a resumed Land, not staged yet\n")
        path_m2, err_m2 = expect(lambda: state.ensure_worktree(run_m2, "gm2", Path(tmp) / "scratch"))
        check("m2: an unstaged edit under todos/ (Land's own path) is accepted", err_m2 is None, err_m2)
        (wt / "a.py").write_text("x = 'sed -i after verification'\n")
        check("m2: an unstaged edit to a tracked file outside Land's paths refuses",
              raises(lambda: state.ensure_worktree(run_m2, "gm2", Path(tmp) / "scratch"), RuntimeError))
        (wt / "untracked.log").write_text("test artifact\n")
        (wt / "a.py").write_text("x = 1\n")
        path_m2, err_m2 = expect(lambda: state.ensure_worktree(run_m2, "gm2", Path(tmp) / "scratch"))
        check("m2: an untracked test artifact does not count", err_m2 is None, err_m2)

    # PR #861 B-3 (engine backstop): Land never commits a force-staged ignored file. Only paths the
    # branch ADDED count, so a file already tracked at the base that matches an ignore rule passes.
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        (repo / "backend").mkdir()
        (repo / ".gitignore").write_text("backend/.env\n*.log\n")
        (repo / "a.py").write_text("x = 1\n")
        (repo / "legacy.log").write_text("tracked before the ignore rule\n")
        subprocess.run(["git", "-C", str(repo), "add", ".gitignore", "a.py"], check=True)
        subprocess.run(["git", "-C", str(repo), "add", "-f", "legacy.log"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q",
                        "-m", "base"], check=True)
        subprocess.run(["git", "-C", str(repo), "update-ref", "refs/remotes/origin/main", "HEAD"], check=True)
        wt = Path(tmp) / "wt-b3"
        subprocess.run(["git", "-C", str(repo), "worktree", "add", "-q", "-b", "worktree-b3", str(wt)], check=True)
        (wt / "b.py").write_text("y = 2\n")
        (wt / "legacy.log").write_text("edited, still tracked\n")
        subprocess.run(["git", "-C", str(wt), "add", "b.py", "legacy.log"], check=True)

        def b3_run():
            tree = subprocess.run(["git", "-C", str(wt), "write-tree"], capture_output=True, text=True).stdout.strip()
            return worktree_run("b3", "gb3", "worktree-b3", worktree=str(wt), tree_id=tree)

        path_b3, err_b3 = expect(lambda: state.ensure_worktree(b3_run(), "gb3", Path(tmp) / "scratch"))
        check("B-3: a normal staged change passes, even beside a base-tracked file matching an ignore rule",
              err_b3 is None and path_b3 == str(wt), err_b3)
        (wt / "backend").mkdir(exist_ok=True)
        (wt / "backend" / ".env").write_text("SECRET_KEY=fake-value-for-the-test\n")  # pragma: allowlist secret
        subprocess.run(["git", "-C", str(wt), "add", "-f", "backend/.env"], check=True)
        _, err_b3 = expect(lambda: state.ensure_worktree(b3_run(), "gb3", Path(tmp) / "scratch"))
        check("B-3: a force-staged backend/.env is refused, and the error names it",
              isinstance(err_b3, RuntimeError) and "backend/.env" in str(err_b3) and "legacy.log" not in str(err_b3),
              err_b3)
        subprocess.run(["git", "-C", str(repo), "update-ref", "-d", "refs/remotes/origin/main"], check=True)
        _, err_b3 = expect(lambda: state.ensure_worktree(b3_run(), "gb3", Path(tmp) / "scratch"))
        check("B-3: with no base to compare against, the check fails closed", isinstance(err_b3, RuntimeError), err_b3)

    # Todo 468 (slice B): ensure_worktree's re-add path and its staging backstop.
    def git_(repo, *args):
        return subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *args],
                              capture_output=True, text=True, check=True).stdout.strip()

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        (repo / ".gitignore").write_text("backend/.env\n*.log\n")
        (repo / ".worktreeinclude").write_text("# copied into every worktree\nbackend/.env\nweb/.env\n")
        (repo / "a.py").write_text("x = 1\n")
        (repo / "legacy.log").write_text("tracked before the ignore rule\n")
        git_(repo, "add", ".gitignore", ".worktreeinclude", "a.py")
        git_(repo, "add", "-f", "legacy.log")
        git_(repo, "commit", "-q", "-m", "base")
        bare = Path(tmp) / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
        git_(repo, "remote", "add", "origin", str(bare))
        git_(repo, "push", "-q", "origin", "main")
        git_(repo, "fetch", "-q", "origin")
        git_(repo, "branch", "feat/468-b")
        git_(repo, "push", "-q", "origin", "feat/468-b")
        git_(repo, "fetch", "-q", "origin")

        # A failed tree check after a re-add leaves no new worktree behind.
        empty_tree = git_(repo, "hash-object", "-w", "-t", "tree", "/dev/null")  # a real tree, not the branch's
        run_t = worktree_run("t1", "gt1", "feat/468-b", worktree=str(Path(tmp) / "gone"), tree_id=empty_tree,
                             main_root=str(repo))
        _, err = expect(lambda: state.ensure_worktree(run_t, "gt1", Path(tmp) / "scratch"))
        check("468: a failed tree check after a re-add removes the new worktree again",
              isinstance(err, RuntimeError) and "lost its staged work" in str(err)
              and not (Path(tmp) / "scratch" / "gt1").exists()
              and str(Path(tmp) / "scratch" / "gt1") not in git_(repo, "worktree", "list"), err)

        # The local branch is gone but it was pushed: recover from origin/<branch>, with no upstream
        # written (the sandbox denies .git/config writes, so --track would fail there).
        git_(repo, "branch", "-D", "feat/468-b")
        run_o = worktree_run("o1", "go1", "feat/468-b", worktree=str(Path(tmp) / "gone"), main_root=str(repo))
        path_o, err = expect(lambda: state.ensure_worktree(run_o, "go1", Path(tmp) / "scratch"))
        upstream = subprocess.run(["git", "-C", str(repo), "config", "branch.feat/468-b.remote"],
                                  capture_output=True, text=True).stdout.strip()
        check("468: a pushed branch whose local ref is gone is recovered from origin/<branch>, untracked",
              err is None and path_o and git_(path_o, "rev-parse", "HEAD") == git_(repo, "rev-parse", "origin/feat/468-b")
              and upstream == "", err or upstream)

        # A worker that deletes the .env rule from .gitignore can `git add -A` backend/.env without -f.
        wt = Path(path_o)
        (wt / ".gitignore").write_text("*.log\n")
        (wt / "backend").mkdir()
        (wt / "backend" / ".env").write_text("SECRET_KEY=fake-value-for-the-test\n")  # pragma: allowlist secret
        git_(wt, "add", "-A")
        _, err = expect(lambda: state.ensure_worktree(run_o, "go1", Path(tmp) / "scratch"))
        check("468: a .worktreeinclude path the branch adds is refused even after a .gitignore edit",
              isinstance(err, RuntimeError) and "backend/.env" in str(err), err)
        git_(wt, "rm", "-q", "--cached", "backend/.env")
        git_(wt, "checkout", "--", ".gitignore")
        git_(wt, "add", ".gitignore")

        # A git mv of a tracked file onto an ignored path is refused with its real cause.
        git_(wt, "mv", "legacy.log", "moved.log")
        _, err = expect(lambda: state.ensure_worktree(run_o, "go1", Path(tmp) / "scratch"))
        check("468: a rename onto an ignored path is refused, naming the rename, not a force-stage",
              isinstance(err, RuntimeError) and "moved.log" in str(err) and "legacy.log" in str(err)
              and "force-staged" not in str(err), err)

    # Final review m4: a dependency cycle exits 2 with `state: dependency cycle: ...`, not a traceback.
    with tempfile.TemporaryDirectory() as tmp:
        run_c = ready_run([("901", ["c901.py"]), ("902", ["c902.py"])], workers=1)
        run_c["todos"]["901"]["dependencies"] = ["902"]
        run_c["todos"]["902"]["dependencies"] = ["901"]
        runfile = Path(tmp) / "run.json"
        state.save(run_c, runfile)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        result = subprocess.run([sys.executable, os.path.join(script_dir, "state.py"), "group", str(runfile)],
                                capture_output=True, text=True)
        check("m4: a dependency cycle exits 2 with a state: message",
              result.returncode == 2 and result.stderr.startswith("state: dependency cycle")
              and "Traceback" not in result.stderr, (result.returncode, result.stderr[-300:]))

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

    # todo 469: the pilot's 432 -- a worker blocks, the owner clears the blocker, the todo is re-briefed.
    run = ready_run([("432", ["backend/a.py"])], workers=1)
    state.apply_grouping(run)
    first = state.execute_args(run, 0, "/main")[0]
    state.ingest_execute(run, [{"group": first["group"], "ids": ["432"], "retried": False, "verdict": None,
                                "worker": worker(["432"], status="blocked") | {"blockers": "no backend/.env"}}])
    check("a blocked worker leaves the todo blocked", run["todos"]["432"]["stage"] == "blocked")
    state.transition(run, "432", "ready", reason="blocker cleared by #864")
    regrouped = state.apply_grouping(run)
    again, err = expect(lambda: state.execute_args(run, len(run["waves"]) - 1, "/main"))
    check("a reopened todo is re-briefed in a new group and wave",
          err is None and len(again) == 1 and again[0]["ids"] == ["432"] and again[0]["group"] != first["group"]
          and regrouped["waves"] == [[again[0]["group"]]], err or again)
    check("the re-brief keeps the blocked attempt's worktree findable",
          run["todos"]["432"]["previous"][0]["worktree"] == "/wt/g1", run["todos"]["432"].get("previous"))

    # Todo 468: wave N-1 is still in review or Land while wave N executes, so a worker in wave N
    # must not touch a lane wave N-1 holds -- until that wave has merged.
    def lane_run():
        rl = ready_run([("l1", ["backend/plant_community_backend/settings.py"]), ("l2", ["l2.py"])], workers=1)
        state.apply_grouping(rl)
        bl0 = state.execute_args(rl, 0, "/m")
        state.ingest_execute(rl, [{"group": bl0[0]["group"], "ids": ["l1"], "worker": worker(["l1"]),
                                   "verdict": verdict(["l1"]), "retried": False}])
        state.set_group(rl, bl0[0]["group"], "pr_open", pr=5)
        return rl, bl0[0]["group"]

    settings_doc = state.group.LANE_DOC["settings"]
    run_l, gl1 = lane_run()
    bl1, err = expect(lambda: state.execute_args(run_l, 1, "/m"))
    check("468: lanes_forbidden includes the lanes of the previous wave while it is not merged",
          err is None and bl1[0]["ids"] == ["l2"] and settings_doc in bl1[0]["lanes_forbidden"], err or bl1)
    run_l, gl1 = lane_run()
    state.set_group(run_l, gl1, "reviewed")
    state.set_group(run_l, gl1, "merged")
    bl1, err = expect(lambda: state.execute_args(run_l, 1, "/m"))
    check("468: a merged previous wave no longer forbids its lanes",
          err is None and settings_doc not in bl1[0]["lanes_forbidden"], err or bl1)

    # Todo 468: a member blocked by the owner after grouping (decide/set, not the gate) leaves its
    # group, and its in-group dependent is blocked with it instead of shipping without it.
    run_x = ready_run([("x402", ["xs.py", "x402.py"]), ("x403", ["xs.py", "x403.py"]),
                       ("x404", ["xs.py", "x404.py"])], workers=1)
    run_x["todos"]["x403"]["dependencies"] = ["x402"]
    state.apply_grouping(run_x)
    gx = run_x["todos"]["x402"]["group"]
    state.decide(run_x, "x402", "blocked", decision="Owner: not this sweep")
    bx, err = expect(lambda: state.execute_args(run_x, 0, "/m"))
    check("468: an owner-blocked member's in-group dependent is blocked, and only the rest is handed out",
          err is None and [b["ids"] for b in bx] == [["x404"]] and run_x["todos"]["x403"]["stage"] == "blocked"
          and run_x["todos"]["x403"]["reason"] == "dependency x402 blocked", err or (bx, run_x["todos"]["x403"]))
    check("468: the owner-blocked member and its dependent leave the group",
          "group" not in run_x["todos"]["x402"] and "group" not in run_x["todos"]["x403"]
          and run_x["groups"][gx]["ids"] == ["x404"], (run_x["todos"]["x402"], run_x["groups"][gx]))

    # PR #869 round 1: a retried member keeps its first attempt's `wave`; blocked by the owner after
    # regrouping, it must still leave its new group, and its in-group dependent must block with it.
    run_r2 = ready_run([("r101", ["rx.py", "r101.py"]), ("r102", ["rx.py", "r102.py"])], workers=1)
    run_r2["todos"]["r102"]["dependencies"] = ["r101"]
    state.apply_grouping(run_r2)
    br = state.execute_args(run_r2, 0, "/m")[0]
    state.ingest_execute(run_r2, [{"group": br["group"], "ids": br["ids"], "worker": None, "verdict": None,
                                   "retried": False, "worktree": "/wt/attempt1"}])
    for i in ("r101", "r102"):
        state.transition(run_r2, i, "ready")
    state.apply_grouping(run_r2)
    g_r2 = run_r2["todos"]["r101"]["group"]
    state.decide(run_r2, "r101", "blocked", decision="Owner: drop it")
    got, err = expect(lambda: state.execute_args(run_r2, len(run_r2["waves"]) - 1, "/m"))
    check("PR #869: a retried member blocked after regrouping leaves its group, and blocks its dependent",
          err is None and got == [] and run_r2["todos"]["r102"]["reason"] == "dependency r101 blocked"
          and "group" not in run_r2["todos"]["r101"] and run_r2["groups"][g_r2]["ids"] == [],
          err or (got, run_r2["todos"]["r101"], run_r2["groups"][g_r2]))

    # PR #869 round 1: a retried group is appended after the run's last wave, so it must not hold a lane
    # that wave holds (both e2e here), or two PRs hold one lane at once.
    run_e2 = ready_run([("e101", ["e101.py"]), ("e102", ["e102.py"])], workers=1)
    for i in ("e101", "e102"):
        run_e2["todos"][i]["triage"]["needs_e2e"] = True
    state.apply_grouping(run_e2)
    be = state.execute_args(run_e2, 0, "/m")[0]
    state.ingest_execute(run_e2, [{"group": be["group"], "ids": ["e101"], "worker": None, "verdict": None,
                                   "retried": False}])
    state.transition(run_e2, "e101", "ready")
    state.apply_grouping(run_e2)
    wave_e = {i: next(w for w, gids in enumerate(run_e2["waves"]) if run_e2["todos"][i]["group"] in gids)
              for i in ("e101", "e102")}
    check("PR #869: a regrouped todo is placed 2+ waves after the last wave's holder of its lane",
          wave_e["e101"] - wave_e["e102"] >= 2, (wave_e, run_e2["waves"]))

    # PR #869 round 1: a group holding a lane the previous, unmerged wave still holds is refused, not
    # briefed with that lane quietly dropped from lanes_forbidden.
    run_l, gl1 = lane_run()
    g_l2 = run_l["todos"]["l2"]["group"]
    run_l["groups"][g_l2]["lanes"] = ["settings"]
    check("PR #869: execute_args refuses a group holding a lane the previous wave still holds",
          raises(lambda: state.execute_args(run_l, 1, "/m")) and run_l["todos"]["l2"]["stage"] == "ready")

    # Todo 468: ingest_review takes a round only when it follows the group's review_round, so a stale
    # round-1 output re-ingested later cannot overwrite tree_id and verified_ac.
    run_g = ready_run([("rg", ["rg.py"])], workers=1)
    state.apply_grouping(run_g)
    bg = state.execute_args(run_g, 0, "/m")[0]
    state.ingest_execute(run_g, [{"group": bg["group"], "ids": ["rg"], "worker": worker(["rg"]),
                                  "verdict": verdict(["rg"]), "retried": False}])
    state.set_group(run_g, bg["group"], "pr_open", pr=7)
    clean = {"group": bg["group"], "ids": ["rg"], "findings": [], "blocking": [], "reviewers_ok": True,
             "repair": None, "verdict": None}
    check("468: a round-2 output before round 1 is refused", raises(lambda: state.ingest_review(run_g, [clean], 2)))
    state.ingest_review(run_g, [clean], 1)
    stale = dict(clean, blocking=[{"severity": "high", "file": "a.py", "line": 1, "summary": "old", "suggested_fix": ""}],
                 repair=worker(["rg"], tree="TSTALE"), verdict=verdict(["rg"], before="TSTALE", after="TSTALE"))
    check("468: a round-1 output re-ingested after round 1 is refused, and tree_id is untouched",
          raises(lambda: state.ingest_review(run_g, [stale], 1)) and run_g["todos"]["rg"]["tree_id"] == "T1",
          run_g["todos"]["rg"])
    state.ingest_review(run_g, [clean], 2)
    check("468: a round-2 output for a reviewed group is refused",
          run_g["todos"]["rg"]["stage"] == "reviewed" and raises(lambda: state.ingest_review(run_g, [clean], 2)))

    # Todo 468: the review-doc lane reaches the plan from the run file, and the brief names the doc.
    doc = "docs/reviews/2026-05-07-1641-full-review.md"
    todos_rv = [{"id": i, "path": f"todos/{i}-pending-p3-x.md", "priority": "p3", "source_review": doc}
                for i in ("rv1", "rv2")]
    run_rv = state.new_run("r", "sweep", 3, todos_rv, ["rv1", "rv2"])
    state.record_triage(run_rv, [rec("rv1", ["rv1.py"]), rec("rv2", ["rv2.py"])])
    state.accept_ready(run_rv)
    state.apply_grouping(run_rv)
    waves_rv = {i: next(w for w, gids in enumerate(run_rv["waves"]) if run_rv["todos"][i]["group"] in gids)
                for i in ("rv1", "rv2")}
    brv = state.execute_args(run_rv, 0, "/m")
    check("468: two todos from one review doc are planned two waves apart, and the brief names the doc",
          abs(waves_rv["rv1"] - waves_rv["rv2"]) >= 2 and any(doc in lane for lane in brv[0]["lanes_held"]),
          (run_rv["waves"], brv))

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


def expect(fn):
    """Call fn(), returning (result, None) on success or (None, exc) on any
    exception -- S4: a check that expects fn() to SUCCEED must still print a
    clean FAIL when a regression makes it raise, instead of aborting the
    whole suite with an uncaught traceback."""
    try:
        return fn(), None
    except Exception as exc:  # noqa: BLE001 -- deliberately broad, see docstring
        return None, exc


if __name__ == "__main__":
    sys.exit(main())
