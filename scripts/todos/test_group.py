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

    try:
        group.plan([t("1", ["a.py"], deps=["2"]), t("2", ["b.py"], deps=["1"])], open_ids={"1", "2"}, workers=3)
        raised = ""
    except group.CycleError as exc:
        raised = str(exc)
    check("a dependency cycle aborts and names its todos", "1" in raised and "2" in raised, raised)

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
