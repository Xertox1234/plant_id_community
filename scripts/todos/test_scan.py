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
    # Final review m3: a harness agent branch's hex name is not a list of todo ids.
    check("ids_in skips worktree-agent-* branches", scan.ids_in(["worktree-agent-a367c0a10e427e588"]) == set(),
          scan.ids_in(["worktree-agent-a367c0a10e427e588"]))
    check("ids_in reads an id only as a whole token", scan.ids_in(["pr819", "x1234y", "feat/12345-x"]) == set(),
          scan.ids_in(["pr819", "x1234y", "feat/12345-x"]))
    check("ids_in keeps real branch shapes: <type>/<id>-, a slice letter, a mid-name id, wt<id>",
          scan.ids_in(["feat/412-a", "feat/410b-remove", "release/testflight-428-link-cards", "worktree-wt429"])
          == {"412", "410", "428", "429"})
    check("merged heads are fetched with a limit above the repo's PR count", getattr(scan, "MERGED_PR_LIMIT", 0) >= 5000)
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

    # Final review I2: "changed since triage" compares commits, not dates. GitHub squash-merges
    # commit in +0000, so a triage merged at 19:30 -0600 on 2026-09-27 is dated 2026-09-28.
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        (repo / "todos").mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        rel = "todos/412-pending-p3-a.md"

        def commit(message, date):
            env = dict(os.environ, GIT_COMMITTER_DATE=date, GIT_AUTHOR_DATE=date)
            subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
            subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t",
                            "commit", "-q", "-m", message], check=True, env=env)

        write(repo / "todos", "412-pending-p3-a.md", "pending", "412")
        commit("create", "2026-09-20T10:00:00 +0000")
        write(repo / "todos", "412-pending-p3-a.md", "pending", "412",
              extra="triage: blocked-owner\ntriaged: 2026-09-27\n")
        commit("triage (evening merge, 19:30 -0600)", "2026-09-28T01:30:00 +0000")
        check("I2: an evening triage merge dated the next day in UTC is not 'changed since triage'",
              scan.git_changed_since(rel, "2026-09-27", "HEAD", repo=repo) is False)
        (repo / "other.md").write_text("x\n")
        commit("unrelated", "2026-09-28T02:00:00 +0000")
        check("I2: a later commit to another file does not count",
              scan.git_changed_since(rel, "2026-09-27", "HEAD", repo=repo) is False)
        (repo / rel).write_text((repo / rel).read_text() + "\nOwner: unblocked, the key is rotated.\n")
        commit("owner edit, same local day", "2026-09-28T03:00:00 +0000")
        check("I2: an edit after the triage commit counts, even on the same day",
              scan.git_changed_since(rel, "2026-09-27", "HEAD", repo=repo) is True)
        write(repo / "todos", "413-pending-p3-b.md", "pending", "413")
        commit("no triaged line ever written", "2026-09-26T10:00:00 +0000")
        check("I2: with no commit writing a triaged: line, the date comparison is the fallback",
              scan.git_changed_since("todos/413-pending-p3-b.md", "2026-09-27", "HEAD", repo=repo) is False
              and scan.git_changed_since("todos/413-pending-p3-b.md", "2026-09-25", "HEAD", repo=repo) is True)

        # Re-review N4: a rename commit "adds" every line, so without --follow it became the stamp,
        # hiding an owner answer made in the same commit as the rename.
        write(repo / "todos", "414-pending-p3-c.md", "pending", "414",
              extra="triage: blocked-owner\ntriaged: 2026-09-27\n")
        commit("triage 414", "2026-09-27T18:00:00 +0000")
        subprocess.run(["git", "-C", str(repo), "mv", "todos/414-pending-p3-c.md", "todos/414-pending-p2-c.md"],
                       check=True)
        renamed = repo / "todos" / "414-pending-p2-c.md"
        renamed.write_text(renamed.read_text() + "\nOwner: the key is rotated; go ahead.\n")
        commit("owner: reprioritise to p2 and answer", "2026-09-28T03:00:00 +0000")
        check("N4: a rename plus an owner answer in one commit counts as changed since triage",
              scan.git_changed_since("todos/414-pending-p2-c.md", "2026-09-27", "HEAD", repo=repo) is True)

    # Error handling tests
    import unittest.mock as mock

    # Test _gh_heads raises SystemExit when gh is missing
    with mock.patch("subprocess.run") as mock_run:
        mock_run.side_effect = FileNotFoundError("gh not found")
        try:
            scan._gh_heads("open", 200)
            check("_gh_heads raises SystemExit when gh is missing", False)
        except SystemExit as e:
            check("_gh_heads raises SystemExit when gh is missing", "not installed or not on PATH" in str(e))

    # Test main() raises SystemExit when git fetch fails
    with mock.patch("subprocess.run") as mock_run:
        def run_side_effect(cmd, *args, **kwargs):
            if cmd[0:2] == ["git", "fetch"]:
                raise subprocess.CalledProcessError(1, cmd)
            if cmd[0:2] == ["git", "rev-parse"]:
                return mock.Mock(stdout="abc123\n", returncode=0)
            return mock.Mock(stdout="", returncode=0)
        mock_run.side_effect = run_side_effect
        try:
            scan.main(["--selector", "sweep", "--run-id", "test"])
            check("main() raises SystemExit when git fetch fails", False)
        except SystemExit as e:
            check("main() raises SystemExit when git fetch fails", "git fetch failed" in str(e) and "network access" in str(e))

    # Test main() raises SystemExit when git rev-parse fails
    with mock.patch("subprocess.run") as mock_run:
        def run_side_effect(cmd, *args, **kwargs):
            if cmd[0:2] == ["git", "rev-parse"]:
                raise subprocess.CalledProcessError(128, cmd)
            return mock.Mock(stdout="", returncode=0)
        mock_run.side_effect = run_side_effect
        try:
            scan.main(["--selector", "sweep", "--run-id", "test", "--ref", "origin/main"])
            check("main() raises SystemExit when git rev-parse fails", False)
        except SystemExit as e:
            check("main() raises SystemExit when git rev-parse fails", "rev-parse failed" in str(e))

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} check(s): {', '.join(FAILURES)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
