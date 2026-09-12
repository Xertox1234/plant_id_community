#!/usr/bin/env python3
"""Verify that the Firebase client API keys are restricted the way we think.

Manual tool, not a CI gate: it needs the real key strings and talks to Google.
Run it after ANY change to a key's restrictions, and before distributing a build.

Two independent halves, because a key has two independent restrictions and losing
either one is silent:

  APPLICATION  which clients may use the key (bundle id / package+SHA-1).
               `gcloud services api-keys update --api-target=...` REPLACES the
               whole restrictions object, so narrowing the API list without
               restating the application restriction quietly deletes it.
  API          which services the key may call.

Why probing is worth doing at all when `gcloud ... describe` already prints the
config: the config says what was *requested*. This says what Google *enforces*.

  exit 0  every case matched expectation
  exit 1  at least one did not
  exit 2  could not look (config unreadable) -- never reported as success

THE TRAP THIS SCRIPT EXISTS TO AVOID
------------------------------------
Most Google endpoints do not evaluate an API key at all. `firebaseappdistribution`
is OAuth-only ("API keys are not supported by this API"); `firestore` REST and
`firebasestorage` v0 both deny on SECURITY RULES before the key is considered.
Probing those and seeing "not blocked" proves nothing -- they answer identically
for a fabricated key -- yet it reads exactly like a pass.

So every API probe is sent TWICE: once with the real key, once with a
syntactically valid fake. The fake MUST come back API_KEY_INVALID. If it does not,
the endpoint is not consulting the key and the target is reported INCONCLUSIVE
rather than counted as evidence either way.
"""
from __future__ import annotations

import json
import plistlib
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MOBILE = REPO / "plant_community_mobile"

PROJECT = "plant-community-prod"
PROJECT_NUMBER = "190351417275"

IOS_BUNDLE = "com.plantcommunity.plantCommunityMobile"
ANDROID_PKG = "com.plantcommunity.plant_community_mobile"
# Debug-keystore SHA-1. Release still signs with the debug key -- todo 383 item 3.
# Not a secret: a certificate fingerprint is derived from a PUBLIC certificate,
# is readable from any APK, and is already the value registered on the Android
# key's restriction. detect-secrets sees only a high-entropy hex string.
ANDROID_SHA1 = "068a6f6a4ff91559a9d03b5bbd8f9f0e3b2a7dc2"  # pragma: allowlist secret

# Same shape as a real key, guaranteed not to be one.
FAKE_KEY = "AIzaSyA0000000000000000000000000000000000"

# Firebase's documented product-to-API mapping for the products this app uses:
# Authentication, Cloud Firestore, Cloud Storage, Cloud Messaging.
# https://firebase.google.com/docs/projects/api-keys
EXPECTED_TARGETS = {
    "firebase.googleapis.com",                 # all products
    "logging.googleapis.com",                  # all products
    "identitytoolkit.googleapis.com",          # Authentication
    "securetoken.googleapis.com",              # Authentication
    "firebaserules.googleapis.com",            # Firestore AND Storage
    "datastore.googleapis.com",                # Cloud Firestore
    "firestore.googleapis.com",                # Cloud Firestore
    "firebasestorage.googleapis.com",          # Cloud Storage
    "firebaseinstallations.googleapis.com",    # Cloud Messaging
    "fcmregistrations.googleapis.com",         # Cloud Messaging
}


class Indeterminate(Exception):
    """Could not look. Never the same thing as looking and finding nothing wrong."""


def load_keys() -> tuple[str, str]:
    try:
        plist = MOBILE / "ios/Runner/GoogleService-Info.plist"
        ios = plistlib.loads(plist.read_bytes())["API_KEY"]
        gs = MOBILE / "android/app/google-services.json"
        android = json.loads(gs.read_text())["client"][0]["api_key"][0]["current_key"]
    except (OSError, ValueError, KeyError, IndexError) as exc:
        raise Indeterminate(f"cannot read the committed Firebase configs: {exc!r}") from exc
    return ios, android


def post(url: str, headers: list[str], body: str | None) -> str:
    cmd = ["curl", "-s", "-m", "25", url]
    if body is not None:
        cmd += ["-X", "POST", "-H", "Content-Type: application/json", "-d", body]
    for h in headers:
        cmd += ["-H", h]
    return subprocess.run(cmd, capture_output=True, text=True).stdout


