"""
sync_media_to_r2 management command (todo 305).

Never hits real R2 — boto3.client() is mocked throughout, per the project's
"never point cheap/CI tooling at billed external services" discipline.
"""

import io
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from boto3.exceptions import S3UploadFailedError
from botocore.exceptions import ClientError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings
from plant_community_backend.r2_config import R2_BOTO3_REQUIRED_VARS

REQUIRED_ENV = {
    "R2_BUCKET_NAME": "test-bucket",
    "R2_ACCESS_KEY_ID": "test-key",
    "R2_SECRET_ACCESS_KEY": "test-secret",  # pragma: allowlist secret
    "R2_ENDPOINT_URL": "https://example.r2.cloudflarestorage.com",
}


def _mock_client(existing_keys=()):
    """A mock boto3 S3 client whose list_objects_v2 paginator reports
    `existing_keys` as already present in the bucket."""
    client = MagicMock()
    paginator = MagicMock()
    paginator.paginate.return_value = [
        {"Contents": [{"Key": key} for key in existing_keys]}
    ]
    client.get_paginator.return_value = paginator
    return client


class RequiredEnvFixtureTests(SimpleTestCase):
    """REQUIRED_ENV keeps hand-written values (the endpoint URL has to look real),
    so this pins its KEYS to the shared tuple instead — a var added to
    r2_config without a fixture value here would otherwise leave every test
    below exercising the command with that var blank (todo 321)."""

    def test_fixture_covers_exactly_the_shared_boto3_vars(self):
        self.assertEqual(tuple(REQUIRED_ENV), R2_BOTO3_REQUIRED_VARS)


