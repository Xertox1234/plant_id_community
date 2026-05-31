---
name: sync-stale-kimi-review-engine
status: pending
priority: p2
issue_id: "135"
created: 2026-05-30
tags: [harness, kimi-review, commit-gate, tooling]
dependencies: []
---

# Sync the stale vendored kimi-review engine to canonical

## Problem

The `kimi-review` commit gate fails its **engine-staleness self-check** before it
ever runs a review: the vendored `scripts/kimi-review` has drifted from the
canonical engine. Every commit on an affected machine must be made with
`SKIP_KIMI_REVIEW=1`, which silently disables the commit-time code-review safety
gate for that commit. Left unsynced, the gate is effectively off for anyone whose
canonical engine has moved ahead of the vendored copy.

## Findings

- Observed during the todo 132 session (PR #308 commit). The `kimi-review.sh`
  pre-commit hook exited non-zero with:
  `[kimi:engine:check] scripts/kimi-review is STALE vs canonical. Run 'bash scripts/sync-kimi-engine.sh' and commit the result.`
- The failure is the **staleness check**, not a `[CRITICAL]` finding — the diff
  review never ran. (Discovery source: human + Claude, commit-gate output.)
- `scripts/sync-kimi-engine.sh` copies the canonical engine
  (`$HOME/.local/share/claude-coworker/tools/kimi-review`, overridable via
  `KIMI_ENGINE_CANONICAL`) into `scripts/kimi-review`, swapping the coworker-venv
  shebang for a portable `#!/usr/bin/env python3`. It intentionally does **not**
  overwrite the hand-maintained `scripts/kimi-profiles.json`.
- The canonical engine lives **outside the repo** (per-developer home dir), so the
  staleness is machine-relative: it fails wherever the local canonical has advanced
  past the committed vendored copy.

## Recommended Action

1. Run the sanctioned sync from the repo root:

   ```bash
   bash scripts/sync-kimi-engine.sh
   ```

2. Review the resulting `scripts/kimi-review` diff — confirm it is only an
   engine-version bump (and the portable shebang), not an unintended behavior change.
3. Commit the synced `scripts/kimi-review` (no `SKIP_KIMI_REVIEW=1` should be needed
   once vendored == canonical).
4. Verify the gate passes on a real staged change (see Acceptance Criteria).

## Technical Details

- Hook: `.claude/hooks/kimi-review.sh` (commit gate) and the `kimi-review`
  pre-commit hook entry in `.pre-commit-config.yaml`.
- Sync script: `scripts/sync-kimi-engine.sh` (vendors canonical → `scripts/kimi-review`).
- CI also runs the vendored engine directly via `.github/workflows/kimi-review.yml`,
  so a stale vendored copy means CI and local both review against an outdated engine.
- Bypass (documented in root `CLAUDE.md`): `SKIP_KIMI_REVIEW=1` — used once for the
  PR #308 commit so todo 132 could land; that bypass is the friction this todo removes.

## Acceptance Criteria

- [ ] `bash scripts/sync-kimi-engine.sh` runs clean and updates `scripts/kimi-review`.
- [ ] A commit with a real staged change passes the `kimi-review` hook **without**
      `SKIP_KIMI_REVIEW=1` (the staleness check passes; the diff review runs).
- [ ] `scripts/kimi-review` diff is an engine sync only — no change to
      `scripts/kimi-profiles.json` and no unexplained behavior change.

## Work Log

### 2026-05-30 - Filed

- Surfaced when the PR #308 (todo 132) commit hit the staleness gate; bypassed that
  commit with `SKIP_KIMI_REVIEW=1` and filed this so the gate is restored repo-wide.

## Notes

- Priority p2 (not p3): the staleness gate fails on **every** commit on an affected
  machine and forces a bypass that disables the commit-time review — an active
  degradation of a safety gate, same family as todo 128 (reduce-kimi-review-friction).
- Whoever fixes this needs the canonical engine present at
  `$HOME/.local/share/claude-coworker/tools/kimi-review` (or set `KIMI_ENGINE_CANONICAL`).
  If the canonical engine isn't available to the assignee, this is blocked on access
  to it — note that and reassign rather than committing a guess.
