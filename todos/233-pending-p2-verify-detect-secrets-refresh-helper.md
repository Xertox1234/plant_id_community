---
status: pending
priority: p2
issue_id: "233"
tags: [detect-secrets, pre-commit, harness, verification]
dependencies: []
---

# Verify the detect-secrets refresh helper end-to-end and resolve the gate version skew

## Problem

PR #372 added `scripts/refresh-secrets-baseline.sh` to clear detect-secrets
baseline churn, but the helper was only syntax-checked (`bash -n`) — it was never
run against a real churn case. Compounding this, the commit gate pins
detect-secrets **v1.4.0** (`.pre-commit-config.yaml`) while `backend/venv` has
**v1.5.0**, so the helper regenerates the baseline with a different version than
the gate validates it with. If the baseline formats diverge, a "refreshed"
baseline could fail the very gate it was meant to satisfy.

## Findings

- `scripts/refresh-secrets-baseline.sh` (added in PR #372, commit `e989192`) uses
  `detect-secrets scan --baseline .secrets.baseline` (correct in-place idiom per
  docs) but has no end-to-end test; the `## Verification` step "V3" in the source
  plan was never executed (no churn case was reproduced).
- `.pre-commit-config.yaml:17` pins `rev: v1.4.0`; `backend/venv/bin/detect-secrets
  --version` reports `1.5.0`. The `scripts/inject` / harness CI does not exercise
  this path.
- The write-time trigger `secrets-baseline-manual-edit` (in `docs/rules/triggers.json`)
  and the doc fix in `docs/PRE_COMMIT_SETUP.md` *were* verified; only the helper +
  version skew remain unverified.
- Discovery source: self-review of PR #372 (2026-06-14), issue #2.

## Recommended Action

1. Reproduce a churn case: shift a placeholder-secret line in a tracked test file
   so its line number changes, and confirm `pre-commit run detect-secrets
   --all-files` re-flags it.
2. Run `bash scripts/refresh-secrets-baseline.sh`; confirm `git diff
   .secrets.baseline` shows only line-number deltas and that `is_secret` /
   `is_verified` audit fields are preserved (not reset to `null`).
3. Re-run `pre-commit run detect-secrets --all-files` and confirm it passes —
   this is the cross-version (1.5.0-written → 1.4.0-validated) compatibility check.
4. If step 3 fails on a format mismatch, **bump the gate** `rev:` in
   `.pre-commit-config.yaml` from `v1.4.0` → `v1.5.0` (single line) so the helper
   and gate agree, then re-run. (Recommended even if step 3 passes, to remove the
   skew as a latent risk.)
5. Confirm `# pragma: allowlist secret` on a shifted placeholder keeps the gate
   green with no baseline diff.

## Technical Details

- `scripts/refresh-secrets-baseline.sh` — the `--exclude-files` set mirrors
  `.pre-commit-config.yaml` lines 24–29; keep them in sync if the gate's excludes
  change.
- `.pre-commit-config.yaml:16–36` — detect-secrets hook block.
- `docs/PRE_COMMIT_SETUP.md` — recovery docs updated in PR #372.

## Acceptance Criteria

- [ ] The helper has been run once against a reproduced churn case, with the
      resulting baseline passing `pre-commit run detect-secrets --all-files`.
- [ ] Audit decisions (`is_secret`/`is_verified`) are confirmed preserved across a
      refresh (not wiped).
- [ ] The v1.4.0 (gate) vs v1.5.0 (venv) skew is resolved — either proven
      compatible in step 3 or removed by bumping the gate `rev:`.

## Work Log

### 2026-06-14 - Filed

- Created from self-review of PR #372 (issue #2). Helper shipped but unverified;
  version skew deferred from the source plan.

## Notes

- p2 because a broken refresh path silently re-introduces the churn this PR set
  out to fix, and the version skew is a real (if low-probability) correctness risk.
- Related: PR #372; `secrets-baseline-manual-edit` trigger in `docs/rules/triggers.json`.