class SyncMediaToR2CommandTests(SimpleTestCase):
    def setUp(self):
        self.media_root = self._make_media_tree()
        self.settings_override = override_settings(MEDIA_ROOT=str(self.media_root))
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.env_patch = patch.dict("os.environ", REQUIRED_ENV)
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    def _make_media_tree(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "original_images").mkdir()
        (tmp / "original_images" / "a.jpg").write_bytes(b"a" * 100)
        (tmp / "original_images" / "b.jpg").write_bytes(b"b" * 200)
        self.addCleanup(lambda: __import__("shutil").rmtree(tmp, ignore_errors=True))
        return tmp

    def test_missing_env_vars_raises(self):
        import os

        # Nested patch.dict: saves the current (REQUIRED_ENV-populated) env
        # as its own restore point, so setUp's env_patch/addCleanup lifecycle
        # is untouched — only this test's env is briefly stripped.
        #
        # Explicitly blank each var — NOT pop(). decouple.Config.get() checks
        # os.environ first, but for a key merely ABSENT from it falls through
        # to backend/.env on disk (verified against decouple's source) rather
        # than the default="" the command relies on. This project's own R2
        # rotation runbook (secret-management.md) has an operator write real
        # R2_* values into backend/.env — on that machine, popping the key
        # would silently leak the real value into this "missing" test. An
        # explicit "" stays present-but-falsy, which is what the command's
        # own `if not value` check treats identically to fully absent.
        with patch.dict("os.environ", {}, clear=False):
            for key in REQUIRED_ENV:
                os.environ[key] = ""
            with self.assertRaises(CommandError) as ctx:
                call_command("sync_media_to_r2")
        self.assertIn("R2_BUCKET_NAME", str(ctx.exception))

    @patch("apps.core.management.commands.sync_media_to_r2.boto3.client")
    def test_dry_run_uploads_nothing(self, mock_client_factory):
        mock_client = _mock_client()
        mock_client_factory.return_value = mock_client

        out = io.StringIO()
        call_command("sync_media_to_r2", stdout=out)

        mock_client.upload_file.assert_not_called()
        mock_client.get_paginator.assert_not_called()  # dry run lists nothing
        self.assertIn("Found 2 file(s)", out.getvalue())
        self.assertIn("Dry run", out.getvalue())

    @patch("apps.core.management.commands.sync_media_to_r2.boto3.client")
    def test_confirm_skips_existing_keys(self, mock_client_factory):
        # a.jpg already exists at the destination; b.jpg does not.
        mock_client = _mock_client(existing_keys=["original_images/a.jpg"])
        mock_client_factory.return_value = mock_client

        out = io.StringIO()
        call_command("sync_media_to_r2", "--confirm", stdout=out)

        mock_client.upload_file.assert_called_once()
        uploaded_key = mock_client.upload_file.call_args.args[2]
        self.assertEqual(uploaded_key, "original_images/b.jpg")
        self.assertIn("1 uploaded, 1 skipped", out.getvalue())

    @patch("apps.core.management.commands.sync_media_to_r2.boto3.client")
    def test_confirm_force_reuploads_existing_keys(self, mock_client_factory):
        mock_client = _mock_client(
            existing_keys=["original_images/a.jpg", "original_images/b.jpg"]
        )
        mock_client_factory.return_value = mock_client

        out = io.StringIO()
        err = io.StringIO()
        call_command("sync_media_to_r2", "--confirm", "--force", stdout=out, stderr=err)

        self.assertEqual(mock_client.upload_file.call_count, 2)
        self.assertIn("2 uploaded, 0 skipped", out.getvalue())
        # Overwriting a live key under a 1-year immutable Cache-Control is
        # exactly the case file_overwrite=False guards against elsewhere —
        # --force must warn, not silently proceed.
        self.assertIn("re-uploading an existing key", err.getvalue())

    @patch("apps.core.management.commands.sync_media_to_r2.boto3.client")
    def test_upload_sets_cache_control_and_content_type(self, mock_client_factory):
        mock_client = _mock_client()
        mock_client_factory.return_value = mock_client

        call_command("sync_media_to_r2", "--confirm", stdout=io.StringIO())

        extra_args = {
            call.args[2]: call.kwargs["ExtraArgs"]
            for call in mock_client.upload_file.call_args_list
        }
        self.assertEqual(
            extra_args["original_images/a.jpg"]["CacheControl"],
            "public, max-age=31536000, immutable",
        )
        self.assertEqual(
            extra_args["original_images/a.jpg"]["ContentType"], "image/jpeg"
        )

    @patch("apps.core.management.commands.sync_media_to_r2.boto3.client")
    def test_upload_failure_is_caught_and_counted(self, mock_client_factory):
        # boto3's managed upload_file() raises S3UploadFailedError on a
        # failed transfer — it does NOT subclass ClientError, so this pins
        # the fix rather than the (previously incomplete) except clause.
        mock_client = _mock_client()
        mock_client.upload_file.side_effect = S3UploadFailedError("transfer failed")
        mock_client_factory.return_value = mock_client

        out = io.StringIO()
        with self.assertRaises(CommandError) as ctx:
            call_command("sync_media_to_r2", "--confirm", stdout=out)

        self.assertIn("2 file(s) failed to upload", str(ctx.exception))
        self.assertIn(
            "0 uploaded, 0 skipped (already present), 2 failed", out.getvalue()
        )

    @patch("apps.core.management.commands.sync_media_to_r2.boto3.client")
    def test_listing_failure_raises_command_error(self, mock_client_factory):
        # A scoped R2 token missing List permission must fail loudly with a
        # clear cause, not crash mid-loop on the first existence check.
        mock_client = MagicMock()
        mock_client.get_paginator.return_value.paginate.side_effect = ClientError(
            {"Error": {"Code": "403", "Message": "Forbidden"}}, "ListObjectsV2"
        )
        mock_client_factory.return_value = mock_client

        with self.assertRaises(CommandError) as ctx:
            call_command("sync_media_to_r2", "--confirm", stdout=io.StringIO())
        self.assertIn("Could not list existing objects", str(ctx.exception))
