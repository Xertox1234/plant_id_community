#!/usr/bin/env python3
"""Stage 0 of the todo sweep: find every open todo and write the run file.

Selects on the frontmatter `status:` value -- every open status, never a grep
for `^status: pending`, which left 8 todos invisible at in_progress on
2026-09-13. It skips todos already in flight (a branch, worktree or open PR
names the id), todos triaged as blocked unless the file changed since, and
duplicate ids. It needs `gh`, so run it with network + TLS (spec §11).

    python3 scripts/todos/scan.py --selector sweep --run-id 2026-09-27-1830 [--dry-run]
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import check_archived_todo_status as chk  # noqa: E402
import state  # noqa: E402
import todofile  # noqa: E402

OPEN_STATUSES = {s for s, cls in chk.CLASS_OF_STATUS.items() if cls == "open"}
PRIORITIES = ["p1", "p2", "p3", "p4"]
# An id is a whole token: after the start, / - _ or "wt" (a worktree name), and before
# - _ / or the end, allowing one slice letter ("feat/410b-...").
ID_RE = re.compile(r"(?:^|(?<=[/_-])|(?<=wt))(\d{3,4})(?=[a-z]?(?:[-_/]|$))")
AGENT_BRANCH_PREFIX = "worktree-agent-"
MERGED_PR_LIMIT = 5000
MAX_WORKERS = 3  # six slots across two overlapping waves; Redis has 16 DBs


def _files(todos_dir, ref, repo):
    """(repo-relative path, text) for each top-level .md in todos_dir, at `ref` or on disk."""
    if ref is None:
        return [(str(p), p.read_text()) for p in sorted(Path(todos_dir).glob("*.md"))]
    run = lambda *a: subprocess.run(["git", "-C", str(repo), *a], capture_output=True,  # noqa: E731
                                    text=True, check=True).stdout
    names = [n for n in run("ls-tree", "--name-only", ref, f"{todos_dir}/").splitlines() if n.endswith(".md")]
    return [(name, run("show", f"{ref}:{name}")) for name in sorted(names)]


def load_todos(todos_dir, ref=None, repo="."):
    todos = []
    for rel, text in _files(todos_dir, ref, repo):
        path = Path(rel)
        if path.name in chk.SKIP_NAMES:
            continue
        data = todofile.parse_frontmatter(text)
        if not data or "status" not in data:
            continue
        status = str(data["status"]).strip().lower()
        if status not in OPEN_STATUSES:
            continue
        todos.append({
            "id": str(data.get("issue_id") or path.name.split("-", 1)[0]),
            "path": rel,
            "status": status,
            "priority": str(data.get("priority", "p4")),
            "title": todofile.title(text),
            "tags": [str(t) for t in data.get("tags") or []],
            "dependencies": [str(d) for d in data.get("dependencies") or []],
            "triage": str(data.get("triage") or ""),
            "triaged": str(data.get("triaged") or ""),
            "blocked_on": str(data.get("blocked_on") or ""),
        })
    return todos


def ids_in(names):
    """Todo ids named by branch names. Harness `worktree-agent-<hex>` branches are skipped
    (their hex holds digit runs: a367c0a10e427e588 read as 367, 427 and 588), and an id
    counts only as a whole delimited token (final review m3)."""
    return {found for name in names if not name.startswith(AGENT_BRANCH_PREFIX)
            for found in ID_RE.findall(name)}


def inflight_from(worktree_branches, local_branches, open_heads, merged_heads):
    """An open PR always counts; a local branch or worktree counts unless its PR merged."""
    open_set = set(open_heads)
    live = [b for b in [*worktree_branches, *local_branches] if b not in merged_heads or b in open_set]
    cleanup = sorted(b for b in set(worktree_branches) if b in merged_heads and b not in open_set)
    return ids_in(live) | ids_in(open_set), cleanup


def _rank(todo):
    return (PRIORITIES.index(todo["priority"]) if todo["priority"] in PRIORITIES else len(PRIORITIES), todo["id"])


def git_changed_since(path, triaged, ref="HEAD", repo="."):
    """True when the file changed after the commit that wrote its `triaged:` line.

    Commits are compared, not dates (final review I2): `triaged:` is the owner's
    local date, but GitHub squash-merges commit in +0000, so an evening triage
    merge at -0600 is dated the next day and read as "changed since". Only when
    no reachable commit ever wrote a `triaged:` line does the date comparison run.
    """
    if not triaged:
        return True

    def git(*args):
        return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True).stdout.strip()

    # --follow (N4): without it a later rename commit "adds" every line, triaged: included, and
    # becomes the stamp -- hiding an owner answer made in that same commit.
    stamp = git("log", "-1", "--follow", "--format=%H", "-G^triaged:", ref, "--", path)
    if stamp:
        return bool(git("rev-list", f"{stamp}..{ref}", "--", path))
    out = git("log", "-1", "--format=%cs", ref, "--", path)
    return bool(out) and out > triaged


def select(todos, *, selector, inflight, priority=None, ids=None, tag=None, exclude_ids=None,
           retriage=False, changed_since=git_changed_since):
    counts = {}
    for todo in todos:
        counts.setdefault(todo["id"], []).append(todo["path"])
    selected, excluded = [], []
    for todo in sorted(todos, key=_rank):
        if priority and todo["priority"] != priority:
            continue
        if ids and todo["id"] not in ids:
            continue
        if tag and tag not in todo["tags"]:
            continue
        if exclude_ids and todo["id"] in exclude_ids:
            continue
        if len(counts[todo["id"]]) > 1:
            reason = f"duplicate issue_id {todo['id']}: {', '.join(counts[todo['id']])}"
            if (todo["id"], reason) not in excluded:
                excluded.append((todo["id"], reason))
            continue
        if todo["id"] in inflight:
            excluded.append((todo["id"], "in flight: branch, worktree or open PR"))
            continue
        if (todo["triage"].startswith("blocked-") and not retriage
                and not changed_since(todo["path"], todo["triaged"])):
            excluded.append((todo["id"], f"{todo['triage']}: {todo['blocked_on'] or 'no reason recorded'}"))
            continue
        selected.append(dict(todo, stranded=todo["status"] == "in_progress"))
    if selector == "next":
        open_ids = {t["id"] for t in todos}
        selected = [t for t in selected if not t["stranded"] and not set(t["dependencies"]) & open_ids][:1]
    return selected, excluded


def _git_lines(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.splitlines()


def _gh_heads(state_name, limit):
    cmd = ["gh", "pr", "list", "--state", state_name, "--json", "headRefName", "--limit", str(limit)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        raise SystemExit("scan: gh is not installed or not on PATH.\n"
                         "Install gh (GitHub CLI) to use scan.py, or download it from "
                         "https://github.com/cli/cli.")
    if proc.returncode != 0:
        raise SystemExit(f"scan: `{' '.join(cmd)}` failed: {proc.stderr.strip()[:200]}\n"
                         "gh needs network + TLS: run with the sandbox off, or apply "
                         "sandbox.enableWeakerNetworkIsolation (spec §11).")
    return [pr["headRefName"] for pr in json.loads(proc.stdout or "[]")]


def gather_inflight():
    worktrees = [line.split("refs/heads/", 1)[1] for line in _git_lines("worktree", "list", "--porcelain")
                 if line.startswith("branch refs/heads/")]
    local = _git_lines("for-each-ref", "--format=%(refname:short)", "refs/heads")
    # The repo has ~860 PRs. A cap below the merged-PR count silently drops the oldest merged heads, and a
    # stale local branch whose PR merged long ago would then re-exclude its todo (final review m3).
    # 5000 is comfortably above today's count; `gh` paginates up to --limit itself.
    return inflight_from(worktrees, local, _gh_heads("open", 200), set(_gh_heads("merged", MERGED_PR_LIMIT)))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--selector", choices=["sweep", "batch", "next"], required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--todos-dir", default="todos")
    parser.add_argument("--ref", default="origin/main", help="read todos at this git ref (fetched first)")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--priority")
    parser.add_argument("--ids")
    parser.add_argument("--tag")
    parser.add_argument("--exclude-ids")
    parser.add_argument("--retriage", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if not 1 <= args.workers <= MAX_WORKERS:
        parser.error(f"--workers must be 1..{MAX_WORKERS} (two overlapping waves share six slots)")

    split = lambda s: {x.strip() for x in s.split(",") if x.strip()} if s else None  # noqa: E731
    if args.ref.startswith("origin/"):
        try:
            subprocess.run(["git", "fetch", "-q", "origin", args.ref.split("/", 1)[1]], check=True)
        except subprocess.CalledProcessError:
            raise SystemExit(f"scan: git fetch failed. scan needs network access to github.com.\n"
                             "Run with the sandbox disabled, or apply sandbox.enableWeakerNetworkIsolation (spec §11).")
    try:
        ref_sha = subprocess.run(["git", "rev-parse", "--short", args.ref], capture_output=True, text=True,
                                 check=True).stdout.strip()
    except subprocess.CalledProcessError:
        raise SystemExit(f"scan: git rev-parse failed for ref '{args.ref}'.\n"
                         "Check that the ref exists in your repository.")
    todos = load_todos(args.todos_dir, ref=args.ref)
    inflight, cleanup = gather_inflight()
    selected, excluded = select(todos, selector=args.selector, inflight=inflight, priority=args.priority,
                                ids=split(args.ids), tag=args.tag, exclude_ids=split(args.exclude_ids),
                                retriage=args.retriage,
                                changed_since=lambda p, d: git_changed_since(p, d, args.ref))

    print(f"Todo sweep plan -- run {args.run_id} (selector={args.selector}, workers={args.workers}, "
          f"todos at {args.ref} {ref_sha})")
    print(f"Selected ({len(selected)}):")
    for t in selected:
        flag = "  STRANDED" if t["stranded"] else ""
        print(f"  {t['id']} [{t['priority']}] {t['status']:<11} {t['title'][:60]}{flag}")
    print(f"Excluded ({len(excluded)}):")
    for todo_id, reason in excluded:
        print(f"  {todo_id}  {reason}")
    if cleanup:
        print("Cleanup candidates (worktrees on merged branches; remove only with owner OK):")
        for branch in cleanup:
            print(f"  {branch}")
    if args.dry_run:
        print("Dry run: no run file written.")
        return 0

    path = state.run_path(args.todos_dir, args.run_id)
    if path.exists():
        print(f"scan: {path} already exists; resume it with todo-resume", file=sys.stderr)
        return 2
    run = state.new_run(args.run_id, args.selector, args.workers, selected, {t["id"] for t in todos})
    run["ref_sha"] = ref_sha
    state.save(run, path)
    print(f"Run file: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
