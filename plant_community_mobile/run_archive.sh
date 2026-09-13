#!/bin/bash
#
# Build the iOS App Store IPA, then prove it is actually configured.
#
# WHY NOT `xcodebuild archive` DIRECTLY -- this is the whole point of this file.
# lib/firebase_options.dart and lib/services/api_service.dart read their
# configuration from String.fromEnvironment, which is a COMPILE-TIME constant
# supplied by --dart-define. xcodebuild knows nothing about Flutter's defines, so
# a bare `xcodebuild archive` compiles an app whose Firebase key and API base URL
# are empty strings. _required() then throws StateError and main() falls through
# to ConfigurationErrorApp: the app opens to "Firebase configuration is required"
# and never reaches a sign-in screen.
#
# That is not hypothetical. Builds 1 and 2 shipped to App Store Connect that way
# on 2026-09-12 and had to be expired. See todos/383 item 8.
#
# `flutter build ipa` also EXPORTS the .ipa, which the old xcodebuild-only script
# never did -- run_upload.sh reads build/ios/ipa/*.ipa, which nothing produced.
#
# Usage:
#   ./run_archive.sh                 # build number from pubspec.yaml
#   BUILD_NUMBER=7 ./run_archive.sh  # explicit
#   ./run_archive.sh --next          # highest on App Store Connect, plus one
#   SKIP_BUILD=1 ./run_archive.sh    # re-verify the existing ipa, build nothing
#   SKIP_ASC_CHECK=1 ./run_archive.sh   # build anyway without asking Apple
#
# Apple rejects a build number that already exists for the version, and
# ExportOptions sets manageAppVersionAndBuildNumber=false so Xcode will NOT
# silently renumber around a collision -- the upload fails loudly instead, after
# a full five-minute build. So this script asks App Store Connect for the
# highest existing number BEFORE building. See todos/389: the hand-maintained
# pubspec integer was wrong twice in two days, and expiring a build does not
# free its number.
#
set -euo pipefail

cd "$(dirname "$0")"

WANT_NEXT=""
for arg in "$@"; do
  case "$arg" in
    --next) WANT_NEXT=1 ;;
    *) echo "ERROR: unknown argument: $arg" >&2; exit 1 ;;
  esac
done
[ "${BUILD_NUMBER:-}" = "next" ] && { WANT_NEXT=1; BUILD_NUMBER=""; }

DEFINES="${DEFINES:-.env.production}"
EXPORT_OPTIONS="${EXPORT_OPTIONS:-ios/ExportOptions.plist}"
IPA="${IPA:-build/ios/ipa/plant_community_mobile.ipa}"

die() { echo "ERROR: $*" >&2; exit 1; }

# ---------------------------------------------------------------- preflight --
[ -f "$DEFINES" ]        || die "missing $DEFINES -- release config lives there (gitignored). See .env.example."
[ -f "$EXPORT_OPTIONS" ] || die "missing $EXPORT_OPTIONS"

# Fail before a 5-minute build rather than after it.
for key in FIREBASE_IOS_API_KEY FIREBASE_IOS_APP_ID FIREBASE_MESSAGING_SENDER_ID \
           FIREBASE_PROJECT_ID API_BASE_URL; do
  grep -qE "^${key}=.+" "$DEFINES" || die "$DEFINES has no non-empty $key"
done

API_URL="$(grep -E '^API_BASE_URL=' "$DEFINES" | head -1 | cut -d= -f2-)"
case "$API_URL" in
  https://*) ;;
  *) die "API_BASE_URL must be https for a release build, got: $API_URL" ;;
esac
# .env.local points at a disposable dev tunnel; shipping it yields an app that
# starts and then cannot reach any backend -- harder to diagnose than a crash.
case "$API_URL" in
  *trycloudflare.com*|*localhost*|*127.0.0.1*|*10.0.2.2*)
    die "API_BASE_URL is a dev/tunnel URL, not production: $API_URL" ;;
esac

EFFECTIVE_BUILD="${BUILD_NUMBER:-$(grep -E '^version:' pubspec.yaml | head -1 | sed 's/.*+//')}"

# ------------------------------------------------- build number vs. reality --
# The pubspec integer is maintained by hand and has no idea what Apple already
# holds. Ask, before spending five minutes on a build altool will reject.
#
# Three outcomes, kept distinct on purpose: queried (0), could-not-run (3),
# something-is-wrong (1). A check that could not run must not read as a pass.
HIGHEST=""
if [ -n "${SKIP_BUILD:-}" ]; then
  # Verifying an IPA that already exists -- its number is baked in, and this is
  # the path run_upload.sh reuses. Nothing to decide.
  :
