---
status: completed
priority: p4
issue_id: "068"
tags: [docs, forum, settings, flake8]
dependencies: ["065"]
---

# Fix misleading ENABLE_FORUM comment and document dual setup.cfg

## Problem

Two small documentation/comment issues introduced or exposed by PR #261:

1. The comment on `LOCAL_APPS.insert(2, "apps.forum_integration")` implies
   `apps.forum_integration` provides the `forum` app label, but it doesn't —
   `machina.apps.forum` does. The comment will mislead the next developer touching
   this code.

2. The repo has two `[flake8]` config sections in two `setup.cfg` files
   (`backend/setup.cfg` and root `setup.cfg`). Pre-commit reads the root one;
   manual `cd backend && flake8` reads the backend one. A `per-file-ignores` entry
   added to the wrong file silently does nothing under pre-commit. There is no
   cross-reference between the two files.

## Findings

- `backend/plant_community_backend/settings.py` line ~173 (post-PR #261):
  comment says "provides 'forum' app label via machina.apps.forum" next to
  `apps.forum_integration`, which does not provide that label.
- `setup.cfg` (root) and `backend/setup.cfg` both contain `[flake8]` sections.
  Discovered while fixing flake8 errors in PR #261 — adding the suppression to
  `backend/setup.cfg` had no effect; it needed to go in the root `setup.cfg`.
- Surfaced during `/review` of PR #261 (2026-05-09).

## Recommended Action

1. In `backend/plant_community_backend/settings.py`, replace:

   ```python
   if ENABLE_FORUM:
       # Machina-based legacy forum (provides 'forum' app label via machina.apps.forum)
       LOCAL_APPS.insert(2, "apps.forum_integration")
   ```

   with:

   ```python
   if ENABLE_FORUM:
       # Integration shim for Machina; apps.forum excluded to avoid duplicate 'forum' label
       LOCAL_APPS.insert(2, "apps.forum_integration")
   ```

2. At the top of `backend/setup.cfg`'s `[flake8]` section, add:

   ```ini
   # NOTE: pre-commit reads the root setup.cfg, not this file.
   # Add per-file-ignores for pre-commit here: /setup.cfg (repo root).
   ```

## Technical Details

- `backend/plant_community_backend/settings.py`: comment is in the ENABLE_FORUM
  LOCAL_APPS block, a few lines after the `ENABLE_FORUM = config(...)` line.
- `backend/setup.cfg`: `[flake8]` section is at the top of the file.
- Root `setup.cfg` is what `pre-commit run flake8` reads because pre-commit
  invokes flake8 from the repo root, and flake8 searches upward from that
  directory for its first config file.

## Acceptance Criteria

- [x] Comment on `LOCAL_APPS.insert(2, "apps.forum_integration")` no longer implies
      that `apps.forum_integration` provides the `forum` app label.
- [x] `backend/setup.cfg` `[flake8]` section has a note pointing developers to the
      root `setup.cfg` for pre-commit-visible suppressions.
- [x] `pre-commit run flake8 --files backend/plant_community_backend/settings.py`
      still passes after the comment change.

## Work Log

### 2026-05-09 - Created from PR #261 review

- Two small comment/documentation issues identified that do not warrant blocking
  the PR but should not be forgotten.

### 2026-05-09 - Started by completing-todos skill (run 2026-05-09-1405)

- Picked up by automated workflow.

### 2026-05-09 - Completed by completing-todos skill (run 2026-05-09-1405)

- Verification: all 3 acceptance criteria passed.
  - `settings.py` line 200: new comment confirmed via grep.
  - `backend/setup.cfg`: note line confirmed via head.
  - `pre-commit run flake8 --files backend/plant_community_backend/settings.py` → `Passed`.
- Review: 3 findings total, 0 blocking (1 low repaired: removed leading `/` from path reference; 2 info accepted).
- Known issues — accepted at completion:
  - [info] `backend/setup.cfg`: note doesn't mention that `max-line-length`/`extend-ignore` come from inline pre-commit hook args, not from either setup.cfg. Low documentation value.
  - [info] `settings.py` line 200: comment could name `machina.apps.forum` explicitly as the label holder. Minor clarity nuance, not an error.
