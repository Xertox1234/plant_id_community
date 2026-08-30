"""
One-shot copy of local media (MEDIA_ROOT) into the R2 bucket, ahead of
flipping USE_R2 (todo 305).

Deliberately independent of settings.STORAGES / USE_R2 — it authenticates
directly against R2 via the same R2_* env vars, so it can run BEFORE the
flag is flipped (the intended sequencing: sync bytes first, verify, then
flip). Copying every file at its identical relative key means every
existing FileField/Wagtail Image/Rendition row resolves correctly the
instant USE_R2 turns on — no database changes required, no reseed.

Note it doesn't require R2_CUSTOM_DOMAIN — that var only feeds URL
generation in settings.py's STORAGES config; this command talks to R2's
S3-compatible API directly via boto3 and never builds a URL.

Dry-run by default (opt into action with --confirm), the inverse of this
codebase's usual --dry-run-is-opt-in convention (see
apps/blog/management/commands/populate_plant_images.py) — deliberately,
because this command makes real calls to a billed external API against
production media, not local DB rows. Matches the --confirm-gates-production
pattern used by seed_demo_blog.py/seed_demo_content.py instead.
"""

import mimetypes
from pathlib import Path

import boto3
from boto3.exceptions import S3UploadFailedError
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
        "already exist at the destination unless --force (a presence-only "
        "check: it does not detect changed content at an already-synced key)."
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
            help=(
                "Re-upload files that already exist at the destination key. "
                "CAUTION: if that key was already live (USE_R2 on) and served "
                "to any client/CDN, the immutable 1-year Cache-Control means "
                "stale bytes can keep being served for up to a year — this "
                "bypasses the file_overwrite=False protection settings.py "
                "gives normal app uploads."
            ),
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

        # One paginated listing up front regardless of --force: used to skip
        # existing keys normally, or to warn before overwriting them.
        existing_keys = self._list_existing_keys(client, bucket_name)

        uploaded = skipped = failed = 0
        for path in files:
            key = path.relative_to(media_root).as_posix()
            already_exists = key in existing_keys
            if already_exists and not options["force"]:
                skipped += 1
                continue
            if already_exists and options["force"]:
                self.stderr.write(
                    self.style.WARNING(
                        f"{key}: re-uploading an existing key (--force) — any "
                        "cache that already fetched it may keep serving the "
                        "old bytes for up to a year."
                    )
                )
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
            except (ClientError, S3UploadFailedError) as exc:
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

    def _list_existing_keys(self, client, bucket_name):
        """All object keys currently in the bucket.

        One paginated pass instead of a head_object-per-file round trip —
        a media tree with thousands of originals + renditions would
        otherwise cost thousands of sequential HTTP calls on every re-run.
        """
        keys = set()
        try:
            paginator = client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=bucket_name):
                for obj in page.get("Contents", []):
                    keys.add(obj["Key"])
        except ClientError as exc:
            raise CommandError(
                f"Could not list existing objects in bucket {bucket_name!r} "
                f"(check the R2 token has List permission): {exc}"
            ) from exc
        return keys
