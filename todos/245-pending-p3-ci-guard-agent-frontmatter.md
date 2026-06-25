---
status: pending
priority: p3
issue_id: "245"
tags: [harness, ci, agents, pre-commit, maintainability]
dependencies: []
---

# Add a CI/pre-commit guard that every .claude/agents/*.md frontmatter is loadable

## Problem

Todo 229 found that 14 of 17 `.claude/agents/*.md` had **silently failed to load**
for an unknown period: their `description:` frontmatter was a multi-line block with a
bare `<example>` at column 0, which the Claude Code agent loader rejects. Nothing in
the toolchain caught it — the broken fleet was discovered only by accident while
trying to dispatch a reviewer. The fix (229) is one edit away from regressing: any new
agent, or an editor re-expanding a description, reintroduces the same unloadable shape
with no signal until someone happens to dispatch the agent.

Add a deterministic guard so this can't recur unnoticed.

## Recommended Action

1. Add a small validator script (e.g. `scripts/inject/check_agent_frontmatter.py`)
   that, for each `.claude/agents/*.md`, asserts the frontmatter is the loadable shape:
   - delimited by `---` / `---`;
   - every line between the delimiters matches `^[a-z_][a-z0-9_]*:` (a single-physical-line
     `key: value` field) — **no blank lines, no continuation lines, no bare `<example>`/
     tag lines** (this is the exact discriminator between the agents that load and those
     that don't; do NOT use strict `yaml.safe_load`, which also rejects the *working*
     agents' colon/quote-bearing single-line descriptions);
   - `name` and `description` keys are present.
   Exit non-zero listing any offending file + line.
2. Wire it into `.pre-commit-config.yaml` as a `repo: local` hook (there are already
   several local-hook blocks, e.g. block-env-files, eslint-web), scoped with
   `files: ^\.claude/agents/.*\.md$`.
3. (Optional) Also run it in CI for defense-in-depth if agent files can be edited
   outside the pre-commit path.

## Technical Details

- Editing `.pre-commit-config.yaml` (repo root) and adding `scripts/` files is NOT
  Auto-Mode-gated (that gate is `.claude/` + root `.mcp.json`/`CLAUDE.md`). Only the
  agent files being *validated* live under `.claude/`.
- Reference the discriminator and fix from todo 229
  (`todos/archive/229-completed-p3-fix-broken-reviewer-agent-frontmatter.md`) and the
  one-off validator in that work (`scratchpad/fix_agent_frontmatter.py::structural_ok`).
- Keep it cheap and dependency-free (stdlib only) — it runs on every commit touching
  an agent file.

## Acceptance Criteria

- [ ] Validator script exists and is dependency-free (stdlib only).
- [ ] Positive control: it PASSES on the current 17 `.claude/agents/*.md` (all loadable
      after todo 229).
- [ ] Negative control: it FAILS on a deliberately-broken fixture (a `description` with a
      bare multi-line `<example>` block), pointing at the offending file/line.
- [ ] Wired into `.pre-commit-config.yaml` as a local hook scoped to
      `^\.claude/agents/.*\.md$`; `pre-commit run <hook-id> --all-files` is green.

## Work Log

### 2026-06-24 - Created

- Filed from todo 229 wrap-up: the reviewer fleet was silently non-functional and
  nothing guarded against it. This adds the missing write-time check.
