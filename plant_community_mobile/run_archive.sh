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
#   SKIP_BUILD=1 ./run_archive.sh    # re-verify the existing ipa, build nothing
#
# Apple rejects a build number that already exists for the version, and
# ExportOptions sets manageAppVersionAndBuildNumber=false so Xcode will NOT
# silently renumber around a collision -- the upload fails loudly instead. Bump
# pubspec.yaml or pass BUILD_NUMBER.
#
set -euo pipefail

cd "$(dirname "$0")"

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

echo "==> defines      : $DEFINES"
echo "==> API_BASE_URL : $API_URL"
echo "==> export opts  : $EXPORT_OPTIONS (manageAppVersionAndBuildNumber must be false)"
echo "==> build number : $EFFECTIVE_BUILD  (Apple rejects a duplicate; bump pubspec or set BUILD_NUMBER)"

# ------------------------------------------------------------------- build --
if [ -n "${SKIP_BUILD:-}" ]; then
  echo "==> SKIP_BUILD set: verifying the existing $IPA, building nothing"
else
  rm -f "$IPA"   # so a failed export cannot leave a STALE ipa for run_upload.sh

  flutter build ipa --release \
    --dart-define-from-file="$DEFINES" \
    --export-options-plist="$EXPORT_OPTIONS" \
    ${BUILD_NUMBER:+--build-number="$BUILD_NUMBER"}
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
