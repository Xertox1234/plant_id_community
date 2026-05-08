---
status: completed
priority: p4
issue_id: "055"
tags: [agents, code-review, polish]
dependencies: []
---

# Full Review Orchestrator — Polish Items

## Problem

Low-priority items surfaced in the code review of PR #251 (`feature/full-review-orchestrator`). Each is a small prompt-edit in `.claude/agents/full-review-orchestrator.md` that's safe to defer past merge but worth cleaning up before the agent gets heavy use.

## Findings

1. **`--wave-size N` parsing source not pinned.** Phase 0 step 4 says "if the user's invocation message includes `--wave-size N`", but the orchestrator gets a prompt from Main Claude — not the user's raw input. Either pin to "search the invocation prompt for the substring `--wave-size <int>`" or have Main Claude pre-extract and pass the value explicitly.

2. **Empty match set in Phase 4c not handled.** If a filter matches zero findings, the current Phase 4c text still prints "Matched: 0 findings across 0 files" then asks "Dispatch repairs?" — a dead-end. The spec at `docs/superpowers/specs/2026-05-06-full-review-orchestrator-design.md:362` has the right behavior (`"0 findings matched, refine filter or type 'none'"`); copy that into the agent file.

3. **`info` severity column missing from `INDEX.md`.** Phase 3 step 9 row format has Critical / High / Medium / Low columns. Findings coerced to `info` (severity coercion path, Phase 3 step 5) silently disappear from the running history summary. Add an Info column to INDEX, or roll info counts into Low.

4. **No drift guard for the reviewer fleet.** The 11 reviewer files share a hand-edited `## Output Format (Review Mode)` and `## Repair Mode` block that hardcodes each reviewer's own `agent` ID. A future reviewer added without the block, or with a typo'd ID, won't be caught. Add a 5-line shell check (or pre-commit hook):

   ```bash
   for f in .claude/agents/*-reviewer.md; do
     grep -q '## Output Format (Review Mode)' "$f" || echo "missing review block: $f"
     grep -q '## Repair Mode' "$f" || echo "missing repair block: $f"
   done
   ```

## Recommended Action

- Items 1-3: small edits to `.claude/agents/full-review-orchestrator.md`. ~15 min total.
- Item 4: add the check to a Makefile target or `.husky/pre-commit`. ~10 min.

## Work Log

### 2026-05-08 - Started by completing-todos skill (run 2026-05-08-0038)

- Picked up by automated workflow.

### 2026-05-08 - Completed by completing-todos skill (run 2026-05-08-0038)

- Fixed 4 items in full-review-orchestrator.md:
  1. Phase 0 step 4: pinned wave-size parsing to "search the invocation prompt you received from Main Claude" (not raw user input).
  2. Phase 4c: added zero-match guard — prints "0 findings matched, refine filter or type 'none'." and loops back to filter prompt instead of dead-end "Dispatch repairs?".
  3. Phase 3 step 9: added `<info>` column to INDEX.md row format template; added note to add Info column if missing.
  4. docs/reviews/INDEX.md: added Info column to header, backfilled 40 info findings for the 2026-05-07 review.
- Created scripts/check_reviewer_format.sh — checks every *-reviewer.md for required Output Format and Repair Mode blocks; runs clean against all 11 reviewers.
- Updated docs/superpowers/specs spec to match new INDEX.md column format.
- Verification: drift guard script exits 0; all file edits confirmed applied.
- Review: 3 low findings (wave-size phrasing, nullglob edge case, spec sync) — all repaired.

## Related

- PR #251 (merged)
- `docs/superpowers/specs/2026-05-06-full-review-orchestrator-design.md`
- `.claude/agents/full-review-orchestrator.md`
