#!/usr/bin/env python3
"""Tests for scripts/todos/scan.py.

Run: python3 scripts/todos/test_scan.py (also run by harness-ci.yml).

Scan decides what the sweep can see. The old sweep grepped `^status: pending`
and 8 in_progress todos became invisible (2026-09-13). These tests pin the
blind spots: every open status, duplicate ids, ids buried in longer numbers,
merged multi-slice branches, and the retriage rule.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scan  # noqa: E402

FAILURES = []


def check(label, condition, detail=""):
    print(f"  {'PASS' if condition else 'FAIL'}  {label}{'' if condition else f'  -- {detail}'}")
    if not condition:
        FAILURES.append(label)


def write(root, name, status, issue_id, priority="p3", extra=""):
    (Path(root) / name).write_text(
        f'---\nstatus: {status}\npriority: {priority}\nissue_id: "{issue_id}"\n'
        f"tags: [web]\ndependencies: []\n{extra}---\n\n# Title {issue_id}\n"
    )


def ids(todos):
    return [t["id"] for t in todos]


def main():
    with tempfile.TemporaryDirectory() as tmp:
        write(tmp, "412-pending-p3-a.md", "pending", "412")
        write(tmp, "413-in_progress-p3-b.md", "in_progress", "413")
        write(tmp, "387-blocked-p3-c.md", "blocked", "387")
        write(tmp, "414-ready-p2-d.md", "ready", "414", priority="p2")
        write(tmp, "415-completed-p3-e.md", "completed", "415")
        (Path(tmp) / "README.md").write_text("---\nstatus: pending | in_progress\n---\n# idx\n")
        (Path(tmp) / "TEMPLATE.md").write_text("---\nstatus: pending\n---\n# t\n")
        (Path(tmp) / "old-prose.md").write_text("# no frontmatter\n")
        todos = scan.load_todos(tmp)
        check("every open status is loaded, terminal and index files are not",
              sorted(ids(todos)) == ["387", "412", "413", "414"], ids(todos))
        check("the open statuses match the archive checker's", scan.OPEN_STATUSES == {"pending", "ready",
                                                                                     "in_progress", "blocked"})
        check("title comes from the H1", next(t for t in todos if t["id"] == "412")["title"] == "Title 412")

        selected, excluded = scan.select(todos, selector="sweep", inflight=set())
        check("sorted by priority then id", ids(selected) == ["414", "387", "412", "413"], ids(selected))
        check("in_progress is selected and flagged stranded",
              next(t for t in selected if t["id"] == "413")["stranded"])
        check("legacy status: blocked without a triage field is still selected", "387" in ids(selected))

        selected, excluded = scan.select(todos, selector="sweep", inflight={"412"})
        check("an in-flight todo is excluded with a reason",
              "412" not in ids(selected) and excluded[0][0] == "412" and "in flight" in excluded[0][1])

        # Review focus 2: duplicate ids.
        write(tmp, "430-pending-p4-f.md", "pending", "430", priority="p4")
        write(tmp, "430-pending-p4-g.md", "pending", "430", priority="p4")
        selected, excluded = scan.select(scan.load_todos(tmp), selector="sweep", inflight=set())
        check("duplicate issue_id excludes both",
              "430" not in ids(selected) and any(i == "430" and "duplicate" in r for i, r in excluded), excluded)

        write(tmp, "416-pending-p3-h.md", "pending", "416",
              extra='triage: blocked-owner\nblocked_on: "vendor"\ntriaged: 2026-09-20\n')
        todos = scan.load_todos(tmp)
        _, excluded = scan.select(todos, selector="sweep", inflight=set(), changed_since=lambda p, d: False)
        check("a blocked triage is skipped with its reason", ("416", "blocked-owner: vendor") in excluded, excluded)
        selected, _ = scan.select(todos, selector="sweep", inflight=set(), changed_since=lambda p, d: True)
        check("a blocked todo edited after triage comes back", "416" in ids(selected))
        selected, _ = scan.select(todos, selector="sweep", inflight=set(), retriage=True,
                                  changed_since=lambda p, d: False)
        check("--retriage brings it back", "416" in ids(selected))

        selected, _ = scan.select(todos, selector="batch", inflight=set(), priority="p2")
        check("--priority filters", ids(selected) == ["414"])
        selected, _ = scan.select(todos, selector="batch", inflight=set(), ids={"412", "413"}, exclude_ids={"413"})
        check("--ids and --exclude-ids combine", ids(selected) == ["412"])
        selected, _ = scan.select(todos, selector="batch", inflight=set(), tag="nope")
        check("--tag filters on the tags list", selected == [])

        write(tmp, "417-pending-p1-i.md", "pending", "417", priority="p1")
        (Path(tmp) / "417-pending-p1-i.md").write_text(
            (Path(tmp) / "417-pending-p1-i.md").read_text().replace("dependencies: []", 'dependencies: ["412"]'))
        selected, _ = scan.select(scan.load_todos(tmp), selector="next", inflight=set())
        check("next picks the top todo whose dependencies are done, skipping stranded",
              ids(selected) == ["414"], ids(selected))

    # Review focus 3: ids and branch state.
    check("ids_in finds three-digit ids", scan.ids_in(["feat/412-onboarding"]) == {"412"})
    check("ids_in ignores longer numbers", scan.ids_in(["fix/1234-x", "pr-4120"]) == {"1234", "4120"})
    inflight, cleanup = scan.inflight_from(
        worktree_branches=["feat/447-slice-c", "fix/364-mailers"],
        local_branches=["feat/447-slice-c", "fix/364-mailers", "docs/kimi-plan"],
        open_heads=["feat/385-mobile-blog"],
        merged_heads={"feat/447-slice-c"},
    )
    check("merged heads are not in flight", inflight == {"364", "385"}, inflight)
    check("worktrees on merged branches are cleanup candidates", cleanup == ["feat/447-slice-c"], cleanup)
    inflight, cleanup = scan.inflight_from(["feat/385-mobile-blog"], [], ["feat/385-mobile-blog"],
                                           {"feat/385-mobile-blog"})
    check("a branch with an open PR stays in flight even if it merged before",
          inflight == {"385"} and cleanup == [], (inflight, cleanup))

    # Scan must read origin/main, not a stale working tree.
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        (repo / "todos").mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        write(repo / "todos", "412-pending-p3-a.md", "pending", "412")
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t",
                        "commit", "-q", "-m", "x"], check=True)
        (repo / "todos" / "412-pending-p3-a.md").unlink()
        write(repo / "todos", "999-pending-p3-local.md", "pending", "999")
        at_ref = scan.load_todos("todos", ref="HEAD", repo=repo)
        check("with a ref, scan reads the committed tree, not the working tree",
              ids(at_ref) == ["412"] and at_ref[0]["path"] == "todos/412-pending-p3-a.md", at_ref)
        check("the committed todo's title comes from git", at_ref[0]["title"] == "Title 412")

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} check(s): {', '.join(FAILURES)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
