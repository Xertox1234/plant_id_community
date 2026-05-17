#!/usr/bin/env bash
# Pre-commit kimi-review gate over the staged diff.
# CRITICAL findings block the commit; WARNING findings print but do not block.
#
# Bypass:    SKIP_KIMI_REVIEW=1 git commit ...
# Auto-skips when kimi-review is not on PATH (devs without the tool aren't blocked),
# on timeout, or when the kimi-review run itself fails — the gate fails open so a
# tooling problem never blocks an otherwise-valid commit. The CRITICAL check runs
# BEFORE the exit-status checks so a crash-after-detection still blocks.

set -uo pipefail

[ "${SKIP_KIMI_REVIEW:-}" = "1" ] && exit 0
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
  --profile plant_id 2>&1)
REVIEW_STATUS=$?
# Strip ANSI escape codes so the CRITICAL gate isn't bypassed by colored output.
REVIEW_OUTPUT=$(printf '%s' "$REVIEW_RAW" | sed $'s/\x1b\\[[0-9;]*m//g')

printf '%s\n' "$REVIEW_OUTPUT"

# CRITICAL check first — kimi-review may print findings and still exit non-zero.
# Match the bracketed [CRITICAL] tag followed by a finding body; the negative
# phrasing and clean-output message carry the bare word but never the tag.
if printf '%s\n' "$REVIEW_OUTPUT" | grep -Eq '[[]CRITICAL[]].*[^[:space:]]'; then
  echo "" >&2
  echo "Commit blocked: kimi-review reported CRITICAL findings above." >&2
  echo "Fix the issues or set SKIP_KIMI_REVIEW=1 to bypass." >&2
  exit 1
fi

if [ $REVIEW_STATUS -eq 124 ]; then
  echo "kimi-review timed out; skipping gate." >&2
  exit 0
fi

if [ $REVIEW_STATUS -ne 0 ]; then
  echo "kimi-review failed to run (exit $REVIEW_STATUS); skipping gate." >&2
  exit 0
fi
