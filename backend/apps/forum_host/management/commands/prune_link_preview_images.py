"""Management command: delete cached link-preview images nothing refers to.

A link card's image is our own re-encoded copy of the page's og:image, stored
under ``WAGTAILFORUM_LINK_PREVIEW_IMAGE_PREFIX`` (todo 428 slice B). Editing a
card away or deleting its post leaves the file behind; this command reaps it.
Run nightly from the ``forum-prune-cron`` Railway service (03:00 UTC).

The rules that make it safe (todo 428, owner decision 2026-09-24):

- **A reference is any body that can still be shown.** That is every
  ``Post.body`` (drafts and unpublished posts included, no ``live`` filter)
  AND every Wagtail revision of a post: a post waiting for moderation exists
  only as a revision, and the edit-history sheet shows old revisions. Any
  string in either that starts with the prefix counts, wherever it sits, so
  an unexpected shape errs towards keeping a file.
- **Grace period.** A file younger than
  ``LINK_PREVIEW_IMAGE_PRUNE_GRACE_HOURS`` is never deleted: a post being
  saved right now can hold an image no stored body refers to yet.
- **List the storage prefix, then subtract the referenced set.** Nothing is
  deleted by guessing from post rows. Every file under the prefix is a
  candidate, including the suffixed duplicate a concurrent store can leave
  behind, which never passes ``is_cached_image_name`` and so is never served.

The references are read AFTER the listing, so a post committed before the
scan is always seen. One window remains: the fetcher reuses an existing file
without touching it, so a post that re-shares an image older than the grace
period, and commits between the scan and the delete, points at a deleted file.
The card then shows no image. The window is the scan's length, once a night.

``--dry-run`` reports what would go and deletes nothing.
"""

import json
import logging
from datetime import timedelta

from apps.forum_host import constants
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

logger = logging.getLogger(__name__)

CHUNK = 500


def _collect_names(value, prefix, names):
    """Add every string in ``value`` (any nesting) that starts with ``prefix``."""
    if isinstance(value, str):
        if value.startswith(prefix):
            names.add(value)
    elif isinstance(value, dict):
        for item in value.values():
            _collect_names(item, prefix, names)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _collect_names(item, prefix, names)


def _referenced_names(prefix):
    from django.contrib.contenttypes.models import ContentType
    from wagtail.models import Revision
    from wagtail_forum.models import Post

    names = set()
    for post in Post.objects.only("id", "body").iterator(chunk_size=CHUNK):
        # StreamValue.raw_data is a RawDataView, not a list (see migration
        # 0038): convert it before walking.
        _collect_names(list(post.body.raw_data), prefix, names)

    post_type = ContentType.objects.get_for_model(Post)
    revisions = Revision.objects.filter(base_content_type=post_type).only(
        "id", "content"
    )
    for revision in revisions.iterator(chunk_size=CHUNK):
        content = revision.content
        body = content.get("body") if isinstance(content, dict) else None
        if isinstance(body, str):
            # A revision stores the StreamField serialised: a JSON string.
            try:
                body = json.loads(body)
            except ValueError as exc:
                # Its references can't be read, so no deletion is safe.
                raise CommandError(
                    f"[PRUNE] revision {revision.pk} has an unreadable body; "
                    "nothing deleted"
                ) from exc
        _collect_names(body, prefix, names)
    return names


class Command(BaseCommand):
    help = "Delete cached link-preview images that no post or post revision refers to."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be deleted without deleting anything.",
        )

    def handle(self, *args, **options):
        from wagtail_forum.conf import get_setting

        dry_run = options["dry_run"]
        prefix = get_setting("LINK_PREVIEW_IMAGE_PREFIX")
        # A blank or root prefix would make every media file a candidate.
        if (
            not isinstance(prefix, str)
            or not prefix.strip("/")
            or not prefix.endswith("/")
        ):
            raise CommandError(
                f"[PRUNE] refusing to run: LINK_PREVIEW_IMAGE_PREFIX is {prefix!r}"
            )

        try:
            _dirs, files = default_storage.listdir(prefix.rstrip("/"))
        except FileNotFoundError:
            files = []
        cutoff = timezone.now() - timedelta(
            hours=constants.LINK_PREVIEW_IMAGE_PRUNE_GRACE_HOURS
        )
        old = []
        too_new = 0
        for filename in sorted(files):
            name = f"{prefix}{filename}"
            try:
                modified = default_storage.get_modified_time(name)
            except Exception:
                logger.warning("[PRUNE] no modified time for %s; kept", name)
                continue
            if modified < cutoff:
                old.append(name)
            else:
                too_new += 1

        referenced = _referenced_names(prefix)
        deleted = 0
        failed = 0
        for name in old:
            if name in referenced:
                continue
            if dry_run:
                logger.info("[PRUNE] would delete %s", name)
                deleted += 1
                continue
            try:
                default_storage.delete(name)
            except Exception:
                logger.exception("[PRUNE] could not delete %s", name)
                failed += 1
                continue
            logger.info("[PRUNE] deleted %s", name)
            deleted += 1

        verb = "would delete" if dry_run else "deleted"
        self.stdout.write(
            f"[PRUNE] link-preview images: {len(files)} stored, "
            f"{too_new} younger than "
            f"{constants.LINK_PREVIEW_IMAGE_PRUNE_GRACE_HOURS}h, "
            f"{verb} {deleted}, {failed} failed."
        )
        if failed:
            raise CommandError(f"[PRUNE] {failed} image(s) could not be deleted")
