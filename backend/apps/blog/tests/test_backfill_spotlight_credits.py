"""`backfill_spotlight_credits` (todo 438).

Spotlight photos saved before todo 376 have no `image_credit`. The command
rebuilds it from the taggit tags the provider services wrote. The images here
are created by the REAL `download_and_create_wagtail_image` (only the HTTP
download is mocked), so a change to the tag shapes the services write breaks
these tests instead of silently breaking the backfill.
"""

from datetime import date
from io import StringIO
from unittest import mock

from apps.plant_identification.services.pexels_service import PexelsImageService
from apps.plant_identification.services.unsplash_service import UnsplashImageService
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from wagtail.images import get_image_model
from wagtail.images.tests.utils import get_test_image_file
from wagtail.models import Page

from ..models import BlogIndexPage, BlogPostPage
from .test_plant_spotlight_credit import spotlight_raw

User = get_user_model()

UTM = "utm_source=plant_community&utm_medium=referral"


def downloaded_image(service_cls, image_data):
    """Create a Wagtail image through the provider's real save path."""
    png = get_test_image_file(filename="download.png").file.getvalue()
    response = mock.Mock(content=png)
    response.raise_for_status.return_value = None
    module = service_cls.__module__
    with mock.patch(f"{module}.requests.get", return_value=response):
        image = service_cls("test-key").download_and_create_wagtail_image(image_data)
    assert image is not None
    return image


