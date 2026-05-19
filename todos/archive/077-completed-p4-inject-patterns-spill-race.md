---
status: completed
priority: p4
issue_id: "077"
tags: [harness, hooks]
dependencies: []
---

# inject-patterns.sh spill file uses a fixed shared path

## Problem

`.claude/hooks/inject-patterns.sh` writes rule-injection overflow to a fixed
path, `/tmp/plant-id-injection-context.md`. Two hook invocations running
concurrently can overwrite each other's spill file, so the agent could read the
wrong or partial rule context.

## Findings

- Surfaced by the `kimi-review` PreToolUse gate during commit `da3e6da`
  (WARNING tier, non-blocking).
- `.claude/hooks/inject-patterns.sh` — `SPILL_FILE="/tmp/plant-id-injection-context.md"`
  (fixed path, near the `THRESHOLD=9000` block).
- Faithful port of OCRecipes' original design (same fixed-path behavior).
- Real-world risk is low: a single Claude session edits sequentially, and the
  spill path only triggers when injected rules exceed ~9 KB (multi-domain edits).

## Recommended Action

1. Give the spill file a per-invocation suffix, e.g. `/tmp/plant-id-injection-context.$$.md`
   (`$$` = PID), or `mktemp` with a stable prefix.
2. Update the truncation notice line so it points at the actual path written.
3. Update `.claude/hooks/test-inject-patterns.sh` — `SPILL_FILE` is currently a
   fixed constant in the test; switch it to glob/discover the per-PID file or
   assert on the truncation-notice path emitted in stdout.
4. Run `bash .claude/hooks/test-inject-patterns.sh` — all tests pass.

## Technical Details

- Hook: `.claude/hooks/inject-patterns.sh` (spill block)
- Test: `.claude/hooks/test-inject-patterns.sh` (`SPILL_FILE` constant)

## Acceptance Criteria

- [x] Spill file path is unique per hook invocation.
- [x] The truncation notice points at the path actually written.
- [x] `test-inject-patterns.sh` passes against the new path scheme.

## Work Log

### 2026-05-17 - Created

- Filed from the kimi-review WARNING on commit `da3e6da` (OCRecipes harness port).

### 2026-05-18 - Attempted by completing-todos skill (run 2026-05-18-2300) — SKIPPED (blocked)

- Picked up by the automated sweep. Investigation complete and a minimal fix
  was designed, but the edit is **blocked by the harness self-modification guard**.
- Designed fix (ready to apply by hand):
  - `.claude/hooks/inject-patterns.sh`: change
    `SPILL_FILE="/tmp/plant-id-injection-context.md"` →
    `SPILL_FILE="/tmp/plant-id-injection-context.$$.md"` (PID suffix → unique
    per hook invocation). The truncation notice already interpolates
    `"$SPILL_FILE"`, so criterion 2 is satisfied automatically.
  - `.claude/hooks/test-inject-patterns.sh`: replace the fixed
    `SPILL_FILE="/tmp/plant-id-injection-context.md"` constant with a glob
    `SPILL_GLOB="/tmp/plant-id-injection-context.*.md"`, and update `run_hook`
    / `check_empty` to `rm -f $SPILL_GLOB` and to `cat` each glob match.
- **Why blocked:** editing files under `.claude/hooks/` counts as the agent
  modifying its own startup harness; the auto-mode classifier hard-blocks it.
  Working around the block via `sed`/`Bash` would defeat its intent, so it was
  not attempted.
- Note: a runtime spill is currently unreachable anyway — all 11 `docs/rules/*.md`
  files total 9266 bytes and no single file path matches enough domains to cross
  the 9000-byte `THRESHOLD`. The fix is still correct defensive hygiene.
- **To complete:** a human applies the two edits above, then runs
  `bash .claude/hooks/test-inject-patterns.sh` (expect all checks pass).

### 2026-05-19 - Started by completing-todos skill (run 2026-05-19-0044)

- Re-picked up; auto mode is off so harness edits surface permission prompts
  rather than hard-blocking.

### 2026-05-19 - Implementation

- `.claude/hooks/inject-patterns.sh`: `SPILL_FILE` now
  `/tmp/plant-id-injection-context.$$.md` (`$$` = PID, unique per invocation).
  The truncation notice already interpolates `"$SPILL_FILE"`, so it now points
  at the per-PID path automatically.
- `.claude/hooks/test-inject-patterns.sh`: replaced the fixed `SPILL_FILE`
  constant with a `SPILL_GLOB="/tmp/plant-id-injection-context.*.md"`; `run_hook`
  and `check_empty` now `rm -f $SPILL_GLOB` and `run_hook` cats each glob match.
- Verification:
  - `bash .claude/hooks/test-inject-patterns.sh` → `Results: 16 passed, 0 failed` / exit 0.
  - Two `bash` invocations of `echo /tmp/...$$.md` produced PIDs 74906 and 74907 —
    distinct paths, confirming per-invocation uniqueness.

### 2026-05-19 - Completed by completing-todos skill (run 2026-05-19-0044)

- Verification: all 3 acceptance criteria passed (16/16 hook tests, per-PID path confirmed).
- Review: code-review-orchestrator dispatched (direct shell review — no shell
  specialist agent) — 0 findings, no blocking.

## Notes

p4 — correctness nicety, not a live bug. Single-session edits are sequential and
the spill path is rarely reached. Bundle with other harness polish if convenient.
