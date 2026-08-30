"""
One-shot copy of local media (MEDIA_ROOT) into the R2 bucket, ahead of
flipping USE_R2 (todo 305).

Deliberately independent of settings.STORAGES / USE_R2 — it authenticates
directly against R2 via the same R2_* env vars, so it can run BEFORE the
flag is flipped (the intended sequencing: sync bytes first, verify, then
flip). Copying every file at its identical relative key means every
existing FileField/Wagtail Image/Rendition row resolves correctly the
instant USE_R2 turns on — no database changes required, no reseed.
"""

import mimetypes
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from decouple import config
from django.core.management.base import BaseCommand, CommandError

# Must match settings.py's STORAGES["default"]["OPTIONS"]["object_parameters"]
# so files copied here get the same caching behavior as new R2 uploads.
CACHE_CONTROL = "public, max-age=31536000, immutable"


class Command(BaseCommand):
    help = (
        "One-shot copy of MEDIA_ROOT into the R2 bucket at identical relative "
        "keys, ahead of flipping USE_R2 (todo 305). Dry-run by default; "
        "--confirm actually uploads. Safely re-runnable — skips keys that "
        "already exist at the destination unless --force."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Actually upload. Without this, only report what would happen.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-upload files that already exist at the destination key.",
        )

    def handle(self, *args, **options):
        from django.conf import settings

        media_root = Path(settings.MEDIA_ROOT)
        if not media_root.is_dir():
            raise CommandError(f"MEDIA_ROOT does not exist: {media_root}")

        bucket_name = config("R2_BUCKET_NAME", default="")
        access_key = config("R2_ACCESS_KEY_ID", default="")
        secret_key = config("R2_SECRET_ACCESS_KEY", default="")
        endpoint_url = config("R2_ENDPOINT_URL", default="")
        missing = [
            name
            for name, value in [
                ("R2_BUCKET_NAME", bucket_name),
                ("R2_ACCESS_KEY_ID", access_key),
                ("R2_SECRET_ACCESS_KEY", secret_key),
                ("R2_ENDPOINT_URL", endpoint_url),
            ]
            if not value
        ]
        if missing:
            raise CommandError(
                f"Missing required env var(s): {', '.join(missing)}. "
                "These must be set even though USE_R2 can stay off while "
                "this command runs."
            )

        client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="auto",
        )

        files = sorted(p for p in media_root.rglob("*") if p.is_file())
        total_bytes = sum(p.stat().st_size for p in files)
        self.stdout.write(
            f"Found {len(files)} file(s), {total_bytes / (1024 * 1024):.1f} MB, "
            f"under {media_root}"
        )

        if not options["confirm"]:
            self.stdout.write(
                self.style.WARNING(
                    "Dry run — no files uploaded. Re-run with --confirm to upload."
                )
            )
            return

        uploaded = skipped = failed = 0
        for path in files:
            key = path.relative_to(media_root).as_posix()
            if not options["force"] and self._key_exists(client, bucket_name, key):
                skipped += 1
                continue
            content_type, _ = mimetypes.guess_type(path.name)
            try:
                client.upload_file(
                    str(path),
                    bucket_name,
                    key,
                    ExtraArgs={
                        "ContentType": content_type or "application/octet-stream",
                        "CacheControl": CACHE_CONTROL,
                    },
                )
                uploaded += 1
            except ClientError as exc:
                failed += 1
                self.stderr.write(self.style.ERROR(f"{key}: {exc}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Sync complete: {uploaded} uploaded, {skipped} skipped "
                f"(already present), {failed} failed."
            )
        )
        if failed:
            raise CommandError(f"{failed} file(s) failed to upload — see errors above.")

    def _key_exists(self, client, bucket_name, key):
        try:
            client.head_object(Bucket=bucket_name, Key=key)
            return True
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey"):
                return False
            raise