class BackfillSpotlightCreditsTest(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="backfillauthor",
            email="backfillauthor@example.com",
            password="pass12345",  # pragma: allowlist secret
        )
        root = Page.objects.get(id=1)
        self.blog_index = BlogIndexPage(title="Backfill Blog", slug="backfill-blog")
        root.add_child(instance=self.blog_index)
        self.unsplash_image = downloaded_image(
            UnsplashImageService,
            {
                "id": "abc123",
                "description": "Monstera",
                "urls": {"regular": "https://images.unsplash.com/abc123"},
                "photographer": {"name": "Jane Doe", "username": "janedoe"},
            },
        )
        self.pexels_image = downloaded_image(
            PexelsImageService,
            {
                "id": 42,
                "description": "Pothos",
                "urls": {"large": "https://images.pexels.com/42"},
                "photographer": {"name": "Sam Roe", "url": "https://x.example"},
            },
        )

    def make_post(self, slug, **block):
        post = BlogPostPage(
            title=f"Post {slug}",
            slug=slug,
            author=self.user,
            publish_date=date.today(),
            introduction="<p>intro</p>",
            # Raw JSON form: spotlight_raw() holds the image as a pk.
            content_blocks=[
                {"type": "plant_spotlight", "value": spotlight_raw(**block)}
            ],
        )
        self.blog_index.add_child(instance=post)
        return post

    def run_command(self, *args, photo=None):
        """Run the command with the Unsplash lookup mocked.

        `photo` is what `UnsplashImageService.get_photo` (GET /photos/:id)
        answers; None means unavailable, so the credit falls back to the tags.
        Mocked because backend/.env may carry a real UNSPLASH_ACCESS_KEY. The
        lookup mock is kept on `self.lookup` for assertions.
        """
        out = StringIO()
        with (
            mock.patch(
                "apps.blog.services.blog_cache_service.BlogCacheService."
                "invalidate_blog_post"
            ) as invalidate,
            mock.patch(
                "apps.plant_identification.services.unsplash_service."
                "UnsplashImageService.get_photo",
                return_value=photo,
            ) as lookup,
            # The handler invalidates from on_commit (todo 442); the patch
            # stays open while the captured callbacks run.
            self.captureOnCommitCallbacks(execute=True),
        ):
            call_command("backfill_spotlight_credits", *args, stdout=out)
        self.lookup = lookup
        return out.getvalue(), invalidate

    @staticmethod
    def spotlight(page):
        page.refresh_from_db()
        return next(b for b in page.content_blocks if b.block_type == "plant_spotlight")

    def test_unsplash_image_gets_username_credit_and_utm_link_published(self):
        post = self.make_post("unsplash", image=self.unsplash_image.pk)
        block_id = self.spotlight(post).id

        # No `photo`: the Unsplash lookup is unavailable, so the credit is
        # rebuilt from the tags (username) — the todo 442 fallback path.
        _, invalidate = self.run_command()

        block = self.spotlight(post)
        self.assertEqual(block.value["image_credit"], "Photo by janedoe on Unsplash")
        self.assertEqual(
            block.value["image_credit_url"], f"https://unsplash.com/@janedoe?{UTM}"
        )
        self.assertEqual(block.id, block_id)
        # Written through a published revision, not a bare save.
        self.assertFalse(post.has_unpublished_changes)
        revision_block = self.spotlight_of(post.get_latest_revision().as_object())
        self.assertEqual(
            revision_block.value["image_credit"], "Photo by janedoe on Unsplash"
        )
        invalidate.assert_called_with(post.slug)

    @staticmethod
    def spotlight_of(page):
        return next(b for b in page.content_blocks if b.block_type == "plant_spotlight")

    def test_pexels_image_gets_text_only_credit(self):
        post = self.make_post("pexels", image=self.pexels_image.pk)
        self.run_command()
        block = self.spotlight(post)
        self.assertEqual(block.value["image_credit"], "Photo by Sam Roe from Pexels")
        self.assertFalse(block.value["image_credit_url"])

    # --- todo 442: the photographer's real name from GET /photos/:id ---

    # What UnsplashImageService.get_photo returns: a search-result-shaped dict.
    UNSPLASH_PHOTO = {
        "id": "abc123",
        "photographer": {
            "name": "Jane Doe",
            "username": "janedoe",
            "profile_url": "https://unsplash.com/@janedoe",
        },
    }

    def test_unsplash_lookup_credits_the_photographer_by_name(self):
        post = self.make_post("named", image=self.unsplash_image.pk)

        out, _ = self.run_command(photo=self.UNSPLASH_PHOTO)

        # Asked for the photo the image's unsplash_id: tag names.
        self.lookup.assert_called_once_with("abc123")
        block = self.spotlight(post)
        self.assertEqual(block.value["image_credit"], "Photo by Jane Doe on Unsplash")
        self.assertEqual(
            block.value["image_credit_url"], f"https://unsplash.com/@janedoe?{UTM}"
        )
        self.assertIn("Photo by Jane Doe on Unsplash", out)

    def test_dry_run_reports_the_looked_up_name_and_writes_nothing(self):
        post = self.make_post("named-dry", image=self.unsplash_image.pk)
        out, _ = self.run_command("--dry-run", photo=self.UNSPLASH_PHOTO)
        self.assertIn("Would credit", out)
        self.assertIn("Photo by Jane Doe on Unsplash", out)
        self.assertFalse(self.spotlight(post).value["image_credit"])

    def test_pexels_image_is_never_looked_up(self):
        # The owner decision scoped the API call to Unsplash.
        self.make_post("pexels-no-lookup", image=self.pexels_image.pk)
        self.run_command(photo=self.UNSPLASH_PHOTO)
        self.lookup.assert_not_called()

    def test_existing_credit_is_left_alone(self):
        post = self.make_post(
            "credited", image=self.unsplash_image.pk, image_credit="Editor credit"
        )
        revision_id = post.latest_revision_id
        self.run_command()
        post.refresh_from_db()
        self.assertEqual(self.spotlight(post).value["image_credit"], "Editor credit")
        self.assertEqual(post.latest_revision_id, revision_id)

    def test_untagged_image_is_reported_not_invented(self):
        plain = get_image_model().objects.create(
            title="Editor upload", file=get_test_image_file(filename="plain.png")
        )
        post = self.make_post("untagged", image=plain.pk)
        out, _ = self.run_command()
        self.assertFalse(self.spotlight(post).value["image_credit"])
        self.assertIn(f"image {plain.pk} has no provider/photographer tags", out)

    def test_dry_run_reports_and_writes_nothing(self):
        post = self.make_post("dry-run", image=self.unsplash_image.pk)
        revision_id = post.latest_revision_id
        out, invalidate = self.run_command("--dry-run")
        self.assertIn("Would credit", out)
        self.assertIn("Photo by janedoe on Unsplash", out)
        self.assertFalse(self.spotlight(post).value["image_credit"])
        post.refresh_from_db()
        self.assertEqual(post.latest_revision_id, revision_id)
        invalidate.assert_not_called()

    def test_page_with_unpublished_draft_is_skipped_and_reported(self):
        post = self.make_post("drafted", image=self.unsplash_image.pk)
        post.title = "Editor draft title"
        post.save_revision()
        draft_revision_id = post.latest_revision_id

        out, invalidate = self.run_command()

        self.assertIn("unpublished draft changes", out)
        post.refresh_from_db()
        self.assertEqual(post.latest_revision_id, draft_revision_id)
        self.assertFalse(self.spotlight(post).value["image_credit"])
        invalidate.assert_not_called()

    # --- PR #825 review round 1 ---

    def test_locked_page_is_skipped_and_reported(self):
        post = self.make_post("locked", image=self.unsplash_image.pk)
        BlogPostPage.objects.filter(pk=post.pk).update(locked=True)

        out, invalidate = self.run_command()

        self.assertIn("is locked", out)
        self.assertFalse(self.spotlight(post).value["image_credit"])
        invalidate.assert_not_called()

    def test_a_page_deleted_during_the_run_loads_as_none(self):
        from apps.blog.services.plant_spotlight_writes import load_spotlight_base

        post = self.make_post("gone", image=self.unsplash_image.pk)
        page_id = post.pk
        post.delete()

        self.assertIsNone(load_spotlight_base(page_id))

    def test_id_less_spotlight_blocks_are_never_targeted(self):
        from types import SimpleNamespace

        from apps.blog.management.commands.populate_plant_images import Command

        fake = SimpleNamespace(
            content_blocks=[
                SimpleNamespace(
                    block_type="plant_spotlight",
                    id=None,
                    value={"plant_name": "Fern", "image": None},
                )
            ]
        )
        self.assertEqual(Command()._extract_plants_from_post(fake), [])
