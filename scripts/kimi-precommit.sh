#!/usr/bin/env bash
# Pre-commit kimi-review gate over the staged diff.
# A verified CRITICAL finding (engine exit code 2) blocks the commit; WARNING
# findings print but do not block.
#
# Bypass:    SKIP_KIMI_REVIEW=1 git commit ...
# Auto-skips when kimi-review is not on PATH (devs without the tool aren't blocked),
# on timeout, or when the kimi-review run itself fails — the gate fails open so a
# tooling problem never blocks an otherwise-valid commit. The engine owns the
# blocking decision via its exit code (2 = a CRITICAL survived verification).

set -uo pipefail

[ "${SKIP_KIMI_REVIEW:-}" = "1" ] && exit 0

# Engine drift check: vendored scripts/kimi-review must match the canonical engine
# on this machine. Skips silently when the canonical is absent (see check script).
if [ -f scripts/check-kimi-engine.sh ]; then
  bash scripts/check-kimi-engine.sh || exit 1
fi

command -v kimi-review >/dev/null 2>&1 || exit 0

REVIEW_DIFF=$(git diff --cached)
[ -n "$REVIEW_DIFF" ] || exit 0

if command -v timeout >/dev/null 2>&1; then
  TIMEOUT_CMD="timeout 150"
elif command -v gtimeout >/dev/null 2>&1; then
  TIMEOUT_CMD="gtimeout 150"
else
  TIMEOUT_CMD=""
fi

REVIEW_RAW=$(printf '%s' "$REVIEW_DIFF" | NO_COLOR=1 $TIMEOUT_CMD kimi-review \
  --scope "pre-commit staged diff" \
  --tiers CRITICAL,WARNING \
  --profile plant_id \
  --verify deterministic 2>&1)
REVIEW_STATUS=$?
# Strip ANSI escape codes for clean display.
REVIEW_OUTPUT=$(printf '%s' "$REVIEW_RAW" | sed $'s/\x1b\\[[0-9;]*m//g')

printf '%s\n' "$REVIEW_OUTPUT"

# Engine exit 2 = a CRITICAL survived verification → block.
if [ "$REVIEW_STATUS" -eq 2 ]; then
  echo "" >&2
  echo "Commit blocked: kimi-review reported a verified CRITICAL finding above." >&2
  echo "Fix the issue or set SKIP_KIMI_REVIEW=1 to bypass." >&2
  exit 1
fi

if [ "$REVIEW_STATUS" -eq 124 ]; then
  echo "kimi-review timed out; skipping gate." >&2
  exit 0
fi

if [ "$REVIEW_STATUS" -ne 0 ]; then
  echo "kimi-review failed to run (exit $REVIEW_STATUS); skipping gate." >&2
  exit 0
fi
