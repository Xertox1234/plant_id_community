#!/usr/bin/env bash
# Self-test for the CI mypy gate (a bare `python -m mypy`, which checks the
# `files` list in pyproject.toml [tool.mypy]; apps/users since todo 580, the
# wagtail_forum package, apps/garden_calendar, apps/core and
# apps/plant_identification since todo 659).
# Run from backend/: bash bin/test-mypy-gate.sh
#
# pyproject.toml sets follow_imports=silent, which hides errors in modules
# reached only by import. A config drift that also silenced a gated area
# would turn the gate green by having nothing to report (todo 599 item 4).
# So: plant a file with a known type error in each probed source area, run
# the gate's exact command, and require that it fails AND names every one.
#
# Tests are excluded from the gate (the `apps.*.tests.*` and
# `wagtail_forum.tests.*` ignore_errors overrides, owner decision 2026-10-19):
# a second canary with the same error under each area's tests/ must NOT be
# reported, so an exclusion cannot silently stop matching when a test layout
# or an override pattern changes. Test modules at an app's root are named one
# by one in the override; a name that stops matching prints mypy's "unused
# section" note (warn_unused_configs), which fails this test too.
set -uo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
cd "$here" || exit 2

forum=packages/wagtail_forum/wagtail_forum
garden=apps/garden_calendar
core=apps/core
pid=apps/plant_identification
canaries=("apps/users/_mypy_gate_canary.py" "$forum/_mypy_gate_canary.py" "$garden/_mypy_gate_canary.py" "$core/_mypy_gate_canary.py" "$pid/_mypy_gate_canary.py")
test_canaries=("apps/users/tests/_mypy_gate_canary.py" "$forum/tests/_mypy_gate_canary.py" "$garden/tests/_mypy_gate_canary.py" "$core/tests/_mypy_gate_canary.py" "$pid/tests/_mypy_gate_canary.py")
all=("${canaries[@]}" "${test_canaries[@]}")
for f in "${all[@]}"; do
  if [[ -e "$f" ]]; then
    echo "test-mypy-gate: $f already exists; refusing to overwrite it" >&2
    exit 2
  fi
done
trap 'rm -f "${all[@]}"' EXIT
for f in "${all[@]}"; do
  cat > "$f" <<'PY'
"""Planted by bin/test-mypy-gate.sh; deleted when it exits."""

CANARY: int = "not an int"
PY
done

output=$(python -m mypy 2>&1)
status=$?
echo "$output" | tail -5

if [[ $status -ne 1 ]]; then
  echo "test-mypy-gate: FAIL: mypy exited $status with known errors planted (want 1)" >&2
  exit 1
fi
for canary in "${canaries[@]}"; do
  if ! grep -q "^$canary:[0-9]*: error: Incompatible types in assignment" <<<"$output"; then
    echo "test-mypy-gate: FAIL: mypy did not report the planted error in $canary" >&2
    exit 1
  fi
done
for test_canary in "${test_canaries[@]}"; do
  if grep -q "^$test_canary:" <<<"$output"; then
    echo "test-mypy-gate: FAIL: the gate reported $test_canary; tests must be excluded (tests overrides)" >&2
    exit 1
  fi
done
if grep -q "unused section" <<<"$output"; then
  echo "test-mypy-gate: FAIL: a [tool.mypy] override matches no module (unused section)" >&2
  exit 1
fi
canary_patterns=()
for canary in "${canaries[@]}"; do
  canary_patterns+=(-e "^$canary:")
done
others=$(grep ": error:" <<<"$output" | grep -vc "${canary_patterns[@]}")
if [[ $others -ne 0 ]]; then
  echo "test-mypy-gate: FAIL: $others error(s) besides the canaries; fix those first" >&2
  exit 1
fi
echo "test-mypy-gate: OK: the gate reports errors planted in apps/users, $forum, $garden, $core and $pid and ignores those in their tests/"
