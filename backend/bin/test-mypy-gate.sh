#!/usr/bin/env bash
# Self-test for the CI mypy gate (a bare `python -m mypy`, which checks the
# `files` list in pyproject.toml [tool.mypy]; apps/users since todo 580).
# Run from backend/: bash bin/test-mypy-gate.sh
#
# pyproject.toml sets follow_imports=silent, which hides errors in modules
# reached only by import. A config drift that also silenced the named app
# would turn the gate green by having nothing to report (todo 599 item 4).
# So: plant a file with a known type error in apps/users, run the gate's exact
# command, and require that it fails AND names that file.
#
# Tests are excluded from the gate (the `apps.*.tests.*` ignore_errors override,
# owner decision 2026-10-19): a second canary with the same error under
# apps/users/tests/ must NOT be reported, so the exclusion cannot silently
# stop matching when a test layout or the override pattern changes.
set -uo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
cd "$here" || exit 2

canary="apps/users/_mypy_gate_canary.py"
test_canary="apps/users/tests/_mypy_gate_canary.py"
for f in "$canary" "$test_canary"; do
  if [[ -e "$f" ]]; then
    echo "test-mypy-gate: $f already exists; refusing to overwrite it" >&2
    exit 2
  fi
done
trap 'rm -f "$canary" "$test_canary"' EXIT
for f in "$canary" "$test_canary"; do
  cat > "$f" <<'PY'
"""Planted by bin/test-mypy-gate.sh; deleted when it exits."""

CANARY: int = "not an int"
PY
done

output=$(python -m mypy 2>&1)
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
if grep -q "^$test_canary:" <<<"$output"; then
  echo "test-mypy-gate: FAIL: the gate reported $test_canary; tests must be excluded (apps.*.tests.* override)" >&2
  exit 1
fi
others=$(grep ": error:" <<<"$output" | grep -vc "^$canary:")
if [[ $others -ne 0 ]]; then
  echo "test-mypy-gate: FAIL: $others error(s) besides the canary; fix those first" >&2
  exit 1
fi
echo "test-mypy-gate: OK: the gate reports an error planted in apps/users and ignores one in apps/users/tests"
