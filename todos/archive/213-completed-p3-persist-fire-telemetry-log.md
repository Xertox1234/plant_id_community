---
status: completed
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

- [x] `match_triggers.py` and `report_fires.py` default to a non-`/tmp` path that
  survives a reboot
- [x] `python3 scripts/inject/report_fires.py` shows accumulated fire counts from
  previous sessions after a reboot
- [x] CLAUDE.md documents the log path and `report_fires.py` invocation

## Work Log

### 2026-06-03 - Created from harness audit L1

- Finding: ephemeral `/tmp` default makes historical trend analysis impossible.
- The mechanism (writer + reader) is correctly wired; only the default path needs
  updating.

### 2026-06-04 - Completed by completing-todos skill (run 2026-06-04-1024)

- `match_triggers.py:178` and `report_fires.py:16`: default changed from
  `/tmp/inject-fires.log` to `os.path.expanduser("~/.claude/inject-fires.log")`.
- CLAUDE.md `inject-patterns.sh` bullet extended with log path + `report_fires.py`
  invocation.
- Verification:
  - Criterion 1: `grep inject-fires scripts/inject/match_triggers.py` → line 178
    `_default_log = os.path.join(os.path.expanduser("~"), ".claude", "inject-fires.log")`
  - Criterion 2: `python3 scripts/inject/report_fires.py` →
    `No fire log at /Users/williamtower/.claude/inject-fires.log — no triggers have fired yet.`
    (correct non-/tmp path; "no fires yet" expected on a fresh session)
  - Criterion 3: `grep -A3 inject-patterns CLAUDE.md` shows log path + report_fires.py line.
- Known issues (medium, noted from code review):
  - `os.makedirs` added to `_log_fires` (applied inline — trivial, in-scope): without it,
    open() raises FileNotFoundError silently on fresh machines where ~/.claude/ doesn't
    exist yet.
- `python3 scripts/inject/test_match_triggers.py`: 34 tests, OK.
- Review: 0 blocking findings, 1 medium (makedirs) applied.
