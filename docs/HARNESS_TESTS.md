# Harness Tests

The harness ships a test suite covering the Claude Code hooks and the
`scripts/inject/` pipeline. CI runs these automatically on every PR that
touches `.claude/hooks/`, `scripts/inject/`, `docs/rules/`, or
`.github/workflows/harness-ci.yml` itself (see that file).

## Run locally (one command)

From the repo root:

```bash
bash .claude/hooks/test-inject-patterns.sh && \
bash .claude/hooks/test-kimi-review.sh && \
bash .claude/hooks/test-guard-worktree-isolation.sh && \
python3 scripts/inject/test_match_triggers.py && \
python3 scripts/inject/test_capture_trigger.py && \
python3 scripts/inject/test_capture_from_review.py
```

No package installs needed — all tests use the stdlib and the vendored scripts.

## What is tested

| File | Tests |
|------|-------|
| `.claude/hooks/test-inject-patterns.sh` | Rule injection (16 assertions) |
| `.claude/hooks/test-kimi-review.sh` | Commit-gate hook + engine unit tests (20 assertions) |
| `.claude/hooks/test-guard-worktree-isolation.sh` | Worktree isolation guard (10 assertions) |
| `scripts/inject/test_match_triggers.py` | Trigger matching (34 cases) |
| `scripts/inject/test_capture_trigger.py` | Trigger capture from history |
| `scripts/inject/test_capture_from_review.py` | Trigger capture from review output |
