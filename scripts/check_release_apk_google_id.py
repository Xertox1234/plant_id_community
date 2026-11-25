#!/usr/bin/env python3
"""Fail unless a release APK carries the Google client ID sign-in needs.

google_sign_in_android reads the ``default_web_client_id`` string by name, so
the release resource shrinker drops it unless ``res/raw/keep.xml`` keeps it.

Usage: check_release_apk_google_id.py <app-release.apk>
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "plant_community_mobile/android/app/google-services.json"


def expected_ids() -> set[str]:
    """The web (``client_type`` 3) client IDs in google-services.json."""
    clients = json.loads(CONFIG.read_text())["client"]
    return {
        oauth["client_id"]
        for client in clients
        for oauth in client.get("oauth_client", [])
        if oauth.get("client_type") == 3
    }


def find_aapt2() -> str:
    sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    if not sdk:
        sys.exit("ANDROID_HOME is not set")
    found = list(Path(sdk, "build-tools").glob("*/aapt2"))
    if not found:
        sys.exit(f"no aapt2 under {sdk}/build-tools")
    # Numeric, so 37.0.0 beats 9.0.0.
    return str(
        max(found, key=lambda p: [int(n) for n in re.findall(r"\d+", p.parent.name)])
    )


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    expected = expected_ids()
    if not expected:
        sys.exit(f"no client_type 3 entry in {CONFIG}")
    dump = subprocess.run(
        [find_aapt2(), "dump", "resources", sys.argv[1]],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    match = re.search(r'string/default_web_client_id\b[^\n]*\n\s+\(\) "([^"]*)"', dump)
    if not match:
        sys.exit(
            "default_web_client_id is missing from the APK, so Google sign-in would "
            "fail. Check android/app/src/main/res/raw/keep.xml."
        )
    if match.group(1) not in expected:
        sys.exit("default_web_client_id does not match google-services.json")
    print("default_web_client_id is present and matches google-services.json")


if __name__ == "__main__":
    main()
