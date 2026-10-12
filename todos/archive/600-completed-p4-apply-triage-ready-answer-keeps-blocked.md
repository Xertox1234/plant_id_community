---
status: completed
priority: p4
issue_id: "600"
tags: [todo-sweep, tooling]
dependencies: []
triage: ready
triaged: 2026-10-11
---

# `apply-triage` keeps a triager's block after the owner answers "ready"

## Problem

When the triager classes a todo `needs-design` (or `blocked-*`) and the owner's Decide answer makes it
`ready`, `apply-triage` still writes the triager's class and `blocked_on` into the todo's frontmatter.
`_triage_fields` (`scripts/todos/state.py:484`) sets `triage: record["class"]` and copies
`record["blocked_on"]`. Its only override turns a todo INTO `blocked-owner`; nothing turns an answered one
into `ready`.

Seen three times. Most recently, todo 581 in run 2026-10-11-1929 committed `triage: needs-design` plus a
`blocked_on` asking the very question the owner had just answered. It was hand-fixed in the triage worktree
before PR #1039. Left unfixed, a todo the owner unblocked reads as still blocked, and a later scan that
honours `blocked_on` skips it. It surfaced earlier in runs 2026-10-11-1448 and -1434 (see memory notes).

## Acceptance Criteria

- [x] When a todo's run entry is `ready` with an `owner_decision`, `apply-triage` writes `triage: ready` and
      no `blocked_on`, whatever the triager's class was.
- [x] A test in `scripts/todos/` covers a `needs-design` record answered `ready`, and fails with the fix
      reverted.
- [x] The existing todo-468 behaviour (an owner's own block becomes `blocked-owner`) is unchanged, and its
      tests still pass.

## Work Log

### 2026-10-11 - Implemented by the todo sweep (run 2026-10-11-2219)

- `_triage_fields` (`scripts/todos/state.py`) writes `triage: ready` and removes `blocked_on` when the run entry is `ready` with an `owner_decision`, whatever the triager's class. Keyed on the stage, so a worker's later block (PR #869) and an owner's own block (todo 468, `blocked-owner`) are unchanged.
- `todofile.set_fields` takes `None` to remove a key's line (a no-op when absent; still refuses a multi-line value), so a `blocked_on` left by an earlier run's triage goes too.
- Tests: `scripts/todos/test_state.py` (a `needs-design` record answered `ready`; fails with the fix reverted) and `scripts/todos/test_todofile.py` (removal).

### 2026-10-11 - Verified by the todo sweep (run 2026-10-11-2219)

- AC 1: `python3 scripts/todos/test_state.py` — evidence `.sweep-evidence/g13/600-ac0.txt` (not committed), last lines:

  ```text
    PASS  519 #5: a later todo's duplicate `triage:` line is refused, naming the todo and the key
    PASS  519 #5: ... before anything is written: the stranded todo before it is not renamed or edited
    PASS  519 #5: a stranded todo's duplicate `status:` line is refused before its git mv

  All checks passed.
  ```

- AC 2: `bash -c 'T=$(mktemp -d "${TMPDIR:-/tmp}/rv600.XXXXXX") && cp -R scripts "$T/" && sed -e "s/fields\[\"triage\"\] = \"ready\"/pass/" -e "s/fields\[\"blocked_on\"\] = None/pass/" scripts/todos/state.py > "$T/scripts/todos/state.py" && echo "reverted lines: $(grep -c "^        pass$" "$T/scripts/todos/state.py")" && echo "--- with the fix reverted:" && python3 "$T/scripts/todos/test_state.py" | grep -E "600|FAILED|All checks"; echo "reverted exit=${PIPESTATUS[0]}"; echo "--- with the fix:"; python3 scripts/todos/test_state.py | grep -E "600|FAILED|All checks"; echo "fixed exit=${PIPESTATUS[0]}"'` — evidence `.sweep-evidence/g13/600-ac1.txt` (not committed), last lines:

  ```text
  --- with the fix:
    PASS  600: a needs-design todo the owner answered ready is written triage: ready with no blocked_on
    PASS  600: ... while one skipped without an answer keeps the triager's class and blocked_on
  All checks passed.
  fixed exit=0
  ```

- AC 3: `bash -c 'cd . && python3 scripts/todos/test_state.py | grep -E "468|869|600|All checks|FAILED"; echo exit=${PIPESTATUS[0]}'` — evidence `.sweep-evidence/g13/600-ac2.txt` (not committed), last lines:

  ```text
    PASS  468: the next sweep does not re-ask the answered todo, and does re-ask the skipped one
    PASS  worktrees lists every unarchived todo's worktrees, earlier attempts included (todo 468 F5)
    PASS  triage-args --root passes an absolute origin/main tree to the triagers (todo 468)
  All checks passed.
  exit=0
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-11-2219)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
