# Todo Sweep v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single-context `completing-todos` loop with a workflow-driven engine: deterministic scripts own state and file edits, four role-based agents do triage, implementation, verification and review, and the main session only lands PRs.

**Architecture:** Python scripts in `scripts/todos/` own every mechanical step (scan, group, run-file state, slot environment, archiving) and are unit-tested. Three named workflows in `.claude/workflows/` fan out the agents in `.claude/agents/`. A `PreToolUse` hook enforces "workers stage and stop". The skills become thin runbooks that call the scripts and workflows. Part A builds and tests everything. Task 14 is the pilot. Part B rewrites the skills, and **starts only after the pilot passes**.

**Tech Stack:** Python 3.12 stdlib + PyYAML (already used by `scripts/check_archived_todo_status.py`), bash + python3 hooks, Claude Code Workflow scripts (plain JS), Claude Code custom agents (Markdown + single-line frontmatter), git, gh.

**Spec:** `docs/superpowers/specs/2026-09-27-todo-sweep-multi-agent-design.md`. Read it before starting any task; this plan argues from it.

## Global Constraints

- Only `scripts/todos/state.py` code writes `todos/.sweep-run-<run_id>.json` (spec §4.1 boundaries).
- Scan reads todos **at `origin/main`** (after `git fetch`), never from the working tree. On 2026-09-27 the main checkout was 45 commits behind, and reading it would have re-selected five todos (385, 401, 412, 413, 429) that were already completed and archived on `origin/main`.
- Stage names (`staged`, `pr_open`, …) never go in a todo's `status:` (spec §6.4).
- Workflows never commit, push or call `gh`; `todo-worker` and `todo-verifier` are hook-limited to git `add mv rm diff status log show fetch write-tree rev-parse` (spec §4.1).
- Default workers: 3; hard maximum 3 (see the slot rule below).
- **Slot rule (refines spec §7.3):** slot = `(wave % 2) × workers + position`, slots 1–6, Redis DB `9 + slot` (10–15; dev uses 1 and 3). Two consecutive waves overlap (wave N in review while wave N+1 executes), so they need disjoint slots. Sixteen Redis DBs therefore cap workers at 3.
- Test DB per slot: `DATABASE_URL` database name `plant_community_w<slot>` → pytest creates `test_plant_community_w<slot>`.
- Single-lane resources: `backend/plant_community_backend/settings.py`, `.secrets.baseline`, `e2e`, `deps` (spec §7.2, §7.4).
- Review budget: two rounds per PR; round 2 never repairs; non-blocking findings become a follow-up todo (CLAUDE.md "Review loop budget").
- Blocking severity = `critical` or `high` (carried over from `completing-todos` Step 4).
- A kimi gate timeout is recorded as `kimi: skipped`, never as passed (spec §9).
- Test files follow the repo convention: plain `python3` scripts next to the code (`scripts/todos/test_<module>.py`) with the `check(label, condition, detail)` helper and a `main()` returning 0/1. This is not the `scripts/todos/tests/` path the spec names; the repo convention wins.
- Agent frontmatter is single-line `key: value` only (memory: reviewer fleet frontmatter).
- Commits from a sandboxed shell: use `/usr/bin/git`, not `rtk git` (rtk reports exit 0 when a pre-commit hook failed). If the kimi engine check reports a false `STALE` before Task 1 lands, re-run the commit with the sandbox disabled; never run `sync-kimi-engine.sh` to "fix" it.

## Review Focus

1. **A frontmatter value YAML would reinterpret** (`yes`, `412`, `null`, `a: b`, a newline) must come back as the same string. `yes` coming back as `True` would silently corrupt an owner's answer. Test: Task 3 `round-trips …`.
2. **Duplicate `issue_id`** (the repo has two todos with id 430 today): the run file is keyed by id, so scan must exclude both with a reason rather than let one overwrite the other. Test: Task 5 `duplicate issue_id excludes both`.
3. **A todo id buried in a longer number** (`fix/1234-x`, `pr-4120`) must not mark todo 412 as in flight. A *merged* branch for a multi-slice todo (447) must not either, but a branch whose earlier PR merged and that now has an open PR must. Test: Task 5 `ids_in ignores longer numbers`, `merged heads are not in flight` and `a branch with an open PR stays in flight`.
4. **A forbidden git call hidden in a compound or wrapped command** (`cd x && /usr/bin/git commit`, `rtk git push`, `bash -c "git push"`, `$(git reset --hard)`, a newline-separated second line) must be denied for workers, while a harmless mention (`grep -rn "git commit" docs`) is allowed. Test: Task 10 test cases.
5. **`ac.json` disagreeing with the todo's Acceptance Criteria** (a count mismatch, a box inside a fenced example, missing evidence) must stop `land.py` rather than flip the wrong boxes. Test: Task 9 `count mismatch refuses`, `fenced boxes are ignored`, `missing evidence is not flipped`.

---

## Part A — Engine, agents, workflows (no skill changes yet)

### Task 1: Kimi engine check without process substitution

The sandbox blocks `/dev/fd`, so `diff <(…) <(…)` fails and the check reports a false `STALE` (memory: `project_sandbox_devfd_false_stale_kimi`). This blocks every sandboxed commit, including the main session's Land commits.

**Files:**

- Modify: `scripts/check-kimi-engine.sh:16`

**Interfaces:**

- Consumes: nothing.
- Produces: same exit codes as today (0 match, 1 stale). The output lines are unchanged.

- [ ] **Step 1: Reproduce the false STALE in the sandbox**

Run (sandboxed, from the repo root): `bash scripts/check-kimi-engine.sh; echo "exit=$?"`
Expected: `STALE` and `exit=1` even though the engine is identical (memory records this).

- [ ] **Step 2: Replace the comparison with temp files**

Replace line 16 of `scripts/check-kimi-engine.sh`:

```bash
if diff <(tail -n +2 "$CANON") <(tail -n +2 "$VENDORED") >/dev/null 2>&1; then
```

with:

```bash
# Temp files, not `diff <(…) <(…)`: process substitution needs /dev/fd, which the
# Claude Code sandbox blocks, and that made this check report a false STALE for
# every sandboxed commit (memory: project_sandbox_devfd_false_stale_kimi).
CANON_BODY=$(mktemp) && VENDORED_BODY=$(mktemp) || exit 1
trap 'rm -f "$CANON_BODY" "$VENDORED_BODY"' EXIT
tail -n +2 "$CANON" > "$CANON_BODY"
tail -n +2 "$VENDORED" > "$VENDORED_BODY"
if cmp -s "$CANON_BODY" "$VENDORED_BODY"; then
```

- [ ] **Step 3: Verify in the sandbox and outside it**

Run sandboxed: `bash scripts/check-kimi-engine.sh; echo "exit=$?"` → Expected: `matches canonical`, `exit=0`.
Mutation check: `cp scripts/kimi-review "$TMPDIR/kr.bak" && echo '# drift' >> scripts/kimi-review && bash scripts/check-kimi-engine.sh; echo "exit=$?"; cp "$TMPDIR/kr.bak" scripts/kimi-review && bash scripts/check-kimi-engine.sh` → Expected: `STALE exit=1`, then `matches canonical`. Confirm with `git diff --stat scripts/kimi-review` → empty.

- [ ] **Step 4: Commit**

```bash
/usr/bin/git add scripts/check-kimi-engine.sh
/usr/bin/git commit -m "fix(harness): kimi engine check without process substitution" -m "The sandbox blocks /dev/fd, so diff <(…) reported a false STALE on every sandboxed commit." -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Expected: the kimi gate line reads `Passed` from a **sandboxed** shell.

---

### Task 2: Ignore rules and worktree includes

**Files:**

- Modify: `.gitignore` (append after line 221, `todos/.completing-todos-run-*.json`)
- Create: `.worktreeinclude`

**Interfaces:**

- Produces: `todos/.sweep-run-*.json` and `.sweep-evidence/` ignored everywhere; worker worktrees receive `backend/.env` and `web/.env`.

- [ ] **Step 1: Add the ignore rules**

Append directly after the line `todos/.completing-todos-run-*.json` in `.gitignore`:

```gitignore
# Todo sweep v2 (docs/superpowers/specs/2026-09-27-todo-sweep-multi-agent-design.md):
# per-run state, and per-group evidence inside worker worktrees.
todos/.sweep-run-*.json
todos/.sweep-run-*.tmp
.sweep-evidence/
```

- [ ] **Step 2: Create `.worktreeinclude`**

```gitignore
# Gitignored files Claude Code copies into every worktree it creates
# (https://code.claude.com/docs/en/worktrees). Only files that match AND are
# gitignored are copied. Toolchains (venv, node_modules) are deliberately NOT
# listed — too large; workers use the main checkout's (spec §7.4).
backend/.env
web/.env
```

- [ ] **Step 3: Verify**

Run: `git check-ignore -v todos/.sweep-run-x.json a/.sweep-evidence/g1/ac.json backend/.env web/.env`
Expected: four lines, each naming the matching `.gitignore` rule.

- [ ] **Step 4: Commit**

```bash
/usr/bin/git add .gitignore .worktreeinclude
/usr/bin/git commit -m "chore(todos): ignore sweep run state and evidence; copy env files into worktrees" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: `todofile.py` — minimal, byte-preserving todo edits

**Files:**

- Create: `scripts/todos/todofile.py`
- Test: `scripts/todos/test_todofile.py`

**Interfaces:**

- Consumes: `yaml` (PyYAML), `scripts/check_archived_todo_status.py` (`REPOINT_RE`, `FENCE_RE`).
- Produces:
  - `parse_frontmatter(text: str) -> dict | None`, `read_frontmatter(path) -> dict | None`
  - `set_fields(path, fields: dict[str, object]) -> None` (raises `ValueError` on a missing block or a multi-line value)
  - `render(value) -> str`
  - `title(text: str) -> str` (first `#` heading, or `""`)
  - `append_work_log(path, block: str) -> None` (inserts at the end of `## Work Log`, before the next `##` heading; creates the section if absent)
  - `ac_lines(text: str) -> list[tuple[int, bool, str]]` (line index, checked, line text) for checkbox lines under `## Acceptance Criteria`, outside fenced blocks
  - `is_repoint(line: str) -> bool`
  - `with_status(filename: str, status: str) -> str` (raises `ValueError` when the name has no status segment)

- [ ] **Step 1: Write the failing test**

Create `scripts/todos/test_todofile.py`:

```python
#!/usr/bin/env python3
"""Tests for scripts/todos/todofile.py.

Run: python3 scripts/todos/test_todofile.py (also run by harness-ci.yml).

The cases that matter are the silent corruptions: a value YAML reinterprets
(`yes` -> True), a multi-line value half-rewritten, a checkbox inside a fenced
example counted as a criterion, and a Work Log entry landing under Notes.
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import todofile as tf  # noqa: E402

FAILURES = []


def check(label, condition, detail=""):
    print(f"  {'PASS' if condition else 'FAIL'}  {label}{'' if condition else f'  -- {detail}'}")
    if not condition:
        FAILURES.append(label)


HEAD = '---\nstatus: pending\npriority: p3\nissue_id: "412"\ntags: [web, forum]\ndependencies: []\n---\n'
BODY = (
    "\n# Onboarding checklist\n\n## Acceptance Criteria\n\n- [ ] first\n- [x] second\n\n"
    "```markdown\n- [ ] example inside a fence\n```\n\n"
    "- [ ] third -> todo 283 (re-pointed 2026-07-26)\n\n"
    "## Work Log\n\n### 2026-09-01 - Created\n\n- filed.\n\n## Notes\n\nnote text\n"
)


def write(tmp, text, name="412-pending-p3-x.md"):
    path = Path(tmp) / name
    path.write_text(text)
    return path


def main():
    with tempfile.TemporaryDirectory() as tmp:
        p = write(tmp, HEAD + BODY)
        data = tf.read_frontmatter(p)
        check("reads scalars and flow lists", data["issue_id"] == "412" and data["tags"] == ["web", "forum"], data)

        tf.set_fields(p, {"triage": "blocked-owner", "triaged": "2026-09-27"})
        text = p.read_text()
        check("appends new keys inside the block",
              "dependencies: []\ntriage: blocked-owner\ntriaged: 2026-09-27\n---\n" in text, text[:200])
        check("keeps the body byte for byte", text.endswith(BODY), text[-80:])

        tf.set_fields(p, {"triage": "ready"})
        check("replaces an existing key in place",
              tf.read_frontmatter(p)["triage"] == "ready" and p.read_text().count("\ntriage:") == 1)
        check("'triage' does not match the 'triaged' line", "triaged: 2026-09-27" in p.read_text())

        # Review focus 1: every value comes back as the same string.
        for value in ["yes", "412", "null", "a: b", 'say "hi"', "line1\nline2", ""]:
            tf.set_fields(p, {"owner_decision": value})
            got = tf.read_frontmatter(p)["owner_decision"]
            check(f"round-trips {value!r} as a string", got == value, repr(got))

        multi = write(tmp, "---\nstatus: pending\nblocked_on:\n  - a\n  - b\n---\n# t\n", "413-pending-p3-y.md")
        before = multi.read_text()
        try:
            tf.set_fields(multi, {"blocked_on": "x"})
            raised = False
        except ValueError:
            raised = True
        check("refuses a multi-line value and leaves the file alone", raised and multi.read_text() == before)

        check("no frontmatter reads as None", tf.read_frontmatter(write(tmp, "# prose\n", "old.md")) is None)
        comment = write(tmp, "---\nstatus: in_progress  # Change from pending\n---\n# t\n", "414-in_progress-p3-z.md")
        check("a YAML comment is not part of the value", tf.read_frontmatter(comment)["status"] == "in_progress")

        check("title is the first H1", tf.title(p.read_text()) == "Onboarding checklist")

        boxes = tf.ac_lines(p.read_text())
        check("ac_lines skips fenced examples", len(boxes) == 3, boxes)
        check("ac_lines reports checked state", [b[1] for b in boxes] == [False, True, False], boxes)
        check("is_repoint accepts the arrow convention", tf.is_repoint(boxes[2][2]))
        check("is_repoint rejects plain prose", not tf.is_repoint("- [ ] see todo notes"))

        tf.append_work_log(p, "### 2026-09-27 - Verified\n\n- ok.\n")
        text = p.read_text()
        check("work log entry lands before ## Notes",
              text.index("### 2026-09-27 - Verified") < text.index("## Notes")
              and text.index("### 2026-09-01 - Created") < text.index("### 2026-09-27 - Verified"), text)
        nolog = write(tmp, "---\nstatus: pending\n---\n# t\n", "415-pending-p3-w.md")
        tf.append_work_log(nolog, "### d - e\n")
        check("a missing Work Log section is created", nolog.read_text().endswith("## Work Log\n\n### d - e\n"))

        check("with_status swaps the status segment",
              tf.with_status("412-pending-p3-onboarding.md", "completed") == "412-completed-p3-onboarding.md")
        check("with_status keeps a date prefix",
              tf.with_status("2025-11-01-003-in_progress-p1-x.md", "pending") == "2025-11-01-003-pending-p1-x.md")
        try:
            tf.with_status("README.md", "completed")
            raised = False
        except ValueError:
            raised = True
        check("with_status refuses a name without a status segment", raised)

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} check(s): {', '.join(FAILURES)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 scripts/todos/test_todofile.py`
Expected: `ModuleNotFoundError: No module named 'todofile'`.

- [ ] **Step 3: Write the implementation**

Create `scripts/todos/todofile.py`:

```python
#!/usr/bin/env python3
"""Read and minimally edit todo files without reformatting them.

Every writer here changes only the lines it owns, so a triage or archive diff
shows exactly the fields it wrote. Anything ambiguous (a multi-line value, a
filename with no status segment) raises instead of guessing.
"""

import json
import os
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from check_archived_todo_status import FENCE_RE, REPOINT_RE  # noqa: E402

FM_RE = re.compile(r"\A---\n(.*?\n)---\n", re.S)
# Written unquoted: lowercase words joined by - or _ (triage classes, statuses)
# and ISO dates. Everything else is JSON-quoted -- valid YAML -- so "yes", "412"
# or "a: b" read back as the same string instead of a bool, int or mapping.
BARE_RE = re.compile(r"[a-z]+(?:[-_][a-z]+)*|\d{4}-\d{2}-\d{2}")
YAML_WORDS = {"yes", "no", "on", "off", "true", "false", "null", "none", "y", "n"}
CHECKBOX_RE = re.compile(r"^\s*-\s\[( |x|X)\]")
FILENAME_RE = re.compile(r"^((?:\d{4}-\d{2}-\d{2}-)?\d+-)([a-z_]+)(-.+)$")


def parse_frontmatter(text):
    """Return the frontmatter mapping in `text`, or None when it has none."""
    match = FM_RE.match(text)
    if not match:
        return None
    data = yaml.safe_load(match.group(1))
    return data if isinstance(data, dict) else None


def read_frontmatter(path):
    return parse_frontmatter(Path(path).read_text())


def render(value):
    text = str(value)
    if BARE_RE.fullmatch(text) and text not in YAML_WORDS:
        return text
    return json.dumps(text, ensure_ascii=False)


def set_fields(path, fields):
    """Set top-level scalar keys in place, appending any that are missing."""
    path = Path(path)
    text = path.read_text()
    match = FM_RE.match(text)
    if not match:
        raise ValueError(f"{path}: no frontmatter block")
    lines = match.group(1).splitlines(keepends=True)
    for key, value in fields.items():
        new_line = f"{key}: {render(value)}\n"
        for i, line in enumerate(lines):
            if line.startswith(f"{key}:"):
                following = lines[i + 1] if i + 1 < len(lines) else ""
                if following[:1] in (" ", "\t", "-"):
                    raise ValueError(f"{path}: {key} has a multi-line value; edit it by hand")
                lines[i] = new_line
                break
        else:
            lines.append(new_line)
    path.write_text("---\n" + "".join(lines) + "---\n" + text[match.end():])


def title(text):
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def _section_bounds(lines, heading):
    """(start, end) line indexes of a `## heading` section body, or None."""
    start = None
    for i, line in enumerate(lines):
        if line.rstrip("\n") == f"## {heading}":
            start = i + 1
        elif start is not None and line.startswith("## "):
            return start, i
    return (start, len(lines)) if start is not None else None