def api_probes(key: str) -> list[tuple[str, str, str | None, str]]:
    """(service, url, body, expectation) -- expectation is 'keep' or 'drop'."""
    return [
        ("identitytoolkit",
         f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={key}", "{}", "keep"),
        ("securetoken",
         f"https://securetoken.googleapis.com/v1/token?key={key}",
         '{"grant_type":"refresh_token","refresh_token":"probe-not-a-real-token"}', "keep"),
        ("firebaseinstallations",
         f"https://firebaseinstallations.googleapis.com/v1/projects/{PROJECT}/installations?key={key}",
         "{}", "keep"),
        # Dropped AND enabled project-wide, so a block here can only be the key.
        # An API that is merely disabled would answer SERVICE_DISABLED and prove
        # nothing, which is why sqladmin -- the scary-looking one -- is useless here.
        ("firebaseremoteconfig",
         f"https://firebaseremoteconfig.googleapis.com/v1/projects/{PROJECT_NUMBER}"
         f"/namespaces/firebase:fetch?key={key}",
         '{"app_instance_id":"probe","app_id":"probe"}', "drop"),
        # CANARY. This endpoint is OAuth-only and never evaluates an API key, so
        # it MUST come back INCONCLUSIVE. It is here so the self-check is
        # exercised on every run rather than sitting dormant: neutering the
        # fake-key screen makes this row claim a verdict, and the run fails.
        # Without it, deleting the screen entirely changed nothing (MUTANT3).
        ("firebaseappdistribution(canary)",
         f"https://firebaseappdistribution.googleapis.com/v1/projects/{PROJECT_NUMBER}"
         f"/apps/probe/releases?key={key}", None, "inconclusive"),
    ]


def check_api_targets(name: str, key: str, headers: list[str]) -> int:
    print(f"  API restriction -- {name}")
    failures = 0
    for svc, url, body, expect in api_probes(key):
        real = post(url, headers, body)
        fake = post(url.replace(key, FAKE_KEY), headers, body)

        if "API_KEY_INVALID" not in fake:
            got, verdict = "inconclusive", "endpoint ignores API keys; proves nothing"
        elif "SERVICE_DISABLED" in real:
            got, verdict = "inconclusive", "service off project-wide; proves nothing"
        elif "API_KEY_SERVICE_BLOCKED" in real:
            got, verdict = "drop", "BLOCKED"
        else:
            got, verdict = "keep", "reachable"

        ok = got == expect
        failures += not ok
        # An unexpected INCONCLUSIVE is a FAIL, not a shrug: it means the probe
        # stopped being able to see, which is the failure mode this whole script
        # is built around.
        print(f"    {'PASS' if ok else 'FAIL':4s}         {svc:31s} expect {expect:12s} -> {verdict}")
    return failures


def check_app_restriction(ios: str, android: str) -> int:
    print("  APPLICATION restriction -- each key must admit only its own platform")
    ios_h = [f"X-Ios-Bundle-Identifier: {IOS_BUNDLE}"]
    and_h = [f"X-Android-Package: {ANDROID_PKG}", f"X-Android-Cert: {ANDROID_SHA1}"]
    wrong = ["X-Ios-Bundle-Identifier: com.attacker.app"]

    cases = [
        ("iOS", ios, "own iOS headers", ios_h, "ADMIT"),
        ("iOS", ios, "no headers", [], "BLOCK"),
        ("iOS", ios, "wrong bundle id", wrong, "BLOCK"),
        ("iOS", ios, "Android headers", and_h, "BLOCK"),
        ("Android", android, "own Android headers", and_h, "ADMIT"),
        ("Android", android, "no headers", [], "BLOCK"),
        ("Android", android, "iOS headers", ios_h, "BLOCK"),
        ("Android", android, "wrong bundle id", wrong, "BLOCK"),
    ]
    failures = 0
    for plat, key, desc, headers, expect in cases:
        body = post(f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={key}",
                    headers, "{}")
        # Match the machine-readable reason, not the prose. The message says
        # "...are blocked." in LOWER case; an uppercase-only match scored six
        # correct blocks as failures once.
        blocked = re.search(r"API_KEY_\w*APP_BLOCKED|are blocked", body, re.I)
        got = "BLOCK" if blocked else ("ADMIT" if "MISSING_ID_TOKEN" in body else "?")
        ok = got == expect
        failures += not ok
        print(f"    {'PASS' if ok else 'FAIL':4s}         {plat:8s} {desc:20s} expect {expect} -> {got}")
    return failures


def check_config() -> int:
    """The configured targets, read back from GCP rather than assumed."""
    print("  CONFIG read-back -- gcloud services api-keys list")
    try:
        out = subprocess.run(
            ["gcloud", "services", "api-keys", "list", f"--project={PROJECT}", "--format=json"],
            capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        raise Indeterminate(f"gcloud unavailable: {exc!r}") from exc
    if out.returncode != 0:
        raise Indeterminate(f"gcloud failed: {out.stderr.strip()[:200]}")
    try:
        keys = json.loads(out.stdout)
    except ValueError as exc:
        raise Indeterminate(f"gcloud did not return JSON: {exc!r}") from exc

    failures = 0
    for k in keys:
        r = k.get("restrictions", {})
        targets = {t["service"] for t in r.get("apiTargets", [])}
        app = [x for x in r if x != "apiTargets"]
        label = k["displayName"][:34]
        if "Browser" in label:
            print(f"    NOTE         {label:36s} present; see todo 383 item 6")
            continue
        ok_t = targets == EXPECTED_TARGETS
        ok_a = bool(app)
        failures += not (ok_t and ok_a)
        print(f"    {'PASS' if ok_t and ok_a else 'FAIL':4s}         {label:36s} "
              f"{len(targets)} targets, app restriction: {app or 'MISSING'}")
        if not ok_t:
            if extra := targets - EXPECTED_TARGETS:
                print(f"                   unexpected: {sorted(extra)}")
            if missing := EXPECTED_TARGETS - targets:
                print(f"                   MISSING:    {sorted(missing)}")
    return failures


def main() -> int:
    try:
        ios, android = load_keys()
        print(f"Firebase key restrictions -- {PROJECT}\n")
        failures = check_config()
        print()
        failures += check_app_restriction(ios, android)
        print()
        failures += check_api_targets("iOS key", ios, [f"X-Ios-Bundle-Identifier: {IOS_BUNDLE}"])
        failures += check_api_targets(
            "Android key", android,
            [f"X-Android-Package: {ANDROID_PKG}", f"X-Android-Cert: {ANDROID_SHA1}"])
    except Indeterminate as exc:
        print(f"\nINDETERMINATE: {exc}", file=sys.stderr)
        print("Could not verify. This is NOT a pass.", file=sys.stderr)
        return 2

    print()
    print("All checks matched expectation." if not failures
          else f"{failures} check(s) did not match expectation.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
