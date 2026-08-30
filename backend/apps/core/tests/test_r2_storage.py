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
    for key in (
        "USE_R2",
        "R2_BUCKET_NAME",
        "R2_ACCESS_KEY_ID",
        "R2_SECRET_ACCESS_KEY",
        "R2_ENDPOINT_URL",
        "R2_CUSTOM_DOMAIN",
    ):
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
    env = {**os.environ, **BASE_ENV, **env_overrides}
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
