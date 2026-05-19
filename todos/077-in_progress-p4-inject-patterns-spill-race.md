---
status: in_progress
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

- [ ] Spill file path is unique per hook invocation.
- [ ] The truncation notice points at the path actually written.
- [ ] `test-inject-patterns.sh` passes against the new path scheme.

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

## Notes

p4 — correctness nicety, not a live bug. Single-session edits are sequential and
the spill path is rarely reached. Bundle with other harness polish if convenient.
