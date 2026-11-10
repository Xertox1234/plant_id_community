#!/usr/bin/env python3
"""Emulator tests for firebase/firestore.rules and firebase/storage.rules
(auth audit M15, todo 707).

Run from the repo root (needs Java and firebase-tools; no credentials):

    firebase emulators:exec --only firestore,storage --project demo-rules \
        "python3 scripts/test_firebase_rules_emulator.py"

The emulators accept an unsigned ID token, so each case states who is asking
(uid, verified or not) and what the rules must answer. Standard library only.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request

PROJECT = os.environ.get("GCLOUD_PROJECT", "demo-rules")
HOST = os.environ.get("FIRESTORE_EMULATOR_HOST", "127.0.0.1:8080")
DOCS = f"http://{HOST}/v1/projects/{PROJECT}/databases/(default)/documents"
STORAGE_HOST = os.environ.get("FIREBASE_STORAGE_EMULATOR_HOST", "127.0.0.1:9199")
BUCKET = f"http://{STORAGE_HOST}/v0/b/{PROJECT}.appspot.com/o"
ADMIN = "owner"  # the emulator's rules-bypass bearer token
PLANT = {"fields": {"name": {"stringValue": "Monstera"}}}

ALLOWED = 200
DENIED = 403


def _b64(data: dict) -> str:
    raw = json.dumps(data).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def token(uid: str, *, verified: bool, provider: str = "password") -> str:
    now = int(time.time())
    claims = {
        "iss": f"https://securetoken.google.com/{PROJECT}",
        "aud": PROJECT,
        "sub": uid,
        "user_id": uid,
        "email": f"{uid}@example.com",
        "email_verified": verified,
        "iat": now,
        "auth_time": now,
        "exp": now + 3600,
        "firebase": {"sign_in_provider": provider, "identities": {}},
    }
    return f"{_b64({'alg': 'none', 'typ': 'JWT'})}.{_b64(claims)}."


def _send(request: urllib.request.Request, bearer: str | None) -> int:
    if bearer:
        request.add_header("Authorization", f"Bearer {bearer}")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


def call(method: str, path: str, bearer: str | None, body: dict | None = None) -> int:
    request = urllib.request.Request(  # noqa: S310 - fixed http:// emulator URL
        f"{DOCS}/{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
    )
    return _send(request, bearer)


def upload(name: str, bearer: str | None) -> int:
    request = urllib.request.Request(  # noqa: S310 - fixed http:// emulator URL
        f"{BUCKET}?name={urllib.parse.quote(name, safe='')}",
        method="POST",
        data=b"not really a png",
        headers={"Content-Type": "image/png"},
    )
    return _send(request, bearer)


def download(name: str, bearer: str | None) -> int:
    request = urllib.request.Request(  # noqa: S310 - fixed http:// emulator URL
        f"{BUCKET}/{urllib.parse.quote(name, safe='')}?alt=media"
    )
    return _send(request, bearer)


def wipe() -> None:
    url = (
        f"http://{HOST}/emulator/v1/projects/{PROJECT}"
        "/databases/(default)/documents"
    )
    request = urllib.request.Request(url, method="DELETE")  # noqa: S310
    urllib.request.urlopen(request, timeout=10).close()  # noqa: S310


ADA = token("ada", verified=True)
ADA_UNVERIFIED = token("ada", verified=False)
BOB = token("bob", verified=True)
ADA_PLANT = "users/ada/identified_plants/p1"


class RulesCase(unittest.TestCase):
    def setUp(self) -> None:
        wipe()
        # A plant of Ada's already in place, written past the rules.
        self.assertEqual(call("PATCH", ADA_PLANT, ADMIN, PLANT), ALLOWED)


class TheEmulatorEnforcesRules(RulesCase):
    """Guard against a false green: prove a denial is possible at all."""

    def test_an_undeclared_path_is_denied_and_admin_is_not(self) -> None:
        self.assertEqual(call("PATCH", "nowhere/x", ADA, PLANT), DENIED)
        self.assertEqual(call("PATCH", "nowhere/x", ADMIN, PLANT), ALLOWED)


class IdentifiedPlants(RulesCase):
    """The one path the app uses: users/{uid}/identified_plants/{plantId}."""

    def test_a_verified_owner_reads_lists_writes_and_deletes(self) -> None:
        self.assertEqual(call("GET", ADA_PLANT, ADA), ALLOWED)
        self.assertEqual(call("GET", "users/ada/identified_plants", ADA), ALLOWED)
        self.assertEqual(
            call("PATCH", "users/ada/identified_plants/p2", ADA, PLANT), ALLOWED
        )
        self.assertEqual(call("PATCH", ADA_PLANT, ADA, PLANT), ALLOWED)
        self.assertEqual(call("DELETE", ADA_PLANT, ADA), ALLOWED)

    def test_an_unverified_owner_can_do_nothing(self) -> None:
        self.assertEqual(call("GET", ADA_PLANT, ADA_UNVERIFIED), DENIED)
        self.assertEqual(
            call("GET", "users/ada/identified_plants", ADA_UNVERIFIED), DENIED
        )
        self.assertEqual(
            call("PATCH", "users/ada/identified_plants/p2", ADA_UNVERIFIED, PLANT),
            DENIED,
        )
        self.assertEqual(call("PATCH", ADA_PLANT, ADA_UNVERIFIED, PLANT), DENIED)
        self.assertEqual(call("DELETE", ADA_PLANT, ADA_UNVERIFIED), DENIED)

    def test_another_verified_user_can_do_nothing(self) -> None:
        self.assertEqual(call("GET", ADA_PLANT, BOB), DENIED)
        self.assertEqual(call("GET", "users/ada/identified_plants", BOB), DENIED)
        self.assertEqual(call("PATCH", ADA_PLANT, BOB, PLANT), DENIED)
        self.assertEqual(call("DELETE", ADA_PLANT, BOB), DENIED)

    def test_no_sign_in_can_do_nothing(self) -> None:
        self.assertEqual(call("GET", ADA_PLANT, None), DENIED)
        self.assertEqual(call("PATCH", ADA_PLANT, None, PLANT), DENIED)

    def test_an_anonymous_sign_in_can_do_nothing(self) -> None:
        anonymous = token("ada", verified=False, provider="anonymous")
        self.assertEqual(call("GET", ADA_PLANT, anonymous), DENIED)
        self.assertEqual(call("PATCH", ADA_PLANT, anonymous, PLANT), DENIED)


class EverythingElseIsClosed(RulesCase):
    """No client reads or writes these, so nobody may (they were open to any
    signed-in Firebase account, verified or not)."""

    def _owned(self) -> dict:
        return {"fields": {"user_id": {"stringValue": "ada"}}}

    def test_the_user_document_itself(self) -> None:
        self.assertEqual(call("PATCH", "users/ada", ADA, PLANT), DENIED)
        self.assertEqual(call("GET", "users/ada", ADA), DENIED)

    def test_collections_no_client_uses(self) -> None:
        for collection in (
            "plant_identifications",
            "user_plants",
            "disease_diagnoses",
            "sync_queue",
        ):
            with self.subTest(collection=collection):
                path = f"{collection}/doc1"
                self.assertEqual(call("PATCH", path, ADA, self._owned()), DENIED)
                self.assertEqual(call("PATCH", path, ADMIN, self._owned()), ALLOWED)
                self.assertEqual(call("GET", path, ADA), DENIED)
                self.assertEqual(call("DELETE", path, ADA), DENIED)

    def test_user_preferences(self) -> None:
        self.assertEqual(call("PATCH", "user_preferences/ada", ADA, PLANT), DENIED)
        self.assertEqual(call("GET", "user_preferences/ada", ADA), DENIED)

    def test_a_public_plant_is_not_readable_by_other_accounts(self) -> None:
        public = {
            "fields": {
                "user_id": {"stringValue": "ada"},
                "is_public": {"booleanValue": True},
            }
        }
        self.assertEqual(call("PATCH", "user_plants/pub", ADMIN, public), ALLOWED)
        self.assertEqual(call("GET", "user_plants/pub", BOB), DENIED)


class StorageIsClosed(unittest.TestCase):
    """No client uses Firebase Storage (removed from the app by #1251), so
    every path refuses every caller. The paths are the ones the old rules
    opened."""

    PATHS = ("avatars/ada.png", "plant-identifications/ada/leaf.png", "new/x.png")

    def test_the_emulator_enforces_rules(self) -> None:
        self.assertEqual(upload("guard/x.png", ADMIN), ALLOWED)
        self.assertEqual(download("guard/x.png", ADMIN), ALLOWED)

    def test_every_upload_is_refused(self) -> None:
        for name in self.PATHS:
            for who in (ADA, ADA_UNVERIFIED, None):
                with self.subTest(name=name, signed_in=who is not None):
                    self.assertEqual(upload(name, who), DENIED)

    def test_every_read_is_refused(self) -> None:
        for name in self.PATHS:
            self.assertEqual(upload(name, ADMIN), ALLOWED)
            for who in (ADA, BOB, None):
                with self.subTest(name=name, signed_in=who is not None):
                    self.assertEqual(download(name, who), DENIED)


if __name__ == "__main__":
    missing = [
        name
        for name in ("FIRESTORE_EMULATOR_HOST", "FIREBASE_STORAGE_EMULATOR_HOST")
        if name not in os.environ
    ]
    if missing:
        sys.exit(
            f"{', '.join(missing)} not set: run this through `firebase "
            "emulators:exec --only firestore,storage --project demo-rules`."
        )
    unittest.main(verbosity=2)
