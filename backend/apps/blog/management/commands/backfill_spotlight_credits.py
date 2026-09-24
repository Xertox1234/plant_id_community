"""
Backfill the stock-photo credit on plant_spotlight blocks (todo 438).

Spotlight blocks populated before todo 376 have an image and no
`image_credit`. `populate_plant_images` skips them ("Already has image"), and
`--force` would fetch a different photo. The Wagtail images themselves carry
the provider's taggit tags, so the credit is rebuilt from those
(`PlantImageService.attribution_from_image_tags`). A block whose image has no
recognisable provider tags is reported and left alone — the command never
invents a credit.

Writes go through `apps.blog.services.plant_spotlight_writes`: one
`save_revision().publish()` per live page (cache invalidated, admin revision
in step), a draft revision for a page that is not live, and a reported skip
for a live page with unpublished draft changes or one in moderation.

Usage:
    python manage.py backfill_spotlight_credits --dry-run
    python manage.py backfill_spotlight_credits
"""

from apps.blog.models import BlogPostPage
from apps.blog.services.plant_spotlight_writes import (
    DRAFT_SAVED,
    SKIP_MESSAGES,
    WRITTEN,
    load_spotlight_base,
    save_spotlight_updates,
)
from apps.plant_identification.services.plant_image_service import PlantImageService
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Rebuild missing plant_spotlight photo credits from the images' tags"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing anything",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        credited = skipped_pages = unrecoverable = failed = 0

        for page_id in BlogPostPage.objects.order_by("pk").values_list("pk", flat=True):
            base = load_spotlight_base(page_id)
            page = base.page
            candidates = [
                block
                for block in page.content_blocks
                if block.block_type == "plant_spotlight"
                and block.value.get("image")
                and not (block.value.get("image_credit") or "").strip()
            ]
            if not candidates:
                continue

            label = f'page {page_id} "{page.title}"'
            if base.skip_reason:
                skipped_pages += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipped {label} ({len(candidates)} uncredited "
                        f"spotlight(s)): {SKIP_MESSAGES[base.skip_reason]}"
                    )
                )
                continue

            updates = {}
            for block in candidates:
                image = block.value["image"]
                rebuilt = PlantImageService.attribution_from_image_tags(
                    image.tags.names()
                )
                if rebuilt is None:
                    unrecoverable += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"{label}: image {image.pk} has no provider/"
                            "photographer tags; add its credit in the CMS"
                        )
                    )
                    continue
                credit, credit_url = rebuilt
                updates[str(block.id)] = {
                    "image_credit": credit,
                    "image_credit_url": credit_url,
                }
                verb = "Would credit" if dry_run else "Crediting"
                self.stdout.write(
                    f"{verb} {label} image {image.pk}: {credit}"
                    + (f" <{credit_url}>" if credit_url else "")
                )

            if dry_run or not updates:
                continue

            try:
                outcome = save_spotlight_updates(base, updates)
            except Exception as e:  # report and keep going; one bad page
                self.stderr.write(f"  Error saving {label}: {e}")
                outcome = None
            if outcome in WRITTEN:
                credited += len(updates)
                if outcome == DRAFT_SAVED:
                    self.stdout.write(
                        f"  Saved as a draft revision: {label} is not live"
                    )
            else:
                failed += 1
                reason = SKIP_MESSAGES.get(outcome, "could not be saved")
                self.stdout.write(self.style.ERROR(f"  Not written: {label} {reason}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Credited: {credited}; pages skipped: {skipped_pages}; "
                f"uncreditable images: {unrecoverable}; pages failed: {failed}"
            )
        )
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - No changes made"))
