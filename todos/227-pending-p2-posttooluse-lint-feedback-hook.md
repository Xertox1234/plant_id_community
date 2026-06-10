---
status: pending
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

- [ ] Editing a .py/.ts/.dart file with a formatting violation results in the file
      being auto-formatted after the edit.
- [ ] An unfixable lint error surfaces back to Claude (verify by observing exit-2
      stderr in a test session).
- [ ] Hook test script passes; missing formatter binaries cause silent skip.

## Work Log

### 2026-06-10 - Created

- Filed from harness audit session (recommendation #4).