def append_work_log(path, block):
    """Append a Work Log entry at the end of that section (before ## Notes)."""
    path = Path(path)
    lines = path.read_text().splitlines(keepends=True)
    bounds = _section_bounds(lines, "Work Log")
    entry = block if block.endswith("\n") else block + "\n"
    if bounds is None:
        text = "".join(lines).rstrip("\n") + "\n\n## Work Log\n\n" + entry
    else:
        _, end = bounds
        head = "".join(lines[:end]).rstrip("\n") + "\n\n" + entry
        tail = "".join(lines[end:])
        text = head + ("\n" + tail if tail else "")
    path.write_text(text)


def ac_lines(text):
    """Checkbox lines under ## Acceptance Criteria, skipping fenced examples."""
    lines = text.splitlines()
    bounds = _section_bounds([line + "\n" for line in lines], "Acceptance Criteria")
    if bounds is None:
        return []
    found, in_fence = [], False
    for i in range(*bounds):
        line = lines[i]
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        match = None if in_fence else CHECKBOX_RE.match(line)
        if match:
            found.append((i, match.group(1) != " ", line))
    return found


def is_repoint(line):
    return bool(REPOINT_RE.search(line))


def with_status(filename, status):
    match = FILENAME_RE.match(filename)
    if not match:
        raise ValueError(f"{filename}: no status segment to replace")
    return f"{match.group(1)}{status}{match.group(3)}"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 scripts/todos/test_todofile.py`
Expected: every line `PASS`, then `All checks passed.`

- [ ] **Step 5: Commit**

```bash
/usr/bin/git add scripts/todos/todofile.py scripts/todos/test_todofile.py
/usr/bin/git commit -m "feat(todos): todofile helpers for byte-preserving todo edits" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: `state.py` core — run file, transitions, triage flow

**Files:**

- Create: `scripts/todos/state.py`
- Test: `scripts/todos/test_state.py`

**Interfaces:**

- Consumes: `todofile.set_fields`, `todofile.append_work_log`, `todofile.with_status` (Task 3).
- Produces (used by Tasks 5, 7, 15–17):
  - `TERMINAL: set[str]`, `ALLOWED: dict[str, set[str]]`, `MAX_RETRIES = 1`, `class TransitionError(Exception)`
  - `run_path(todos_dir, run_id) -> Path`
  - `new_run(run_id: str, selector: str, workers: int, todos: list[dict], open_ids) -> dict`. Each todo dict needs `id`, `path`, `priority`, and optionally `dependencies`, `stranded`.
  - `load(path) -> dict`, `save(run, path) -> None` (atomic)
  - `transition(run, todo_id, to, **fields) -> None`
  - `summary(run) -> dict[str, list[str]]`, `is_complete(run) -> bool`
  - `records_from_output(path, key: str) -> list`
  - `triage_args(run) -> list[{"id", "path"}]`
  - `record_triage(run, records: list[dict]) -> list[str]` (ids still `scanned`)
  - `accept_ready(run) -> list[str]`
  - `questions(run) -> list[dict]`
  - `decide(run, todo_id, outcome, decision="", verify_only=False, reset_stranded=False) -> None`
  - `run_git(repo, *args) -> str`
  - `apply_triage(run, repo_root, today, git=run_git) -> list[str]`
  - CLI `python3 scripts/todos/state.py <cmd> RUNFILE …` with `show`, `set`, `triage-args`, `record-triage`, `accept-ready`, `questions`, `decide`, `apply-triage`, `finish`

- [ ] **Step 1: Write the failing test**

Create `scripts/todos/test_state.py`:

```python
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

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} check(s): {', '.join(FAILURES)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 scripts/todos/test_state.py`
Expected: `ModuleNotFoundError: No module named 'state'`.

- [ ] **Step 3: Write the implementation**

Create `scripts/todos/state.py`:

```python
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
    run = load(args.runfile)
    try:
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
    except (TransitionError, KeyError, ValueError, RuntimeError) as exc:
        print(f"state: {exc}", file=sys.stderr)
        return 2
    save(run, args.runfile)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 scripts/todos/test_state.py`
Expected: every line `PASS`, then `All checks passed.`

- [ ] **Step 5: Commit**

```bash
/usr/bin/git add scripts/todos/state.py scripts/todos/test_state.py
/usr/bin/git commit -m "feat(todos): sweep run file with an enforced stage table and triage flow" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: `scan.py` — Stage 0 discovery

**Files:**

- Create: `scripts/todos/scan.py`
- Test: `scripts/todos/test_scan.py`

**Interfaces:**

- Consumes: `state.new_run`, `state.run_path`, `state.save` (Task 4); `todofile.read_frontmatter`, `todofile.title` (Task 3); `check_archived_todo_status.CLASS_OF_STATUS`, `SKIP_NAMES`.
- Produces:
  - `OPEN_STATUSES: set[str]`
  - `load_todos(todos_dir, ref=None, repo=".") -> list[dict]`, each with keys `id, path, status, priority, title, tags, dependencies, triage, triaged, blocked_on`. With `ref`, files are read from git at that ref (`git ls-tree` + `git show`), not from the working tree.
  - `inflight_from(...)`: a branch with an **open** PR is always in flight, even when an earlier PR from the same branch merged.
  - `ids_in(names) -> set[str]`
  - `inflight_from(worktree_branches, local_branches, open_heads, merged_heads) -> tuple[set[str], list[str]]` (in-flight ids, cleanup branches)
  - `select(todos, *, selector, inflight, priority=None, ids=None, tag=None, exclude_ids=None, retriage=False, changed_since=...) -> tuple[list[dict], list[tuple[str, str]]]`
  - CLI: `python3 scripts/todos/scan.py --selector {sweep,batch,next} --run-id ID [--ref origin/main] [--workers N] [--priority pX] [--ids a,b] [--tag t] [--exclude-ids a,b] [--retriage] [--dry-run]`. It runs `git fetch origin main` first, and the run file records `ref_sha`.

- [ ] **Step 1: Write the failing test**

Create `scripts/todos/test_scan.py`:

```python
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
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 scripts/todos/test_scan.py`
Expected: `ModuleNotFoundError: No module named 'scan'`.

- [ ] **Step 3: Write the implementation**

Create `scripts/todos/scan.py`:

```python
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
ID_RE = re.compile(r"(?<!\d)(\d{3,4})(?!\d)")
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
    return {found for name in names for found in ID_RE.findall(name)}


def inflight_from(worktree_branches, local_branches, open_heads, merged_heads):
    """An open PR always counts; a local branch or worktree counts unless its PR merged."""
    open_set = set(open_heads)
    live = [b for b in [*worktree_branches, *local_branches] if b not in merged_heads or b in open_set]
    cleanup = sorted(b for b in set(worktree_branches) if b in merged_heads and b not in open_set)
    return ids_in(live) | ids_in(open_set), cleanup


def _rank(todo):
    return (PRIORITIES.index(todo["priority"]) if todo["priority"] in PRIORITIES else len(PRIORITIES), todo["id"])


def git_changed_since(path, triaged, ref="HEAD"):
    """True when the file has a commit (reachable from ref) dated after its triage date."""
    if not triaged:
        return True
    out = subprocess.run(["git", "log", "-1", "--format=%cs", ref, "--", path],
                         capture_output=True, text=True).stdout.strip()
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
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"scan: `{' '.join(cmd)}` failed: {proc.stderr.strip()[:200]}\n"
                         "gh needs network + TLS: run with the sandbox off, or apply "
                         "sandbox.enableWeakerNetworkIsolation (spec §11).")
    return [pr["headRefName"] for pr in json.loads(proc.stdout or "[]")]


def gather_inflight():
    worktrees = [line.split("refs/heads/", 1)[1] for line in _git_lines("worktree", "list", "--porcelain")
                 if line.startswith("branch refs/heads/")]
    local = _git_lines("for-each-ref", "--format=%(refname:short)", "refs/heads")
    return inflight_from(worktrees, local, _gh_heads("open", 200), set(_gh_heads("merged", 300)))


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
        subprocess.run(["git", "fetch", "-q", "origin", args.ref.split("/", 1)[1]], check=True)
    ref_sha = subprocess.run(["git", "rev-parse", "--short", args.ref], capture_output=True, text=True,
                             check=True).stdout.strip()
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 scripts/todos/test_scan.py`
Expected: every line `PASS`, then `All checks passed.`

- [ ] **Step 5: Smoke-test the CLI against the real backlog**

Run (sandbox off, because it calls `gh`): `python3 scripts/todos/scan.py --selector sweep --run-id smoke --dry-run`
Expected, as measured on 2026-09-27:

- the header names `origin/main` and its short sha;
- `387` (legacy `status: blocked`) is among Selected;
- todos whose PRs merged and archived them upstream (385, 401, 412, 413, 429) are **absent**, even if your checkout is behind;
- todos with an open PR (then: 394, 403, 410) are under Excluded as in flight;
- worktrees on merged branches are under Cleanup candidates;
- any duplicate `issue_id` is under Excluded (there may be none);
- `Dry run: no run file written.`

Confirm with `ls todos/ | grep -c '^\.sweep-run-'` → `0`.

- [ ] **Step 6: Commit**

```bash
/usr/bin/git add scripts/todos/scan.py scripts/todos/test_scan.py
/usr/bin/git commit -m "feat(todos): scan every open todo status, exclude in-flight and duplicate ids" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: `group.py` — groups, lanes, waves

**Files:**

- Create: `scripts/todos/group.py`
- Test: `scripts/todos/test_group.py`

**Interfaces:**

- Consumes: nothing from other tasks. Pure functions over triage records.
- Produces (used by Task 7):
  - `LANE_FILES: dict[str, str]`, `LANE_DOC: dict[str, str]`, `MAX_BUNDLE = 3`, `class CycleError(Exception)`
  - `lanes_for(record: dict) -> set[str]`
  - `build_groups(todos: list[dict]) -> list[list[str]]`. Each todo has `id`, `priority`, `triage` (TRIAGE record), `verify_only`.
  - `plan(todos: list[dict], open_ids: set[str], workers: int) -> dict` with `groups: {gid: {"ids", "lanes", "deps"}}`, `waves: list[list[gid]]` (a `[]` wave means "wait for the wave two back to merge"), and `unschedulable: {todo_id: reason}`. Each todo also carries `dependencies`.

- [ ] **Step 1: Write the failing test**

Create `scripts/todos/test_group.py`:

```python
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
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 scripts/todos/test_group.py`
Expected: `ModuleNotFoundError: No module named 'group'`.

- [ ] **Step 3: Write the implementation**

Create `scripts/todos/group.py`:

```python
#!/usr/bin/env python3
"""Deterministic grouping and wave planning for the todo sweep (spec §7).

Groups: todos whose predicted files overlap (transitively) become one group --
one worker, one PR. Tiny todos in the same top-level module are bundled, at
most MAX_BUNDLE per group. Verify-only todos always stand alone.

Waves: at most `workers` groups each. Two waves overlap in time (wave N is in
review/land while wave N+1 executes), so a lane held in wave N cannot be held
in wave N+1, and a group whose dependency is in wave N cannot start before
wave N+2 (its worktree is cut from origin/main, which has the dependency only
after it merges). An empty wave means "wait for the wave two back to merge".
"""

import re

PRIORITIES = ["p1", "p2", "p3", "p4"]
LANE_FILES = {
    "backend/plant_community_backend/settings.py": "settings",
    ".secrets.baseline": "secrets-baseline",
}
DEPS_RE = re.compile(r"(?:^|/)(?:requirements[^/]*\.txt|package(?:-lock)?\.json|pubspec\.(?:yaml|lock))$")
LANE_DOC = {
    "settings": "backend/plant_community_backend/settings.py",
    "secrets-baseline": ".secrets.baseline",
    "e2e": "Playwright, or anything served on :5174 / :8000",
    "deps": "dependency manifests (requirements*.txt, package*.json, pubspec.*) and their installed environments",
}
MAX_BUNDLE = 3


class CycleError(Exception):
    pass


def lanes_for(record):
    files = record.get("predicted_files", [])
    lanes = {LANE_FILES[f] for f in files if f in LANE_FILES}
    if record.get("needs_e2e"):
        lanes.add("e2e")
    if any(DEPS_RE.search(f) for f in files):
        lanes.add("deps")
    return lanes


def _rank(todo):
    p = todo["priority"]
    return (PRIORITIES.index(p) if p in PRIORITIES else len(PRIORITIES), todo["id"])


def build_groups(todos):
    todos = sorted(todos, key=_rank)
    parent = {t["id"]: t["id"] for t in todos}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    owner = {}
    for todo in todos:
        if todo.get("verify_only"):
            continue
        for path in todo["triage"]["predicted_files"]:
            if path in owner:
                parent[find(todo["id"])] = find(owner[path])
            else:
                owner[path] = todo["id"]

    components = {}
    for todo in todos:
        components.setdefault(find(todo["id"]), []).append(todo)

    groups, tiny = [], {}
    for members in components.values():
        only = members[0]
        if len(members) == 1 and only["triage"]["size"] == "xs" and not only.get("verify_only"):
            files = only["triage"]["predicted_files"]
            tiny.setdefault(files[0].split("/", 1)[0] if files else "misc", []).append(only)
        else:
            groups.append(members)
    for members in tiny.values():
        groups.extend(members[i:i + MAX_BUNDLE] for i in range(0, len(members), MAX_BUNDLE))

    groups = [sorted(g, key=_rank) for g in groups]
    groups.sort(key=lambda g: _rank(g[0]))
    return [[t["id"] for t in g] for g in groups]


def _find_cycle(deps):
    color, stack = {}, []

    def visit(node):
        color[node] = "grey"
        stack.append(node)
        for nxt in sorted(deps[node]):
            if color.get(nxt) == "grey":
                return stack[stack.index(nxt):] + [nxt]
            if nxt not in color:
                found = visit(nxt)
                if found:
                    return found
        stack.pop()
        color[node] = "black"
        return None

    for node in sorted(deps):
        if node not in color:
            found = visit(node)
            if found:
                return found
    return None


def plan(todos, open_ids, workers):
    by_id = {t["id"]: t for t in todos}
    grouped = build_groups(todos)
    gids = [f"g{n}" for n in range(1, len(grouped) + 1)]
    gid_of = {todo_id: gid for gid, ids in zip(gids, grouped) for todo_id in ids}
    lanes = {gid: sorted(set().union(*(lanes_for(by_id[i]["triage"]) for i in ids)))
             for gid, ids in zip(gids, grouped)}
    deps = {gid: set() for gid in gids}
    unschedulable = {}
    for gid, ids in zip(gids, grouped):
        for todo_id in ids:
            for dep in by_id[todo_id].get("dependencies", []):
                if dep in gid_of:
                    if gid_of[dep] != gid:
                        deps[gid].add(gid_of[dep])
                elif dep in open_ids:
                    unschedulable[todo_id] = f"depends on open todo {dep}, which is not ready in this run"

    cycle = _find_cycle(deps)
    if cycle:
        names = [" + ".join(ids) for gid in cycle for ids in [grouped[gids.index(gid)]]]
        raise CycleError("dependency cycle: " + " -> ".join(names))

    blocked_groups = {gid_of[i] for i in unschedulable}
    changed = True
    while changed:
        changed = False
        for gid in gids:
            if gid not in blocked_groups and deps[gid] & blocked_groups:
                blocked_groups.add(gid)
                changed = True
    for gid in blocked_groups:
        for todo_id in grouped[gids.index(gid)]:
            unschedulable.setdefault(todo_id, "depends on an unschedulable group")

    placed, waves = {}, []
    pending = [g for g in gids if g not in blocked_groups]
    empty_run = 0
    while pending:
        wave_no = len(waves)
        previous = set().union(*(lanes[g] for g in waves[-1])) if waves else set()
        chosen, used = [], set()
        for gid in pending:
            if len(chosen) == workers:
                break
            if any(placed.get(dep, wave_no) > wave_no - 2 for dep in deps[gid]):
                continue
            if set(lanes[gid]) & (used | previous):
                continue
            chosen.append(gid)
            used |= set(lanes[gid])
        empty_run = empty_run + 1 if not chosen else 0
        if empty_run > 2:
            raise RuntimeError(f"wave planning made no progress; pending={pending}")
        for gid in chosen:
            placed[gid] = wave_no
            pending.remove(gid)
        waves.append(chosen)

    return {
        "groups": {gid: {"ids": ids, "lanes": lanes[gid], "deps": sorted(deps[gid])}
                   for gid, ids in zip(gids, grouped) if gid not in blocked_groups},
        "waves": waves,
        "unschedulable": unschedulable,
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 scripts/todos/test_group.py`
Expected: every line `PASS`, then `All checks passed.`

- [ ] **Step 5: Commit**

```bash
/usr/bin/git add scripts/todos/group.py scripts/todos/test_group.py
/usr/bin/git commit -m "feat(todos): deterministic groups, single-lane resources and wave planning" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: `state.py` flow — group, execute, review, worktree liveness

**Files:**

- Modify: `scripts/todos/state.py` (add functions and CLI subcommands)
- Test: `scripts/todos/test_state_flow.py`

**Interfaces:**

- Consumes: `group.plan`, `group.LANE_DOC` (Task 6); `state.transition`, `run_git` (Task 4).
- Produces (used by the workflows in Task 12 and the skills in Tasks 15–17):
  - `apply_grouping(run) -> dict` stores `groups`, `waves`, `unschedulable`; unschedulable todos → `blocked`
  - `slot_for(wave: int, position: int, workers: int) -> int`
  - `execute_args(run, wave: int, main_root: str) -> list[dict]` (GroupBrief; marks `executing`)
  - `evaluate(worker: dict | None, verdict: dict | None) -> str | None`
  - `ingest_execute(run, results: list[dict]) -> dict[str, str]`
  - `review_args(run, round_no: int, wave: int) -> list[dict]`
  - `ingest_review(run, results: list[dict], round_no: int) -> dict[str, str]` (group → `clean` / `repair-staged` / `rerun` / `blocked`)
  - `set_group(run, gid, stage, **fields) -> None`, `annotate(run, gid, **fields) -> None` (no stage change)
  - `ensure_worktree(run, gid, scratch, git=run_git) -> str`
  - `apply_grouping` APPENDS groups and waves (group ids continue from the highest existing `gN`) and records each todo's current `group`. A retried todo is regrouped without erasing waves that already have PRs.
  - CLI subcommands: `group`, `execute-args`, `ingest-execute`, `review-args`, `ingest-review`, `set-group`, `annotate`, `ensure-worktree`

GroupBrief (JSON keys): `run_id, group, ids, todo_paths, owner_decisions, plan_needed, verify_only, in_scope_files, lanes_held, lanes_forbidden, slot, evidence_dir, main_root`.
Review item (JSON keys): `run_id, round, group, ids, worktree, branch, pr, size, slot, evidence_dir, main_root, test_edits`.

- [ ] **Step 1: Write the failing test**

Create `scripts/todos/test_state_flow.py`:

```python
#!/usr/bin/env python3
"""Tests for the execute/review half of scripts/todos/state.py.

Run: python3 scripts/todos/test_state_flow.py (also run by harness-ci.yml).

evaluate() is where "a different agent re-ran the evidence" becomes a rule
instead of a hope (spec §5.2): a verifier that passes while the staged tree
moved, or leaves the working tree dirty, must void the verdict.
"""

