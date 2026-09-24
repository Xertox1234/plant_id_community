#!/bin/bash
#
# Self-test for run_archive.sh's build-number validation (todo 391).
#
# Runs a COPY of run_archive.sh in a throwaway directory with fake release
# config, a stubbed App Store Connect query and a `flutter` that refuses to run.
# Nothing is built and no network is touched.
#
# Usage: plant_community_mobile/scripts/test_run_archive.sh
#
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$HERE/../run_archive.sh"
PASS=0
FAIL=0

check() { # name, haystack, must-contain, must-not-contain
  if grep -qF -- "$3" <<<"$2" && ! grep -qF -- "$4" <<<"$2"; then
    echo "PASS: $1"; PASS=$((PASS + 1))
  else
    echo "FAIL: $1"; while IFS= read -r l; do echo "    | $l"; done <<<"$2"
    FAIL=$((FAIL + 1))
  fi
}

sandbox() { # pubspec version line, stubbed ASC highest -> sets $d
  local dir
  # An explicit template: macOS `mktemp -d` alone ignores $TMPDIR.
  dir="$(mktemp -d "${TMPDIR:-/tmp}/run_archive_test.XXXXXX")" \
    || { echo "FAIL: mktemp -d failed" >&2; exit 2; }
  mkdir -p "$dir/ios" "$dir/scripts" "$dir/bin"
  cp "$SCRIPT" "$dir/run_archive.sh"
  printf 'name: x\n%s\n' "$1" >"$dir/pubspec.yaml"
  printf '%s\n' FIREBASE_IOS_API_KEY=k FIREBASE_IOS_APP_ID=a \
    FIREBASE_MESSAGING_SENDER_ID=s FIREBASE_PROJECT_ID=p \
    API_BASE_URL=https://api.example.com >"$dir/.env.production"
  : >"$dir/ios/ExportOptions.plist"
  printf '#!/bin/sh\necho %s\n' "$2" >"$dir/scripts/asc_build_numbers.py"
  printf '#!/bin/sh\necho FLUTTER_WAS_CALLED\nexit 99\n' >"$dir/bin/flutter"
  chmod +x "$dir/run_archive.sh" "$dir/scripts/asc_build_numbers.py" "$dir/bin/flutter"
  d="$dir"
}

run() { # dir, env assignments... -> combined output
  local dir="$1"; shift
  (cd "$dir" && env PATH="$dir/bin:$PATH" "$@" ./run_archive.sh 2>&1)
}

# 1. SKIP_BUILD verifies an EXISTING ipa whose number is baked in. A pubspec
#    with no `+N` must not fail that run as "bad build number": run_upload.sh
#    maps any failure here to "$IPA FAILED verification", blaming a good IPA.
sandbox 'version: 1.0.0' 5
out="$(run "$d" SKIP_BUILD=1)"
check "SKIP_BUILD ignores an unparseable pubspec build number" \
  "$out" "no ipa at" "must be a bare integer"
rm -rf "$d"

# 1b. BUILD_NUMBER=next exported for the build is inherited by run_upload.sh's
#     SKIP_BUILD=1 verification run, which skips the App Store Connect query.
#     --next must not die there either (PR #822 review).
sandbox 'version: 1.0.0+7' 5
out="$(run "$d" SKIP_BUILD=1 BUILD_NUMBER=next)"
check "SKIP_BUILD with BUILD_NUMBER=next still verifies" \
  "$out" "no ipa at" "needs App Store Connect"
rm -rf "$d"

# 2. Control: the same pubspec WITHOUT SKIP_BUILD is still refused, so test 1
#    passes because of the SKIP_BUILD guard and not because validation broke.
sandbox 'version: 1.0.0' 5
out="$(run "$d")"
check "without SKIP_BUILD an unparseable build number is refused" \
  "$out" "must be a bare integer" "FLUTTER_WAS_CALLED"
rm -rf "$d"

# 3. A 20-digit number is all digits, but `[ -le ]` cannot compare it: bash
#    errors, the elif is exempt from set -e, the duplicate check is skipped and
#    the build proceeds. is_uint must refuse it first.
sandbox 'version: 1.0.0+1' 5
out="$(run "$d" BUILD_NUMBER=12345678901234567890)"
check "a build number too long for [ -le ] is refused before building" \
  "$out" "must be a bare integer" "FLUTTER_WAS_CALLED"
rm -rf "$d"

# 4. The same overflow arriving from App Store Connect.
sandbox 'version: 1.0.0+7' 12345678901234567890
out="$(run "$d")"
check "an over-long App Store Connect number is refused before building" \
  "$out" "non-numeric highest build number" "FLUTTER_WAS_CALLED"
rm -rf "$d"

# 5. Control: an ordinary duplicate is still caught by the comparison.
sandbox 'version: 1.0.0+5' 5
out="$(run "$d")"
check "a taken build number is still refused" \
  "$out" "already taken" "FLUTTER_WAS_CALLED"
rm -rf "$d"

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
