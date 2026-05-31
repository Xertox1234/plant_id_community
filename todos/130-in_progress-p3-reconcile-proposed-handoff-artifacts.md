---
name: reconcile-proposed-handoff-artifacts
status: pending
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

- [ ] For each `.proposed`/handoff file in `scripts/inject/`, confirm whether it
      is already applied (`diff` against the live target) and delete it if so,
      or clearly mark it pending if not.
- [ ] Fix the `inject-patterns.sh` header so it no longer claims to be a proposed
      handoff artifact (it is the live hook). (Self-mod-blocked — handoff edit.)
- [ ] No `.proposed` file remains that is byte-identical to its applied target.

## Notes

Low risk, pure hygiene. The header edit needs Auto Mode disabled.
