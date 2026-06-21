---
status: completed
priority: p3
issue_id: "232"
tags: [harness, hooks, ruff, testing]
dependencies: []
---

# Enforce that the format-on-edit skip-list matches setup.cfg F401 ignores

## Problem

The PostToolUse hook `.claude/hooks/format-on-edit.sh` (PR #372) hardcodes a
skip-list of 7 backend files whose unused imports are intentional (re-exports /
import-smoke-test), mirroring `setup.cfg [flake8] per-file-ignores`. Nothing
enforces that the two lists stay in sync. The dangerous direction: if someone
adds a **new** intentional-re-export file to `setup.cfg` (F401) but not to the
hook, the hook will strip imports the author meant to keep — silently breaking a
re-export, with no test to catch it.

## Findings

- `.claude/hooks/format-on-edit.sh` — `case "$REL" in … exit 0 ;; esac` lists the
  7 skip paths; a comment says "keep the two lists in sync" but there is no check.
- `setup.cfg` — `[flake8] per-file-ignores` is the source of truth for which files
  carry intentional F401. As of PR #372 these are: `apps/blog/api/viewsets.py`,
  `apps/blog/tests/test_analytics.py`, `apps/plant_identification/models.py`,
  `apps/plant_identification/views.py`, `apps/users/views.py`,
  `test_django_imports.py` (+ `plant_community_backend/settings.py`, which the hook
  also skips for its non-standard import order).
- `.claude/hooks/test-format-on-edit.sh` asserts a skip-list path is left
  untouched, but only for one hardcoded path — it does not detect a setup.cfg
  entry that is missing from the hook.
- Discovery source: self-review of PR #372 (2026-06-14), issue #1.

## Recommended Action

1. Add a check (in `test-format-on-edit.sh` or a small `scripts/` helper) that
   parses the `F401` entries from `setup.cfg [flake8] per-file-ignores` and asserts
   the set equals the hook's skip-list (the hook may legitimately include extras
   like `settings.py` — assert setup.cfg's F401 set is a **subset** of the hook
   skip-list, so a new ignore that isn't mirrored fails CI).
2. Wire it into the `Hook self-tests` step of `.github/workflows/harness-ci.yml`
   (already runs `test-format-on-edit.sh`).
3. Consider extracting the skip-list to a single shared source (e.g. a generated
   list) so the hook reads it rather than duplicating — only if step 1 proves too
   brittle; a subset-assertion test is the lighter fix.

## Technical Details

- Parsing `setup.cfg`: the `per-file-ignores` block is multi-line `path: CODES`;
  select lines whose CODES contain `F401`.
- The hook's skip-list is a bash `case` — simplest to compare is to have the test
  source the same path list from a single place, or to grep both and diff the sets.

## Acceptance Criteria

- [x] A test fails when a file with an `F401` per-file-ignore in `setup.cfg` is not
      present in the hook's skip-list. (done 2026-06-21 — DEMONSTRATED: injecting a
      fake `apps/fake_reexport.py: F401` into setup.cfg made the test report
      `FAIL: skip-list ⊇ setup.cfg F401 ignores` (PASS=14 FAIL=1); reverted →
      all-pass. A "teeth" assertion also pins the detection logic directly.)
- [x] The test runs in `harness-ci.yml` and passes on the current (in-sync) state.
      (done 2026-06-21 — added as test #14 in `test-format-on-edit.sh`, which
      `harness-ci.yml:50` already runs in the Hook self-tests step; 15/15 pass.)

## Work Log

### 2026-06-21 - Completed (run 2026-06-21-1412)

- Added `SKIPLIST-START`/`SKIPLIST-END` sentinels around the hook's skip-list in
  `format-on-edit.sh` so the test can parse it robustly (the dispatch `case
  backend/*.py)` would otherwise false-match a naive regex).
- Added test #14 to `test-format-on-edit.sh`: parses setup.cfg `[flake8]
  per-file-ignores` for F401 entries (configparser, `interpolation=None`) and the
  hook skip-list (between sentinels, normalized to backend-relative), and asserts
  the F401 set ⊆ the skip-list. Chose the lighter **subset-assertion** over
  extracting a shared source (per the todo's step-3 guidance — the hook may carry
  extras like `settings.py`). Includes a non-vacuous guard (CFG must be non-empty)
  and a "teeth" assertion (an unmirrored entry is detected).
- No `harness-ci.yml` change needed — line 50 already runs `test-format-on-edit.sh`.
- Verified: 15/15 pass in-sync; injecting a fake `apps/fake_reexport.py: F401`
  flips it to FAIL (1), reverted → pass.

### 2026-06-14 - Filed

- Created from self-review of PR #372 (issue #1). Skip-list ↔ setup.cfg sync is
  currently maintained only by a comment.

## Notes

- p3: latent footgun, not an active defect — the lists are in sync today. Becomes
  relevant the next time someone adds an intentional re-export module.
- Related: PR #372; `.claude/hooks/format-on-edit.sh`; todo 227 (broader edit-time
  lint hook).
