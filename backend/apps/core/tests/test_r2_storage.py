"""
STORAGES / USE_R2 flag (todo 305).

STORAGES and the USE_R2 fail-fast check are computed once at settings
import time, so the only way to exercise a different USE_R2 value is a
fresh interpreter — override_settings() can't re-run that module-level
logic. The subprocess tests below spawn `manage.py check` with controlled
env vars for exactly that reason; the "flag off" behavior (this suite's
own running state) is asserted in-process since it needs no fresh
interpreter.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase
from plant_community_backend.r2_config import (
    R2_CACHE_CONTROL,
    R2_REGION_NAME,
    R2_REQUIRED_VARS,
)

BACKEND_DIR = Path(__file__).resolve().parents[3]

# Minimum env manage.py needs to get through settings.py without unrelated
# failures (JWT/SECRET_KEY length checks, DB URL) — mirrors the Dockerfile's
# own build-only throwaway values.
BASE_ENV = {
    "JWT_SECRET_KEY": "test-only-throwaway-value-not-a-real-key-00000000000000",  # pragma: allowlist secret
    "SECRET_KEY": "test-only-throwaway-value-not-a-real-key-0000000000000000000000000",  # pragma: allowlist secret
    "DATABASE_URL": "sqlite:////tmp/r2_storage_test.sqlite3",
}


def _run_check(**env_overrides):
    """Run `manage.py check` in a fresh interpreter with the given env."""
    env = {**os.environ, **BASE_ENV}
    # Explicitly blank these — NOT pop(). decouple.Config.get() checks
    # os.environ first, but for a key merely ABSENT from it falls through
    # to backend/.env on disk (verified against decouple's source) rather
    # than the default="" this test relies on. This project's own R2
    # rotation runbook (secret-management.md) has an operator write real
    # R2_* values into backend/.env — on that machine, popping the key
    # would silently leak the real value in here. An explicit "" stays
    # present-but-falsy, which is what validate_environment() itself checks.
    # Driven by the shared tuple (todo 321) so a newly added R2 var is blanked
    # here automatically — a var this loop forgets is one that CAN leak a real
    # backend/.env value into these tests.
    for key in ("USE_R2", *R2_REQUIRED_VARS):
        env[key] = ""
    env.update(env_overrides)
    return subprocess.run(
        [sys.executable, "manage.py", "check"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _print_storages(**env_overrides):
    """Run a fresh interpreter and dump settings.STORAGES as JSON."""
    env = {**os.environ, **BASE_ENV}
    # Blank first, overrides second — same reasoning as _run_check above, and it
    # matters more here: this helper prints STORAGES to stdout, so a caller that
    # overrides only SOME vars would dump an operator's real backend/.env
    # credentials into the test output. Structural guard, not caller discipline.
    for key in ("USE_R2", *R2_REQUIRED_VARS):
        env[key] = ""
    env.update(env_overrides)
    result = subprocess.run(
        [
            sys.executable,
            "manage.py",
            "shell",
            "-c",
            "import json; from django.conf import settings; "
            "print('STORAGES_JSON:' + json.dumps(settings.STORAGES))",
        ],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    for line in result.stdout.splitlines():
        if line.startswith("STORAGES_JSON:"):
            return json.loads(line[len("STORAGES_JSON:") :])
    raise AssertionError(
        f"STORAGES_JSON not found in output:\n{result.stdout}\n{result.stderr}"
    )


class StoragesFlagOffTests(SimpleTestCase):
    """AC1: dev/test unchanged when USE_R2 is unset — asserted in-process."""

    def test_use_r2_defaults_false(self):
        self.assertFalse(settings.USE_R2)

    def test_default_storage_is_filesystem(self):
        self.assertEqual(
            settings.STORAGES["default"]["BACKEND"],
            "django.core.files.storage.FileSystemStorage",
        )

    def test_staticfiles_storage_unchanged_from_djangos_own_default(self):
        # Pins that defining STORAGES explicitly (for R2) doesn't change
        # "staticfiles" from what Django was already resolving pre-PR.
        # STATICFILES_STORAGE ("whitenoise...") is dead since Django 5.1
        # removed the shim that used to synthesize STORAGES from it (see
        # docs/deployment/railway.md: "vestigial") — reactivating whitenoise
        # here would be an unrelated, out-of-scope behavior change.
        self.assertEqual(
            settings.STORAGES["staticfiles"]["BACKEND"],
            "django.contrib.staticfiles.storage.StaticFilesStorage",
        )


class StoragesFlagOnTests(SimpleTestCase):
    """USE_R2=True resolves to S3Storage with the exact required OPTIONS."""

    def test_s3_storage_options(self):
        storages = _print_storages(
            DEBUG="True",
            USE_R2="True",
            R2_BUCKET_NAME="test-bucket",
            R2_ACCESS_KEY_ID="test-key",
            R2_SECRET_ACCESS_KEY="test-secret",  # pragma: allowlist secret
            R2_ENDPOINT_URL="https://example.r2.cloudflarestorage.com",
            R2_CUSTOM_DOMAIN="media.example.com",
        )
        default = storages["default"]
        self.assertEqual(default["BACKEND"], "storages.backends.s3.S3Storage")
        options = default["OPTIONS"]
        self.assertEqual(options["bucket_name"], "test-bucket")
        self.assertEqual(options["custom_domain"], "media.example.com")
        # The two settings most likely to be missed, and each defeats an AC
        # on its own if wrong (see settings.py comments for why).
        self.assertIs(options["querystring_auth"], False)
        self.assertIs(options["file_overwrite"], False)
        self.assertNotIn("default_acl", options)


class StoragesSharedConfigTests(SimpleTestCase):
    """STORAGES reads r2_config's shared definitions, not its own copies (todo 321).

    The STORAGES block still spells out each `"<option>": config("R2_*")` line —
    those map env vars onto django-storages' own option names. This test is what
    keeps that hand-written block honest against r2_config.py.
    """

    # Which django-storages OPTION each env var must land in. Hand-written on
    # purpose — this is the single place that mapping is asserted, so adding a
    # var to r2_config fails here until someone states where it feeds. Checking
    # the option BY KEY (not just "the value appears somewhere in OPTIONS")
    # is what catches a swapped access_key/secret_key.
    VAR_TO_OPTION = {
        "R2_BUCKET_NAME": "bucket_name",
        "R2_ACCESS_KEY_ID": "access_key",
        # Not a credential — "secret_key" is django-storages' option NAME.
        "R2_SECRET_ACCESS_KEY": "secret_key",  # pragma: allowlist secret
        "R2_ENDPOINT_URL": "endpoint_url",
        "R2_CUSTOM_DOMAIN": "custom_domain",
    }

    def test_storages_consumes_the_shared_definitions(self):
        self.assertEqual(
            tuple(self.VAR_TO_OPTION),
            R2_REQUIRED_VARS,
            "a var was added to r2_config without saying which STORAGES option "
            "it feeds — add it to VAR_TO_OPTION",
        )
        # One unique sentinel per var: whichever var STORAGES stops reading (or
        # reads into the wrong option), this fails naming that var.
        sentinels = {var: f"sentinel-{var.lower()}" for var in R2_REQUIRED_VARS}
        storages = _print_storages(DEBUG="True", USE_R2="True", **sentinels)
        options = storages["default"]["OPTIONS"]

        for var, option in self.VAR_TO_OPTION.items():
            with self.subTest(var=var):
                self.assertEqual(
                    options.get(option),
                    sentinels[var],
                    f"STORAGES option {option!r} should carry {var}",
                )

        self.assertEqual(options["region_name"], R2_REGION_NAME)
        # The settings-side Cache-Control had no assertion before todo 321 —
        # only the sync command's copy of the string was covered.
        self.assertEqual(options["object_parameters"]["CacheControl"], R2_CACHE_CONTROL)


class ValidateEnvironmentR2Tests(SimpleTestCase):
    """validate_environment() fails fast for missing R2_* vars in production."""

    def test_missing_r2_vars_fails_fast_in_production(self):
        result = _run_check(
            DEBUG="False",
            ALLOWED_HOSTS="example.com",
            CSRF_TRUSTED_ORIGINS="https://example.com",
            PLANT_ID_API_KEY="1" * 32,
            CORS_ALLOWED_ORIGINS="https://example.com",
            REDIS_URL="redis://localhost:6379/1",
            USE_R2="True",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("R2_BUCKET_NAME is required", result.stderr)
        # Anchors the URL-only arm from OUTSIDE the R2_REQUIRED_VARS
        # composition (todo 321): shrinking R2_URL_ONLY_VARS to () would stop
        # production requiring R2_CUSTOM_DOMAIN, and every other test in this
        # file derives its expectations from that same tuple, so all of them
        # would shrink with it and stay green.
        self.assertIn("R2_CUSTOM_DOMAIN is required", result.stderr)

    def test_configured_r2_vars_pass_in_production(self):
        result = _run_check(
            DEBUG="False",
            ALLOWED_HOSTS="example.com",
            CSRF_TRUSTED_ORIGINS="https://example.com",
            PLANT_ID_API_KEY="1" * 32,
            CORS_ALLOWED_ORIGINS="https://example.com",
            REDIS_URL="redis://localhost:6379/1",
            USE_R2="True",
            R2_BUCKET_NAME="test-bucket",
            R2_ACCESS_KEY_ID="test-key",
            R2_SECRET_ACCESS_KEY="test-secret",  # pragma: allowlist secret
            R2_ENDPOINT_URL="https://example.r2.cloudflarestorage.com",
            R2_CUSTOM_DOMAIN="media.example.com",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_flag_off_does_not_require_r2_vars_in_production(self):
        result = _run_check(
            DEBUG="False",
            ALLOWED_HOSTS="example.com",
            CSRF_TRUSTED_ORIGINS="https://example.com",
            PLANT_ID_API_KEY="1" * 32,
            CORS_ALLOWED_ORIGINS="https://example.com",
            REDIS_URL="redis://localhost:6379/1",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_r2_vars_warns_but_does_not_crash_in_debug(self):
        # The STORAGES block that builds S3Storage's OPTIONS has no DEBUG
        # guard, so a dev/scratch server with USE_R2=True and blank vars
        # would otherwise boot clean and fail later with an opaque boto3
        # error far from the real cause. This must be visible at startup
        # even though it isn't fatal outside production.
        result = _run_check(DEBUG="True", USE_R2="True")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("R2_BUCKET_NAME is required", result.stdout + result.stderr)
