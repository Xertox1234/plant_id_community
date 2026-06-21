---
status: completed
priority: p2
issue_id: "227"
tags: [harness, hooks, code-quality]
dependencies: []
---

# Add PostToolUse format/lint hook with exit-2 stderr feedback

## Problem

Formatting and lint errors are currently caught at commit time (kimi-review gate,
pre-commit hooks) instead of edit time. The 2026 community-consensus pattern is a
PostToolUse hook that formats the edited file and feeds lint errors back to Claude
via exit code 2 + stderr, so it self-corrects on the next turn. This is the one
consensus hook pattern missing from this harness, and it would reduce the
"formatter reformats whole files at commit" friction (todo 117 territory).

## Findings

- No PostToolUse hooks exist in `.claude/settings.json` (only PreToolUse + Stop).
- Boris Cherny's published workflow and the official hooks guide both use
  PostToolUse auto-format with exit-2 stderr feedback
  (<https://code.claude.com/docs/en/hooks-guide>).
- Guidance: cheap formatters per-edit; typecheck at Stop or commit; full suite in
  CI. Per-edit typecheck (10-30s) is explicitly discouraged.
- Stack mapping: Python → `ruff format` + `ruff check --fix` (verify ruff is in
  backend tooling; repo currently uses flake8 — pick whichever is configured),
  TS/TSX → `prettier --write` + `eslint --fix`, Dart → `dart format`.
- Discovery source: 2026-06-10 harness audit, community research phase.

## Recommended Action

1. Write `.claude/hooks/format-on-edit.sh`: read PreToolUse-style event JSON from
   stdin, extract `tool_input.file_path`, dispatch by extension, run the
   formatter; on remaining lint errors print them to stderr and exit 2 so Claude
   sees and fixes them. Fail-open (exit 0) when the tool is missing.
2. Register under `PostToolUse` with matcher `Edit|Write|MultiEdit`, timeout ~30s.
3. Add `test-format-on-edit.sh` alongside the other hook tests.
4. Confirm interaction with the kimi-review commit gate (formatted-at-edit files
   should shrink commit-time diffs, not grow them).

## Technical Details

- `.claude/settings.json` hooks block; follow the existing
  `cd "$(git rev-parse --show-toplevel ...)"` invocation pattern.
- Only format the file from the event — never repo-wide (see
  feedback_bulk_mechanical_edits memory; whole-file reformats caused friction,
  todo 117).
- `.claude/` edits require Auto Mode disabled (classifier self-mod block).

## Acceptance Criteria

- [x] Editing a .py/.ts/.dart file with a formatting violation results in the file
      being auto-formatted after the edit. (done 2026-06-21 — friction-safe LINT-FIX,
      not whole-file format, per user decision + todos 087/117: Python `ruff F401`
      (demonstrated live this session — stripped unused imports from edited files),
      TS `eslint --fix`, Dart `dart fix --apply`. Verified `eslint --fix` makes ZERO
      changes to clean committed code = no whole-file reformat.)
- [x] An unfixable lint error surfaces back to Claude (verify by observing exit-2
      stderr in a test session). (done 2026-06-21 — exit-2 + stderr for residual
      Python F401 (test #7 + live) and residual TS eslint errors (test #9).)
- [x] Hook test script passes; missing formatter binaries cause silent skip. (done
      2026-06-21 — `test-format-on-edit.sh` 13/13 pass; fail-open exit-0 tested for
      missing ruff, eslint, AND dart.)

## Work Log

### 2026-06-21 - Completed: extended the existing Python hook to TS + Dart (run 2026-06-21-1412)

The premise "no PostToolUse hooks exist" was STALE — `format-on-edit.sh` already
existed as the **Python branch** of this todo (ruff F401 fix + exit-2 residual,
registered in `.claude/settings.json`). It was deliberately scoped to lint-FIX,
NOT whole-file format, because prettier/black/dart-format reformatting caused the
commit friction in todos 087/117.

**User decision (asked):** extend friction-safe to TS + Dart — lint-autofix only,
NOT `prettier --write` / `dart format`.

- Refactored `format-on-edit.sh` into a per-stack dispatch (Python branch
  preserved verbatim): `web/src/*.ts[x]` → `eslint --fix` + exit-2 on residual
  eslint errors; `plant_community_mobile/*.dart` (non-generated) → `dart fix
  --apply` (apply-only — `dart fix` has no own-domain residual to report; broader
  `dart analyze` is the flutter-analyze CI gate's job, and per-edit would be noise).
- Added test seams `FORMAT_ON_EDIT_{ESLINT,DART}` and 6 tests to
  `test-format-on-edit.sh` (TS clean/residual/fail-open, Dart invoked/generated-skip/
  fail-open) → **13/13 pass**.
- Confirmed **`eslint --fix` is friction-safe**: zero changes to clean committed
  code (the web project formats with prettier separately; eslint carries
  code-quality rules, not stylistic ones). `dart fix` verified single-file + fast
  (~0.9s).
- Updated the settings.json statusMessage ("Auto-fixing lint (py imports / ts /
  dart)...").

Self-review note: while live-testing I ran `git checkout web/src/utils/validation.ts`
to "undo eslint" — but HEAD still had the pre-M12 file, so the checkout reverted
todo-225's uncommitted M12 deletion. Caught immediately, re-applied M12, re-verified
(type-check clean, 44 targeted tests pass). Lesson logged: never `git checkout` a
file carrying uncommitted work to isolate a hook's effect — test the hook on an
untouched file instead.

### 2026-06-10 - Created

- Filed from harness audit session (recommendation #4).