import os
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
    res = state.ingest_review(run, [{"group": g_ok, "ids": ids_ok, "findings": [], "blocking": [],
                                     "reviewers_ok": False, "repair": None, "verdict": None}], 1)
    check("an incomplete review asks for a rerun and changes nothing",
          res[g_ok] == "rerun" and run["todos"][ids_ok[0]].get("review_round", 0) == 0)
    blocking = [{"severity": "high", "file": "a.py", "line": 1, "summary": "bug", "suggested_fix": ""}]
    res = state.ingest_review(run, [{"group": g_ok, "ids": ids_ok, "findings": blocking, "blocking": blocking,
                                     "reviewers_ok": True, "repair": worker(ids_ok, tree="T5"),
                                     "verdict": verdict(ids_ok, before="T5", after="T5")}], 1)
    check("a verified round-1 repair is staged for the main session to commit", res[g_ok] == "repair-staged")
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
    for i in ids_ok:
        run["todos"][i]["branch"] = "worktree-g1"

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q",
                        "--allow-empty", "-m", "init"], check=True)
        subprocess.run(["git", "-C", str(repo), "branch", "worktree-g1"], check=True)
        for i in ids_ok:
            run["todos"][i]["worktree"] = str(Path(tmp) / "gone")
            run["todos"][i]["branch"] = "worktree-g1"
        path = state.ensure_worktree(run, g_ok, Path(tmp) / "scratch", git=lambda *a: state.run_git(repo, *a[1:]))
        check("a missing worktree is re-added from its branch", Path(path).is_dir() and path.endswith(g_ok), path)
        check("the run file points at the new worktree", run["todos"][ids_ok[0]]["worktree"] == path)
        check("an existing worktree is left alone", state.ensure_worktree(run, g_ok, Path(tmp) / "scratch") == path)

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
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 scripts/todos/test_state_flow.py`
Expected: `AttributeError: module 'state' has no attribute 'evaluate'`.

- [ ] **Step 3: Add the flow functions to `state.py`**

Add `import group  # noqa: E402` directly below `import todofile  # noqa: E402`. Insert the following block directly above `def _cmd_decide`:

```python
SIZE_RANK = {"xs": 0, "s": 1, "m": 2, "l": 3}


def apply_grouping(run):
    """Group the ready todos and APPEND their groups and waves.

    Appending (never replacing) is what lets a retried todo be regrouped
    without erasing the groups and waves that already have PRs.
    """
    todos = [
        {"id": i, "priority": e["priority"], "dependencies": e["dependencies"],
         "verify_only": e.get("verify_only", False), "triage": e["triage"]}
        for i, e in sorted(run["todos"].items()) if e["stage"] == "ready"
    ]
    result = group.plan(todos, set(run["open_ids"]), run["workers"])
    offset = max((int(g[1:]) for g in run["groups"]), default=0)
    rename = {gid: f"g{offset + int(gid[1:])}" for gid in result["groups"]}
    for todo_id, reason in result["unschedulable"].items():
        transition(run, todo_id, "blocked", reason=reason)
    for gid, spec in result["groups"].items():
        run["groups"][rename[gid]] = dict(spec, deps=[rename[d] for d in spec["deps"]])
        for todo_id in spec["ids"]:
            run["todos"][todo_id]["group"] = rename[gid]
    new_waves = [[rename[g] for g in wave] for wave in result["waves"]]
    run["waves"].extend(new_waves)
    run["unschedulable"].update(result["unschedulable"])
    return {"waves": new_waves, "unschedulable": result["unschedulable"]}


def slot_for(wave, position, workers):
    return (wave % 2) * workers + position


def _group_entries(run, gid):
    """The todos currently in group gid (a retried todo moves to a new group)."""
    return [(i, run["todos"][i]) for i in run["groups"][gid]["ids"] if run["todos"][i].get("group") == gid]


def execute_args(run, wave, main_root):
    if wave >= len(run["waves"]):
        raise ValueError(f"wave {wave} does not exist ({len(run['waves'])} waves)")
    if wave >= 1:
        for gid in run["waves"][wave - 1]:
            for todo_id, entry in _group_entries(run, gid):
                if entry["stage"] in {"ready", "executing"}:
                    raise TransitionError(f"wave {wave - 1} has not finished executing ({todo_id})")
    if wave >= 2:
        for gid in run["waves"][wave - 2]:
            for todo_id, entry in _group_entries(run, gid):
                if entry["stage"] not in TERMINAL | {"merged"}:
                    raise TransitionError(f"wave {wave - 2} is not merged yet ({todo_id} is {entry['stage']})")
    briefs, gids = [], run["waves"][wave]
    for position, gid in enumerate(gids, start=1):
        entries = _group_entries(run, gid)
        held = run["groups"][gid]["lanes"]
        forbidden = sorted({lane for other in gids if other != gid for lane in run["groups"][other]["lanes"]})
        slot = slot_for(wave, position, run["workers"])
        briefs.append({
            "run_id": run["run_id"],
            "group": gid,
            "ids": [i for i, _ in entries],
            "todo_paths": [e["path"] for _, e in entries],
            "owner_decisions": {i: e.get("owner_decision", "") for i, e in entries},
            "plan_needed": any(e["triage"]["class"] == "needs-research" for _, e in entries),
            "verify_only": all(e.get("verify_only") for _, e in entries),
            "in_scope_files": sorted({f for _, e in entries for f in e["triage"]["predicted_files"]}),
            "lanes_held": [group.LANE_DOC[lane] for lane in held],
            "lanes_forbidden": [group.LANE_DOC[lane] for lane in forbidden],
            "slot": slot,
            "evidence_dir": f".sweep-evidence/{gid}",
            "main_root": main_root,
        })
        for todo_id, _ in entries:
            transition(run, todo_id, "executing", group=gid, slot=slot, wave=wave, main_root=main_root)
    return briefs


def evaluate(worker, verdict):
    """None when the verdict can be trusted, else why not (spec §5.2)."""
    if verdict is None:
        return "no verdict"
    if verdict["verdict"] != "pass":
        return "verifier: fail"
    if len({worker["tree_id"], verdict["tree_id_before"], verdict["tree_id_after"]}) != 1:
        return "staged tree changed during verification"
    if not verdict["clean_after"]:
        return "working tree not clean after verification"
    if not all(item["verified"] for item in verdict["ac"]):
        return "verifier passed with an unverified criterion"
    return None


def ingest_execute(run, results):
    outcome = {}
    for result in results:
        worker, verdict = result.get("worker"), result.get("verdict")
        for todo_id in result["ids"]:
            if worker is None:
                transition(run, todo_id, "failed", reason="worker returned nothing")
            elif worker["status"] == "blocked":
                transition(run, todo_id, "blocked", reason=worker.get("blockers") or "worker blocked")
            elif worker["status"] != "staged":
                transition(run, todo_id, "failed", reason=f"worker status {worker['status']}: {worker.get('blockers', '')}")
            else:
                transition(run, todo_id, "staged", worktree=worker["worktree"], branch=worker["branch"],
                           tree_id=worker["tree_id"], ac_file=worker["ac_file"])
                problem = evaluate(worker, verdict)
                if problem:
                    transition(run, todo_id, "failed", reason=problem)
                else:
                    transition(run, todo_id, "verified", test_edits=verdict["test_edits_flagged"])
            outcome[todo_id] = run["todos"][todo_id]["stage"]
    return outcome


def set_group(run, gid, stage, **fields):
    for todo_id, _ in _group_entries(run, gid):
        transition(run, todo_id, stage, **fields)


def annotate(run, gid, **fields):
    """Record fields on every todo of a group without a stage change (e.g. a renamed branch)."""
    for _, entry in _group_entries(run, gid):
        entry.update(fields)


def review_args(run, round_no, wave):
    if round_no not in (1, 2):
        raise ValueError("round must be 1 or 2")
    items = []
    for gid in run["waves"][wave]:
        entries = _group_entries(run, gid)
        if not entries:
            continue
        first = entries[0][1]
        if first["stage"] != "pr_open" or first.get("review_round", 0) != round_no - 1:
            continue
        items.append({
            "run_id": run["run_id"], "round": round_no, "group": gid, "ids": [i for i, _ in entries],
            "worktree": first["worktree"], "branch": first["branch"], "pr": first["pr"],
            "size": max((e["triage"]["size"] for _, e in entries), key=SIZE_RANK.__getitem__),
            "slot": first["slot"], "evidence_dir": f".sweep-evidence/{gid}",
            "main_root": first.get("main_root", ""),
            "test_edits": sorted({t for _, e in entries for t in e.get("test_edits", [])}),
        })
    return items


def ingest_review(run, results, round_no):
    outcome = {}
    for result in results:
        gid = result["group"]
        entries = _group_entries(run, gid)
        follow = [f"{f['file']}:{f['line']} {f['summary']}" for f in result["findings"]
                  if f["severity"] not in {"critical", "high"}][:10]
        for _, entry in entries:
            entry.setdefault("followups", []).extend(follow)
            entry["checklist_skipped"] = bool(result.get("checklist_skipped"))
        if not result["reviewers_ok"]:
            outcome[gid] = "rerun"
            continue
        blocking = result["blocking"]
        if round_no == 1:
            if blocking:
                problem = evaluate(result["repair"], result["verdict"]) if result["repair"] else "no repair"
                if problem:
                    set_group(run, gid, "blocked", reason=f"round-1 repair failed: {problem}")
                    outcome[gid] = "blocked"
                    continue
                for _, entry in entries:
                    entry["tree_id"] = result["repair"]["tree_id"]
                outcome[gid] = "repair-staged"
            else:
                outcome[gid] = "clean"
            for _, entry in entries:
                entry["review_round"] = 1
        else:
            if blocking:
                set_group(run, gid, "blocked", reason=f"{len(blocking)} blocking findings after round 2")
                outcome[gid] = "blocked"
            else:
                set_group(run, gid, "reviewed", review_round=2)
                outcome[gid] = "clean"
    return outcome


def ensure_worktree(run, gid, scratch, git=run_git):
    entries = _group_entries(run, gid)
    current = entries[0][1].get("worktree", "")
    if current and Path(current).is_dir():
        return current
    target = Path(scratch) / gid
    target.parent.mkdir(parents=True, exist_ok=True)
    git(".", "worktree", "add", str(target), entries[0][1]["branch"])
    for _, entry in entries:
        entry["worktree"] = str(target)
    return str(target)
```

Then extend `build_parser()`, before `return parser`:

```python
    p = sub.add_parser("group")
    p.add_argument("runfile")
    p = sub.add_parser("execute-args")
    p.add_argument("runfile"), p.add_argument("--wave", type=int, required=True)
    p.add_argument("--main-root", required=True)
    p = sub.add_parser("ingest-execute")
    p.add_argument("runfile"), p.add_argument("--output", required=True)
    p = sub.add_parser("review-args")
    p.add_argument("runfile"), p.add_argument("--round", type=int, required=True)
    p.add_argument("--wave", type=int, required=True)
    p = sub.add_parser("ingest-review")
    p.add_argument("runfile"), p.add_argument("--output", required=True)
    p.add_argument("--round", type=int, required=True)
    p = sub.add_parser("set-group")
    p.add_argument("runfile"), p.add_argument("group"), p.add_argument("stage")
    p.add_argument("--field", action="append")
    p = sub.add_parser("ensure-worktree")
    p.add_argument("runfile"), p.add_argument("group"), p.add_argument("--scratch", required=True)
    p = sub.add_parser("annotate")
    p.add_argument("runfile"), p.add_argument("group"), p.add_argument("--field", action="append")
```

and extend `main()` inside the `try:` chain, before `except`:

```python
        elif args.cmd == "group":
            result = apply_grouping(run)
            print(json.dumps({"waves": result["waves"], "unschedulable": result["unschedulable"]}, indent=1))
        elif args.cmd == "execute-args":
            print(json.dumps({"run_id": run["run_id"], "briefs": execute_args(run, args.wave, args.main_root)}))
        elif args.cmd == "ingest-execute":
            print(json.dumps(ingest_execute(run, records_from_output(args.output, "results")), indent=1))
        elif args.cmd == "review-args":
            print(json.dumps({"round": args.round, "prs": review_args(run, args.round, args.wave)}))
        elif args.cmd == "ingest-review":
            print(json.dumps(ingest_review(run, records_from_output(args.output, "results"), args.round), indent=1))
        elif args.cmd == "set-group":
            set_group(run, args.group, args.stage, **_parse_fields(args.field))
        elif args.cmd == "ensure-worktree":
            print(ensure_worktree(run, args.group, args.scratch))
        elif args.cmd == "annotate":
            annotate(run, args.group, **_parse_fields(args.field))
```

Note that `execute-args` and `review-args` also `save()` the run file, because they transition todos to `executing`. That is intended: the arguments and the stage change are one step.

- [ ] **Step 4: Run both state test files**

Run: `python3 scripts/todos/test_state_flow.py && python3 scripts/todos/test_state.py`
Expected: both end with `All checks passed.`

- [ ] **Step 5: Commit**

```bash
/usr/bin/git add scripts/todos/state.py scripts/todos/test_state_flow.py
/usr/bin/git commit -m "feat(todos): execute/review flow with a tree-hash check on every verdict" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: `slot_env.py` — per-slot test resources

**Files:**

- Create: `scripts/todos/slot_env.py`
- Test: `scripts/todos/test_slot_env.py`

**Interfaces:**

- Produces:
  - `MAX_SLOT = 6`
  - `parse_dotenv(text) -> dict[str, str]`
  - `slot_env(environ: dict, dotenv_text: str, slot: int, worktree) -> dict` (raises `ValueError`)
  - CLI `python3 <worktree>/scripts/todos/slot_env.py <slot> -- <command> [args…]` (execs the command). Workers and verifiers call it from Tasks 11–12.

- [ ] **Step 1: Write the failing test**

Create `scripts/todos/test_slot_env.py`:

```python
#!/usr/bin/env python3
"""Tests for scripts/todos/slot_env.py.

Run: python3 scripts/todos/test_slot_env.py (also run by harness-ci.yml).

Two concurrent backend test runs sharing one database produce fake failures
(memory: project_reuse_db_wagtail_root_truncation). These pin that each slot
gets its own database and Redis DB, and that nothing leaks into .env.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import slot_env as se  # noqa: E402

FAILURES = []


def check(label, condition, detail=""):
    print(f"  {'PASS' if condition else 'FAIL'}  {label}{'' if condition else f'  -- {detail}'}")
    if not condition:
        FAILURES.append(label)


DOTENV = (
    "# comment\nSECRET_KEY=abc\nDATABASE_URL='postgresql://u:p@localhost:5432/plant_community?sslmode=disable'\n"
    "export REDIS_URL=redis://127.0.0.1:6379/1\n"
)


def main():
    parsed = se.parse_dotenv(DOTENV)
    check("parse_dotenv strips quotes and export", parsed["REDIS_URL"] == "redis://127.0.0.1:6379/1"
          and parsed["DATABASE_URL"].startswith("postgresql://"), parsed)

    env = se.slot_env({"PATH": "/bin"}, DOTENV, 2, "/wt/g1")
    check("slot 2 gets its own database",
          env["DATABASE_URL"] == "postgresql://u:p@localhost:5432/plant_community_w2?sslmode=disable", env)
    check("slot 2 gets Redis DB 11", env["REDIS_URL"] == "redis://127.0.0.1:6379/11")
    check("PYTHONPATH puts the worktree's wagtail_forum first",
          env["PYTHONPATH"] == "/wt/g1/backend/packages/wagtail_forum")
    check("other variables pass through", env["PATH"] == "/bin")
    check("SWEEP_SLOT is set", env["SWEEP_SLOT"] == "2")

    env = se.slot_env({"DATABASE_URL": "postgres://h/plant_community_w5", "PYTHONPATH": "/x"}, DOTENV, 3, "/wt")
    check("an environment DATABASE_URL wins and is re-slotted", env["DATABASE_URL"] == "postgres://h/plant_community_w3")
    check("an existing PYTHONPATH is kept after ours", env["PYTHONPATH"] == f"/wt/backend/packages/wagtail_forum{os.pathsep}/x")

    for bad in (0, 7):
        try:
            se.slot_env({}, DOTENV, bad, "/wt")
            raised = False
        except ValueError:
            raised = True
        check(f"slot {bad} is refused", raised)
    try:
        se.slot_env({}, "SECRET_KEY=x\n", 1, "/wt")
        raised = False
    except ValueError:
        raised = True
    check("no DATABASE_URL anywhere is refused, not defaulted", raised)
    check("Redis defaults to localhost when unset",
          se.slot_env({}, "DATABASE_URL=postgres://h/db\n", 1, "/wt")["REDIS_URL"] == "redis://127.0.0.1:6379/10")

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} check(s): {', '.join(FAILURES)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 scripts/todos/test_slot_env.py`
Expected: `ModuleNotFoundError: No module named 'slot_env'`.

- [ ] **Step 3: Write the implementation**

Create `scripts/todos/slot_env.py`:

```python
#!/usr/bin/env python3
"""Run a command with one todo-sweep worker slot's test resources.

    python3 <worktree>/scripts/todos/slot_env.py <slot> -- <command> [args...]

