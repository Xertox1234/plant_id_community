#!/usr/bin/env bash
#
# Run the emulator-backed Firestore offline→online round-trip integration test.
#
# Starts local Firebase Auth + Firestore emulators via `firebase emulators:exec`,
# then runs the integration test on a device/simulator. emulators:exec injects
# FIRESTORE_EMULATOR_HOST / FIREBASE_AUTH_EMULATOR_HOST (matching the ports in
# firebase.json — the single source of truth) into the subprocess; we forward
# those straight to the test as --dart-define values. The test redirects all
# Firestore/Auth traffic to those local emulators (useFirestoreEmulator /
# useAuthEmulator), so production Firebase is never contacted. The emulators are
# torn down when the test finishes.
#
# This is the manual way to exercise the offline→online round-trip — plain
# `flutter test` never scans integration_test/, so the test is not part of the
# default suite or CI. Verified on an iOS simulator (host loopback). An Android
# emulator would also need a debug cleartext exception for the emulator host and
# the 10.0.2.2 loopback alias; that path is not wired up here.
#
# Usage:
#   ./plant_community_mobile/scripts/run_firestore_emulator_test.sh [device-id]
#
# If device-id is omitted, Flutter picks the default connected device.
#
# Requires: firebase CLI, Flutter, and a booted device/simulator.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEVICE="${1:-}"

# Exported so the inner emulators:exec command (single-quoted, run by firebase in
# a child shell) can read it alongside firebase's injected emulator-host vars.
export FLUTTER_DEVICE_ARG=""
if [[ -n "$DEVICE" ]]; then
  export FLUTTER_DEVICE_ARG="-d $DEVICE"
fi

# The app's native [DEFAULT] Firebase app is auto-configured from the bundled
# GoogleService-Info.plist / google-services.json (no FIREBASE_* dart-defines
# needed). The emulator --project must match that native projectId so client
# requests land in the right namespace.
PROJECT_ID="plant-community-prod"

cd "$REPO_ROOT"

firebase emulators:exec --project "$PROJECT_ID" --only auth,firestore '
  cd plant_community_mobile
  flutter test integration_test/firestore_emulator_roundtrip_test.dart $FLUTTER_DEVICE_ARG \
    --dart-define=FIRESTORE_EMULATOR_HOST="$FIRESTORE_EMULATOR_HOST" \
    --dart-define=FIREBASE_AUTH_EMULATOR_HOST="$FIREBASE_AUTH_EMULATOR_HOST"
'
