"""`populate_plant_images` after the PR #825 review follow-ups (todo 442).

- A write the service refuses, or that raises, must not leave the images the
  run fetched for that page in the library (owner decision 2026-09-28: a
  refused write deletes the images it fetched).
- Each page's content is loaded once, by `load_spotlight_base`; the command
  iterates ids rather than full pages.

The provider lookup is mocked; everything from the fetched image onward is
real: the Wagtail Image row, `save_spotlight_updates`, the revision.
"""

from datetime import date
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from wagtail.images import get_image_model
from wagtail.images.tests.utils import get_test_image_file
from wagtail.models import Page

from ..models import BlogIndexPage, BlogPostPage
from .test_plant_spotlight_credit import CREDIT, spotlight_raw

User = get_user_model()

FETCH = (
    "apps.plant_identification.services.plant_image_service."
    "PlantImageService.get_best_plant_image"
)
STATS = (
    "apps.plant_identification.services.plant_image_service."
    "PlantImageService.get_source_stats"
)
SAVE = "apps.blog.management.commands.populate_plant_images.save_spotlight_updates"
UNSPLASH_DATA = {
    "photographer": {
        "name": "Jane Doe",
        "profile_url": "https://unsplash.com/@janedoe",
    }
}


class PopulateCommandTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="populateauthor",
            email="populateauthor@example.com",
            password="pass12345",  # pragma: allowlist secret
        )
        root = Page.objects.get(id=1)
        self.blog_index = BlogIndexPage(title="Populate Blog", slug="populate-blog")
        root.add_child(instance=self.blog_index)

    def make_post(self, slug, **block):
        post = BlogPostPage(
            title=f"Post {slug}",
            slug=slug,
            author=self.user,
            publish_date=date.today(),
            introduction="<p>intro</p>",
            content_blocks=[("plant_spotlight", spotlight_raw(**block))],
        )
        self.blog_index.add_child(instance=post)
        return post

    def fetched_image(self):
        return get_image_model().objects.create(
            title="Fetched monstera",
            file=get_test_image_file(filename="fetched.png"),
        )

    def run_command(self, *args, fetch=None, save=None):
        """Run the command with the provider mocked; `fetch`/`save` are side effects."""
        out = StringIO()
        with (
            mock.patch(FETCH, side_effect=fetch) as fetch_mock,
            mock.patch(STATS, return_value={}),
            self.captureOnCommitCallbacks(execute=True),
        ):
            if save is None:
                call_command("populate_plant_images", *args, stdout=out)
            else:
                with mock.patch(SAVE, side_effect=save):
                    call_command("populate_plant_images", *args, stdout=out)
        return out.getvalue(), fetch_mock

    @staticmethod
    def spotlight(page):
        page.refresh_from_db()
        return next(b for b in page.content_blocks if b.block_type == "plant_spotlight")


class PopulateDiscardsUnwrittenImagesTest(PopulateCommandTestCase):
    def test_a_write_refused_mid_run_deletes_the_fetched_image(self):
        # An editor saves the page while the provider fetch is in flight: the
        # real save_spotlight_updates sees the moved revision pointer and
        # refuses. The image that fetch created must not stay in the library.
        post = self.make_post("edited-meanwhile")
        image = self.fetched_image()

        def fetch(**kwargs):
            editor_copy = BlogPostPage.objects.get(pk=post.pk)
            editor_copy.title = "Editor saved during the fetch"
            editor_copy.save_revision().publish()
            return "unsplash", UNSPLASH_DATA, image

        out, _ = self.run_command(f"--post-id={post.pk}", fetch=fetch)

        self.assertIn("was edited while this command ran", out)
        self.assertIn("Discarded 1 fetched image(s): nothing was written", out)
        self.assertFalse(get_image_model().objects.filter(pk=image.pk).exists())
        self.assertIsNone(self.spotlight(post).value["image"])
        self.assertEqual(
            post.get_latest_revision().as_object().title,
            "Editor saved during the fetch",
        )

    def test_a_write_that_raises_before_committing_deletes_the_fetched_image(self):
        post = self.make_post("save-raises")
        image = self.fetched_image()

        def save(base, updates):
            raise RuntimeError("database went away")

        out, _ = self.run_command(
            f"--post-id={post.pk}",
            fetch=lambda **kwargs: ("unsplash", UNSPLASH_DATA, image),
            save=save,
        )

        self.assertIn("could not be saved", out)
        self.assertIn("Discarded 1 fetched image(s)", out)
        self.assertFalse(get_image_model().objects.filter(pk=image.pk).exists())

    def test_a_write_that_raises_after_the_page_moved_keeps_the_image(self):
        # The one case a raise does not prove "nothing written": another app's
        # on_commit hook raising AFTER the revision committed. The revision
        # pointers moved, so a revision may reference the image — keep it.
        post = self.make_post("committed-then-raised")
        image = self.fetched_image()

        def save(base, updates):
            committed = BlogPostPage.objects.get(pk=post.pk)
            committed.save_revision().publish()
            raise RuntimeError("a post-commit hook failed")

        out, _ = self.run_command(
            f"--post-id={post.pk}",
            fetch=lambda **kwargs: ("unsplash", UNSPLASH_DATA, image),
            save=save,
        )

        self.assertIn("Kept 1 fetched image(s)", out)
        self.assertTrue(get_image_model().objects.filter(pk=image.pk).exists())

    def test_a_written_image_stays(self):
        post = self.make_post("written")
        image = self.fetched_image()

        out, _ = self.run_command(
            f"--post-id={post.pk}",
            fetch=lambda **kwargs: ("unsplash", UNSPLASH_DATA, image),
        )

        self.assertNotIn("Discarded", out)
        self.assertIn(f"Added image from unsplash - {CREDIT}", out)
        self.assertEqual(self.spotlight(post).value["image"].pk, image.pk)


class PopulateLoadsEachPageOnceTest(PopulateCommandTestCase):
    @staticmethod
    def content_loads(captured):
        """Queries that fetched a page's StreamField content."""
        return [
            q["sql"]
            for q in captured
            if '"blog_blogpostpage"."content_blocks"' in q["sql"]
        ]

    def test_dry_run_loads_each_page_content_once(self):
        # Before todo 442 the command iterated full pages and then
        # load_spotlight_base reloaded each one: two content loads per page
        # (and --post-id loaded the page before checking it existed).
        first = self.make_post("once-a")
        self.make_post("once-b")

        for args, pages in [
            ((f"--post-id={first.pk}",), 1),
            ((), 2),
        ]:
            with self.subTest(args=args):
                with CaptureQueriesContext(connection) as ctx:
                    out, fetch = self.run_command("--dry-run", *args)
                loads = self.content_loads(ctx.captured_queries)
                self.assertEqual(len(loads), pages, "\n\n".join(loads))
                fetch.assert_not_called()
                self.assertIn(f"Processing {pages} blog posts", out)

    def test_an_unknown_post_id_is_a_command_error(self):
        with self.assertRaises(CommandError):
            self.run_command("--post-id=999999", "--dry-run")
