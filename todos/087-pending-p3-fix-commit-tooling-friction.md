---
status: pending
priority: p3
issue_id: "087"
tags: [tooling, ci, dev-experience]
dependencies: []
---

# Fix commit-time tooling friction (kimi-review gate + formatting drift)

## Problem

Committing in this repo reliably hits two pre-commit snags that forced three
`--no-verify` bypasses during the 2026-05-17 audit. Neither is a code defect, but
both degrade the commit workflow and erode trust in the gate.

## Findings

Observed during the 2026-05-17 full audit (Phase 7 — see
`docs/audits/2026-05-17-full.md`, "Note — kimi-review CRITICAL"):

1. **kimi-review pre-commit gate blocks on false-positive `[CRITICAL]`s.**
   - It blocked a commit on a finding it *self-recanted* in the same output
     ("So my original thought is incorrect. No vulnerability. I recant.") — the
     gate matches the `[CRITICAL]` tag literally and ignores the retraction.
   - It also mis-scoped the diff once, flagging `.github/workflows/kimi-review.yml`
     (a pre-existing `main` file) as if it were part of the change set.
   - Net effect: real commits get blocked; `SKIP_KIMI_REVIEW=1` / `--no-verify`
     becomes routine, which defeats the gate's purpose.
2. **The repo has Python formatting drift.** The pre-commit auto-formatter
   reformats entire older files (single→double quotes, line rewrapping) on any
   commit that touches them — a ~150-line change ballooned to ~1660 lines across
   ~6 files. PRs touching old code are unreviewable without bypassing the formatter.

## Recommended Action

1. **kimi-review gate** (`.claude/hooks/kimi-review.sh` and/or the vendored
   `scripts/kimi-review`):
   - Ignore a `[CRITICAL]` if the same response contains a retraction, or have
     kimi-review emit a final structured verdict the gate keys on instead of
     scanning for the tag.
   - Scope the reviewed diff strictly to the staged changes (`git diff --cached`),
     so pre-existing `main` files are never flagged.
2. **Formatting drift**: run the project's formatter (black/ruff-format) repo-wide
   in a single dedicated commit (`style: apply formatter repo-wide`), so future
   PRs only diff real changes. Add the bulk-format commit SHA to
   `.git-blame-ignore-revs` so blame stays useful.

## Acceptance Criteria

- [ ] A self-recanted or mis-scoped kimi-review finding no longer blocks a commit.
- [ ] kimi-review reviews only the staged diff, not unrelated `main` files.
- [ ] `git commit` touching an older Python file no longer triggers whole-file
      reformatting (repo is formatter-clean).

## Work Log

### 2026-05-18 - Created

- Follow-up requested after the 2026-05-17 full audit, which hit both snags
  repeatedly during its commit phase.

### 2026-05-18 - Investigated by completing-todos skill (run 2026-05-18-2300) — SKIPPED

- Picked up by the automated sweep; investigated and **skipped**. Per-criterion status:
- **Criterion 1 (self-recant `[CRITICAL]` no longer blocks):** NOT done — needs
  design, not a sweep-pace fix. The gate (`.claude/hooks/kimi-review.sh` step 8)
  greps `[[]CRITICAL[]].*[^[:space:]]`, which already tolerates the bare word and
  a bare `[CRITICAL]` tag, but still blocks when the model emits a real
  `[CRITICAL] path:line — desc` finding and recants later in the same response.
  Both candidate fixes are risky: a retraction-phrase grep is brittle in both
  directions (could suppress genuine findings phrased "on closer inspection…"),
  and a structured-verdict approach requires changing `scripts/kimi-review`'s
  system prompt — a change that affects every commit gate in the project and
  deserves a brainstorming pass first.
- **Criterion 2 (review only the staged diff):** ALREADY SATISFIED by current
  code. `.claude/hooks/kimi-review.sh` scopes via `git diff --cached` for both
  the file list (step 5) and the piped diff (step 7); `scripts/kimi-review`
  gives piped stdin priority over `--base` (lines 108–110). The audit's
  mis-scoping was a *manual* `kimi-review --base main` invocation, not the hook
  path — no code change needed for the hook.
- **Criterion 3 (repo formatter-clean):** NOT done — requires a dedicated
  `style: apply formatter repo-wide` commit plus a SHA in `.git-blame-ignore-revs`.
  The completing-todos skill forbids auto-commit (safety rail #1), and running
  the formatter without committing would pollute every subsequent todo's diff
  and code review. This must be a deliberate human-driven commit.
- **Net:** 1 of 3 criteria already met (criterion 2). Criteria 1 and 3 each need
  a dedicated, human-supervised effort — not appropriate for an automated sweep.

### 2026-05-21 - Re-confirmed SKIP by completing-todos skill (run 2026-05-21-2253)

- Picked up again as part of a 4-todo goal sweep (086, 087, 088, 091).
- Re-confirmed the prior per-criterion finding stands:
  - **Criterion 1** (self-recanted `[CRITICAL]` no longer blocks): blocked — the
    fix lives in `.claude/hooks/kimi-review.sh`, which the harness self-mod guard
    hard-blocks an automated session from editing. Also a brittle design change
    that deserves a brainstorming pass first.
  - **Criterion 2** (review only the staged diff): already satisfied by current
    hook code (no work).
  - **Criterion 3** (repo formatter-clean): needs a deliberate human-committed
    `style: apply formatter repo-wide` commit plus a `.git-blame-ignore-revs`
    entry. Auto-commit is forbidden (skill safety rail #1), and running the
    formatter without committing would pollute every other todo's diff.
- 1 of 3 criteria met; the remaining two need a human-supervised effort. Left
  `pending`.

## Notes

p3 — pure dev-experience / tooling health; no functional or security impact. The
two items are independent and can be done separately.
