---
name: gate-harness-tests-in-ci
status: pending
priority: p2
created: 2026-05-30
tags: [harness, ci, testing, hooks]
source_review: "docs/audits/2026-05-30-harness.md"
source_finding: "F3"
---

# Gate the harness's own tests in CI

## Problem

The harness ships a real test suite and it currently **passes**:

- `.claude/hooks/test-inject-patterns.sh` (16), `test-kimi-review.sh` (20),
  `test-guard-worktree-isolation.sh` (10) — 46 hook assertions green.
- `scripts/inject/test_match_triggers.py` (34), `test_capture_trigger.py`,
  `test_capture_from_review.py` — green.

But **no CI runs any of them** (`grep -rl scripts/inject .github/workflows` and
`grep -rl hooks/test .github/workflows` both empty). The harness is the project's
quality system, and the quality system has no quality system: a future edit to a
hook (e.g. one that breaks the `jq` JSON output, silently disabling rule
injection for everyone) or to `match_triggers.py` would ship unnoticed.

## Acceptance criteria

- [ ] A CI step runs the hook self-tests (`.claude/hooks/test-*.sh`) and the
      python harness tests (`scripts/inject/test_*.py`) on every PR touching
      `.claude/**`, `scripts/inject/**`, or `docs/rules/**`.
- [ ] The step is blocking (a red harness test fails the PR).
- [ ] Document the one-command local equivalent in the harness docs so devs can
      run it before pushing.

## Notes

Could be a job inside the new `web-ci.yml`/a dedicated `harness-ci.yml`, or folded
into an existing workflow. The test scripts themselves are NOT under `.claude/`
(hook tests are, but they're run, not edited, by CI) — the workflow file is
editable directly.
