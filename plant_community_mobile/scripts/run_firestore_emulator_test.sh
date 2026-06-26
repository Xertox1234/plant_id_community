#!/usr/bin/env bash
#
# Run the emulator-backed Firestore offline→online round-trip integration test.
#
# Starts local Firebase Auth + Firestore emulators via `firebase emulators:exec`,
# then runs the integration test on a device/simulator with the emulator host/port
# passed in as --dart-define values. The test redirects all Firestore/Auth traffic
# to those local emulators (useFirestoreEmulator/useAuthEmulator), so production
# Firebase is never contacted. The emulators are torn down when the test finishes.
#
# Usage:
#   ./plant_community_mobile/scripts/run_firestore_emulator_test.sh [device-id]
#
# If device-id is omitted, Flutter picks the default connected device. Verified on
# an iOS simulator, which reaches the emulators on 127.0.0.1. An Android emulator
# reaches the host at 10.0.2.2 (pass FIRESTORE_EMULATOR_HOST=10.0.2.2:8080 and the
# matching FIREBASE_AUTH_EMULATOR_HOST), but ALSO needs a debug-manifest cleartext
# exception for those hosts — not currently configured, so use iOS for now.
#
# Requires: firebase CLI, Flutter, and a booted device/simulator.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEVICE="${1:-}"
FS_HOST="${FIRESTORE_EMULATOR_HOST:-127.0.0.1:8080}"
AUTH_HOST="${FIREBASE_AUTH_EMULATOR_HOST:-127.0.0.1:9099}"

DEVICE_ARG=""
if [[ -n "$DEVICE" ]]; then
  DEVICE_ARG="-d $DEVICE"
fi

# The app's native [DEFAULT] Firebase app is auto-configured from the bundled
# GoogleService-Info.plist / google-services.json, so the test reuses that config
# (no FIREBASE_* dart-defines needed). The emulator --project must match that
# native projectId so client requests land in the right namespace. All Firestore
# and Auth traffic is redirected to the local emulators, so prod is never reached.
PROJECT_ID="plant-community-prod"

cd "$REPO_ROOT"

firebase emulators:exec --project "$PROJECT_ID" --only auth,firestore \
  "cd plant_community_mobile && flutter test \
     integration_test/firestore_emulator_roundtrip_test.dart $DEVICE_ARG \
     --dart-define=FIRESTORE_EMULATOR_HOST=$FS_HOST \
     --dart-define=FIREBASE_AUTH_EMULATOR_HOST=$AUTH_HOST"
