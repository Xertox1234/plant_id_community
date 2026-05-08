#!/usr/bin/env bash
# Verifies every *-reviewer.md agent file has the required Output Format and Repair Mode blocks.
# Run manually or wire into CI as a lint step.
set -euo pipefail
shopt -s nullglob

errors=0
for f in .claude/agents/*-reviewer.md; do
  grep -q '## Output Format (Review Mode)' "$f" || { echo "missing '## Output Format (Review Mode)': $f"; errors=$((errors + 1)); }
  grep -q '## Repair Mode' "$f"              || { echo "missing '## Repair Mode': $f"; errors=$((errors + 1)); }
done

if [ "$errors" -eq 0 ]; then
  echo "All reviewer agents have required format blocks."
else
  echo "$errors error(s) found." >&2
  exit 1
fi
