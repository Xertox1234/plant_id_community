"""`plant_spotlight_writes` helpers shared by the two spotlight commands (todo 442).

`describe_outcome` is the one place the outcome of `save_spotlight_updates`
becomes a line of command output, and `page_unchanged_since` is the check a
command makes before deleting what it fetched for a write that raised.
"""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
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
