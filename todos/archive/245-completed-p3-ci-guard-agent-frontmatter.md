---
status: completed
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

- [x] Validator script exists and is dependency-free (stdlib only).
- [x] Positive control: it PASSES on the current 17 `.claude/agents/*.md` (all loadable
      after todo 229).
- [x] Negative control: it FAILS on a deliberately-broken fixture (a `description` with a
      bare multi-line `<example>` block), pointing at the offending file/line.
- [x] Wired into `.pre-commit-config.yaml` as a local hook scoped to
      `^\.claude/agents/.*\.md$`; `pre-commit run <hook-id> --all-files` is green.

## Work Log

### 2026-06-24 - Created

- Filed from todo 229 wrap-up: the reviewer fleet was silently non-functional and
  nothing guarded against it. This adds the missing write-time check.

### 2026-07-13 - Started by completing-todos skill (run 2026-07-13-0237)

- Picked up by automated workflow.
- Note: the file count has drifted since this todo was filed — there are 14
  `.claude/agents/*.md` today, not 17 (4 generic reviewers were retired into
  `cross-cutting-reviewer` per todo 244). The acceptance criterion's intent
  (passes on the current real set) holds regardless of the stale count.
- Wrote `scripts/inject/check_agent_frontmatter.py` (stdlib only: `re`, `sys`,
  `pathlib`), following the existing `scripts/inject/route_domains.py`
  convention — a pure `check_frontmatter(path, lines)` core function separate
  from `main()`, so it's testable without touching the filesystem.
- Wrote `scripts/inject/test_check_agent_frontmatter.py` (unittest, matching
  `test_route_domains.py`'s style — standalone-executable, no pytest
  dependency).
- Dry-ran the discriminator against all 14 real files with a throwaway awk
  script before writing any Python, to confirm zero false positives ahead of
  time.
- Verification:
  - `python3 scripts/inject/test_check_agent_frontmatter.py -v` → 5 passed
    (positive control across all 14 real files; 4 negative-control fixtures:
    bare `<example>` block pointing at line 4, missing closing delimiter,
    missing required key, blank line in frontmatter).
  - `python3 scripts/inject/check_agent_frontmatter.py; echo $?` → exit 0
    against the real repo.
  - `pre-commit run check-agent-frontmatter --all-files` →
    "Validate .claude/agents/*.md frontmatter is loadable.......................Passed".

### 2026-07-13 - Completed by completing-todos skill (run 2026-07-13-0237)

- Review: code-review-orchestrator (cross-cutting-reviewer) → 2 medium, 1 low,
  1 info. Repaired all 3 actionable findings.
- Repair (medium): added `test_empty_file_fails_cleanly` and
  `test_no_opening_delimiter_fails_cleanly` — closes the untested `not lines`
  operand of the line-29 `or` guard (reviewer's mutation test showed dropping
  it causes an unhandled `IndexError` on an empty file with none of the
  original 5 tests catching it).
- Repair (medium): added a `SubprocessTests` class (`test_real_repo_passes`,
  `test_broken_fixture_fails_with_offending_line`,
  `test_missing_agents_dir_fails`) that drives the actual script/exit-code
  contract the pre-commit hook depends on — matching
  `test_route_domains.py`'s `SubprocessTests` pattern that this file's
  docstring already claimed to follow but didn't.
- Repair (low): `.pre-commit-config.yaml`'s "Hook Execution Order" summary
  comment updated (item 4) to mention agent-frontmatter validation.
- Re-verification: `python3 scripts/inject/test_check_agent_frontmatter.py -v`
  → 10 passed. `pre-commit run check-agent-frontmatter --all-files` → still
  green.

#### Known issues — accepted at completion

- **[info]** This new test file isn't wired into
  `.github/workflows/harness-ci.yml`'s explicit "Python inject tests" step.
  Not applied: the todo's own Recommended Action marks CI wiring
  "(Optional)" and it's absent from the Acceptance Criteria; `test_route_domains.py`
  has the identical gap already, so this continues an existing pattern rather
  than introducing a new one.
