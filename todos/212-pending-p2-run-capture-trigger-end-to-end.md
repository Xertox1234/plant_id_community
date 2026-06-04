---
status: pending
priority: p2
issue_id: "212"
tags: [harness, jit-injection, auto-capture]
dependencies: []
source_review: "docs/audits/2026-06-03-harness.md"
source_finding: "M1"
---

# Run auto-capture trigger path end-to-end in a live session

## Problem

The codify→capture→trigger loop has never completed end-to-end in production. All
8 triggers in `docs/rules/triggers.json` are hand-seeded with `severity: "warn"`;
zero `candidate` triggers exist. The 05-30 audit said this was unproven; the 06-03
audit confirms it remains unproven despite the machinery being fully in place.

## Findings

- `docs/rules/triggers.json` has 8 entries, all `"severity": "warn"`, all from manual
  edits (git log shows 3 commits touching the file: initial seed `46234f1`, codify
  session `979001e`, and another codify commit `c82a205` — none from `capture_trigger.py`
  being invoked programmatically by `capture_from_review.py`).
- Trigger #8 (`celery-task-prefixed-decorator-option`, added 2026-06-02) was
  hand-written in commit `c82a205` ("triggers.json: JIT write-time trigger for the
  task_*-prefixed Celery option") — `capture_trigger.py --severity candidate` was not
  called.
- `capture_trigger.py` exists and supports `--severity candidate` for auto-captured
  triggers. `capture_from_review.py` wires the code-review output into it. Neither
  has produced a `candidate` trigger in the wild.
- Source: 2026-06-03 harness audit (M1), verified via `git log` + `git show c82a205`.

## Recommended Action

1. In the next session that finds a recurring mistake worth capturing (a real bug
   that bit us, not a hypothetical), use `capture_from_review.py` or invoke
   `capture_trigger.py --severity candidate` directly — do NOT hand-edit
   `triggers.json`.
2. After the candidate trigger is in place, promote it to `warn` via
   `capture_trigger.py --update --severity warn` once verified.
3. Document the first successful end-to-end run in `docs/LEARNINGS.md`.

## Technical Details

The intended loop:

1. Code review agent finds a recurring-mistake class worth JIT-injecting.
2. `capture_from_review.py` (or codify) calls `capture_trigger.py --severity candidate`.
3. `capture_trigger.py` appends a `"severity": "candidate"` trigger to `triggers.json`.
4. `match_triggers.py` injects it on the next matching edit (same as `warn`).
5. After observing it work correctly, promote to `warn`.

The machinery is fully in place; the loop has just never been exercised outside
of a hand-edit session.

## Acceptance Criteria

- [ ] At least one `"severity": "candidate"` trigger exists in `triggers.json`,
  added via `capture_trigger.py` (not hand-edited)
- [ ] `git log -- docs/rules/triggers.json` shows a commit with message referencing
  `capture_trigger.py` or `capture_from_review.py`

## Work Log

### 2026-06-03 - Created from harness audit M1

- Finding: 05-30 audit said auto-capture path unproven; 06-03 confirms still unproven.
- All 8 triggers hand-seeded; capture_trigger.py never invoked in production.