Slot N (1..6) gets its own Postgres database -- pytest then creates
test_plant_community_wN -- and Redis DB 9+N, so the six slots of two
overlapping waves never share test state (spec §7.3). Values are set in the
process environment only, never written to .env: python-decouple lets the
environment win over backend/.env, which the worktree has via
.worktreeinclude. PYTHONPATH puts this worktree's wagtail_forum ahead of the
main checkout's editable install, which otherwise gets collected twice.
"""

import os
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

MAX_SLOT = 6  # Redis DBs 10..15; dev uses 1 and 3
DEFAULT_REDIS = "redis://127.0.0.1:6379/1"


def parse_dotenv(text):
    values = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export "):].strip()
        values[key] = value.strip().strip("'\"")
    return values


def slot_env(environ, dotenv_text, slot, worktree):
    if not 1 <= slot <= MAX_SLOT:
        raise ValueError(f"slot must be 1..{MAX_SLOT}, got {slot}")
    dotenv = parse_dotenv(dotenv_text)
    db_url = environ.get("DATABASE_URL") or dotenv.get("DATABASE_URL")
    if not db_url:
        raise ValueError("no DATABASE_URL in the environment or backend/.env")
    redis_url = environ.get("REDIS_URL") or dotenv.get("REDIS_URL") or DEFAULT_REDIS
    env = dict(environ)
    env["DATABASE_URL"] = urlunsplit(urlsplit(db_url)._replace(path=f"/plant_community_w{slot}"))
    env["REDIS_URL"] = urlunsplit(urlsplit(redis_url)._replace(path=f"/{9 + slot}"))
    forum = str(Path(worktree) / "backend" / "packages" / "wagtail_forum")
    env["PYTHONPATH"] = forum + (os.pathsep + environ["PYTHONPATH"] if environ.get("PYTHONPATH") else "")
    env["SWEEP_SLOT"] = str(slot)
    return env


def main(argv):
    if len(argv) < 4 or argv[2] != "--" or not argv[1].isdigit():
        print(__doc__, file=sys.stderr)
        return 2
    worktree = Path(__file__).resolve().parents[2]
    dotenv = worktree / "backend" / ".env"
    try:
        env = slot_env(dict(os.environ), dotenv.read_text() if dotenv.is_file() else "", int(argv[1]), worktree)
    except ValueError as exc:
        print(f"slot_env: {exc}", file=sys.stderr)
        return 2
    os.execvpe(argv[3], argv[3:], env)
    return 127  # not reached


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

- [ ] **Step 4: Run the tests, then a live smoke test**

Run: `python3 scripts/todos/test_slot_env.py` → `All checks passed.`
Live: `python3 scripts/todos/slot_env.py 2 -- env | grep -E '^(DATABASE_URL|REDIS_URL|SWEEP_SLOT)=' | sed -E 's#//[^@]*@#//***@#'`
Expected: `DATABASE_URL=…/plant_community_w2`, `REDIS_URL=…/11`, `SWEEP_SLOT=2` (credentials masked by the `sed`).

- [ ] **Step 5: Commit**

```bash
/usr/bin/git add scripts/todos/slot_env.py scripts/todos/test_slot_env.py
/usr/bin/git commit -m "feat(todos): slot_env gives each sweep worker its own test DB and Redis DB" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: `land.py` — flip verified criteria and archive

**Files:**

- Create: `scripts/todos/land.py`
- Test: `scripts/todos/test_land.py`

**Interfaces:**

- Consumes: `todofile.*` (Task 3); `state.load` (Task 4) (read-only, so it can find `ac_file` and `verified_ac`).
- Produces:
  - `class LandError(Exception)`
  - `flip_acs(repo, todo_rel, ac_entries: list, verdict_ac: list, run_id, date) -> tuple[list[int], list[int]]` (flipped, still unchecked)
  - `archive(repo, todo_rel, run_id, date, git=run_git) -> dict` with keys `archived`, `paths` (to stage), `baseline_updated`, `review`
  - `fix_baseline(repo, old_rel, new_rel) -> bool`, `check_off_review(repo, todo_path, date, git=run_git) -> dict | None`
  - CLI: `land.py flip-acs --run RUNFILE --id NNN --repo WT --date D` and `land.py archive --run RUNFILE --id NNN --repo WT --date D` (both print JSON)

This task depends on Task 7 storing `verified_ac` on each todo entry. Add that now in `state.py` `ingest_execute`: change `transition(run, todo_id, "verified", test_edits=verdict["test_edits_flagged"])` to `transition(run, todo_id, "verified", test_edits=verdict["test_edits_flagged"], verified_ac=verdict["ac"])`. In `ingest_review` round 1 `repair-staged`, add `entry["verified_ac"] = result["verdict"]["ac"]` next to the `tree_id` update. Re-run `python3 scripts/todos/test_state_flow.py` → `All checks passed.`

- [ ] **Step 1: Write the failing test**

Create `scripts/todos/test_land.py`:

```python
#!/usr/bin/env python3
"""Tests for scripts/todos/land.py.

Run: python3 scripts/todos/test_land.py (also run by harness-ci.yml).

land.py is where a checkbox becomes a claim. Pinned here: a box flips only
with the worker's pass AND the verifier's agreement AND an evidence file;
ac.json that disagrees with the todo stops everything; fenced examples are
not criteria; archive refuses bare boxes but accepts re-points; the review
doc is renamed COMPLETED only when nothing is left open.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import land  # noqa: E402
import todofile  # noqa: E402

FAILURES = []


def check(label, condition, detail=""):
    print(f"  {'PASS' if condition else 'FAIL'}  {label}{'' if condition else f'  -- {detail}'}")
    if not condition:
        FAILURES.append(label)


def todo_text(issue, finding, boxes):
    return (f'---\nstatus: pending\npriority: p3\nissue_id: "{issue}"\ndependencies: []\n'
            f'source_review: "docs/reviews/r.md"\nsource_finding: "{finding}"\n---\n\n# T\n\n'
            "## Acceptance Criteria\n\n" + "".join(f"- [ ] {b}\n" for b in boxes)
            + "\n```markdown\n- [ ] fenced example\n```\n\n## Work Log\n\n### d - created\n\n## Notes\n\nn\n")


def setup(tmp):
    repo = Path(tmp) / "repo"
    (repo / "todos" / "archive").mkdir(parents=True)
    (repo / "docs" / "reviews").mkdir(parents=True)
    (repo / "todos" / "archive" / ".keep").write_text("")
    (repo / "todos" / "412-pending-p3-a.md").write_text(todo_text("412", "7", ["one", "two", "three"]))
    (repo / "todos" / "413-pending-p3-b.md").write_text(
        todo_text("413", "8", ["only", "moved -> todo 500 (re-pointed 2026-09-27)"]))
    (repo / "docs" / "reviews" / "r.md").write_text(
        "# Review\n\n## Finding Status\n\n- [ ] #7 first thing → todo 412\n- [ ] #8 second → todo 413\n\n## Other\n\n- [ ] x\n")
    (repo / ".secrets.baseline").write_text('{"results": {"todos/412-pending-p3-a.md": []}}\n')
    ev = repo / ".sweep-evidence" / "g1"
    ev.mkdir(parents=True)
    for name in ("412-ac1.txt", "412-ac2.txt", "413-ac1.txt"):
        (ev / name).write_text("line a\nline b\n7 passed in 0.4s\n")
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "todos", "docs", ".secrets.baseline"], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x"],
                   check=True)
    return repo


def entry(todo, index, passed=True, evidence=True):
    return {"todo": todo, "index": index, "text": "t", "command": f"pytest ac{index + 1}",
            "evidence_path": f".sweep-evidence/g1/{todo}-ac{index + 1}.txt" if evidence else "", "pass": passed}


def agree(todo, index, ok=True):
    return {"todo": todo, "index": index, "verified": ok, "note": ""}


def raises(fn):
    try:
        fn()
    except land.LandError as exc:
        return str(exc)
    return ""


