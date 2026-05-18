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

## Notes

p3 — pure dev-experience / tooling health; no functional or security impact. The
two items are independent and can be done separately.
