"""
Management command to populate plant images in blog post spotlight blocks.

This command scans all blog posts for plant_spotlight blocks without images
and automatically fetches appropriate images using the unified image service.

Writes go through `apps.blog.services.plant_spotlight_writes` (todo 438): one
`save_revision().publish()` per live page, so the admin's latest revision
carries the image and credit and `page_published` invalidates the blog cache.
A live page with unpublished draft changes, or one in moderation, is skipped
and reported before any image is fetched. Pages are iterated by id and each is
loaded once, by `load_spotlight_base` (todo 442). The images fetched for a
page whose write is then refused are deleted again (owner decision
2026-09-28), so a refused write leaves nothing unreferenced in the image
library.
"""

import logging

from apps.blog.models import BlogPostPage
from apps.blog.services.plant_spotlight_writes import (
    SKIP_MESSAGES,
    WRITTEN,
    describe_outcome,
    load_spotlight_base,
    page_label,
    page_unchanged_since,
    save_spotlight_updates,
)
from apps.plant_identification.services.plant_image_service import PlantImageService
from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Populate missing plant images in blog post spotlight blocks"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without making changes",
        )
        parser.add_argument(
            "--max-ai-images",
            type=int,
            default=3,
            help="Maximum number of AI-generated images to create (default: 3)",
        )
        parser.add_argument(
            "--prefer-source",
            choices=["unsplash", "pexels", "ai"],
            help="Preferred image source",
        )
        parser.add_argument(
            "--post-id", type=int, help="Process only a specific blog post by ID"
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Replace existing images in spotlight blocks",
        )

    def handle(self, *args, **options):
        self.dry_run = options["dry_run"]
        self.max_ai_images = options["max_ai_images"]
        self.prefer_source = options["prefer_source"]
        self.force = options["force"]

        # Initialize the image service
        try:
            self.image_service = PlantImageService()
        except Exception as e:
            raise CommandError(f"Failed to initialize image service: {e}")

        # Show service status
        self._show_service_status()

        # Ids only: load_spotlight_base loads each page once, so the full row
        # is not fetched here and then again before the write (todo 442).
        if options["post_id"]:
            if not BlogPostPage.objects.filter(pk=options["post_id"]).exists():
                raise CommandError(f"Blog post with ID {options['post_id']} not found")
            page_ids = [options["post_id"]]
        else:
            page_ids = list(
                BlogPostPage.objects.live()
                .public()
                .order_by("pk")
                .values_list("pk", flat=True)
            )

        self.stdout.write(f"Processing {len(page_ids)} blog posts...")

        # Process posts
        total_plants_found = 0
        total_images_added = 0
        ai_images_used = 0

        for page_id in page_ids:
            # Load the content to change BEFORE any fetch: a page this command
            # must not write (unpublished draft changes, in moderation) costs
            # no API call and no AI spend (todo 438).
            base = load_spotlight_base(page_id)
            if base is None:
                self.stdout.write(
                    f"\nSkipped: page {page_id} was deleted during the run"
                )
                continue
            page = base.page
            label = page_label(page)
            self.stdout.write(f"\nProcessing: {page.title}")

            plants_in_post = self._extract_plants_from_post(page)
            if not plants_in_post:
                self.stdout.write("  No plant spotlight blocks found")
                continue

            total_plants_found += len(plants_in_post)

            if base.skip_reason:
                self.stdout.write(
                    self.style.WARNING(
                        f"  Skipped: {label} {SKIP_MESSAGES[base.skip_reason]}"
                    )
                )
                continue

            updates = {}
            added = []
            fetched_images = []
            for plant_info in plants_in_post:
                block_id = plant_info["block_id"]
                plant_name = plant_info["plant_name"]
                scientific_name = plant_info.get("scientific_name")
                has_image = plant_info["has_image"]

                # Skip if already has image and not forcing
                if has_image and not self.force:
                    self.stdout.write(
                        f"  {plant_name}: Already has image (use --force to replace)"
                    )
                    continue

                # Check AI limit
                allow_ai = ai_images_used < self.max_ai_images

                if self.dry_run:
                    self.stdout.write(
                        f"  {plant_name}: Would fetch image (AI allowed: {allow_ai})"
                    )
                    continue

                # Fetch image
                try:
                    result = self.image_service.get_best_plant_image(
                        plant_name=plant_name,
                        scientific_name=scientific_name,
                        prefer_source=self.prefer_source,
                        allow_ai_generation=allow_ai,
                    )

                    if result:
                        source, image_data, wagtail_image = result
                        fetched_images.append(wagtail_image)
                        # AI spend happened at generation, whatever the write does.
                        if source == "ai":
                            ai_images_used += 1
                        attribution = self.image_service.get_attribution_text(
                            source, image_data
                        )
                        attribution_url = self.image_service.get_attribution_url(
                            source, image_data
                        )
                        # The credit is written with the image, never
                        # separately, so a --force replacement cannot leave the
                        # previous photographer's credit on a new image (todo 376).
                        updates[block_id] = {
                            "image": wagtail_image,
                            "image_credit": attribution,
                            "image_credit_url": attribution_url or "",
                        }
                        added.append((plant_name, source, attribution))
                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                f"  {plant_name}: No suitable image found"
                            )
                        )

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"  {plant_name}: Error - {str(e)}")
                    )

            if not updates:
                continue

            # One revision per page for all of its spotlight changes.
            try:
                outcome = save_spotlight_updates(base, updates)
            except Exception as e:
                logger.error(f"[PLANT_IMAGE] Failed to update post {page.pk}: {e}")
                outcome = None

            if outcome in WRITTEN:
                total_images_added += len(added)
                for plant_name, source, attribution in added:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  {plant_name}: Added image from {source} - {attribution}"
                        )
                    )
            else:
                self._discard_fetched_images(base, fetched_images, outcome)
            line = describe_outcome(outcome, label)
            if line:
                self.stdout.write(
                    f"  {line}" if outcome in WRITTEN else self.style.ERROR(f"  {line}")
                )

        # Show summary
        self.stdout.write(f"\n{self.style.SUCCESS('Summary:')}")
        self.stdout.write(f"  Total plants found: {total_plants_found}")
        self.stdout.write(f"  Images added: {total_images_added}")
        self.stdout.write(f"  AI images used: {ai_images_used}")

        if self.dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - No changes made"))

    def _discard_fetched_images(self, base, images, outcome):
        """
        Delete the Wagtail images fetched for a page whose write did not happen.

        A refused write (the page was edited during the run, a block is gone,
        it got locked meanwhile) would otherwise leave every image this run
        fetched for the page in the library, unreferenced, and the next run
        fetches again (todo 442; owner decision 2026-09-28: a refused write
        deletes the images it fetched). After an EXCEPTION the images go only
        when the page's revision pointers have not moved: the write is atomic,
        so a failure inside it committed nothing, but an exception from another
        app's on_commit hook arrives after the commit, and a revision may then
        reference the images.
        """
        if not images:
            return
        if outcome is None and not page_unchanged_since(base):
            self.stdout.write(
                self.style.WARNING(
                    f"  Kept {len(images)} fetched image(s): the page changed, "
                    "so a revision may reference them"
                )
            )
            return
        for image in images:
            try:
                image.delete()
            except Exception as e:
                logger.error(
                    f"[PLANT_IMAGE] Could not delete unreferenced image {image.pk}: {e}"
                )
        self.stdout.write(
            f"  Discarded {len(images)} fetched image(s): nothing was written"
        )

    def _show_service_status(self):
        """Display the status of image services."""
        stats = self.image_service.get_source_stats()

        self.stdout.write(f"\n{self.style.SUCCESS('Image Service Status:')}")
        for source, info in stats.items():
            status = "✓" if info["available"] else "✗"
            self.stdout.write(f"  {source}: {status} {info['description']}")

            if source == "ai" and info["available"]:
                daily_cost = info.get("daily_cost", 0)
                cost_limit = info.get("cost_limit", 5.0)
                self.stdout.write(
                    f"    Daily cost: ${daily_cost:.2f} / ${cost_limit:.2f}"
                )

    def _extract_plants_from_post(self, post):
        """
        Extract plant information from plant_spotlight blocks in a blog post.

        Args:
            post: BlogPostPage instance

        Returns:
            List of plant information dictionaries
        """
        plants = []

        for block in post.content_blocks:
            # Id-less legacy blocks can't be targeted by id (PR #825).
            if block.block_type == "plant_spotlight" and block.id is not None:
                block_value = block.value
                plant_name = block_value.get("plant_name", "").strip()

                if plant_name:
                    plants.append(
                        {
                            "block_id": str(block.id),
                            "plant_name": plant_name,
                            "scientific_name": block_value.get(
                                "scientific_name", ""
                            ).strip()
                            or None,
                            "has_image": bool(block_value.get("image")),
                        }
                    )

        return plants