def main():
    with tempfile.TemporaryDirectory() as tmp:
        repo = setup(tmp)
        rel = "todos/412-pending-p3-a.md"

        msg = raises(lambda: land.flip_acs(repo, rel, [entry("412", 0), entry("412", 1)], [], "r", "2026-09-27"))
        check("count mismatch refuses", "has 3 criteria" in msg, msg)
        check("a refusal changes nothing", "- [x]" not in (repo / rel).read_text())

        flipped, left = land.flip_acs(
            repo, rel,
            [entry("412", 0), entry("412", 1, passed=True), entry("412", 2, evidence=False)],
            [agree("412", 0), agree("412", 1, ok=False), agree("412", 2)],
            "r", "2026-09-27")
        text = (repo / rel).read_text()
        check("only pass + verifier agreement + evidence flips", flipped == [0] and left == [1, 2], (flipped, left))
        check("the verifier's disagreement leaves the box open", "- [ ] two" in text)
        check("missing evidence is not flipped", "- [ ] three" in text)
        check("fenced boxes are ignored", "- [ ] fenced example" in text)
        check("the Work Log quotes the evidence tail before ## Notes",
              "7 passed in 0.4s" in text and text.index("Verified by the todo sweep") < text.index("## Notes"), text)

        msg = raises(lambda: land.archive(repo, rel, "r", "2026-09-27"))
        check("archive refuses bare unchecked criteria", "2 unchecked" in msg, msg)

        land.flip_acs(repo, rel, [entry("412", 0), entry("412", 1), entry("412", 2)],
                      [agree("412", 0), agree("412", 1), agree("412", 2)], "r", "2026-09-27")
        (repo / ".sweep-evidence/g1/412-ac3.txt").write_text("ok\n")
        land.flip_acs(repo, rel, [entry("412", 0), entry("412", 1), entry("412", 2)],
                      [agree("412", 0), agree("412", 1), agree("412", 2)], "r", "2026-09-27")
        result = land.archive(repo, rel, "r", "2026-09-27")
        dest = repo / "todos/archive/412-completed-p3-a.md"
        check("archive moves filename and status together",
              dest.exists() and todofile.read_frontmatter(dest)["status"] == "completed", result)
        check("the baseline path follows the rename",
              '"todos/archive/412-completed-p3-a.md"' in (repo / ".secrets.baseline").read_text())
        review = (repo / "docs/reviews/r.md").read_text()
        check("the source finding is checked off with a date",
              "- [x] #7 first thing → todo 412 (completed 2026-09-27)" in review, review)
        check("the review doc stays while a finding is open", result["review"]["renamed"] is False)
        check("paths to stage include the archived todo and review doc",
              {"todos/archive/412-completed-p3-a.md", "docs/reviews/r.md", ".secrets.baseline"} <= set(result["paths"]),
              result["paths"])

        rel2 = "todos/413-pending-p3-b.md"
        land.flip_acs(repo, rel2, [entry("413", 0), entry("413", 1, passed=False)], [agree("413", 0)], "r", "d")
        result = land.archive(repo, rel2, "r", "2026-09-27")
        check("a re-pointed criterion does not block archive", result["archived"].endswith("413-completed-p3-b.md"))
        check("the last finding renames the review doc COMPLETED",
              result["review"]["renamed"] and (repo / "docs/reviews/r-COMPLETED.md").exists(), result)
        check("the todo's source_review follows the rename",
              todofile.read_frontmatter(repo / result["archived"])["source_review"] == "docs/reviews/r-COMPLETED.md")
        check("findings outside ## Finding Status are not counted",
              "- [ ] x" in (repo / "docs/reviews/r-COMPLETED.md").read_text())

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} check(s): {', '.join(FAILURES)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 scripts/todos/test_land.py`
Expected: `ModuleNotFoundError: No module named 'land'`.

- [ ] **Step 3: Write the implementation**

Create `scripts/todos/land.py`:

```python
#!/usr/bin/env python3
"""Stage D helpers: make a verified group's todos archivable, exactly.

    land.py flip-acs --run RUNFILE --id 412 --repo WORKTREE --date 2026-09-27
    land.py archive  --run RUNFILE --id 412 --repo WORKTREE --date 2026-09-27

flip-acs checks a box only where the worker's ac.json says pass AND the
verifier re-ran it and agreed AND the evidence file exists. It quotes the
evidence tail into the Work Log, because .sweep-evidence/ is gitignored and the
Work Log is the only record that survives the merge. archive applies the
per-todo contract (completing-todos Safety Rails 4-5): status and filename move
together, a .secrets.baseline entry follows the rename (a filename-only edit,
never a regeneration), and the source review finding is checked off. The
review doc is renamed COMPLETED only when nothing in its Finding Status is open.
Re-pointed findings stay open by design (CLAUDE.md Review Doc Tracking rule 4).
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import state  # noqa: E402
import todofile  # noqa: E402

EVIDENCE_TAIL = 5


class LandError(Exception):
    pass


def run_git(repo, *args):
    proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if proc.returncode != 0:
        raise LandError(f"git {' '.join(args)}: {proc.stderr.strip()}")
    return proc.stdout


def _tail(path):
    lines = Path(path).read_text(errors="replace").rstrip("\n").splitlines()
    return lines[-EVIDENCE_TAIL:]


def flip_acs(repo, todo_rel, ac_entries, verdict_ac, run_id, date):
    repo = Path(repo)
    path = repo / todo_rel
    todo_id = str((todofile.read_frontmatter(path) or {}).get("issue_id", ""))
    text = path.read_text()
    boxes = todofile.ac_lines(text)
    mine = sorted((e for e in ac_entries if str(e["todo"]) == todo_id), key=lambda e: e["index"])
    if [e["index"] for e in mine] != list(range(len(boxes))):
        raise LandError(f"{todo_rel}: ac.json has indexes {[e['index'] for e in mine]} for todo {todo_id}, "
                        f"but the file has {len(boxes)} criteria")
    agreed = {v["index"] for v in verdict_ac if str(v["todo"]) == todo_id and v["verified"]}
    lines = text.splitlines(keepends=True)
    flipped, notes = [], []
    for (line_no, checked, _), entry in zip(boxes, mine):
        index = entry["index"]
        evidence = repo / entry["evidence_path"] if entry.get("evidence_path") else None
        if checked or not (entry["pass"] and index in agreed and evidence and evidence.is_file()):
            continue
        lines[line_no] = lines[line_no].replace("[ ]", "[x]", 1)
        flipped.append(index)
        quoted = "\n".join(f"  {line}" for line in _tail(evidence))
        notes.append(f"- AC {index + 1}: `{entry['command']}` — evidence `{entry['evidence_path']}`, "
                     f"last lines:\n\n  ```text\n{quoted}\n  ```\n")
    path.write_text("".join(lines))
    if flipped:
        todofile.append_work_log(path, f"### {date} - Verified by the todo sweep (run {run_id})\n\n" + "\n".join(notes))
    remaining = [e["index"] for (_, checked, _), e in zip(boxes, mine) if not checked and e["index"] not in flipped]
    return flipped, remaining


def fix_baseline(repo, old_rel, new_rel):
    path = Path(repo) / ".secrets.baseline"
    if not path.is_file():
        return False
    text = path.read_text()
    if f'"{old_rel}"' not in text:
        return False
    path.write_text(text.replace(f'"{old_rel}"', f'"{new_rel}"'))
    return True


def check_off_review(repo, todo_path, date, git=run_git):
    data = todofile.read_frontmatter(todo_path) or {}
    source, finding = data.get("source_review"), data.get("source_finding")
    if not source or not finding:
        return None
    review = Path(repo) / source
    if not review.is_file():
        raise LandError(f"source_review {source} not found")
    lines = review.read_text().splitlines(keepends=True)
    start = next((i for i, line in enumerate(lines) if line.rstrip("\n") == "## Finding Status"), None)
    if start is None:
        raise LandError(f"{source}: no '## Finding Status' section")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    key = re.escape(str(finding))
    open_re, done_re = re.compile(rf"^- \[ \] #{key}(?=\s|$)"), re.compile(rf"^- \[x\] #{key}(?=\s|$)")
    hit = next((i for i in range(start + 1, end) if open_re.match(lines[i])), None)
    if hit is None:
        if any(done_re.match(lines[i]) for i in range(start + 1, end)):
            return {"finding": finding, "renamed": False, "paths": [], "note": "already checked"}
        raise LandError(f"{source}: no open line for finding #{finding}")
    lines[hit] = lines[hit].rstrip("\n").replace("- [ ]", "- [x]", 1) + f" (completed {date})\n"
    review.write_text("".join(lines))
    still_open = sum(1 for i in range(start + 1, end) if lines[i].startswith("- [ ]"))
    if still_open:
        return {"finding": finding, "renamed": False, "paths": [source], "note": f"{still_open} still open"}
    completed = source[:-3] + "-COMPLETED.md" if source.endswith(".md") else source + "-COMPLETED"
    git(repo, "mv", source, completed)
    todofile.set_fields(todo_path, {"source_review": completed})
    return {"finding": finding, "renamed": True, "paths": [completed], "note": "all findings resolved"}


def archive(repo, todo_rel, run_id, date, git=run_git):
    repo = Path(repo)
    text = (repo / todo_rel).read_text()
    bare = [line for _, checked, line in todofile.ac_lines(text) if not checked and not todofile.is_repoint(line)]
    if bare:
        raise LandError(f"{todo_rel}: {len(bare)} unchecked criteria; flip them with evidence or re-point them first")
    dest_rel = f"todos/archive/{todofile.with_status(Path(todo_rel).name, 'completed')}"
    git(repo, "mv", todo_rel, dest_rel)  # rename first; the edits below are staged by the caller
    dest = repo / dest_rel
    todofile.set_fields(dest, {"status": "completed"})
    todofile.append_work_log(dest, f"### {date} - Completed by the todo sweep (run {run_id})\n\n"
                                   "- Archived by `land.py archive`; evidence is quoted above, review is on the PR.\n")
    baseline = fix_baseline(repo, todo_rel, dest_rel)
    review = check_off_review(repo, dest, date, git)
    paths = [dest_rel] + ([".secrets.baseline"] if baseline else []) + (review["paths"] if review else [])
    return {"archived": dest_rel, "paths": paths, "baseline_updated": baseline, "review": review}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("cmd", choices=["flip-acs", "archive"])
    parser.add_argument("--run", required=True)
    parser.add_argument("--id", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--date", required=True)
    args = parser.parse_args(argv)
    run = state.load(args.run)
    entry = run["todos"][args.id]
    try:
        if args.cmd == "flip-acs":
            ac_entries = json.loads((Path(args.repo) / entry["ac_file"]).read_text())
            flipped, remaining = flip_acs(args.repo, entry["path"], ac_entries, entry.get("verified_ac", []),
                                          run["run_id"], args.date)
            print(json.dumps({"flipped": flipped, "remaining": remaining}))
        else:
            print(json.dumps(archive(args.repo, entry["path"], run["run_id"], args.date)))
    except LandError as exc:
        print(f"land: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 scripts/todos/test_land.py && python3 scripts/todos/test_state_flow.py`
Expected: both `All checks passed.`

- [ ] **Step 5: Commit**

```bash
/usr/bin/git add scripts/todos/land.py scripts/todos/test_land.py scripts/todos/state.py
/usr/bin/git commit -m "feat(todos): land.py flips only verified criteria and archives per the todo contract" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Worker git guard hook

**Files:**

- Create: `scripts/todos/worker_git_guard.py`
- Create: `.claude/hooks/guard-todo-worker-git.sh`
- Test: `.claude/hooks/test-guard-todo-worker-git.sh`
- Modify: `.claude/settings.json` (the `PreToolUse` → `"matcher": "Bash"` hooks list)

Edit these with the Edit/Write tools, not shell redirection. `.claude/hooks/` and `.claude/settings.json` are write-denied to Bash in the main checkout's sandbox.

**Interfaces:**

- Consumes: the `PreToolUse` event JSON (`agent_type`, `tool_input.command`). The docs say hooks fire inside subagents with `agent_type` set. Pilot P4 confirms it.
- Produces: `worker_git_guard.decide(event: dict) -> str | None` (the deny reason); stdout `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": …}}` on deny, nothing on allow.

- [ ] **Step 1: Write the failing test**

Create `.claude/hooks/test-guard-todo-worker-git.sh`:

```bash
#!/usr/bin/env bash
# Tests for guard-todo-worker-git.sh — run from anywhere.
# The guard limits todo-worker / todo-verifier Bash calls to staging-only git
# (spec §4.1). The cases that matter are the disguises: wrappers, absolute
# paths, compound commands, bash -c, $(...), a second line — and the harmless
# mention of "git commit" inside a grep, which must still be allowed.
set -uo pipefail

HOOK="$(cd "$(dirname "$0")" && pwd)/guard-todo-worker-git.sh"
PASS=0; FAIL=0

event() {
  python3 -c 'import json, sys; print(json.dumps({"agent_type": sys.argv[1], "tool_input": {"command": sys.argv[2]}}))' "$1" "$2"
}

assert_deny() {
  local name="$1" out
  out=$(event "$2" "$3" | bash "$HOOK" 2>/dev/null)
  if grep -q '"permissionDecision": "deny"' <<< "$out"; then
    echo "PASS: $name"; PASS=$((PASS+1))
  else
    echo "FAIL: $name (expected deny)"; echo "  got: $out"; FAIL=$((FAIL+1))
  fi
}

assert_allow() {
  local name="$1" out
  out=$(event "$2" "$3" | bash "$HOOK" 2>/dev/null)
  if [ -z "$out" ]; then
    echo "PASS: $name"; PASS=$((PASS+1))
  else
    echo "FAIL: $name (expected allow)"; echo "  got: $out"; FAIL=$((FAIL+1))
  fi
}

W=todo-worker
assert_deny  "worker: git commit"                    $W 'git commit -m x'
assert_deny  "worker: git push"                      $W 'git push origin HEAD'
assert_deny  "worker: absolute git with -C"          $W '/usr/bin/git -C /tmp/wt commit -m x'
assert_deny  "worker: rtk wrapper"                   $W 'rtk git commit -m x'
assert_deny  "worker: env prefix"                    $W 'FOO=1 git push'
assert_deny  "worker: compound after cd"             $W 'cd /tmp/wt && git switch main'
assert_deny  "worker: git stash"                     $W 'git stash push -m x'
assert_deny  "worker: git checkout"                  $W 'git checkout -- a.py'
assert_deny  "worker: git -c option then reset"      $W 'git -c core.x=y reset --hard'
assert_deny  "worker: bash -c"                       $W 'bash -c "git push"'
assert_deny  "worker: command substitution"          $W 'echo $(git reset --hard)'
assert_deny  "worker: second line"                   $W $'git add a.py\ngit commit -m x'
assert_deny  "worker: gh"                            $W 'gh pr create --fill'
assert_deny  "worker: unparseable quoting"           $W 'git add "a.py'
assert_deny  "verifier: git commit"                  todo-verifier 'git commit -m x'
assert_allow "worker: git add -A"                    $W 'git -C /tmp/wt add -A'
assert_allow "worker: status porcelain"              $W '/usr/bin/git -C /tmp/wt status --porcelain'
assert_allow "worker: write-tree"                    $W 'git write-tree'
assert_allow "worker: diff cached vs origin/main"    $W 'git diff --cached --name-status origin/main'
assert_allow "worker: mention inside grep"           $W 'grep -rn "git commit" docs/'
assert_allow "worker: pytest via slot_env"           $W 'python3 scripts/todos/slot_env.py 1 -- python -m pytest apps/x'
assert_allow "main session (no agent_type)"          "" 'git commit -m x'
assert_allow "another agent type"                    code-review-orchestrator 'git push'

OUT=$(echo 'not json' | bash "$HOOK" 2>/dev/null)
if [ -z "$OUT" ]; then echo "PASS: malformed JSON fails open"; PASS=$((PASS+1)); else echo "FAIL: malformed JSON"; FAIL=$((FAIL+1)); fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ $FAIL -eq 0 ]
```

- [ ] **Step 2: Run it to verify it fails**

Run: `bash .claude/hooks/test-guard-todo-worker-git.sh`
Expected: `FAIL` lines for every deny case (the hook does not exist yet), exit non-zero.

- [ ] **Step 3: Write the decision module**

Create `scripts/todos/worker_git_guard.py`:

```python
#!/usr/bin/env python3
"""PreToolUse decision for Bash calls from todo-worker / todo-verifier agents.

Workers write and stage; only the main session commits, pushes and opens PRs
(spec §4.1). Agent frontmatter cannot say that -- `disallowedTools:
Bash(git push *)` removes Bash entirely -- so this hook does: for those two
agent types it allows a short list of git subcommands and denies every other
git subcommand and all of gh. Every other caller passes through untouched.

It reads the command text, so it sees wrappers (rtk, env, xargs), absolute
paths, compound commands, `bash -c`, `$(...)` and multi-line commands. It is a
guard against mistakes, not a sandbox: a script file that runs git inside is
not visible here.

Tests: .claude/hooks/test-guard-todo-worker-git.sh
"""

import json
import os
import shlex
import sys

GUARDED_AGENTS = {"todo-worker", "todo-verifier"}
GIT_ALLOWED = {"add", "mv", "rm", "diff", "status", "log", "show", "fetch", "write-tree", "rev-parse"}
WRAPPERS = {"rtk", "command", "env", "time", "nohup", "xargs", "exec", "sudo"}
SHELLS = {"bash", "sh", "zsh"}
GIT_OPTS_WITH_ARG = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}
PUNCTUATION = ";&|()`"


def simple_commands(command):
    lexer = shlex.shlex(command.replace("\n", ";"), posix=True, punctuation_chars=PUNCTUATION)
    lexer.whitespace_split = True
    current = []
    for token in lexer:
        if token and set(token) <= set(PUNCTUATION):
            if current:
                yield current
            current = []
        else:
            current.append(token)
    if current:
        yield current


def check_words(words):
    i = 0
    while i < len(words):
        word = words[i]
        name = word.split("=", 1)[0]
        if "=" in word and not word.startswith("-") and name.isidentifier():
            i += 1
            continue
        if os.path.basename(word) in WRAPPERS:
            i += 1
            while i < len(words) and words[i].startswith("-"):
                i += 1
            continue
        break
    if i >= len(words):
        return None
    program, rest = os.path.basename(words[i]), words[i + 1:]
    if program == "gh":
        return "gh is reserved for the main session (Land)"
    if program in SHELLS and len(rest) >= 2 and rest[0] == "-c":
        return decide_command(rest[1])
    if program == "eval":
        return decide_command(" ".join(rest))
    if program != "git":
        return None
    j = 0
    while j < len(rest) and rest[j].startswith("-"):
        j += 2 if rest[j] in GIT_OPTS_WITH_ARG else 1
    if j >= len(rest) or rest[j] in GIT_ALLOWED:
        return None
    return (f"git {rest[j]} is reserved for the main session; workers stage and stop "
            f"(allowed: {', '.join(sorted(GIT_ALLOWED))})")


def decide_command(command):
    try:
        for words in simple_commands(command):
            reason = check_words(words)
            if reason:
                return reason
    except ValueError:
        return "command could not be parsed; simplify the quoting"
    return None


def decide(event):
    if event.get("agent_type") not in GUARDED_AGENTS:
        return None
    return decide_command(str((event.get("tool_input") or {}).get("command", "")))


def main():
    try:
        event = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    if not isinstance(event, dict):
        return 0
    reason = decide(event)
    if reason:
        json.dump({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                          "permissionDecisionReason": f"todo sweep: {reason}"}}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Write the hook wrapper**

Create `.claude/hooks/guard-todo-worker-git.sh`:

```bash
#!/usr/bin/env bash
# PreToolUse hook (Bash) — keep todo-worker / todo-verifier agents from
# committing, pushing, moving branches or calling gh. The decision lives in
# scripts/todos/worker_git_guard.py (see its docstring); every other caller
# passes through. Fails open when python3 is missing or the event is unparseable.
#
# Tests: .claude/hooks/test-guard-todo-worker-git.sh
set -uo pipefail
command -v python3 >/dev/null 2>&1 || exit 0
exec python3 "$(cd "$(dirname "$0")/../.." && pwd)/scripts/todos/worker_git_guard.py"
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `bash .claude/hooks/test-guard-todo-worker-git.sh`
Expected: `Results: 24 passed, 0 failed`.

- [ ] **Step 6: Register the hook**

In `.claude/settings.json`, in the `PreToolUse` entry whose `"matcher": "Bash"`, append to its `hooks` array after the `check-test-env.sh` object:

```json
{
  "type": "command",
  "command": "cd \"$(git rev-parse --show-toplevel 2>/dev/null || echo '.')\" && bash .claude/hooks/guard-todo-worker-git.sh",
  "timeout": 10,
  "statusMessage": "Checking todo-worker git scope..."
}
```

Verify: `python3 -c "import json; d=json.load(open('.claude/settings.json')); print([h['command'].split('&& ')[-1] for h in d['hooks']['PreToolUse'][1]['hooks']])"`
Expected: the list ends with `bash .claude/hooks/guard-todo-worker-git.sh`.

- [ ] **Step 7: Commit**

```bash
/usr/bin/git add scripts/todos/worker_git_guard.py .claude/hooks/guard-todo-worker-git.sh .claude/hooks/test-guard-todo-worker-git.sh .claude/settings.json
/usr/bin/git commit -m "feat(harness): hook limits todo-worker and todo-verifier to staging-only git" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: The three agent definitions

**Files:**

- Create: `.claude/agents/todo-triager.md`
- Create: `.claude/agents/todo-worker.md`
- Create: `.claude/agents/todo-verifier.md`

**Interfaces:**

- Consumes: record schemas from the workflows (Task 12), `slot_env.py` (Task 8), the hook (Task 10).
- Produces: agent types `todo-triager`, `todo-worker`, `todo-verifier`, resolvable by `agent(…, {agentType})` in workflows. New agents load at session start, so they exist only in sessions started after this merges.

- [ ] **Step 1: Create `.claude/agents/todo-triager.md`**

````markdown
---
name: todo-triager
description: Read-only classifier for one todo in a todo sweep. Reads the todo, checks the codebase for whether the work already exists, and returns a TRIAGE record; in plan mode returns an implementation plan instead. Dispatched by the todo-triage and todo-execute workflows. Never edits anything.
tools: Read, Grep, Glob
effort: medium
color: cyan
---

# Todo Triager

You classify ONE todo for the todo sweep
(`docs/superpowers/specs/2026-09-27-todo-sweep-multi-agent-design.md` §5.1, §6.1).
You have Read, Grep and Glob only. Your final message is the structured record — no prose.

## Input

The prompt gives `id` and `path` (repo-relative). If its first line is `MODE: plan`, skip to **Plan mode**.

## Classify

1. Read the todo in full: Problem, Findings, Recommended Action, Technical Details, Acceptance Criteria, Work Log.
2. Check whether the work already exists: grep for the symbols, settings, routes, flags or files the
   Recommended Action would add or change. Put what you searched and what it showed in `evidence`
   (paths + one-line findings, ≤ 400 chars).
3. `class` — the first that fits:
   - `already-done` — the code the todo asks for is present and each criterion looks satisfiable as written. `evidence` names the files.
   - `stale` — the premise no longer holds: the target code was removed or rewritten, or a later todo superseded it.
   - `blocked-prod` — a criterion needs production data or access (Railway shell, prod DB, prod logs). Never propose doing it.
   - `blocked-device` — a criterion needs a physical device, TestFlight, or a store console.
   - `blocked-external` — a criterion needs a vendor dashboard, a credential, DNS, or a person outside the repo. Also any todo with `status: blocked`.
   - `blocked-owner` — the todo waits on the owner, or needs a product/spend decision that no `owner_decision` records.
   - `needs-design` — two or more reasonable designs and the todo does not choose.
   - `needs-research` — the approach is known but an unfamiliar API, library or area must be learned first, and a plan would change the work.
   - `ready` — none of the above.
4. `owner_question` — one question answerable in one line, with its options when there are any
   ("Enable by default, or keep it behind FORUM_X_ENABLED?"). For `already-done` or `stale`, ask for
   confirmation with the evidence. Empty only when the class is `ready` and nothing is ambiguous.
5. `blocked_on` — one line naming what would unblock it; empty for `ready`.
6. `predicted_files` — repo-relative paths the work will change, including tests you expect it to add.
   Always list `backend/plant_community_backend/settings.py` or `.secrets.baseline` when the work touches
   them, and any dependency manifest (`requirements*.txt`, `package*.json`, `pubspec.*`). These are single-lane resources.
7. `size` — `xs` one file, a few lines · `s` one module · `m` several files in one app · `l` cross-platform,
   a migration, or more than about 8 files.
8. `needs_e2e` — true when a criterion needs Playwright or a running dev server.
9. `notes_for_siblings` — what another todo's worker must know (a shared helper, a renamed file); else empty.

Do not pick a class to be helpful. When the todo is unclear, say so in `owner_question`.

## Plan mode

The prompt names the todo files and the owner's decisions. Return the `plan` field only, ≤ 4000 chars:
the files to change, the approach in numbered steps, the tests to add, and the risks. Give context, not code. The
worker who receives it knows the repo conventions from CLAUDE.md.
````

- [ ] **Step 2: Create `.claude/agents/todo-worker.md`**

````markdown
---
name: todo-worker
description: The single writer for one todo group in a todo sweep. Implements, tests, records acceptance-criteria evidence, stages everything and stops. Never commits, pushes, switches branches or runs gh (a hook enforces this), never checks criteria boxes or archives. Dispatched by the todo-execute and todo-review workflows.
color: green
---

# Todo Worker

You are the only writer for ONE group of todos in the todo sweep
(`docs/superpowers/specs/2026-09-27-todo-sweep-multi-agent-design.md` §5.2, §6.2, §7.4).
You implement, test, record evidence, stage, and stop. You never commit, push, switch branches or run `gh`
— `.claude/hooks/guard-todo-worker-git.sh` denies them — and you never check an acceptance-criteria box,
archive a todo, or change its `status:`. The main session lands your work.

## Modes (first line of the prompt)

- `MODE: implement` — you are in a fresh worktree cut from origin/main. The prompt has a `BRIEF:` (JSON) and a `PLAN:`.
- `MODE: retry` — the verifier failed your earlier attempt. Work in the given `WORKTREE`. Fix what `VERIFIER NOTES` say and nothing else.
- `MODE: repair` — round-1 review found blocking issues. Work in the given `WORKTREE`. Fix only the listed `FINDINGS`.
  If `WORKTREE/EVIDENCE_DIR` is missing (the harness swept the worktree after push, and Land re-created it from the
  branch), regenerate `ac.json` and the evidence for every criterion before you finish. The verifier needs them.
- `BRIEF.verify_only: true` — change no code. Gather evidence for every criterion and add the Work Log entry.

## Setup

1. `WT` = `/usr/bin/git rev-parse --show-toplevel` (implement) or the given `WORKTREE`. Use absolute paths
   under `WT` everywhere. Use `/usr/bin/git`, one git call per Bash command, and no heredocs that contain `git`.
2. `MAIN` = `BRIEF.main_root` (or `MAIN_ROOT`), `SLOT` = `BRIEF.slot` (or `SLOT`).
3. Toolchain — never write DATABASE_URL, REDIS_URL or PYTHONPATH into `.env`:
   - Backend tests, from `WT/backend`: `python3 WT/scripts/todos/slot_env.py SLOT -- MAIN/backend/venv/bin/python -m pytest <nodes> --create-db`
   - Web: once, `ln -sfn MAIN/web/node_modules WT/web/node_modules`; then `npm run …` from `WT/web`.
   - Flutter: `flutter pub get` in `WT/plant_community_mobile`.
   - Changing a dependency manifest needs the deps lane: if `BRIEF.lanes_held` does not mention dependency
     manifests, stop with status `blocked` and blockers `needs the deps lane`.
4. Read every todo in `BRIEF.todo_paths` in full, and the pattern docs for its area (CLAUDE.md "Pattern
   Library"). `BRIEF.owner_decisions` are binding.

## Scope

- `BRIEF.in_scope_files` is a prediction, not a fence. But never touch what `BRIEF.lanes_forbidden` names;
  if you must, stop with status `blocked` and say which.
- Never edit or delete an existing test to make it pass. If a behaviour change legitimately needs a test
  changed, change it and explain in `discoveries`. The verifier flags it and the reviewers check it.

## Evidence — `EVIDENCE` = `WT/<BRIEF.evidence_dir>` (or `EVIDENCE_DIR`)

- For every checkbox line under each todo's `## Acceptance Criteria` (checked or not; lines inside ```
  fences are examples, not criteria), in file order, run the command that proves it and save the full
  output to `EVIDENCE/<todo>-ac<N>.txt` (N from 1).
- Write `EVIDENCE/ac.json`: a JSON list, one object per criterion, `index` from 0 in file order per todo:
  `{"todo": "412", "index": 0, "text": "…", "command": "…", "evidence_path": ".sweep-evidence/g1/412-ac1.txt", "pass": true}`.
  `pass` is true only when the output proves the criterion as written.
- A criterion that can only be settled outside the repo gets `pass: false`, `command: ""`, and a `blockers` line.

## Work Log

Append one entry per todo at the end of `## Work Log` (before `## Notes`): `### <date> - Implemented by the
todo sweep (run <run_id>)` with 2–5 bullets on what changed and why. Do not edit Acceptance Criteria.

## Finish

1. `/usr/bin/git -C WT add -A`
2. `/usr/bin/git -C WT status --porcelain` must print nothing. Fix it if it does.
3. `/usr/bin/git -C WT write-tree` → `tree_id`.
4. Return the WORKER record: `status` `staged` (or `blocked` / `failed` / `no_change` with `blockers`),
   `worktree` WT, `branch` (`/usr/bin/git -C WT rev-parse --abbrev-ref HEAD`), `tree_id`, `files_changed`,
   `ac_file` (repo-relative, e.g. `.sweep-evidence/g1/ac.json`), `tests_run`, `blockers`, `discoveries`,
   `summary`. Stay within every length limit.
````

- [ ] **Step 3: Create `.claude/agents/todo-verifier.md`**

````markdown
---
name: todo-verifier
description: Independent evidence checker for a todo sweep. Re-runs every acceptance-criterion command in a worker's worktree, flags edits to existing tests, and returns a VERDICT. Never edits files; any change to the worktree voids its verdict. Dispatched by the todo-execute and todo-review workflows.
disallowedTools: Edit, Write, NotebookEdit
color: yellow
---

# Todo Verifier

You independently check ONE group's evidence
(`docs/superpowers/specs/2026-09-27-todo-sweep-multi-agent-design.md` §5.2). You do not fix anything.
The main session compares the tree ids you record with the worker's. A worktree you changed voids your
verdict, so run commands but never edit, move or stage. When unsure, the verdict is `fail`.

Input: `WORKTREE` (WT), `SLOT`, `MAIN_ROOT` (MAIN), `AC_FILE` (repo-relative), the todo ids, and the
worker's claimed tree id. Use `/usr/bin/git`, one git call per Bash command.

1. First: `/usr/bin/git -C WT write-tree` → `tree_id_before`, and
   `/usr/bin/git -C WT status --porcelain --untracked-files=no` — if it prints anything, the verdict is `fail`.
2. Read `WT/AC_FILE`. For every entry, open the todo file and confirm the entry's `text` matches the
   criterion at that position. Then re-run `command` yourself with the worker's toolchain. Backend
   tests run from `WT/backend` as `python3 WT/scripts/todos/slot_env.py SLOT -- MAIN/backend/venv/bin/python -m pytest … --create-db`.
   Judge the output against the criterion itself, not against the worker's saved evidence.
   `verified: true` only when YOUR run proves it. An external criterion gets `verified: false`, note `external`.
3. Test edits: `/usr/bin/git -C WT diff --cached --name-status origin/main`. List every existing test file
   with status `M` or `D` (paths containing `test` or `spec`) in `test_edits_flagged`.
4. Last: `/usr/bin/git -C WT write-tree` → `tree_id_after`; `status --porcelain --untracked-files=no` empty →
   `clean_after: true`. Untracked build or test artifacts do not count, because Land commits only the index.
5. `verdict` is `pass` only when every entry is verified. Return the VERDICT record:
   `ids, verdict, ac [{todo, index, verified, note}], test_edits_flagged, commands_rerun, tree_id_before, tree_id_after, clean_after`.
````

- [ ] **Step 4: Verify the frontmatter format**

Run:

```bash
for f in .claude/agents/todo-triager.md .claude/agents/todo-worker.md .claude/agents/todo-verifier.md; do
  awk 'NR==1 && $0!="---"{exit 1} NR>1 && /^---$/{exit 0} NR>1 && !/^[a-zA-Z]+: .+$/{print FILENAME": "$0; exit 1}' "$f" && echo "ok $f"
done
```

Expected: three `ok` lines (every frontmatter line is a single-line `key: value`).

- [ ] **Step 5: Commit**

```bash
/usr/bin/git add .claude/agents/todo-triager.md .claude/agents/todo-worker.md .claude/agents/todo-verifier.md
/usr/bin/git commit -m "feat(harness): todo-triager, todo-worker and todo-verifier agents" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: The three workflows, with a stubbed test harness

**Files:**

- Create: `.claude/workflows/todo-triage.js`
- Create: `.claude/workflows/todo-execute.js`
- Create: `.claude/workflows/todo-review.js`
- Test: `scripts/todos/test_workflows.js`

**Interfaces:**

- Consumes: agent types from Task 11; args from `state.py triage-args` / `execute-args` / `review-args` (Tasks 4, 7).
- Produces (read by `state.py record-triage` / `ingest-execute` / `ingest-review`):
  - `todo-triage` → `{records: TRIAGE[], missing: string[]}`
  - `todo-execute` → `{results: [{group, ids, worker: WORKER|null, verdict: VERDICT|null, retried}]}`
  - `todo-review` → `{results: [{group, ids, findings, ranges, reviewers_ok, checklist_skipped, blocking, repair: WORKER|null, verdict: VERDICT|null}]}`. `reviewers_ok` means the bug review returned; the checklist review is best-effort (`checklist_skipped`).

The WORKER and VERDICT schemas appear in both `todo-execute.js` and `todo-review.js`, because workflow scripts cannot import. Keep them identical. `test_workflows.js` asserts it.

- [ ] **Step 1: Write the failing test harness**

Create `scripts/todos/test_workflows.js`:

```js
#!/usr/bin/env node
// Tests for .claude/workflows/todo-*.js — run: node scripts/todos/test_workflows.js
// Runs each workflow with stub agent()/pipeline()/parallel(), so the control
// flow (which agents run, with which isolation, when retry and repair happen)
// is pinned without spending a token. It also proves each file parses.
'use strict'
const fs = require('fs')
const path = require('path')

const ROOT = path.resolve(__dirname, '..', '..')
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor
const failures = []

function check(label, cond, detail = '') {
  console.log(`  ${cond ? 'PASS' : 'FAIL'}  ${label}${cond ? '' : `  -- ${JSON.stringify(detail)}`}`)
  if (!cond) failures.push(label)
}

function source(name) {
  return fs.readFileSync(path.join(ROOT, '.claude', 'workflows', `${name}.js`), 'utf8')
}

async function run(name, args, respond) {
  const body = source(name).replace(/^export const meta/m, 'const meta')
  const calls = []
  const errors = []
  const agent = async (prompt, opts = {}) => {
    calls.push({ prompt, opts })
    return respond(prompt, opts, calls)
  }
  const pipeline = async (items, ...stages) =>
    Promise.all(items.map(async (item, i) => {
      let value = item
      try {
        for (const stage of stages) value = await stage(value, item, i)
        return value
      } catch (e) {
        errors.push(String(e))
        return null
      }
    }))
  const parallel = async thunks => Promise.all(thunks.map(t => t().catch(e => { errors.push(String(e)); return null })))
  const fn = new AsyncFunction('agent', 'pipeline', 'parallel', 'phase', 'log', 'args', 'budget', 'workflow', body)
  const result = await fn(agent, pipeline, parallel, () => {}, () => {}, args, { total: null }, async () => null)
  return { result, calls, errors }
}

const worker = (over = {}) => ({ ids: ['1'], status: 'staged', worktree: '/wt/g1', branch: 'b', tree_id: 'T',
  files_changed: [], ac_file: '.sweep-evidence/g1/ac.json', tests_run: [], blockers: '', discoveries: '', summary: '', ...over })
const verdict = v => ({ ids: ['1'], verdict: v, ac: [{ todo: '1', index: 0, verified: v === 'pass', note: 'n' }],
  test_edits_flagged: [], commands_rerun: 1, tree_id_before: 'T', tree_id_after: 'T', clean_after: true })
const brief = (over = {}) => ({ run_id: 'r', group: 'g1', ids: ['1'], todo_paths: ['todos/1-pending-p3-x.md'],
  owner_decisions: {}, plan_needed: false, verify_only: false, in_scope_files: [], lanes_held: [], lanes_forbidden: [],
  slot: 1, evidence_dir: '.sweep-evidence/g1', main_root: '/main', ...over })
const pr = (over = {}) => ({ run_id: 'r', round: 1, group: 'g1', ids: ['1'], worktree: '/wt/g1', branch: 'b', pr: 861,
  size: 's', slot: 1, evidence_dir: '.sweep-evidence/g1', main_root: '/main', test_edits: [], ...over })
const byType = (calls, type) => calls.filter(c => c.opts.agentType === type)

function schemaBlock(src, name) {
  const start = src.indexOf(`const ${name} = {`)
  let depth = 0
  for (let i = src.indexOf('{', start); i < src.length; i++) {
    if (src[i] === '{') depth++
    if (src[i] === '}' && --depth === 0) return src.slice(start, i + 1)
  }
  return ''
}

async function main() {
  // --- triage
  let r = await run('todo-triage', { todos: [{ id: '1', path: 'a' }, { id: '2', path: 'b' }] },
    (p, o) => (p.includes('id: 2') ? null : { id: 'WRONG', class: 'ready' }))
  check('triage: one todo-triager per todo', byType(r.calls, 'todo-triager').length === 2)
  check('triage: record ids are forced to the input id', r.result.records[0].id === '1', r.result)
  check('triage: a dead agent is reported missing', r.result.missing.join() === '2', r.result)
  check('triage: no script errors', r.errors.length === 0, r.errors)

  // --- execute: pass first time
  r = await run('todo-execute', { run_id: 'r', briefs: [brief()] },
    (p, o) => (o.agentType === 'todo-worker' ? worker() : verdict('pass')))
  const work = byType(r.calls, 'todo-worker')
  check('execute: the implementer runs in its own worktree', work.length === 1 && work[0].opts.isolation === 'worktree')
  check('execute: no planner unless plan_needed', byType(r.calls, 'todo-triager').length === 0)
  check('execute: one verifier on a pass', byType(r.calls, 'todo-verifier').length === 1)
  check('execute: result carries the verdict', r.result.results[0].verdict.verdict === 'pass' && !r.result.results[0].retried)

  // --- execute: fail, then retry in the same worktree
  let verifies = 0
  r = await run('todo-execute', { run_id: 'r', briefs: [brief()] },
    (p, o) => (o.agentType === 'todo-worker' ? worker() : verdict(++verifies === 1 ? 'fail' : 'pass')))
  const works = byType(r.calls, 'todo-worker')
  check('execute: a failed verdict gets exactly one retry', works.length === 2 && byType(r.calls, 'todo-verifier').length === 2)
  check('execute: the retry reuses the worktree, no new isolation',
    works[1].opts.isolation === undefined && works[1].prompt.startsWith('MODE: retry') && works[1].prompt.includes('/wt/g1'))
  check('execute: retried result is flagged', r.result.results[0].retried && r.result.results[0].verdict.verdict === 'pass')

  // --- execute: planner and dead worker
  r = await run('todo-execute', { run_id: 'r', briefs: [brief({ plan_needed: true })] },
    (p, o) => (o.agentType === 'todo-triager' ? { plan: 'PLAN-TEXT' } : o.agentType === 'todo-worker' ? worker() : verdict('pass')))
  check('execute: needs-research runs a planner in plan mode', byType(r.calls, 'todo-triager')[0].prompt.startsWith('MODE: plan'))
  check('execute: the plan reaches the worker', byType(r.calls, 'todo-worker')[0].prompt.includes('PLAN-TEXT'))
  r = await run('todo-execute', { run_id: 'r', briefs: [brief()] }, () => null)
  check('execute: a dead worker yields worker null and no verifier',
    r.result.results[0].worker === null && byType(r.calls, 'todo-verifier').length === 0, r.result)

  // --- review round 1, size s, blocking finding
  const high = { reviewed_range: 'skill:code-review', findings: [{ severity: 'high', file: 'a.py', line: 1, summary: 'bug', suggested_fix: '' }] }
  r = await run('todo-review', { round: 1, prs: [pr()] },
    (p, o) => (o.agentType === 'general-purpose' ? high : o.agentType === 'todo-worker' ? worker() : verdict('pass')))
  check('review: size s gets only the bug reviewer', byType(r.calls, 'code-review-orchestrator').length === 0)
  const rep = byType(r.calls, 'todo-worker')
  check('review: round 1 repairs in the PR worktree', rep.length === 1 && rep[0].opts.isolation === undefined
    && rep[0].prompt.startsWith('MODE: repair') && rep[0].prompt.includes('/wt/g1'))
  check('review: the repair is re-verified', byType(r.calls, 'todo-verifier').length === 1)
  check('review: reviewer prompts name the explicit diff range',
    byType(r.calls, 'general-purpose')[0].prompt.includes('diff origin/main...HEAD'))

  // --- review round 2, size m, blocking finding
  r = await run('todo-review', { round: 2, prs: [pr({ round: 2, size: 'm' })] }, () => high)
  check('review: size m adds the checklist reviewer', byType(r.calls, 'code-review-orchestrator').length === 1)
  check('review: round 2 never repairs', byType(r.calls, 'todo-worker').length === 0)
  check('review: blocking findings are reported', r.result.results[0].blocking.length === 2, r.result)

  r = await run('todo-review', { round: 2, prs: [pr({ round: 2, size: 'm' })] },
    (p, o) => (o.agentType === 'code-review-orchestrator' ? null : { reviewed_range: 'x', findings: [] }))
  check('review: a dead checklist reviewer is flagged, not blocking',
    r.result.results[0].reviewers_ok === true && r.result.results[0].checklist_skipped === true, r.result)

  r = await run('todo-review', { round: 1, prs: [pr()] }, () => null)
  check('review: a dead bug reviewer marks the review incomplete', r.result.results[0].reviewers_ok === false, r.result)
  check('review: an incomplete review never repairs', byType(r.calls, 'todo-worker').length === 0)

  // --- schemas stay identical across files
  for (const name of ['WORKER', 'VERDICT']) {
    check(`${name} schema is identical in execute and review`,
      schemaBlock(source('todo-execute'), name) !== '' && schemaBlock(source('todo-execute'), name) === schemaBlock(source('todo-review'), name))
  }

  console.log()
  if (failures.length) {
    console.log(`FAILED: ${failures.length} check(s): ${failures.join(', ')}`)
    process.exit(1)
  }
  console.log('All checks passed.')
}

main().catch(e => { console.error(e); process.exit(1) })
```

- [ ] **Step 2: Run it to verify it fails**

Run: `node scripts/todos/test_workflows.js`
Expected: `ENOENT: no such file or directory, open '…/.claude/workflows/todo-triage.js'`.

- [ ] **Step 3: Create `.claude/workflows/todo-triage.js`**

```js
export const meta = {
  name: 'todo-triage',
  description: 'Todo sweep Stage A: classify each selected todo read-only and return one triage record per todo',
  whenToUse: 'Called by the completing-todos engine with args {todos: [{id, path}]} from `state.py triage-args`',
  phases: [{ title: 'Triage', detail: 'one todo-triager per todo' }],
}

const TRIAGE = {
  type: 'object',
  properties: {
    id: { type: 'string' },
    class: {
      type: 'string',
      enum: ['ready', 'blocked-owner', 'blocked-prod', 'blocked-device', 'blocked-external',
        'needs-design', 'needs-research', 'already-done', 'stale'],
    },
    evidence: { type: 'string', maxLength: 400 },
    blocked_on: { type: 'string', maxLength: 200 },
    owner_question: { type: 'string', maxLength: 300 },
    predicted_files: { type: 'array', items: { type: 'string' }, maxItems: 30 },
    size: { type: 'string', enum: ['xs', 's', 'm', 'l'] },
    needs_e2e: { type: 'boolean' },
    notes_for_siblings: { type: 'string', maxLength: 200 },
  },
  required: ['id', 'class', 'evidence', 'blocked_on', 'owner_question', 'predicted_files', 'size',
    'needs_e2e', 'notes_for_siblings'],
}

const todos = (args && args.todos) || []
phase('Triage')
const results = await pipeline(todos, t =>
  agent(`Triage todo ${t.id}.\nid: ${t.id}\npath: ${t.path}\nReturn the TRIAGE record.`,
    { label: `triage:${t.id}`, phase: 'Triage', agentType: 'todo-triager', schema: TRIAGE }))
const records = results.map((r, i) => (r ? { ...r, id: todos[i].id } : null))
const missing = todos.filter((t, i) => !records[i]).map(t => t.id)
if (missing.length) log(`No triage record for ${missing.join(', ')}; they stay at scanned`)
return { records: records.filter(Boolean), missing }
```

- [ ] **Step 4: Create `.claude/workflows/todo-execute.js`**

```js
export const meta = {
  name: 'todo-execute',
  description: 'Todo sweep Stage B: per group, an optional planner, one todo-worker in its own worktree, then an independent todo-verifier with one retry on fail',
  whenToUse: 'Called by the completing-todos engine with args {run_id, briefs} from `state.py execute-args`',
  phases: [
    { title: 'Plan', detail: 'only groups triaged needs-research' },
    { title: 'Implement', detail: 'todo-worker, isolation: worktree' },
    { title: 'Verify', detail: 'todo-verifier; one retry on fail' },
  ],
}

const PLAN = { type: 'object', properties: { plan: { type: 'string', maxLength: 4000 } }, required: ['plan'] }

const WORKER = {
  type: 'object',
  properties: {
    ids: { type: 'array', items: { type: 'string' } },
    status: { type: 'string', enum: ['staged', 'blocked', 'failed', 'no_change'] },
    worktree: { type: 'string' },
    branch: { type: 'string' },
    tree_id: { type: 'string' },
    files_changed: { type: 'array', items: { type: 'string' }, maxItems: 200 },
    ac_file: { type: 'string' },
    tests_run: { type: 'array', items: { type: 'string', maxLength: 300 }, maxItems: 30 },
    blockers: { type: 'string', maxLength: 300 },
    discoveries: { type: 'string', maxLength: 300 },
    summary: { type: 'string', maxLength: 600 },
  },
  required: ['ids', 'status', 'worktree', 'branch', 'tree_id', 'files_changed', 'ac_file', 'tests_run',
    'blockers', 'discoveries', 'summary'],
}

const VERDICT = {
  type: 'object',
  properties: {
    ids: { type: 'array', items: { type: 'string' } },
    verdict: { type: 'string', enum: ['pass', 'fail'] },
    ac: {
      type: 'array',
      maxItems: 60,
      items: {
        type: 'object',
        properties: {
          todo: { type: 'string' },
          index: { type: 'integer' },
          verified: { type: 'boolean' },
          note: { type: 'string', maxLength: 200 },
        },
        required: ['todo', 'index', 'verified', 'note'],
      },
    },
    test_edits_flagged: { type: 'array', items: { type: 'string' }, maxItems: 30 },
    commands_rerun: { type: 'integer' },
    tree_id_before: { type: 'string' },
    tree_id_after: { type: 'string' },
    clean_after: { type: 'boolean' },
  },
  required: ['ids', 'verdict', 'ac', 'test_edits_flagged', 'commands_rerun', 'tree_id_before', 'tree_id_after',
    'clean_after'],
}

const briefs = (args && args.briefs) || []

function planPrompt(b) {
  return [
    'MODE: plan',
    `Write an implementation plan for todo group ${b.group}: ${b.todo_paths.join(', ')}.`,
    `Owner decisions (binding): ${JSON.stringify(b.owner_decisions)}`,
    'Return the plan field only.',
  ].join('\n')
}

function workPrompt(b, plan) {
  return ['MODE: implement', 'BRIEF:', JSON.stringify(b, null, 1), plan ? `PLAN:\n${plan}` : 'PLAN: none',
    'Return the WORKER record.'].join('\n')
}

function verifyPrompt(b, w) {
  return [
    `Verify todo group ${b.group} (${b.ids.join(', ')}).`,
    `WORKTREE: ${w.worktree}`, `SLOT: ${b.slot}`, `MAIN_ROOT: ${b.main_root}`,
    `AC_FILE: ${w.ac_file}`, `CLAIMED_TREE: ${w.tree_id}`,
    'Return the VERDICT record.',
  ].join('\n')
}

function retryPrompt(b, w, v) {
  const notes = v.ac.filter(a => !a.verified).map(a => `todo ${a.todo} AC ${a.index + 1}: ${a.note}`).join('\n')
  return ['MODE: retry', `WORKTREE: ${w.worktree}`, 'BRIEF:', JSON.stringify(b, null, 1),
    `VERIFIER NOTES:\n${notes || `verdict ${v.verdict}; tree or cleanliness check failed`}`,
    'Return the WORKER record.'].join('\n')
}

const results = await pipeline(
  briefs,
  async b => {
    if (!b.plan_needed) return ''
    const p = await agent(planPrompt(b), { label: `plan:${b.group}`, phase: 'Plan', agentType: 'todo-triager', schema: PLAN })
    return p ? p.plan : ''
  },
  (plan, b) => agent(workPrompt(b, plan),
    { label: `work:${b.group}`, phase: 'Implement', agentType: 'todo-worker', isolation: 'worktree', schema: WORKER }),
  async (worker, b) => {
    const base = { group: b.group, ids: b.ids }
    if (!worker || worker.status !== 'staged') return { ...base, worker, verdict: null, retried: false }
    const verdict = await agent(verifyPrompt(b, worker),
      { label: `verify:${b.group}`, phase: 'Verify', agentType: 'todo-verifier', schema: VERDICT })
    if (!verdict || verdict.verdict === 'pass') return { ...base, worker, verdict, retried: false }
    const retry = await agent(retryPrompt(b, worker, verdict),
      { label: `retry:${b.group}`, phase: 'Verify', agentType: 'todo-worker', schema: WORKER })
    if (!retry || retry.status !== 'staged') return { ...base, worker: retry || worker, verdict, retried: true }
    const second = await agent(verifyPrompt(b, retry),
      { label: `verify2:${b.group}`, phase: 'Verify', agentType: 'todo-verifier', schema: VERDICT })
    return { ...base, worker: retry, verdict: second, retried: true }
  },
)

return {
  results: results.map((r, i) => r || { group: briefs[i].group, ids: briefs[i].ids, worker: null, verdict: null, retried: false }),
}
```

- [ ] **Step 5: Create `.claude/workflows/todo-review.js`**

Copy the `WORKER` and `VERDICT` constants from Step 4 **verbatim** (the test compares them character for character) where marked below.

```js
export const meta = {
  name: 'todo-review',
  description: 'Todo sweep Stage C: review each open PR with fresh-context reviewers; in round 1, repair blocking findings in the PR worktree and re-verify',
  whenToUse: 'Called by the completing-todos engine with args {round, prs} from `state.py review-args`',
  phases: [
    { title: 'Review', detail: 'bug review for every PR; checklist review for size m and l' },
    { title: 'Repair', detail: 'round 1 only: todo-worker in the PR worktree, then todo-verifier' },
  ],
}

const FINDINGS = {
  type: 'object',
  properties: {
    reviewed_range: { type: 'string', maxLength: 200 },
    findings: {
      type: 'array',
      maxItems: 40,
      items: {
        type: 'object',
        properties: {
          severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
          file: { type: 'string' },
          line: { type: 'integer' },
          summary: { type: 'string', maxLength: 300 },
          suggested_fix: { type: 'string', maxLength: 300 },
        },
        required: ['severity', 'file', 'line', 'summary', 'suggested_fix'],
      },
    },
  },
  required: ['reviewed_range', 'findings'],
}

// WORKER — paste verbatim from todo-execute.js
// VERDICT — paste verbatim from todo-execute.js

const round = args && args.round
const prs = (args && args.prs) || []
const BLOCKING = new Set(['critical', 'high'])

function diffRange(p) {
  return `/usr/bin/git -C ${p.worktree} diff origin/main...HEAD`
}

function bugPrompt(p) {
  return [
    `Review PR #${p.pr} for todo group ${p.group} (${p.ids.join(', ')}), round ${round}.`,
    `Branch ${p.branch}, worktree ${p.worktree}. The change is exactly: ${diffRange(p)}`,
    `If the Skill tool offers code-review, run it at effort high against PR ${p.pr} and report its findings, with reviewed_range "skill:code-review".`,
    'Otherwise review that diff yourself for correctness bugs, with reviewed_range "git diff origin/main...HEAD".',
    'critical/high = would ship a bug, a security hole or data loss. Style and nits are low.',
    p.test_edits.length ? `The verifier flagged edits to existing tests: ${p.test_edits.join(', ')}. Check each is justified.` : '',
    'Do not post comments, commit or push. Return FINDINGS.',
  ].filter(Boolean).join('\n')
}

function checklistPrompt(p) {
  return [
    `Checklist review of PR #${p.pr} (todo group ${p.group}), round ${round}.`,
    `The change is in worktree ${p.worktree}, not the main checkout. Use ${diffRange(p)} for the diff and add --name-only for the file list.`,
    'Route to the domain reviewers as usual. Report only; do not repair. Return FINDINGS with reviewed_range set to the range you used.',
  ].join('\n')
}

function repairPrompt(p, blocking) {
  return ['MODE: repair', `WORKTREE: ${p.worktree}`, `SLOT: ${p.slot}`, `MAIN_ROOT: ${p.main_root}`,
    `EVIDENCE_DIR: ${p.evidence_dir}`, `TODOS: ${p.ids.join(', ')}`, 'FINDINGS:', JSON.stringify(blocking, null, 1),
    'Fix only these. Re-run the affected criteria and update ac.json and its evidence.',
    'If EVIDENCE_DIR is missing in the worktree, regenerate ac.json and evidence for EVERY criterion first.',
    'Return the WORKER record.'].join('\n')
}

function verifyPrompt(p, w) {
  return [
    `Verify todo group ${p.group} (${p.ids.join(', ')}) after a review repair.`,
    `WORKTREE: ${w.worktree}`, `SLOT: ${p.slot}`, `MAIN_ROOT: ${p.main_root}`,
    `AC_FILE: ${w.ac_file}`, `CLAIMED_TREE: ${w.tree_id}`,
    'Return the VERDICT record.',
  ].join('\n')
}

const results = await pipeline(
  prs,
  async p => {
    const reviewers = [() => agent(bugPrompt(p),
      { label: `bugs:${p.group}`, phase: 'Review', agentType: 'general-purpose', schema: FINDINGS })]
    if (p.size === 'm' || p.size === 'l') {
      reviewers.push(() => agent(checklistPrompt(p),
        { label: `checklist:${p.group}`, phase: 'Review', agentType: 'code-review-orchestrator', schema: FINDINGS }))
    }
    // The bug review gates. The checklist review is best-effort: if it cannot run (e.g. it cannot
    // dispatch nested reviewers from inside a workflow) the PR is flagged, not blocked.
    const found = await parallel(reviewers)
    const ok = found.filter(Boolean)
    return { findings: ok.flatMap(f => f.findings), ranges: ok.map(f => f.reviewed_range),
      reviewers_ok: Boolean(found[0]), checklist_skipped: reviewers.length > 1 && !found[1] }
  },
  async (rev, p) => {
    const blocking = rev.findings.filter(f => BLOCKING.has(f.severity))
    const base = { group: p.group, ids: p.ids, ...rev, blocking }
    if (round !== 1 || !blocking.length || !rev.reviewers_ok) return { ...base, repair: null, verdict: null }
    const repair = await agent(repairPrompt(p, blocking),
      { label: `repair:${p.group}`, phase: 'Repair', agentType: 'todo-worker', schema: WORKER })
    if (!repair || repair.status !== 'staged') return { ...base, repair, verdict: null }
    const verdict = await agent(verifyPrompt(p, repair),
      { label: `verify:${p.group}`, phase: 'Repair', agentType: 'todo-verifier', schema: VERDICT })
    return { ...base, repair, verdict }
  },
)

return {
  results: results.map((r, i) => r || { group: prs[i].group, ids: prs[i].ids, findings: [], ranges: [],
    reviewers_ok: false, checklist_skipped: false, blocking: [], repair: null, verdict: null }),
}
```

Then replace the two `// … paste verbatim` comment lines with the exact `const WORKER = {…}` and `const VERDICT = {…}` blocks from `todo-execute.js`.

- [ ] **Step 6: Run the harness to verify it passes**

Run: `node scripts/todos/test_workflows.js`
Expected: every line `PASS`, then `All checks passed.`

- [ ] **Step 7: Commit**

```bash
/usr/bin/git add .claude/workflows/todo-triage.js .claude/workflows/todo-execute.js .claude/workflows/todo-review.js scripts/todos/test_workflows.js
/usr/bin/git commit -m "feat(harness): todo-triage, todo-execute and todo-review workflows with a stubbed test harness" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: CI wiring, TEMPLATE fields, and the Part A PR

**Files:**

- Modify: `.github/workflows/harness-ci.yml` (the `paths:` list near line 35, the local-equivalent comment near line 19, the hook test step near line 77, and a new step after "Archived-todo status tripwire")
- Modify: `todos/TEMPLATE.md` (the HTML comment block under the frontmatter)

- [ ] **Step 1: Add the test step**

In `.github/workflows/harness-ci.yml`, directly after the `Archived-todo status tripwire` step, add:

```yaml
      - name: Todo sweep engine tests
        run: |
          pip install pyyaml
          python3 scripts/todos/test_todofile.py
          python3 scripts/todos/test_state.py
          python3 scripts/todos/test_state_flow.py
          python3 scripts/todos/test_scan.py
          python3 scripts/todos/test_group.py
          python3 scripts/todos/test_slot_env.py
          python3 scripts/todos/test_land.py
          node scripts/todos/test_workflows.js
```

In the step that runs the hook self-tests (the `run: |` block that starts with `pip install ruff==…`), add a line after `bash .claude/hooks/test-check-test-env.sh`:

```yaml
          bash .claude/hooks/test-guard-todo-worker-git.sh
```

Add `- 'scripts/todos/**'` and `- '.claude/workflows/**'` to the `paths:` list. Add the same test commands to the "Local equivalent" comment block at the top, in its `&& \` style.

- [ ] **Step 2: Document the triage fields in `todos/TEMPLATE.md`**

Inside the `<!-- … -->` comment directly below the frontmatter, after the paragraph that ends "Both are enforced by scripts/check_archived_todo_status.py on every PR.", add:

```text
Optional triage fields, written by the todo sweep (scripts/todos/state.py
apply-triage; spec docs/superpowers/specs/2026-09-27-todo-sweep-multi-agent-design.md
§6.4). Don't hand-maintain them:
  triage:          ready | blocked-owner | blocked-prod | blocked-device |
                   blocked-external | needs-design | needs-research |
                   already-done | stale
  blocked_on:      one line — what would unblock it
  owner_decision:  the owner's answer, verbatim, with its date
  triaged:         YYYY-MM-DD
A sweep skips `triage: blocked-*` todos until the file changes after `triaged`
(or --retriage). Stage names never go in `status:`.
```

- [ ] **Step 3: Run the whole suite locally, as CI will**

Run:

```bash
python3 scripts/todos/test_todofile.py && python3 scripts/todos/test_state.py && python3 scripts/todos/test_state_flow.py \
  && python3 scripts/todos/test_scan.py && python3 scripts/todos/test_group.py && python3 scripts/todos/test_slot_env.py \
  && python3 scripts/todos/test_land.py && node scripts/todos/test_workflows.js \
  && bash .claude/hooks/test-guard-todo-worker-git.sh && python3 scripts/check_archived_todo_status.py --fail-over 0
```

Expected: every file ends with `All checks passed.` / `Results: 24 passed, 0 failed`, and the tripwire exits 0.

- [ ] **Step 4: Commit, push, open the Part A PR**

```bash
/usr/bin/git add .github/workflows/harness-ci.yml todos/TEMPLATE.md
/usr/bin/git commit -m "ci(harness): run the todo sweep engine tests; document triage fields" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
/usr/bin/git push -u origin HEAD
gh pr create --title "feat(todos): todo sweep v2 engine — Part A (scripts, agents, workflows, hook)" --body-file <(printf '%s\n' \
  "Implements Part A of docs/superpowers/plans/2026-09-27-todo-sweep-v2.md (spec: docs/superpowers/specs/2026-09-27-todo-sweep-multi-agent-design.md)." \
  "" "No skill changes: the engine is inert until Part B, which starts after the pilot (Task 14)." \
  "" "🤖 Generated with [Claude Code](https://claude.com/claude-code)")
```

`gh` needs the sandbox off until the spec §11 settings are applied. Run review round 1 (bundled `/code-review` + `code-review-orchestrator`), repair the blocking findings, then round 2 on the repairs. Arm `gh pr merge --auto --squash --delete-branch` after round 2 is clean. Wait for the merge.

---

### Task 14: Pilot — 2 workers, 2 disjoint low-risk todos (gate for Part B)

Run in a **new Claude Code session started from the main checkout after `git pull`**, so the new agents, workflows and hook are loaded (`.claude/` changes reach only new sessions). Follow the Stage 0–D runbook from Task 15 Step 1 **by hand**; Task 15 installs that text as the skill only after this pilot passes.

**Files:**

- Create: `docs/superpowers/specs/2026-09-27-todo-sweep-pilot-results.md`

- [ ] **Step 1: Prerequisites**

The owner has applied the spec §11 settings (or accepts sandbox-off `gh`/push for the pilot), including `workflowSizeGuideline: "large"`. Check: `command -v timeout`, `gh auth status`, `git worktree list` (no peer session holds the chosen todos).

- [ ] **Step 2: Pick the two todos**

Run: `python3 scripts/todos/scan.py --selector sweep --run-id pilot-probe --dry-run`. From Selected, pick two `p4` (or `p3`) todos in **different top-level directories** that don't touch settings.py, `.secrets.baseline`, dependency manifests or e2e. Record their ids as A and B.

- [ ] **Step 3: Run the engine by hand with `--ids A,B --workers 2`**

Follow Task 15's runbook: Scan, Triage (workflow), Decide, Triage PR (merged), Group, Execute wave 0 (workflow), Land both, Review rounds 1 and 2 (workflow), auto-merge, then merge confirmation and cleanup. Keep the task output file paths.

- [ ] **Step 4: Record each check with its evidence**

Write `docs/superpowers/specs/2026-09-27-todo-sweep-pilot-results.md` with one section per check, each `PASS`/`FAIL` plus the command and quoted output:

- **P0** — a worker in a fresh worktree ran one backend test and one Vitest file with the §7.4 toolchain: quote `tests_run` from a WORKER record.
- **P1** — `isolation: worktree` produced a checkout that includes `.claude/`: `/usr/bin/git -C <WT> ls-files .claude | head -3` and `ls <WT>/.claude/agents | head -3`.
- **P2** — two slots ran pytest concurrently with no cross-talk: both WORKER `tests_run` include pytest, and `psql -d postgres -Atc "select datname from pg_database where datname like 'test_plant_community_w%'"`, **polled every 2 s while both runs are in flight**, lists `…_w1` and `…_w2` at the same time. (Corrected after the pilot, todo 469: pytest-django drops each test database at session end, so a query after the runs finds neither.)
- **P3** — the verifier ran commands in the worker's worktree: VERDICT `commands_rerun > 0` and `tree_id_before == WORKER.tree_id`.
- **P4** — the hook blocks worker commits: the transcript of the workflow shows no worker commit. Deliberately, dispatch `Agent(subagent_type: "todo-worker", prompt: "In <scratch git repo> run: git commit --allow-empty -m probe. Report the exact tool result.")` and quote the denial. Also confirm the main session could `git -C <WT> commit`, and could run `land.py` edits inside `.claude/worktrees/…` with `guard-main-branch-edit.sh` silent.
- **P5** — `.worktreeinclude` delivered `backend/.env`: `test -f <WT>/backend/.env && echo present`.
- **P6** — records within caps, and the main session's growth: `state.py record-triage` / `ingest-execute` / `ingest-review` read the task output files directly. Note the main session's context use before and after each wave from `/context`.
- **P7** — both PRs merged with their todos archived in the same PR: `gh pr view <n> --json state,files`.
- **P8** — the review workflow: quote `ranges` (`skill:code-review` or the fallback) and `checklist_skipped` for any size-`m`
  PR. If the checklist reviewer never runs inside a workflow, record that. It is flagged, not blocking.
- **P10** — tools-restricted custom agents still return structured output: the first `todo-triage` run returns
  `records` (not every id under `missing`). A flood of nulls means StructuredOutput is unreachable for
  `tools: Read, Grep, Glob`. Fix it by adding `StructuredOutput` to the triager's `tools` line. Do not debug the triager.
- **P9** — tree-hash detection works on a real worktree (sandbox off: the workflow's worktree is no longer writable once it ends). Before Land, `/usr/bin/git -C <WT> write-tree` equals the recorded `tree_id`, and `/usr/bin/git -C <WT> status --porcelain --untracked-files=no > $TMPDIR/p9.base` records the baseline (never empty: the staged work is listed). Pick a tracked file with **no staged change**, then `cp <WT>/<file> $TMPDIR/p9.bak && echo >> <WT>/<file>`: porcelain now adds `<file>` with `M` in the second (worktree) column, and `write-tree` is unchanged, because it hashes the index. Restore with `cp $TMPDIR/p9.bak <WT>/<file>` and confirm porcelain equals `p9.base` again. (Corrected after the pilot, todo 469: detection needs both checks, which `ensure-worktree` runs.)

- [ ] **Step 5: Gate**

All of P0–P10 `PASS` → commit the results file on a branch, open a PR, merge it, and continue to Part B.
**P1 or P3 `FAIL`** → apply the spec §12 fallback before Part B: Execute agents run without `isolation`, and a new `state.py prepare-worktrees` creates `git worktree add --no-track -b sweep/<run>-<group> <scratchpad>/<group> origin/main` per brief (add to Task 7 with a test). Then re-run the pilot.
Any other `FAIL` → fix the owning task, add a regression test there, and re-run the failed check only.

---

## Part B — Skills (only after Task 14 passes)

### Task 15: `completing-todos` becomes the engine runbook

**Files:**

- Modify (full rewrite): `.claude/skills/completing-todos/SKILL.md`

- [ ] **Step 1: Replace the file with the runbook**

Write `.claude/skills/completing-todos/SKILL.md` with exactly this content (Edit/Write tool; `.claude/skills/` is Bash-write-denied in the main checkout):

````markdown
---
name: completing-todos
description: The todo engine. Drives selected todos through scan, triage, one batch of owner decisions, parallel implementation in worktrees, independent verification, a two-round review, and a merged PR that archives each todo. Invoked by todo-sweep, todo-batch and todo-next, or directly — "finish todo NNN", "complete the pending todos", /completing-todos.
---

# Completing Todos — the engine (todo sweep v2)

**Announce:** "I'm using the completing-todos engine (todo sweep v2)."

Design: `docs/superpowers/specs/2026-09-27-todo-sweep-multi-agent-design.md`. This file is the
main-session runbook. `scripts/todos/*.py` own every state change and file edit. The named workflows
`todo-triage`, `todo-execute` and `todo-review` own the fan-out. Running them is sanctioned: the user invoked a
skill whose instructions call Workflow.

**Stay lean.** Hold only records and `--stat` output. Never read a worker's diff, evidence files, or
a workflow transcript in full. The scripts read the workflow task output files for you.

**Retired rails** (spec §4.1, 2026-09-27). "Never auto-commit" and "`--parallel` reserved" are replaced
by: one committer (this session), workflows never commit (hook-enforced), and one merged PR per todo group.

## Inputs

From the selector skill: `selector` (sweep | batch | next); filters `--priority`, `--ids`, `--tag`,
`--exclude-ids`; `--workers N` (1–3, default 3; next forces 1); `--limit N` (groups this run);
`--retriage`; `--dry-run`. "finish todo NNN" means `batch --ids NNN --workers 1`.

Names used below: `REPO` = the main checkout root; `RUN_ID` = `date -u +%Y-%m-%d-%H%M`;
`RUN` = `REPO/todos/.sweep-run-$RUN_ID.json`; `SCRATCH` = the session scratchpad; `TODAY` = `date +%Y-%m-%d`.
Run scripts from REPO with absolute paths. Use `/usr/bin/git` (rtk hides pre-commit failures).
Until the owner applies the spec §11 settings, `gh`, `git push` and `scan.py` need the sandbox off.

## Stage 0 — Scan

1. `git worktree list` — a peer session may hold todos; scan excludes them, but say so.
2. `python3 scripts/todos/scan.py --selector <s> --run-id $RUN_ID [filters] --workers N [--retriage] --dry-run`
3. Show the plan (Selected / Excluded with reasons / cleanup candidates). If `--dry-run`, stop.
   Otherwise ask once: proceed / cancel.
4. Re-run the same command without `--dry-run` → writes RUN.
   An old `todos/.completing-todos-run-*.json` is from the v1 skill: point the user to `todo-resume`.

## Stage A — Triage

1. `python3 scripts/todos/state.py triage-args $RUN` → `{"todos": […]}`.
2. `Workflow({name: "todo-triage", args: <that object>})`. Wait for the notification.
3. `python3 scripts/todos/state.py record-triage $RUN --output <task output file>`
4. `python3 scripts/todos/state.py accept-ready $RUN`
5. `python3 scripts/todos/state.py questions $RUN`

## Decide — one batch of owner questions

Ask every question from step 5 in as few AskUserQuestion calls as possible (≤ 4 per call). Never
answer one yourself. Record each answer with `python3 scripts/todos/state.py decide $RUN <id> <outcome> [flags]`:

| Class / situation | Options to offer | Record |
|---|---|---|
| `ready` with a question | the question's options | `ready --decision "<answer> ($TODAY)"` |
| `blocked-*`, `needs-design` | "Unblocked: …" / "Still blocked" / "Skip this run" | `ready --decision …` / `blocked --decision "<why>"` / `skipped` |
| `already-done` | "Archive as done (verify only)" / "Not done" | `ready --verify-only` / `ready` |
| `stale` | "Supersede" / "Keep" | Supersede: re-point each open criterion (`→ todo NNN (re-pointed $TODAY)`) and archive the todo as `superseded` inside the triage PR, then `skipped --decision "superseded: …"`. Keep: `blocked --decision …` |
| stranded (`in_progress`, nothing in flight) | "Reset to pending" / "Leave it" | `ready --reset-stranded` / `blocked --decision …` |
| `needs-research` | none needed | `ready` (a planner runs first) |

## Triage PR (skip for selector `next`)

1. `/usr/bin/git -C REPO fetch origin main`, then
   `/usr/bin/git -C REPO worktree add --no-track -b chore/todo-triage-$RUN_ID $SCRATCH/triage-$RUN_ID origin/main`
   (`--no-track`: without it git writes upstream config to `.git/config`, which the sandbox denies)
2. `python3 scripts/todos/state.py apply-triage $RUN --repo $SCRATCH/triage-$RUN_ID --today $TODAY`.
   Only **after** this, do the `stale` → supersede edits and moves from Decide. `apply-triage` writes to each
   todo's current path, so a todo moved first makes it fail.
3. `/usr/bin/git -C $SCRATCH/triage-$RUN_ID add todos` → `git diff --cached --stat` must list only `todos/`
   → commit `chore(todos): triage run $RUN_ID` → push → `gh pr create` → `gh pr merge --auto --squash --delete-branch`.
4. Execute does not start until `gh pr view <n> --json state` says `MERGED`. Then `git -C REPO fetch origin main`
   and `git -C REPO worktree remove $SCRATCH/triage-$RUN_ID`.

For `next`: run step 2 with `--repo <the worker's worktree>` during Land, before `land.py`, and commit it with the todo.

## Group

`python3 scripts/todos/state.py group $RUN` → waves and unschedulable todos (blocked with reasons).
With `--limit N`, execute only the first ⌈N / workers⌉ waves and list the deferred groups in the summary.

## Stage B — Execute (per wave W, in order)

1. `python3 scripts/todos/state.py execute-args $RUN --wave W --main-root REPO` → `{run_id, briefs}`.
   It refuses while wave W−1 is still executing or wave W−2 is not merged. Then Land those first.
   An empty wave (`[]`) means wait for wave W−2 to merge, then move on.
2. `Workflow({name: "todo-execute", args: <that object>})` runs in the background. Meanwhile, land wave W−1.
3. On the notification: `python3 scripts/todos/state.py ingest-execute $RUN --output <task output file>`.
4. `failed` todos: retry once in a later wave with `state.py set $RUN <id> ready`, then `state.py group $RUN`
   (it appends new groups and waves). A second failure: `state.py set $RUN <id> blocked --field reason="…"`.

## Stage D — Land (per `verified` group G of wave W, one at a time)

1. `WT=$(python3 scripts/todos/state.py ensure-worktree $RUN G --scratch $SCRATCH/worktrees)`
2. `/usr/bin/git -C $WT diff --cached --stat` — the only view of the change you take.
3. For each todo id in G: `python3 scripts/todos/land.py flip-acs --run $RUN --id <id> --repo $WT --date $TODAY`.
   If `remaining` has a criterion that is not a re-point, stop this group:
   `state.py set-group $RUN G blocked --field reason="criteria not verified: …"`.
4. For each todo id: `python3 scripts/todos/land.py archive --run $RUN --id <id> --repo $WT --date $TODAY`
   → stage exactly its `paths`: `/usr/bin/git -C $WT add <paths…>` (after `git mv`, re-add the new path).
5. Rename the branch to the repo convention: `/usr/bin/git -C $WT branch -m <type>/<id>-<slug>`, then
   `state.py annotate $RUN G --field branch=<new>`.
6. Commit the index only (never `-a`): `/usr/bin/git -C $WT commit -m "<type>(<scope>): <summary> (todo <id>)" -m "<2–4 bullets from the WORKER summary>" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.
   If the kimi gate prints `timed out; skipping gate`, record `kimi: skipped` (never "passed").
7. `/usr/bin/git -C $WT push -u origin <branch>` → `gh pr create --head <branch> --title … --body …`. The body gives
   the todo ids, the WORKER summary, verification counts, flagged test edits, the `kimi:` status and the Claude Code footer.
   Then `state.py set-group $RUN G pr_open --field pr=<n>`.

## Stage C — Review (per wave, after its PRs are open)

1. `python3 scripts/todos/state.py review-args $RUN --round 1 --wave W` → `Workflow({name: "todo-review", args})`
   → `python3 scripts/todos/state.py ingest-review $RUN --output <file> --round 1`.
   - `clean` → round 2.
   - `repair-staged` → `ensure-worktree`, `git -C $WT diff --cached --stat`, commit `fix: address review round 1 (todo <id>)`, push, then round 2.
   - `rerun` → run round 1 again once. A second `rerun`: `set-group … blocked`.
   - `blocked` → report it.
2. Round 2: `review-args --round 2` → workflow → `ingest-review --round 2`. `clean` →
   `gh pr merge <n> --auto --squash --delete-branch`. The round-2 reviewers read the full diff in fresh
   contexts; that is the "review before arming" step. You read `--stat` and their verdicts only.
   `blocked` → stop that PR and report it. When a group has `checklist_skipped`, add a PR comment saying the
   checklist review could not run (`gh pr comment <n> --body …`), and list it in the wrap-up.
3. Follow-ups: todos with `followups` get one follow-up todo file per PR (next free id, `p4`, the PR number
   in its Findings), all committed together in a closing `chore(todos): follow-ups from run $RUN_ID` PR.

## Merge confirmation and cleanup

For each `reviewed` group: `gh pr view <n> --json state` → `MERGED` → `state.py set-group $RUN G merged`
→ `/usr/bin/git -C REPO worktree remove $WT` (pushed and merged, so nothing is lost) → `state.py set-group $RUN G archived`.

## Wrap-up

`python3 scripts/todos/state.py finish $RUN` removes the run file only when every todo is terminal. The summary lists:
merged PRs, blocked todos with reasons, skipped todos, owner hand-offs (prod, device and vendor steps are never
attempted), the `kimi: skipped` count, deferred groups (`--limit`), and the follow-ups PR.

## Safety rails

1. **Acceptance criteria are gospel.** A box flips only through `land.py flip-acs` (worker pass + verifier
   agreement + evidence file). The only exception is a re-point naming a numbered target
   (`→ todo NNN (re-pointed DATE)`). `scripts/check_archived_todo_status.py` enforces this in CI.
2. **External verification leaves evidence in the file:** the date and the observed result, quoted.
   "Verified" alone is not evidence.
3. **No destructive recovery.** Never reset, force-push, delete or `git checkout --` to recover. Stop and report.
4. **Two review rounds.** Round 2 never repairs; non-blocking findings become follow-up todos.
5. **One committer.** Workflows never commit, push or call `gh`; `guard-todo-worker-git.sh` enforces it for
   workers and verifiers.
6. **Never read production.** A todo needing prod data is `blocked-prod` and an owner hand-off.
7. **Only `state.py` writes the run file; stage names never go in `status:`.**
````

- [ ] **Step 2: Commit**

```bash
/usr/bin/git add .claude/skills/completing-todos/SKILL.md
/usr/bin/git commit -m "feat(skills): completing-todos becomes the todo sweep v2 engine runbook" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 16: Selector skills — `todo-sweep`, `todo-batch`, `todo-next`

**Files:**

- Modify (full rewrite): `.claude/skills/todo-sweep/SKILL.md`, `.claude/skills/todo-batch/SKILL.md`, `.claude/skills/todo-next/SKILL.md`

- [ ] **Step 1: Write `.claude/skills/todo-sweep/SKILL.md`**

```markdown
---
name: todo-sweep
description: Batch through all pending todos in priority order. Use when you want to clear the backlog — when the user says "/todo-sweep", "sweep todos", "clear all pending todos", or "batch complete todos".
---

# Todo Sweep

Selects every open todo and runs the `completing-todos` engine on it (todo sweep v2).

1. Parse flags: `--workers N` (1–3, default 3), `--limit N`, `--retriage`, `--dry-run`.
2. Announce "I'm using todo-sweep; the completing-todos engine does the work." Then follow `completing-todos`
   with selector `sweep` and those flags.

Todos triaged `blocked-*` are skipped until their file changes or you pass `--retriage`. Todos in flight
elsewhere (a branch, worktree or open PR) are listed but not touched.
```

- [ ] **Step 2: Write `.claude/skills/todo-batch/SKILL.md`**

```markdown
---
name: todo-batch
description: Filter pending todos by priority, tags, or IDs and sweep through the matching subset. Use when the user says "/todo-batch", "batch todos", "sweep p3 todos", or "do all blog todos".
---

# Todo Batch

Like `todo-sweep`, restricted to a subset. The `completing-todos` engine does the work.

1. Parse filters from the message: `--priority pX`, `--ids A,B`, `--tag name`, `--exclude-ids A,B`, plus
   `--workers N` (1–3), `--limit N`, `--retriage`, `--dry-run`. Natural language maps to flags:
   "batch all p3 blog todos" → `--priority p3 --tag blog`; "do todos 074, 075" → `--ids 074,075`.
2. If no filter was given, say so and suggest `todo-sweep` instead. Do not guess a filter.
3. Announce, then follow `completing-todos` with selector `batch` and the flags.
```

- [ ] **Step 3: Write `.claude/skills/todo-next/SKILL.md`**

```markdown
---
name: todo-next
description: Pick and complete the single highest-priority pending todo. Daily-driver workflow. Use when the user says "/todo-next", "do next todo", or "pick up next task".
---

# Todo Next

Runs the `completing-todos` engine on one todo: the top-priority open todo whose dependencies are done,
that nobody has in flight and that isn't stranded.

1. Announce, then follow `completing-todos` with selector `next` and `--workers 1`.
2. There's no separate triage PR. The triage fields are written into the todo's own PR during Land (see the engine's
   "Triage PR" section). If triage finds it blocked, record the decision, then offer the next candidate from
   `scan.py --selector sweep --dry-run`.
```

- [ ] **Step 4: Verify the frontmatter stayed intact**

Run: `for s in todo-sweep todo-batch todo-next; do head -4 .claude/skills/$s/SKILL.md | grep -c '^name: '"$s"'$'; done`
Expected: `1` three times.

- [ ] **Step 5: Commit**

```bash
/usr/bin/git add .claude/skills/todo-sweep/SKILL.md .claude/skills/todo-batch/SKILL.md .claude/skills/todo-next/SKILL.md
/usr/bin/git commit -m "feat(skills): todo-sweep, todo-batch and todo-next select for the v2 engine" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 17: `todo-resume` reads the v2 run file

**Files:**

- Modify (full rewrite): `.claude/skills/todo-resume/SKILL.md`

- [ ] **Step 1: Write the file**

```markdown
---
name: todo-resume
description: Resume, restart, or discard an interrupted todo run from its checkpoint file. Use when the user says "/todo-resume", "resume todos", "continue todo run", or "pick up where I left off".
---

# Todo Resume

1. `ls -1t todos/.sweep-run-*.json 2>/dev/null | head -1` → RUN. If none but a v1
   `todos/.completing-todos-run-*.json` exists: explain it's from the retired v1 skill and offer
   **discard** only. Old `in_progress` todos are picked up by the next scan as stranded.
2. `python3 scripts/todos/state.py show $RUN` shows the todos per stage. Ask: resume / restart / discard.
3. **resume**: re-enter `completing-todos` at the earliest stage anything is in:
   - `scanned` → Stage A (triage) for those todos
   - `triaged` → Decide
   - `ready` with no group → `state.py group`; with a group → Stage B for its wave
   - `executing` → the execute workflow was lost. In the same session, `Workflow({scriptPath, resumeFromRunId})`
     if you have its run id. Otherwise `state.py set $RUN <id> failed --field reason="execute workflow lost"`
     then retry it once.
   - `verified` → Stage D (Land)
   - `pr_open` → Stage C, at round `review_round + 1`
   - `reviewed` / `merged` → merge confirmation and cleanup
4. **restart**: delete RUN (confirm first), then re-run the original selector.
5. **discard**: delete RUN (confirm first). No todo file on `main` changes: v2 never leaves a todo
   `in_progress` on `main`, so there's nothing to reset.
```

- [ ] **Step 2: Commit, push, open the Part B PR**

```bash
/usr/bin/git add .claude/skills/todo-resume/SKILL.md
/usr/bin/git commit -m "feat(skills): todo-resume resumes a v2 sweep run from its run file" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
/usr/bin/git push -u origin HEAD
```

Open the PR (body: the pilot results doc link, the retired rails, the 🤖 footer). Run review rounds 1 and 2, then arm auto-merge.
