"""
Backfill the stock-photo credit on plant_spotlight blocks (todo 438).

Spotlight blocks populated before todo 376 have an image and no
`image_credit`. `populate_plant_images` skips them ("Already has image"), and
`--force` would fetch a different photo. The Wagtail images themselves carry
the provider's taggit tags, so the credit is rebuilt from those
(`PlantImageService.rebuild_attribution`). An Unsplash image's tags hold only
the photographer's USERNAME, so the command asks Unsplash for the photo
(`GET /photos/:id`, via the `unsplash_id:` tag) and credits the real name with
a profile link, as a fresh fetch would have (todo 442; owner decision
2026-09-28: the backfill may call the API). When the lookup cannot help — no
key, the photo is gone, no name in the answer — the username credit from the
tags is written instead and counted separately. When it failed in a way a
later run may not (the hourly rate limit, an API error), the block is left
uncredited and counted as deferred, so a re-run can still name the
photographer: a credited block is never a candidate again (todo 530). A block
whose image has no recognisable provider tags is reported and left alone — the
command never invents a credit.

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
    SKIP_MESSAGES,
    WRITTEN,
    describe_outcome,
    load_spotlight_base,
    outcome_after_raise,
    page_label,
    save_spotlight_updates,
)
from apps.plant_identification.services.plant_image_service import (
    CREDIT_FALLBACK,
    CREDIT_FROM_TAGS,
    CREDIT_LOOKUP_UNAVAILABLE,
    PlantImageService,
)
from apps.plant_identification.services.unsplash_service import UNSPLASH_CREDIT_SUFFIX
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
        credited = username_credits = deferred = 0
        skipped_pages = unrecoverable = failed = 0
        # The Unsplash lookup runs through the configured service; without
        # UNSPLASH_ACCESS_KEY it answers None and the tags alone are used.
        image_service = PlantImageService()

        for page_id in BlogPostPage.objects.order_by("pk").values_list("pk", flat=True):
            base = load_spotlight_base(page_id)
            if base is None:
                continue  # deleted since the id list was read
            page = base.page
            candidates = [
                block
                for block in page.content_blocks
                if block.block_type == "plant_spotlight"
                and block.id is not None  # id-less legacy blocks can't be targeted
                and block.value.get("image")
                and not (block.value.get("image_credit") or "").strip()
            ]
            if not candidates:
                continue

            label = page_label(page)
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
            fallbacks = 0
            for block in candidates:
                image = block.value["image"]
                rebuilt, basis = image_service.rebuild_attribution_with_basis(
                    image.tags.names()
                )
                if basis == CREDIT_LOOKUP_UNAVAILABLE:
                    deferred += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"Deferred {label} image {image.pk}: the Unsplash "
                            "lookup failed (rate limit or API error); re-run "
                            "later to credit the photographer by name"
                        )
                    )
                    continue
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
                # Also an Unsplash credit rebuilt from the tags with no
                # lookup at all (no unsplash_id: tag): username only too.
                fallback = basis == CREDIT_FALLBACK or (
                    basis == CREDIT_FROM_TAGS
                    and credit.endswith(UNSPLASH_CREDIT_SUFFIX)
                )
                fallbacks += fallback
                verb = "Would credit" if dry_run else "Crediting"
                self.stdout.write(
                    f"{verb} {label} image {image.pk}: {credit}"
                    + (f" <{credit_url}>" if credit_url else "")
                    + (
                        " (username from the tags; Unsplash gave no name)"
                        if fallback
                        else ""
                    )
                )

            if dry_run or not updates:
                continue

            try:
                outcome = save_spotlight_updates(base, updates)
            except Exception as e:  # report and keep going; one bad page
                self.stderr.write(f"  Error saving {label}: {e}")
                outcome = outcome_after_raise(base, updates)
                if outcome in WRITTEN:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  {label} was written; the error came from a "
                            "post-commit hook"
                        )
                    )
            line = describe_outcome(outcome, label)
            if outcome in WRITTEN:
                credited += len(updates)
                username_credits += fallbacks
                if line:
                    self.stdout.write(f"  {line}")
            else:
                failed += 1
                self.stdout.write(self.style.ERROR(f"  {line}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Credited: {credited} (username only: {username_credits}); "
                f"deferred: {deferred}; pages skipped: {skipped_pages}; "
                f"uncreditable images: {unrecoverable}; pages failed: {failed}"
            )
        )
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - No changes made"))
