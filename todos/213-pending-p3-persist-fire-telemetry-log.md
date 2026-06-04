---
status: pending
priority: p3
issue_id: "213"
tags: [harness, jit-injection, telemetry]
dependencies: []
source_review: "docs/audits/2026-06-03-harness.md"
source_finding: "L1"
---

# Persist fire telemetry log to a stable path

## Problem

`match_triggers.py` and `report_fires.py` both default to `/tmp/inject-fires.log`,
which is cleared on reboot. Cross-session trend analysis ("how often does trigger X
fire?", "which triggers are stale?") is impossible with the current default. The
writer and reader are correctly wired; only the default path is wrong.

## Findings

- `scripts/inject/match_triggers.py:178`: `log_path = os.environ.get("INJECT_FIRES_LOG", "/tmp/inject-fires.log")`
- `scripts/inject/report_fires.py:18`: same default
- The env-var override (`INJECT_FIRES_LOG`) exists but is not documented in CLAUDE.md,
  the usage string, or any setup guide beyond inline code comments.
- Source: 2026-06-03 harness audit (L1), verified via direct Read of both files.

## Recommended Action

1. Choose a persistent default path, e.g. `~/.claude/inject-fires.log` (lives in
   the user's Claude config dir, survives reboots, not committed to the repo).
2. Update the default in `match_triggers.py` and `report_fires.py`.
3. Add a one-liner to CLAUDE.md under the Harness section noting the log path and
   how to run `report_fires.py` to see trigger fire counts.

## Technical Details

```python
# Suggested default (both files):
import os
_DEFAULT_LOG = os.path.join(os.path.expanduser("~"), ".claude", "inject-fires.log")
log_path = os.environ.get("INJECT_FIRES_LOG", _DEFAULT_LOG)
```

The `~/.claude/` directory already exists (Claude Code's config dir). No mkdir
needed. The log file is plain text (one TSV line per fire: timestamp, rel-path,
trigger-id) — safe to let it grow indefinitely for a small project.

## Acceptance Criteria

- [ ] `match_triggers.py` and `report_fires.py` default to a non-`/tmp` path that
  survives a reboot
- [ ] `python3 scripts/inject/report_fires.py` shows accumulated fire counts from
  previous sessions after a reboot
- [ ] CLAUDE.md documents the log path and `report_fires.py` invocation

## Work Log

### 2026-06-03 - Created from harness audit L1

- Finding: ephemeral `/tmp` default makes historical trend analysis impossible.
- The mechanism (writer + reader) is correctly wired; only the default path needs
  updating.
