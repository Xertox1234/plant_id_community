"""`populate_plant_images` after the PR #825 review follow-ups (todo 442).

- A write that raises before committing anything must not leave the images
  the run fetched for that page in the library. A write the service REFUSES
  keeps them: the editor whose save refused it may have picked one, anywhere
  an image can be referenced (owner decision 2026-10-09, after three review
  rounds of todo 442 each found a reference path a keep/discard check missed).
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
        return self.make_post_with_blocks(slug, spotlight_raw(**block))

    def make_post_with_blocks(self, slug, *spotlights):
        post = BlogPostPage(
            title=f"Post {slug}",
            slug=slug,
            author=self.user,
            publish_date=date.today(),
            introduction="<p>intro</p>",
            content_blocks=[("plant_spotlight", raw) for raw in spotlights],
        )
        self.blog_index.add_child(instance=post)
        return post

    def fetched_image(self, title="Fetched monstera"):
        return get_image_model().objects.create(
            title=title,
            file=get_test_image_file(filename="fetched.png"),
        )

    @staticmethod
    def editor_picks(post, image, index=0):
        """An editor's fresh copy of the page with `image` in spotlight block `index`.

        Unsaved: the caller decides whether the editor publishes or drafts it.
        The 3-tuple keeps the block id, as a real admin save would.
        """
        editor_copy = BlogPostPage.objects.get(pk=post.pk)
        stream = editor_copy.content_blocks
        block = stream[index]
        stream[index] = (
            block.block_type,
            {**dict(block.value), "image": image},
            block.id,
        )
        return editor_copy

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
    def test_a_write_refused_mid_run_keeps_the_fetched_image(self):
        # An editor saves the page while the provider fetch is in flight: the
        # real save_spotlight_updates sees the moved revision pointer and
        # refuses. The image stays: the command cannot prove the editor did
        # not pick it.
        post = self.make_post("edited-meanwhile")
        image = self.fetched_image()

        def fetch(**kwargs):
            editor_copy = BlogPostPage.objects.get(pk=post.pk)
            editor_copy.title = "Editor saved during the fetch"
            editor_copy.save_revision().publish()
            return "unsplash", UNSPLASH_DATA, image

        out, _ = self.run_command(f"--post-id={post.pk}", fetch=fetch)

        self.assertIn("was edited while this command ran", out)
        self.assertIn("Kept 1 fetched image(s): the page changed", out)
        self.assertNotIn("Discarded", out)
        self.assertTrue(get_image_model().objects.filter(pk=image.pk).exists())
        self.assertIsNone(self.spotlight(post).value["image"])
        self.assertEqual(
            post.get_latest_revision().as_object().title,
            "Editor saved during the fetch",
        )

    def test_a_write_refused_mid_run_keeps_the_image_the_editor_published(self):
        # The fetch put image A in the library, and the editor whose save
        # refuses the write picked it for the first block. A must survive:
        # deleting the row would turn that block's image into None in the
        # editor's live revision (round-1 review of todo 442). B is kept too:
        # a refused write keeps everything it fetched.
        post = self.make_post_with_blocks(
            "editor-picked",
            spotlight_raw(),
            spotlight_raw(plant_name="Pothos", scientific_name="Epipremnum aureum"),
        )
        image_a = self.fetched_image("Fetched monstera")
        image_b = self.fetched_image("Fetched pothos")
        remaining = iter([image_a, image_b])

        def fetch(**kwargs):
            image = next(remaining)
            if image is image_a:
                self.editor_picks(post, image_a).save_revision().publish()
            return "unsplash", UNSPLASH_DATA, image

        out, fetch_mock = self.run_command(f"--post-id={post.pk}", fetch=fetch)

        self.assertEqual(fetch_mock.call_count, 2)
        self.assertIn("was edited while this command ran", out)
        self.assertIn("Kept 2 fetched image(s)", out)
        self.assertNotIn("Discarded", out)
        images = get_image_model().objects
        self.assertTrue(images.filter(pk=image_a.pk).exists())
        self.assertTrue(images.filter(pk=image_b.pk).exists())
        post.refresh_from_db()
        first, second = [
            b for b in post.content_blocks if b.block_type == "plant_spotlight"
        ]
        self.assertEqual(first.value["image"].pk, image_a.pk)
        self.assertIsNone(second.value["image"])

    def test_a_write_refused_mid_run_keeps_the_image_the_editor_drafted(self):
        # A draft, not a publish: the live row still has no image, so only the
        # latest revision references the fetched one. It must still be kept.
        post = self.make_post("editor-drafted")
        image = self.fetched_image()

        def fetch(**kwargs):
            self.editor_picks(post, image).save_revision()
            return "unsplash", UNSPLASH_DATA, image

        out, _ = self.run_command(f"--post-id={post.pk}", fetch=fetch)

        self.assertIn("was edited while this command ran", out)
        self.assertIn("Kept 1 fetched image(s)", out)
        self.assertNotIn("Discarded", out)
        self.assertTrue(get_image_model().objects.filter(pk=image.pk).exists())
        self.assertIsNone(self.spotlight(post).value["image"])
        draft = post.get_latest_revision().as_object()
        draft_block = next(
            b for b in draft.content_blocks if b.block_type == "plant_spotlight"
        )
        self.assertEqual(draft_block.value["image"].pk, image.pk)

    def test_a_write_refused_mid_run_keeps_the_image_the_editor_set_as_featured(self):
        # The editor picked the fetched image for the page's featured_image
        # column, not for a block. Deleting it would null that SET_NULL column
        # on the live row (round-2 review of todo 442).
        post = self.make_post("editor-featured")
        image = self.fetched_image()

        def fetch(**kwargs):
            editor_copy = BlogPostPage.objects.get(pk=post.pk)
            editor_copy.featured_image = image
            editor_copy.save_revision().publish()
            return "unsplash", UNSPLASH_DATA, image

        out, _ = self.run_command(f"--post-id={post.pk}", fetch=fetch)

        self.assertIn("was edited while this command ran", out)
        self.assertIn("Kept 1 fetched image(s)", out)
        self.assertNotIn("Discarded", out)
        self.assertTrue(get_image_model().objects.filter(pk=image.pk).exists())
        post.refresh_from_db()
        self.assertEqual(post.featured_image_id, image.pk)
        self.assertIsNone(self.spotlight(post).value["image"])

    def test_a_write_refused_mid_run_keeps_the_image_the_editor_embedded(self):
        # The editor embedded the fetched image in the rich-text introduction,
        # a reference path the round-1/2 keep check never looked at (round-3
        # review of todo 442). Deleting it would leave a dangling embed.
        post = self.make_post("editor-embedded")
        image = self.fetched_image()
        embed = f'<embed embedtype="image" id="{image.pk}" format="fullwidth"/>'

        def fetch(**kwargs):
            editor_copy = BlogPostPage.objects.get(pk=post.pk)
            editor_copy.introduction = f"<p>intro</p>{embed}"
            editor_copy.save_revision().publish()
            return "unsplash", UNSPLASH_DATA, image

        out, _ = self.run_command(f"--post-id={post.pk}", fetch=fetch)

        self.assertIn("was edited while this command ran", out)
        self.assertIn("Kept 1 fetched image(s)", out)
        self.assertNotIn("Discarded", out)
        self.assertTrue(get_image_model().objects.filter(pk=image.pk).exists())
        post.refresh_from_db()
        self.assertIn(f'id="{image.pk}"', post.introduction)

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

    def test_a_failing_unchanged_check_keeps_the_image_and_the_run_goes_on(self):
        # The check runs right after a write that raised, often on the same
        # broken connection. Its own failure must not end the run (todo 442
        # review): unknown means keep, and the next page is still processed.
        first = self.make_post("check-fails")
        second = self.make_post("next-page")
        image = self.fetched_image()
        second_image = self.fetched_image("Fetched for the next page")
        remaining = iter([image, second_image])

        def save(base, updates):
            raise RuntimeError("database went away")

        with mock.patch(
            "apps.blog.management.commands.populate_plant_images.page_unchanged_since",
            side_effect=RuntimeError("connection already closed"),
        ):
            out, fetch_mock = self.run_command(
                fetch=lambda **kwargs: ("unsplash", UNSPLASH_DATA, next(remaining)),
                save=save,
            )

        self.assertEqual(fetch_mock.call_count, 2)
        self.assertIn(f"Processing: {first.title}", out)
        self.assertIn(f"Processing: {second.title}", out)
        self.assertEqual(out.count("Kept 1 fetched image(s)"), 2)
        self.assertNotIn("Discarded", out)
        images = get_image_model().objects
        self.assertTrue(images.filter(pk=image.pk).exists())
        self.assertTrue(images.filter(pk=second_image.pk).exists())

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
