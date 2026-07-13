"""
Wagtail admin render smoke tests (todo 217).

Guards the `/cms/` admin render path end to end. A global admin hook or admin
template that raises — e.g. the Django 6.0 `format_html("<literal>")` no-arg
`TypeError` that 500'd *all* of `/cms/` (including the login page) in production
on 2026-06-06 — fails these tests instead of shipping undetected.

Placement note: this lives in `apps/blog/tests/` because at the time of writing
forum apps were gated behind `ENABLE_FORUM` (off in CI) and a smoke test there
would not have run. That flag was removed on 2026-06-10 (forum apps are always
installed), but blog remains a fine home for a global admin render gate. See
todo 217 for the forum admin-hook coverage decision.
"""

from datetime import date

from apps.blog.models import BlogComment, BlogIndexPage, BlogPostPage
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from wagtail.models import Page

User = get_user_model()


class WagtailAdminRenderSmokeTests(TestCase):
    """Render the admin login page and the authenticated dashboard."""

    def test_cms_login_page_renders(self):
        """Unauthenticated login page renders (200), not a 500.

        `insert_global_admin_css`/`insert_global_admin_js` hooks render on every
        admin page including login, so a raising global hook surfaces here.
        `secure=True` clears `SECURE_SSL_REDIRECT` (active when `DEBUG=False`).
        """
        response = self.client.get(reverse("wagtailadmin_login"), secure=True)
        self.assertEqual(response.status_code, 200)

    def test_authenticated_admin_dashboard_renders(self):
        """A superuser hitting the admin home renders the dashboard (200), not 500.

        Exercises `construct_homepage_panels` (the blog summary panel's
        `format_html`) plus admin templates and static resolution end to end.
        """
        admin = User.objects.create_superuser(
            username="smoke-admin",
            email="smoke-admin@example.com",
            password="smoke-admin-pw-217",  # pragma: allowlist secret
        )
        self.client.force_login(admin)

        response = self.client.get(reverse("wagtailadmin_home"), secure=True)
        self.assertEqual(response.status_code, 200)

    def _blog_index(self):
        root = Page.objects.get(id=1)
        try:
            return BlogIndexPage.objects.get(slug="blog")
        except BlogIndexPage.DoesNotExist:
            index = BlogIndexPage(title="Blog", slug="blog")
            root.add_child(instance=index)
            return index

    def test_blog_posts_summary_item_renders(self):
        """The 'Blog Posts' homepage panel actually renders visible text — not
        just a 200 (todo 264). Before the fix, add_blog_summary_items()'s
        SummaryItem(...) call raised TypeError internally, but the broad
        except Exception: pass swallowed it silently, so
        test_authenticated_admin_dashboard_renders above stayed green with the
        panel missing entirely — a bare status-code check can't catch this."""
        author = User.objects.create_user(username="blog-author")
        post = BlogPostPage(
            title="A Post",
            slug="a-post",
            author=author,
            publish_date=date.today(),
            introduction="<p>Intro.</p>",
        )
        self._blog_index().add_child(instance=post)
        post.save_revision().publish()

        admin = User.objects.create_superuser(username="root", email="r@x.io")
        self.client.force_login(admin)
        response = self.client.get(reverse("wagtailadmin_home"), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"1 Blog Posts", response.content)
        # This scenario has featured_count=0 and pending_comments=0 — prove the
        # `if featured_count > 0`/`if pending_comments > 0` guards in
        # add_blog_summary_items actually gate the panels (deleting either
        # guard would otherwise still pass the whole suite). Asserting on the
        # href, not the label text: add_blog_stats_panel (a separate,
        # unrelated, already-working hook) always renders the literal words
        # "Featured Posts" regardless of count, so a label-text assertion here
        # would false-fail; the /blog-admin/featured/ and /blog-admin/comments/
        # links are unique to this new BlogSummaryItem panel.
        self.assertNotIn(b"/blog-admin/featured/", response.content)
        self.assertNotIn(b"/blog-admin/comments/", response.content)

    def test_featured_and_pending_comment_summary_items_render_when_present(self):
        """'Featured Posts' and 'Pending Comments' are conditional panels —
        confirm both actually render when their counts are nonzero (todo 264)."""
        author = User.objects.create_user(username="blog-author-2")
        post = BlogPostPage(
            title="Featured Post",
            slug="featured-post",
            author=author,
            publish_date=date.today(),
            introduction="<p>Intro.</p>",
            is_featured=True,
        )
        self._blog_index().add_child(instance=post)
        post.save_revision().publish()
        BlogComment.objects.create(
            post=post, author=author, content="pending", is_approved=False
        )

        admin = User.objects.create_superuser(username="root2", email="r2@x.io")
        self.client.force_login(admin)
        response = self.client.get(reverse("wagtailadmin_home"), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"1 Featured Posts", response.content)
        self.assertIn(b"1 Pending Comments", response.content)
