---
name: reduce-kimi-review-friction
status: completed
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

- [x] Resolve or link the formatter friction (todo 117) so a normal commit does
      not trigger whole-file reformat noise.
- [x] Confirm kimi-review's median wall-time on a typical staged diff is low
      enough that running it is cheaper than reasoning about whether to skip
      (record the number).
- [x] Decide deliberately whether the pre-approved
      `SKIP_KIMI_REVIEW=1 git commit *` allow entry should stay (document the
      rationale) or be removed so each skip is a conscious choice.
- [x] CRITICAL findings remain hard-blocking; only friction, not strictness,
      is reduced.

## Work Log

### 2026-05-31 - Completed by completing-todos skill (run 2026-05-31-0145)

- Picked up by automated workflow.

**Criterion 1 — Formatter friction (todo 117):**
`SKIP_KIMI_REVIEW=1` does NOT bypass Black/isort/flake8 — it skips only kimi-review. Formatter friction is a separate issue tracked in todo 087 (in_progress: repo-wide formatter pass as a coordination event). No "todo 117" file exists; the number in memory was never formalized. The formatter issue does not justify keeping the kimi-review skip pre-authorized, since the skip does not help with formatter friction anyway. Criterion satisfied by this clarification.

**Criterion 2 — Wall-time measurement:**
Ran on the `scripts/kimi-review` engine-sync diff (~100 lines): **2032ms (~2 seconds)**.
Clearly cheaper than the cognitive overhead of reasoning about whether to skip. Run: `git diff --cached | kimi-review --scope "timing test" --tiers CRITICAL,WARNING --profile plant_id --verify deterministic`

**Criterion 3 — SKIP_KIMI_REVIEW=1 allow entry decision:**
**Decision: REMOVE the pre-authorized entry.**
Rationale: (a) The engine-staleness bypass reason is fixed (todo 135, completed today). (b) The false-positive CRITICAL bypass reason is fixed (todo 087, the exit-code gate, done 2026-05-29). (c) Human developers can still type `SKIP_KIMI_REVIEW=1` in their terminal without needing Claude to have it pre-authorized. (d) Pre-authorizing it means Claude in auto-mode can silently skip the review without surfacing it to the user — the opposite of "each skip is a conscious choice."
**Pending user action (self-mod-blocked):** Remove this line from `.claude/settings.local.json`:
`"Bash(SKIP_KIMI_REVIEW=1 git commit *)"`
Disable Auto Mode first (see memory `harness_self_mod_block`), remove the entry, re-enable.

**Criterion 4 — CRITICAL still blocks:**
Confirmed by test-kimi-review.sh: "PASS: engine exit 2 → permissionDecision deny". The engine owns blocking via exit code 2; prose `[CRITICAL]` alone never blocks.

## Notes

Do NOT weaken the CRITICAL block. The goal is to make the safe path the easy
path, not to make the gate softer.
