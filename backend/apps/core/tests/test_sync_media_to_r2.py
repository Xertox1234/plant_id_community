"""
sync_media_to_r2 management command (todo 305).

Never hits real R2 — boto3.client() is mocked throughout, per the project's
"never point cheap/CI tooling at billed external services" discipline.
"""

import io
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

REQUIRED_ENV = {
    "R2_BUCKET_NAME": "test-bucket",
    "R2_ACCESS_KEY_ID": "test-key",
    "R2_SECRET_ACCESS_KEY": "test-secret",  # pragma: allowlist secret
    "R2_ENDPOINT_URL": "https://example.r2.cloudflarestorage.com",
}


def _not_found(*args, **kwargs):
    raise ClientError({"Error": {"Code": "404"}}, "HeadObject")


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
        import tempfile
        from pathlib import Path

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
        with patch.dict("os.environ", {}, clear=False):
            for key in REQUIRED_ENV:
                os.environ.pop(key, None)
            with self.assertRaises(CommandError) as ctx:
                call_command("sync_media_to_r2")
        self.assertIn("R2_BUCKET_NAME", str(ctx.exception))

    @patch("apps.core.management.commands.sync_media_to_r2.boto3.client")
    def test_dry_run_uploads_nothing(self, mock_client_factory):
        mock_client = MagicMock()
        mock_client_factory.return_value = mock_client

        out = io.StringIO()
        call_command("sync_media_to_r2", stdout=out)

        mock_client.upload_file.assert_not_called()
        self.assertIn("Found 2 file(s)", out.getvalue())
        self.assertIn("Dry run", out.getvalue())

    @patch("apps.core.management.commands.sync_media_to_r2.boto3.client")
    def test_confirm_skips_existing_keys(self, mock_client_factory):
        mock_client = MagicMock()
        # a.jpg already exists at the destination; b.jpg does not.
        mock_client.head_object.side_effect = lambda Bucket, Key: (
            None if Key == "original_images/a.jpg" else _not_found()
        )
        mock_client_factory.return_value = mock_client

        out = io.StringIO()
        call_command("sync_media_to_r2", "--confirm", stdout=out)

        mock_client.upload_file.assert_called_once()
        uploaded_key = mock_client.upload_file.call_args.args[2]
        self.assertEqual(uploaded_key, "original_images/b.jpg")
        self.assertIn("1 uploaded, 1 skipped", out.getvalue())

    @patch("apps.core.management.commands.sync_media_to_r2.boto3.client")
    def test_confirm_force_reuploads_existing_keys(self, mock_client_factory):
        mock_client = MagicMock()
        mock_client.head_object.return_value = {}  # both keys "exist"
        mock_client_factory.return_value = mock_client

        out = io.StringIO()
        call_command("sync_media_to_r2", "--confirm", "--force", stdout=out)

        self.assertEqual(mock_client.upload_file.call_count, 2)
        mock_client.head_object.assert_not_called()
        self.assertIn("2 uploaded, 0 skipped", out.getvalue())

    @patch("apps.core.management.commands.sync_media_to_r2.boto3.client")
    def test_upload_sets_cache_control_and_content_type(self, mock_client_factory):
        mock_client = MagicMock()
        mock_client.head_object.side_effect = _not_found
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
