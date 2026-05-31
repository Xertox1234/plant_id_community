---
name: reconcile-proposed-handoff-artifacts
status: completed
priority: p3
created: 2026-05-30
tags: [harness, drift, hygiene]
source_review: "docs/audits/2026-05-30-harness.md"
source_finding: "F6"
---

# Reconcile stale .proposed / handoff artifacts

## Problem

`.claude/hooks/inject-patterns.sh:8-19` still reads "PROPOSED v1 … ships as a
handoff artifact. Apply: `cp scripts/inject/inject-patterns.sh.proposed …`" — but
`diff -q` shows the installed hook is IDENTICAL to the `.proposed` file: it was
already applied. Several handoff artifacts linger in `scripts/inject/`
(`inject-patterns.sh.proposed`, `codify-SKILL.md.proposed`,
`codify-capture-step.md`). A reader cannot tell applied from pending.

## Acceptance criteria

- [x] For each `.proposed`/handoff file in `scripts/inject/`, confirm whether it
      is already applied (`diff` against the live target) and delete it if so,
      or clearly mark it pending if not.
- [x] Fix the `inject-patterns.sh` header so it no longer claims to be a proposed
      handoff artifact (it is the live hook). (Self-mod-blocked — handoff edit.)
- [x] No `.proposed` file remains that is byte-identical to its applied target.

## Work Log

### 2026-05-31 - Completed by completing-todos skill (run 2026-05-31-0157)

**Criterion 1 — artifact reconciliation:**

- `scripts/inject/inject-patterns.sh.proposed` → `diff -q` vs `.claude/hooks/inject-patterns.sh`: IDENTICAL → deleted via `git rm`
- `scripts/inject/codify-SKILL.md.proposed` → `diff -q` vs `.claude/skills/codify/SKILL.md`: IDENTICAL (exit 0) → deleted via `git rm`
- `scripts/inject/codify-capture-step.md` → Step 5b already present in live skill (grep confirms line 122) → deleted via `rm`
All three were already applied. Zero pending proposed artifacts remain.

**Criterion 2 — inject-patterns.sh header fix (self-mod-blocked handoff):**
Lines 8–19 of `.claude/hooks/inject-patterns.sh` still read:
  `# PROPOSED v1 (just-in-time mistake injection). Changes vs current: ...`
  `# This file is .claude self-mod-blocked, so it ships as a handoff artifact. Apply: ...`
These lines are stale — the hook is the live copy; the .proposed file is gone.
ACTION (requires Auto Mode disabled): Replace lines 8–19 with:
  `# Just-in-time mistake injection — injects domain rules + matched recurring-mistake`
  `# warnings before Edit/Write. Features: kill switch, deduped domain rules, triggers.`

**Criterion 3 — no identical .proposed files remain:**
`ls scripts/inject/*.proposed` → `no matches found` ✓

### 2026-05-31 - Completed by completing-todos skill (run 2026-05-31-1812)

- Criterion 2 (header fix): Auto Mode disabled by user; removed stale "PROPOSED v1" block (lines 8–19) from `.claude/hooks/inject-patterns.sh`, replaced with 2-line description of live hook behaviour.
- Verification: all 3 acceptance criteria confirmed with command output (header clean, no *.proposed files in scripts/inject/).
- Review: pure comment-only change, no logic touched; no code review dispatched.

## Notes

Low risk, pure hygiene. The header edit needs Auto Mode disabled.
