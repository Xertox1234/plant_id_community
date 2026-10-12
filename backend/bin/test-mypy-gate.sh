#!/usr/bin/env bash
# Self-test for the CI mypy gate (`python -m mypy apps/users`, todo 580).
# Run from backend/: bash bin/test-mypy-gate.sh
#
# pyproject.toml sets follow_imports=silent, which hides errors in modules
# reached only by import. A config drift that also silenced the named app
# would turn the gate green by having nothing to report (todo 599 item 4).
# So: plant a file with a known type error in apps/users, run the gate's exact
# command, and require that it fails AND names that file.
set -uo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
cd "$here" || exit 2

canary="apps/users/_mypy_gate_canary.py"
if [[ -e "$canary" ]]; then
  echo "test-mypy-gate: $canary already exists; refusing to overwrite it" >&2
  exit 2
fi
trap 'rm -f "$canary"' EXIT
cat > "$canary" <<'PY'
"""Planted by bin/test-mypy-gate.sh; deleted when it exits."""

CANARY: int = "not an int"
PY

output=$(python -m mypy apps/users 2>&1)
status=$?
echo "$output" | tail -5

if [[ $status -ne 1 ]]; then
  echo "test-mypy-gate: FAIL: mypy exited $status with a known error planted (want 1)" >&2
  exit 1
fi
if ! grep -q "^$canary:[0-9]*: error: Incompatible types in assignment" <<<"$output"; then
  echo "test-mypy-gate: FAIL: mypy did not report the planted error in $canary" >&2
  exit 1
fi
others=$(grep ": error:" <<<"$output" | grep -vc "^$canary:")
if [[ $others -ne 0 ]]; then
  echo "test-mypy-gate: FAIL: $others error(s) besides the canary; fix those first" >&2
  exit 1
fi
echo "test-mypy-gate: OK: the gate reports an error planted in apps/users"
