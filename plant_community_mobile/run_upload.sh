#!/bin/bash
#
# Upload the built IPA to App Store Connect.
#
# Refuses to upload an IPA that has not passed run_archive.sh's verification.
# That is the whole point: on 2026-09-12 two builds uploaded cleanly -- xcodebuild
# green, altool "No errors uploading archive", Apple accepted both -- and both
# opened to the configuration-error screen because no --dart-define reached the
# Dart compiler. A successful upload is not evidence the app works. See
# todos/383 items 8 and 9.
#
# Credentials: ASC_KEY_ID / ASC_ISSUER_ID come from .env.appstore (gitignored) or
# the environment. They are identifiers, not the credential -- the secret is
# ~/.appstoreconnect/private_keys/AuthKey_<ASC_KEY_ID>.p8, which altool reads
# itself. This repo is public, so neither value is committed.
#
#   .env.appstore:
#     ASC_KEY_ID=XXXXXXXXXX
#     ASC_ISSUER_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
#
# Usage:
#   ./run_upload.sh              # verify, then upload
#   VALIDATE_ONLY=1 ./run_upload.sh   # verify + altool --validate-app, no upload
#
set -euo pipefail

cd "$(dirname "$0")"

IPA="build/ios/ipa/plant_community_mobile.ipa"
CREDS="${CREDS:-.env.appstore}"

die() { echo "ERROR: $*" >&2; exit 1; }

[ -f "$CREDS" ] || die "missing $CREDS (gitignored). See the header of this script."

# Parsed, not sourced: `. file` would execute whatever the file contains.
# `|| true`: without it, set -e aborts at the assignment below when a key is
# absent, and the script exits 1 with NO message explaining which one.
val() { grep -E "^$1=" "$CREDS" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '[:space:]' || true; }
ASC_KEY_ID="${ASC_KEY_ID:-$(val ASC_KEY_ID)}"
ASC_ISSUER_ID="${ASC_ISSUER_ID:-$(val ASC_ISSUER_ID)}"

[ -n "$ASC_KEY_ID" ]    || die "$CREDS defines no ASC_KEY_ID"
[ -n "$ASC_ISSUER_ID" ] || die "$CREDS defines no ASC_ISSUER_ID"
[ -f "$HOME/.appstoreconnect/private_keys/AuthKey_${ASC_KEY_ID}.p8" ] \
  || die "no AuthKey_${ASC_KEY_ID}.p8 in ~/.appstoreconnect/private_keys/"
[ -f "$IPA" ] || die "no ipa at $IPA -- run ./run_archive.sh first"

# ---- gate: reuse run_archive.sh's verification rather than duplicating it ----
echo "==> verifying $IPA before upload"
SKIP_BUILD=1 ./run_archive.sh >/dev/null 2>&1 \
  || die "$IPA FAILED verification -- refusing to upload. Run 'SKIP_BUILD=1 ./run_archive.sh' to see why."
echo "    verification passed"

if [ -n "${VALIDATE_ONLY:-}" ]; then
  echo "==> VALIDATE_ONLY: validating without uploading"
  exec xcrun altool --validate-app -f "$IPA" -t ios \
    --apiKey "$ASC_KEY_ID" --apiIssuer "$ASC_ISSUER_ID"
fi

echo "==> uploading to App Store Connect"
xcrun altool --upload-app -f "$IPA" -t ios \
  --apiKey "$ASC_KEY_ID" --apiIssuer "$ASC_ISSUER_ID"

echo
echo "Uploaded. A successful upload is NOT proof the build runs -- confirm the"
echo "build appears in App Store Connect, then install it and sign in."
