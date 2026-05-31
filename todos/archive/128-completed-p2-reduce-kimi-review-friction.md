---
name: reduce-kimi-review-friction
status: in_progress
priority: p2
created: 2026-05-30
tags: [harness, kimi-review, commit-gate]
source_review: "docs/audits/2026-05-30-harness.md"
source_finding: "F4"
---

# Reduce kimi-review friction so skipping isn't the easy path

## Problem

`kimi-review.sh` is the only gate that can *block* bad code, but its bypass is
pre-authorized: `.claude/settings.local.json` allow-lists
`Bash(SKIP_KIMI_REVIEW=1 git commit *)`. It is also fail-open by design
(`kimi-review.sh:15`). Memory `commit_hook_friction` documents recurring friction
(formatter reformats whole files — todo 117 still open) that pushes toward the
skip. A gate whose skip is the path of least resistance gives probabilistic, not
guaranteed, protection.

(Note: actual skip *rate* is unmeasurable — the env var leaves no commit trace.
This is a structural fix, not a metrics chase.)

## Acceptance criteria

- [ ] Resolve or link the formatter friction (todo 117) so a normal commit does
      not trigger whole-file reformat noise.
- [ ] Confirm kimi-review's median wall-time on a typical staged diff is low
      enough that running it is cheaper than reasoning about whether to skip
      (record the number).
- [ ] Decide deliberately whether the pre-approved
      `SKIP_KIMI_REVIEW=1 git commit *` allow entry should stay (document the
      rationale) or be removed so each skip is a conscious choice.
- [ ] CRITICAL findings remain hard-blocking; only friction, not strictness,
      is reduced.

## Work Log

### 2026-05-31 - Started by completing-todos skill (run 2026-05-31-0145)

- Picked up by automated workflow.

## Notes

Do NOT weaken the CRITICAL block. The goal is to make the safe path the easy
path, not to make the gate softer.
