"""`plant_spotlight_writes` helpers shared by the two spotlight commands (todo 442).

`describe_outcome` is the one place the outcome of `save_spotlight_updates`
becomes a line of command output, `page_unchanged_since` is the check a
command makes before deleting what it fetched for a write that raised, and
`referenced_image_pks` is what spares a fetched image an editor picked meanwhile
from the deletion a refused write triggers.
"""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from wagtail.images import get_image_model
from wagtail.images.tests.utils import get_test_image_file
from wagtail.models import Page

from ..models import BlogIndexPage, BlogPostPage
from ..services.plant_spotlight_writes import (
    BLOCK_NOT_FOUND,
    DRAFT_SAVED,
    PUBLISHED,
    SKIPPED_CHANGED_DURING_RUN,
    describe_outcome,
    load_spotlight_base,
    page_label,
    page_unchanged_since,
    referenced_image_pks,
)
from .test_plant_spotlight_credit import spotlight_raw

User = get_user_model()

LABEL = 'page 7 "Monstera care"'


class DescribeOutcomeTest(SimpleTestCase):
    def test_published_needs_no_line(self):
        self.assertIsNone(describe_outcome(PUBLISHED, LABEL))

    def test_draft_saved_names_the_page_and_why(self):
        self.assertEqual(
            describe_outcome(DRAFT_SAVED, LABEL),
            f"Saved as a draft revision: {LABEL} is not live",
        )

    def test_refused_outcomes_carry_their_skip_reason(self):
        self.assertEqual(
            describe_outcome(SKIPPED_CHANGED_DURING_RUN, LABEL),
            f"Not written: {LABEL} was edited while this command ran; re-run",
        )
        self.assertEqual(
            describe_outcome(BLOCK_NOT_FOUND, LABEL),
            f"Not written: {LABEL} no longer has the spotlight block; re-run",
        )

    def test_a_raised_write_reads_as_could_not_be_saved(self):
        # The commands substitute None for the outcome when the write raised.
        self.assertEqual(
            describe_outcome(None, LABEL), f"Not written: {LABEL} could not be saved"
        )


class PageStateHelpersTest(TestCase):
    def setUp(self):
        user = User.objects.create_user(
            username="writesauthor",
            email="writesauthor@example.com",
            password="pass12345",  # pragma: allowlist secret
        )
        root = Page.objects.get(id=1)
        blog_index = BlogIndexPage(title="Writes Blog", slug="writes-blog")
        root.add_child(instance=blog_index)
        self.post = BlogPostPage(
            title="Monstera care",
            slug="monstera-care",
            author=user,
            publish_date=date.today(),
            introduction="<p>intro</p>",
            content_blocks=[("plant_spotlight", spotlight_raw())],
        )
        blog_index.add_child(instance=self.post)

    def test_page_label_names_pk_and_title(self):
        self.assertEqual(page_label(self.post), f'page {self.post.pk} "Monstera care"')

    def test_unchanged_until_a_revision_is_saved(self):
        base = load_spotlight_base(self.post.pk)
        self.assertTrue(page_unchanged_since(base))

        self.post.title = "Edited meanwhile"
        self.post.save_revision()

        self.assertFalse(page_unchanged_since(base))

    def test_a_deleted_page_counts_as_changed(self):
        base = load_spotlight_base(self.post.pk)
        self.post.delete()
        self.assertFalse(page_unchanged_since(base))


class ReferencedImagePksTest(TestCase):
    """`referenced_image_pks`: what the populate command keeps after a refused write."""

    def setUp(self):
        user = User.objects.create_user(
            username="referencesauthor",
            email="referencesauthor@example.com",
            password="pass12345",  # pragma: allowlist secret
        )
        root = Page.objects.get(id=1)
        blog_index = BlogIndexPage(title="References Blog", slug="references-blog")
        root.add_child(instance=blog_index)
        self.post = BlogPostPage(
            title="Pothos care",
            slug="pothos-care",
            author=user,
            publish_date=date.today(),
            introduction="<p>intro</p>",
            content_blocks=[("plant_spotlight", spotlight_raw())],
        )
        blog_index.add_child(instance=self.post)
        self.image = get_image_model().objects.create(
            title="Picked by the editor",
            file=get_test_image_file(filename="picked.png"),
        )

    def pick(self):
        """`self.post` with the image in its spotlight block, not yet saved."""
        stream = self.post.content_blocks
        block = stream[0]
        stream[0] = (
            block.block_type,
            {**dict(block.value), "image": self.image},
            block.id,
        )
        return self.post

    def test_empty_while_nothing_references_an_image(self):
        self.assertEqual(referenced_image_pks(self.post.pk), set())

    def test_sees_an_image_only_a_draft_revision_references(self):
        # The editor saved a draft, not a publish: the live row still has no
        # image, so only the latest revision can vouch for it.
        self.pick().save_revision()

        self.assertEqual(referenced_image_pks(self.post.pk), {self.image.pk})
        live = BlogPostPage.objects.get(pk=self.post.pk)
        self.assertIsNone(live.content_blocks[0].value["image"])

    def test_sees_an_image_the_live_content_references(self):
        self.pick().save_revision().publish()

        self.assertEqual(referenced_image_pks(self.post.pk), {self.image.pk})

    def test_sees_an_image_embedded_in_a_rich_text_paragraph(self):
        # Every image reference counts, not only plant_spotlight.image.
        self.post.content_blocks = [
            ("plant_spotlight", spotlight_raw()),
            (
                "paragraph",
                '<p>Repotting.</p><embed alt="" embedtype="image" '
                f'format="fullwidth" id="{self.image.pk}"/>',
            ),
        ]
        self.post.save_revision()

        self.assertEqual(referenced_image_pks(self.post.pk), {self.image.pk})

    def test_sees_the_featured_image_a_draft_revision_sets(self):
        # Not a block reference: the page's own featured_image column. A draft
        # only, so the live row's column is still empty and the latest
        # revision alone vouches for it (round-2 review of todo 442).
        self.post.featured_image = self.image
        self.post.save_revision()

        self.assertEqual(referenced_image_pks(self.post.pk), {self.image.pk})
        live = BlogPostPage.objects.get(pk=self.post.pk)
        self.assertIsNone(live.featured_image_id)

    def test_sees_the_social_image_the_live_row_sets(self):
        # social_image is a column of the BlogBasePage parent row: inherited
        # image foreign keys count too.
        self.post.social_image = self.image
        self.post.save_revision().publish()

        self.assertEqual(referenced_image_pks(self.post.pk), {self.image.pk})

    def test_empty_for_a_deleted_page(self):
        pk = self.post.pk  # delete() clears the instance's own pk
        self.post.delete()

        self.assertEqual(referenced_image_pks(pk), set())
