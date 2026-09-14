#!/usr/bin/env python3
"""Report the highest iOS build number App Store Connect already holds.

WHY THIS EXISTS -- the build number lives as a hand-maintained integer in
pubspec.yaml and nothing checked it against reality. It was wrong twice in two
days (2026-09-12: pubspec said +2, builds 1-5 existed; 2026-09-13: pubspec said
+6, builds 1-9 existed). A duplicate builds cleanly, passes run_archive.sh's IPA
config gate, and is rejected by altool at the very end -- after ~5 minutes of
work. See todos/389.

Expiring a build does NOT free its number. Every number ever uploaded stays
taken forever, which is why "I expired the old ones" does not help.

STDLIB ONLY, DELIBERATELY. Signing an ES256 JWT normally wants PyJWT +
cryptography, which are in backend/venv and nowhere else -- a release script
that only runs when the backend venv happens to be on PATH is a script that
silently stops running. openssl is on every macOS box, so the signature is made
by `openssl dgst` and the DER output converted to JOSE's raw r||s here.

Usage:
    asc_build_numbers.py                 # highest build number on stdout
    asc_build_numbers.py --json          # {"app_id":..,"highest":..,"builds":[..]}

Exit codes:
    0  queried successfully; highest build number printed on stdout
    3  SKIPPED -- credentials absent or App Store Connect unreachable
    1  hard error (bad credentials, app not found, malformed response)

Exit 3 is distinct on purpose: a check that could not run must not look like a
check that passed.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

BUNDLE_ID = "com.plantcommunity.plantCommunityMobile"
API = "https://api.appstoreconnect.apple.com"
CREDS_FILE = ".env.appstore"
KEY_DIR = "~/.appstoreconnect/private_keys"
TIMEOUT = 30


class Skip(Exception):
    """The check could not run. Not a failure of the thing being checked."""


class Fail(Exception):
    """The check ran and something is genuinely wrong."""


# ----------------------------------------------------------------- credentials --


def _read_creds_file(path: str) -> dict[str, str]:
    """Parse KEY=value lines. Parsed, never sourced -- this is not shell."""
    values: dict[str, str] = {}
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                values[key.strip()] = value.strip()
    except OSError:
        return {}
    return values


def load_credentials(creds_path: str) -> tuple[str, str, str]:
    """Return (key_id, issuer_id, private_key_path) or raise Skip."""
    from_file = _read_creds_file(creds_path)
    key_id = os.environ.get("ASC_KEY_ID") or from_file.get("ASC_KEY_ID", "")
    issuer_id = os.environ.get("ASC_ISSUER_ID") or from_file.get("ASC_ISSUER_ID", "")

    if not key_id or not issuer_id:
        raise Skip(
            f"no ASC_KEY_ID/ASC_ISSUER_ID in the environment or {creds_path} "
            f"(gitignored -- this repo is public)"
        )

    key_path = os.path.expanduser(f"{KEY_DIR}/AuthKey_{key_id}.p8")
    if not os.path.isfile(key_path):
        raise Skip(f"no private key at {key_path}")

    return key_id, issuer_id, key_path


# ------------------------------------------------------------------------ jwt --


def _b64url(raw: bytes) -> bytes:
    return base64.urlsafe_b64encode(raw).rstrip(b"=")


def _der_to_raw(der: bytes) -> bytes:
    """Convert an ECDSA DER signature to JOSE's fixed-width r||s.

    openssl emits SEQUENCE { INTEGER r, INTEGER s } with minimal-length,
    sign-extended integers; ES256 wants each padded to exactly 32 bytes.
    """
    if len(der) < 8 or der[0] != 0x30:
        raise Fail("openssl did not return a DER SEQUENCE signature")

    # Skip the SEQUENCE header (long form is possible but never for P-256).
    index = 2 if der[1] < 0x80 else 2 + (der[1] & 0x7F)

    parts = []
    for _ in range(2):
        if der[index] != 0x02:
            raise Fail("malformed DER signature: expected INTEGER")
        length = der[index + 1]
        value = der[index + 2 : index + 2 + length]
        index += 2 + length
        value = value.lstrip(b"\x00")  # drop DER's sign-extension byte
        if len(value) > 32:
            raise Fail("DER integer wider than P-256")
        parts.append(value.rjust(32, b"\x00"))

    return parts[0] + parts[1]


def mint_token(key_id: str, issuer_id: str, key_path: str) -> str:
    """Sign an ES256 App Store Connect JWT using the openssl CLI."""
    header = {"alg": "ES256", "kid": key_id, "typ": "JWT"}
    now = int(time.time())
    payload = {
        "iss": issuer_id,
        "iat": now,
        "exp": now + 600,  # Apple rejects anything over 20 minutes
        "aud": "appstoreconnect-v1",
    }

    def segment(obj: dict) -> bytes:
        return _b64url(json.dumps(obj, separators=(",", ":")).encode("utf-8"))

    signing_input = segment(header) + b"." + segment(payload)

    try:
        result = subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", key_path],
            input=signing_input,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as exc:  # pragma: no cover - openssl ships with macOS
        raise Skip("openssl is not on PATH, cannot sign the request") from exc

    if result.returncode != 0:
        raise Fail(
            "openssl could not sign with "
            f"{key_path}: {result.stderr.decode('utf-8', 'replace').strip()}"
        )

    return (signing_input + b"." + _b64url(_der_to_raw(result.stdout))).decode("ascii")


# ----------------------------------------------------------------------- http --


def get(url: str, token: str) -> dict:
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:400]
        if exc.code in (401, 403):
            raise Fail(f"App Store Connect rejected the credentials ({exc.code}): {body}")
        raise Fail(f"App Store Connect returned {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise Skip(f"App Store Connect unreachable: {exc.reason}") from exc
    except TimeoutError as exc:
        raise Skip(f"App Store Connect timed out after {TIMEOUT}s") from exc


def find_app_id(token: str, bundle_id: str) -> str:
    data = get(f"{API}/v1/apps?limit=200", token)
    for app in data.get("data", []):
        if app.get("attributes", {}).get("bundleId") == bundle_id:
            return app["id"]
    known = sorted(
        app.get("attributes", {}).get("bundleId", "?") for app in data.get("data", [])
    )
    raise Fail(f"no app with bundleId {bundle_id}; the account holds: {known}")


def build_numbers(token: str, app_id: str) -> list[int]:
    """Every build number on the app, expired ones included.

    Expired builds keep their numbers reserved forever, so they must be counted.
    """
    numbers: list[int] = []
    url = f"{API}/v1/builds?filter[app]={app_id}&limit=200"
    while url:
        page = get(url, token)
        for build in page.get("data", []):
            version = build.get("attributes", {}).get("version", "")
            # ASC calls the build number "version"; it is normally an integer
            # but CFBundleVersion permits dotted forms, so take the leading int.
            match = re.match(r"^\s*(\d+)", str(version))
            if match:
                numbers.append(int(match.group(1)))
        url = page.get("links", {}).get("next", "")
    return sorted(set(numbers))


# ----------------------------------------------------------------------- main --


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit full detail as JSON")
    parser.add_argument("--bundle-id", default=BUNDLE_ID)
    parser.add_argument("--creds", default=CREDS_FILE)
    args = parser.parse_args()

    try:
        key_id, issuer_id, key_path = load_credentials(args.creds)
        token = mint_token(key_id, issuer_id, key_path)
        app_id = find_app_id(token, args.bundle_id)
        numbers = build_numbers(token, app_id)
    except Skip as exc:
        print(f"SKIPPED: {exc}", file=sys.stderr)
        return 3
    except Fail as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    highest = max(numbers) if numbers else 0
    if args.json:
        print(json.dumps({"app_id": app_id, "highest": highest, "builds": numbers}))
    else:
        print(highest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
