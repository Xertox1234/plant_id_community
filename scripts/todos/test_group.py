#!/usr/bin/env python3
"""Tests for scripts/todos/group.py.

Run: python3 scripts/todos/test_group.py (also run by harness-ci.yml).

Grouping decides which work can run at once. The failures worth pinning: two
todos editing one file in parallel PRs, two in-flight PRs holding settings.py,
a dependent todo starting before its dependency merged, and a cycle that
quietly drops todos.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import group  # noqa: E402

FAILURES = []


def check(label, condition, detail=""):
    print(f"  {'PASS' if condition else 'FAIL'}  {label}{'' if condition else f'  -- {detail}'}")
    if not condition:
        FAILURES.append(label)


def t(id_, files, size="s", priority="p3", deps=(), e2e=False, verify_only=False):
    return {"id": id_, "priority": priority, "dependencies": list(deps), "verify_only": verify_only,
            "triage": {"predicted_files": list(files), "size": size, "needs_e2e": e2e}}


def wave_of(result, todo_id):
    gid = next(g for g, v in result["groups"].items() if todo_id in v["ids"])
    return next(n for n, wave in enumerate(result["waves"]) if gid in wave)


def main():
    check("settings.py is a lane", group.lanes_for(t("1", ["backend/plant_community_backend/settings.py"])["triage"])
          == {"settings"})
    check("a dependency manifest is the deps lane", group.lanes_for(t("1", ["web/package.json"])["triage"]) == {"deps"})
    check("needs_e2e is the e2e lane", group.lanes_for(t("1", [], e2e=True)["triage"]) == {"e2e"})

    groups = group.build_groups([t("1", ["a/x.py"]), t("2", ["a/x.py", "a/y.py"]), t("3", ["a/y.py"]),
                                 t("4", ["b/z.py"])])
    check("todos sharing a file (transitively) form one group", ["1", "2", "3"] in groups and ["4"] in groups, groups)

    groups = group.build_groups([t(str(i), [f"web/f{i}.ts"], size="xs") for i in range(1, 5)]
                                + [t("9", ["backend/q.py"], size="xs")])
    check("tiny todos in one module are bundled three at a time",
          ["1", "2", "3"] in groups and ["4"] in groups and ["9"] in groups, groups)
    groups = group.build_groups([t("1", ["web/a.ts"], size="xs", verify_only=True), t("2", ["web/a.ts"], size="xs")])
    check("verify-only todos are never bundled or merged", ["1"] in groups and ["2"] in groups, groups)

    result = group.plan([t("1", ["backend/plant_community_backend/settings.py"]),
                         t("2", ["backend/plant_community_backend/settings.py", "x.py"]),
                         t("3", ["a.py"]), t("4", ["b.py"])], open_ids=set(), workers=3)
    # 1 and 2 share settings.py -> one group; lanes then only matter across groups.
    check("a shared hot file merges its todos into one group",
          any(set(v["ids"]) == {"1", "2"} for v in result["groups"].values()), result["groups"])

    # A shared hot file already merges todos into one group, so lanes bite ACROSS groups:
    # two separate groups that both need e2e (or both change a dependency manifest).
    result = group.plan([t("1", ["p.py"], e2e=True), t("2", ["web/package.json"]),
                         t("3", ["q.py"], e2e=True, priority="p4"), t("4", ["backend/requirements.txt"], priority="p4")],
                        open_ids=set(), workers=3)
    check("two groups holding one lane never share a wave or adjacent waves",
          abs(wave_of(result, "1") - wave_of(result, "3")) >= 2
          and abs(wave_of(result, "2") - wave_of(result, "4")) >= 2, result["waves"])

    result = group.plan([t("1", ["a.py"]), t("2", ["b.py"], deps=["1"]), t("3", ["c.py"])],
                        open_ids={"1", "2", "3"}, workers=3)
    check("a dependent group waits two waves for its dependency to merge",
          wave_of(result, "2") - wave_of(result, "1") >= 2, result["waves"])
    check("an independent group fills the first wave", wave_of(result, "3") == 0, result["waves"])

    result = group.plan([t(str(i), [f"f{i}.py"]) for i in range(1, 6)], open_ids=set(), workers=2)
    check("waves never exceed the worker count", all(len(w) <= 2 for w in result["waves"]), result["waves"])
    check("every group is placed", sum(len(w) for w in result["waves"]) == len(result["groups"]))

    result = group.plan([t("1", ["a.py"], deps=["777"])], open_ids={"1", "777"}, workers=3)
    check("a dependency on an open todo outside the run is unschedulable",
          "1" in result["unschedulable"] and not result["waves"], result)
    result = group.plan([t("1", ["a.py"], deps=["777"]), t("2", ["b.py"], deps=["1"])],
                        open_ids={"1", "2", "777"}, workers=3)
    check("unschedulable propagates to dependents", set(result["unschedulable"]) == {"1", "2"}, result)
    result = group.plan([t("1", ["a.py"], deps=["100"])], open_ids={"1"}, workers=3)
    check("a dependency that is no longer open is satisfied", "1" not in result["unschedulable"])

    # Final review I4 (the reviewer's probe, a real edge today): xs 448 depends on 428, which
    # is open but in flight. Bundled with xs 450 and 451 (all under backend/), it used to
    # block both. Unschedulability is decided per todo before bundling.
    open_now = {"428", "448", "450", "451"}
    result = group.plan([t("448", ["backend/a.py"], size="xs", deps=["428"]), t("450", ["backend/b.py"], size="xs"),
                         t("451", ["backend/c.py"], size="xs")], open_ids=open_now, workers=3)
    check("I4: an unschedulable xs todo is blocked on its own", set(result["unschedulable"]) == {"448"}, result)
    check("I4: its would-be bundle-mates are still bundled and scheduled",
          [v["ids"] for v in result["groups"].values()] == [["450", "451"]]
          and sum(len(w) for w in result["waves"]) == 1, result)
    result = group.plan([t("448", ["backend/a.py"], size="xs", deps=["428"]), t("449", ["backend/d.py"], size="xs",
                                                                                deps=["448"]),
                         t("450", ["backend/b.py"], size="xs")], open_ids=open_now | {"449"}, workers=3)
    check("I4: a todo depending on an unschedulable one is held out of the bundle too",
          set(result["unschedulable"]) == {"448", "449"} and [v["ids"] for v in result["groups"].values()] == [["450"]],
          result)
    result = group.plan([t("448", ["backend/a.py"], deps=["428"]), t("452", ["backend/a.py"]),
                         t("453", ["web/x.ts"])], open_ids=open_now | {"452", "453"}, workers=3)
    check("I4: a todo sharing a real file with an unschedulable one is still blocked with it",
          set(result["unschedulable"]) == {"448", "452"} and [v["ids"] for v in result["groups"].values()] == [["453"]],
          result)

    # PR #861 B-2: xs bundling must not invent a cycle the todos do not have. 103 -> 104 -> 101 used
    # to bundle as [101, 102, 103] + [104], a group cycle, and CycleError stopped the whole plan.
    xs = [t("101", ["backend/p101.py"], size="xs"), t("102", ["backend/p102.py"], size="xs"),
          t("103", ["backend/p103.py"], size="xs", deps=["104"]), t("104", ["backend/p104.py"], size="xs", deps=["101"])]
    try:
        result, raised = group.plan(xs, open_ids={"101", "102", "103", "104"}, workers=3), ""
    except group.CycleError as exc:
        result, raised = None, str(exc)
    check("B-2: bundling an acyclic chain plans without a cycle", result is not None, raised)
    if result is not None:
        check("B-2: the plan keeps the dependency order (each dependency 2+ waves earlier)",
              wave_of(result, "104") - wave_of(result, "101") >= 2
              and wave_of(result, "103") - wave_of(result, "104") >= 2, result["waves"])
        check("B-2: linked xs todos are planned singly (102 is alone in its bucket)",
              all(len(v["ids"]) == 1 for v in result["groups"].values()) and not result["unschedulable"], result)
    xs_cycle = [t("111", ["backend/c111.py"], size="xs", deps=["112"]),
                t("112", ["backend/c112.py"], size="xs", deps=["111"]), t("113", ["backend/c113.py"], size="xs")]
    try:
        group.plan(xs_cycle, open_ids={"111", "112", "113"}, workers=3)
        raised = ""
    except group.CycleError as exc:
        raised = str(exc)
    check("B-2: a real cycle among xs todos still raises", "111" in raised and "112" in raised, raised)

    try:
        group.plan([t("1", ["a.py"], deps=["2"]), t("2", ["b.py"], deps=["1"])], open_ids={"1", "2"}, workers=3)
        raised = ""
    except group.CycleError as exc:
        raised = str(exc)
    check("a dependency cycle aborts and names its todos", "1" in raised and "2" in raised, raised)

    # Todo 468: todos that share a file are one group, so an acyclic chain through a third todo
    # (B -> C -> A, A and B sharing x.py) used to become a group cycle and stop the whole plan.
    shared = [t("121", ["x.py", "a.py"]), t("122", ["x.py", "b.py"], deps=["123"]), t("123", ["c.py"], deps=["121"]),
              t("124", ["d.py"])]
    try:
        result, raised = group.plan(shared, open_ids={"121", "122", "123", "124"}, workers=3), ""
    except group.CycleError as exc:
        result, raised = None, str(exc)
    check("468: shared-file todos with an acyclic chain through another todo plan without a cycle",
          result is not None, raised)
    if result is not None:
        check("468: the todos on the would-be group cycle become one group (one worker, one PR)",
              any(set(v["ids"]) == {"121", "122", "123"} for v in result["groups"].values())
              and any(v["ids"] == ["124"] for v in result["groups"].values()), result["groups"])
        check("468: the merged group has no dependency on itself", all(not v["deps"] for v in result["groups"].values()),
              result["groups"])

    # Todo 468: two todos converted from one review doc both tick its Finding Status and race the
    # -COMPLETED rename, so the doc is a lane: never the same wave, never neighbouring waves.
    doc = "docs/reviews/2026-05-07-1641-full-review.md"
    reviewed = [t("131", ["r1.py"]) | {"source_review": doc}, t("132", ["r2.py"]) | {"source_review": doc},
                t("133", ["r3.py"]) | {"source_review": "docs/reviews/other.md"}, t("134", ["r4.py"])]
    result = group.plan(reviewed, open_ids=set(), workers=3)
    check("468: two groups sourced from one review doc never share or neighbour a wave",
          abs(wave_of(result, "131") - wave_of(result, "132")) >= 2, result["waves"])
    check("468: a different review doc does not hold the lane", wave_of(result, "133") == 0, result["waves"])
    g131 = next(v for v in result["groups"].values() if "131" in v["ids"])
    check("468: the review-doc lane is named after the doc, and has a description for the brief",
          g131["lanes"] == [f"review:{doc}"] and doc in group.lane_doc(f"review:{doc}"), g131)

    # PR #869 round 1: most real source_review values are archived-todo paths or "PR #NNN", which
    # Land never touches; only a docs/reviews/*.md doc is a lane, or the backlog is serialized.
    shared_src = [t(str(140 + n), [f"s{n}.py"]) | {"source_review": "todos/archive/394-completed-p2-x.md"}
                  for n in range(3)] + [t("144", ["s4.py"]) | {"source_review": "PR #812"},
                                        t("145", ["s5.py"]) | {"source_review": "docs/reviews/../../x.md"}]
    result = group.plan(shared_src, open_ids=set(), workers=3)
    check("PR #869: a source_review outside docs/reviews/*.md is not a lane",
          all(not v["lanes"] for v in result["groups"].values()) and len(result["waves"][0]) == 3, result)

    again = group.plan([t("1", ["a.py"]), t("2", ["b.py"])], open_ids=set(), workers=3)
    check("planning is deterministic", again == group.plan([t("1", ["a.py"]), t("2", ["b.py"])],
                                                           open_ids=set(), workers=3))

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} check(s): {', '.join(FAILURES)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
