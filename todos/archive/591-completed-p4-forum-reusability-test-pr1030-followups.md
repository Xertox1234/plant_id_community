---
status: completed
priority: p4
issue_id: "591"
tags: [todos, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-11
---

# Follow-ups from PR #1030 (todo 560)

## Problem

Todo-sweep run 2026-10-11-1448 merged PR #1030 (the wagtail_forum reusability import guard). Its review rounds reported the non-blocking
findings below. The curator merged duplicates and checked each item against main; the refuter dismissed
what is listed as dropped. Line numbers are as of the PR head, so re-check each against main before acting on it.

## Findings

PR #1030 (todo sweep run 2026-10-11-1448, group g6, todos 560); follow-ups: verified.

1. **low** `backend/packages/wagtail_forum/wagtail_forum/tests/test_reusability.py:27` host_import_lines adds one entry per regex hit, not one per line. A line with both an import and a quoted 'apps.' path (e.g. `from apps.x import y  # 'apps.z'`) shows up twice in offenders as file:N, file:N. Only the failure message is affected; pass/fail is not. | also: host_import_lines appends one entry per regex hit, not per line. A line with both an import and a quoted path (e.g. `from apps.x import y  # 'apps.z'`) shows up twice in offenders as `file:N, file:N`. This only affects the failure message, not the pass/fail result.
2. **low** `backend/packages/wagtail_forum/wagtail_forum/tests/test_reusability.py:19` The comment credits 'isort and flake8 (pre-commit)' with splitting the uncovered forms onto their own lines. flake8 only reports E701/E702 and never rewrites code, and isort does not split `if X: from ...`. Black does the splitting. Which forms 'the first two' means is also unclear. | also: The comment says isort and flake8 'split the first two onto their own lines'. flake8 never splits anything: it rejects `import os; import apps.x` (E702) and `if X: from apps.y import z` (E701). Which 'first two' it means is also unclear (the semicolon import and the comma import?).

## Acceptance Criteria

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log

### 2026-10-11 - Filed from todo-sweep run 2026-10-11-1448

Follow-ups for PR #1030 (todo 560).

### 2026-10-11 - Implemented by the todo sweep (run 2026-10-11-2219)

- Finding 1 fixed: `host_import_lines` in `backend/packages/wagtail_forum/wagtail_forum/tests/test_reusability.py`
  now names each offending line once, however many regex hits it has. New test
  `test_host_import_lines_names_a_line_with_two_hits_once` pins `from apps.x import y  # 'apps.z'` to `[2]`
  (it was `[2, 2]`); only the failure message changes, pass/fail never did.
- Finding 2 fixed: the HOST_IMPORT comment now says what pre-commit actually does, checked by running the
  tools: Black splits `import os; import apps.x` and `if X: from apps.y import z`, isort (`--profile black`)
  splits `import x, apps.y`, and flake8 rewrites nothing (it only reports E701/E702).

### 2026-10-11 - Verified by the todo sweep (run 2026-10-11-2219)

- AC 1: `python3 scripts/todos/slot_env.py --main-root . 3 -- backend/venv/bin/python -m pytest backend/packages/wagtail_forum/wagtail_forum/tests/test_reusability.py -v --create-db -p no:cacheprovider` — evidence `.sweep-evidence/g9/591-ac0.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 21 passed, 2 warnings in 0.28s ========================
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-11-2219)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