elif [ -n "${SKIP_ASC_CHECK:-}" ]; then
  echo "!!  SKIPPED the App Store Connect build-number check (SKIP_ASC_CHECK set)."
else
  set +e
  HIGHEST="$(./scripts/asc_build_numbers.py 2>/tmp/asc_check.$$)"
  asc_rc=$?
  set -e
  case "$asc_rc" in
    0) ;;
    3)
      echo "!!  SKIPPED the App Store Connect build-number check:"
      sed 's/^/!!    /' "/tmp/asc_check.$$" >&2
      echo "!!  Build $EFFECTIVE_BUILD is UNVERIFIED -- altool will reject it if it is taken."
      HIGHEST=""
      ;;
    *)
      cat "/tmp/asc_check.$$" >&2
      rm -f "/tmp/asc_check.$$"
      die "could not determine the highest existing build number. Set SKIP_ASC_CHECK=1 to build anyway."
      ;;
  esac
  rm -f "/tmp/asc_check.$$"
fi

if [ -n "$WANT_NEXT" ]; then
  [ -n "$HIGHEST" ] || die "--next needs App Store Connect, and the query did not run (see above)."
  EFFECTIVE_BUILD=$((HIGHEST + 1))
  echo "==> --next      : highest on App Store Connect is $HIGHEST, using $EFFECTIVE_BUILD"
elif [ -n "$HIGHEST" ] && [ "$EFFECTIVE_BUILD" -le "$HIGHEST" ]; then
  # Expiring a build does NOT free its number: every number ever uploaded stays
  # taken forever, so this compares against the highest, not the highest live.
  die "build number $EFFECTIVE_BUILD is already taken -- App Store Connect holds up to $HIGHEST.
       Next free number is $((HIGHEST + 1)). Expiring old builds does not free their numbers.
       Fix: bump pubspec.yaml to 1.0.0+$((HIGHEST + 1)), or run './run_archive.sh --next'."
fi

echo "==> defines      : $DEFINES"
echo "==> API_BASE_URL : $API_URL"
echo "==> export opts  : $EXPORT_OPTIONS (manageAppVersionAndBuildNumber must be false)"
echo "==> build number : $EFFECTIVE_BUILD${HIGHEST:+  (highest on App Store Connect: $HIGHEST)}"

# ------------------------------------------------------------------- build --
if [ -n "${SKIP_BUILD:-}" ]; then
  echo "==> SKIP_BUILD set: verifying the existing $IPA, building nothing"
else
  rm -f "$IPA"   # so a failed export cannot leave a STALE ipa for run_upload.sh

  # Pass the number explicitly rather than letting pubspec decide implicitly:
  # --next resolves it here, and an explicit value cannot drift from the one
  # this script just checked against App Store Connect.
  flutter build ipa --release \
    --dart-define-from-file="$DEFINES" \
    --export-options-plist="$EXPORT_OPTIONS" \
    --build-number="$EFFECTIVE_BUILD"
fi

[ -f "$IPA" ] || die "no ipa at $IPA"

# --------------------------------------------------------------- the gate --
# A green build says nothing about whether the app is configured: the broken
# builds 1 and 2 both compiled, exported, validated and uploaded cleanly. So
# assert against the artifact that is about to be shipped.
echo "==> verifying the built IPA actually carries its configuration"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
unzip -q -o "$IPA" -d "$work"
snap="$work/Payload/Runner.app/Frameworks/App.framework/App"
plist="$work/Payload/Runner.app/GoogleService-Info.plist"
[ -f "$snap" ] || die "no Dart snapshot at Frameworks/App.framework/App"

count() { strings -a "$1" | grep -c -- "$2" || true; }

# Control first. If `strings` cannot see a value we KNOW is in the bundle, then a
# zero below would mean "the check is blind", not "the config is missing".
if [ "$(count "$plist" 'AIzaSy')" -lt 1 ]; then
  die "self-check failed: no API key found even in GoogleService-Info.plist, so this verification cannot be trusted"
fi

keys="$(count "$snap" 'AIzaSy')"
api="$(count "$snap" "$API_URL")"
tunnel="$(count "$snap" 'trycloudflare.com')"

printf '    %-42s %s\n' 'API keys compiled into the snapshot' "$keys"
printf '    %-42s %s\n' 'production API base compiled in'     "$api"
printf '    %-42s %s\n' 'dev tunnel host present (want 0)'    "$tunnel"

[ "$keys"   -ge 1 ] || die "NO Firebase key in the snapshot -- this is the builds 1/2 failure. Do not upload."
[ "$api"    -ge 1 ] || die "API_BASE_URL not compiled in. Do not upload."
[ "$tunnel" -eq 0 ] || die "a dev tunnel URL is compiled in. Do not upload."

echo
echo "OK: $IPA is configured. Upload with ./run_upload.sh"
