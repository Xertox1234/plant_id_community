#!/usr/bin/env bash
# pre-commit hook body: run ONLY the test files staged in this commit, so a
# commit that touches no tests pays nothing. One hook per platform in
# .pre-commit-config.yaml names the platform; pre-commit appends the staged
# paths (repo-relative) that matched the hook's `files:` regex.
#
#   scripts/test-staged.sh backend <backend/.../test_x.py ...>   pytest
#   scripts/test-staged.sh web     <web/src/.../x.test.tsx ...>  vitest
#   scripts/test-staged.sh flutter <plant_community_mobile/test/.../x_test.dart ...>
#
# Fail-closed: a missing toolchain fails the commit with a message rather than
# passing by emptiness. Bypass one commit with SKIP=<hook-id> (for example when
# another pytest run already holds the test database).
set -uo pipefail
platform="${1:-}"; shift || true
root="$(cd "$(dirname "$0")/.." && pwd)"
[ "$#" -gt 0 ] || exit 0

strip_prefix() { # $1=prefix, rest=paths → prints each path without the prefix
  local prefix="$1"; shift
  for f in "$@"; do printf '%s\n' "${f#"$prefix"}"; done
}

case "$platform" in
  backend)
    cd "$root/backend" || exit 2
    if [ ! -x venv/bin/python ]; then
      echo "test-staged: backend/venv/bin/python is missing; create the venv or commit with SKIP=pytest-staged" >&2
      exit 1
    fi
    mapfile -t files < <(strip_prefix "backend/" "$@")
    venv/bin/python -m pytest -q -p no:cacheprovider "${files[@]}"; rc=$?
    # 5 = nothing collected: a staged conftest.py, tests/__init__.py or one of
    # the two files pytest.ini --ignore's. Not a failure.
    [ "$rc" -eq 5 ] && rc=0
    exit "$rc"
    ;;
  web)
    cd "$root/web" || exit 2
    if [ ! -x node_modules/.bin/vitest ]; then
      echo "test-staged: web/node_modules/.bin/vitest is missing; run npm ci or commit with SKIP=vitest-staged" >&2
      exit 1
    fi
    mapfile -t files < <(strip_prefix "web/" "$@")
    exec node_modules/.bin/vitest run "${files[@]}"
    ;;
  flutter)
    cd "$root/plant_community_mobile" || exit 2
    if ! command -v flutter >/dev/null 2>&1; then
      echo "test-staged: flutter is not on PATH; install it or commit with SKIP=flutter-test-staged" >&2
      exit 1
    fi
    mapfile -t files < <(strip_prefix "plant_community_mobile/" "$@")
    exec flutter test "${files[@]}"
    ;;
  *)
    echo "test-staged: unknown platform '$platform' (backend|web|flutter)" >&2
    exit 2
    ;;
esac
