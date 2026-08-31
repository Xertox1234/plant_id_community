"""
Tests for the real blog RSS/Atom feeds (todo 322).

Todo 307 deleted BlogFeedViewSet.rss/.atom — two JSON stubs that never
generated real feed XML. This is the replacement, built on Django's
syndication framework (django.contrib.syndication), mirroring
apps/forum_host/feeds.py's ForumTopicsFeed. Tests hit the real URLconf
(/blog/rss/, /blog/atom/), not the Feed class directly, so a routing
mistake in urls.py is caught too.
"""

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from wagtail.models import Page

from ..models import BlogIndexPage, BlogPostPage

User = get_user_model()


class BlogFeedsTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="feedauthor",
            email="feed@example.com",
        )
        root = Page.objects.get(id=1)
        self.blog_index = BlogIndexPage(title="Feed Blog", slug="feed-blog")
        root.add_child(instance=self.blog_index)

        now = timezone.now()
        self.older = self._make_post("older-post", now - timedelta(days=5))
        self.newer = self._make_post("newer-post", now - timedelta(days=1))

    def _make_post(self, slug, first_published_at, live=True):
        post = BlogPostPage(
            title=slug,
            slug=slug,
            author=self.user,
            publish_date=date.today(),
            introduction="<p>intro</p>",
            content_blocks=[],
            live=live,
        )
        self.blog_index.add_child(instance=post)
        # add_child() doesn't stamp first_published_at until a real
        # publish() call — set it directly so ordering is exercised
        # deterministically, same pattern as test_blog_viewset_routing.py's
        # ordering test case.
        BlogPostPage.objects.filter(pk=post.pk).update(
            first_published_at=first_published_at
        )
        return post

    def test_rss_feed_returns_rss_content_type(self):
        response = self.client.get("/blog/rss/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/rss+xml; charset=utf-8")

    def test_atom_feed_returns_atom_content_type(self):
        response = self.client.get("/blog/atom/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"], "application/atom+xml; charset=utf-8"
        )

    def test_rss_feed_lists_posts_newest_first(self):
        xml = self.client.get("/blog/rss/").content.decode()
        self.assertLess(xml.index("newer-post"), xml.index("older-post"))

    def test_atom_feed_lists_posts_newest_first(self):
        xml = self.client.get("/blog/atom/").content.decode()
        self.assertLess(xml.index("newer-post"), xml.index("older-post"))

    def test_rss_feed_item_link_uses_flat_spa_route(self):
        # Not item.get_absolute_url() — BlogPostPage doesn't override it, so
        # that would return the Wagtail page-tree path instead of the SPA's
        # flat /blog/:slug route.
        xml = self.client.get("/blog/rss/").content.decode()
        self.assertIn("/blog/newer-post</link>", xml)

    def test_rss_feed_excludes_draft_post(self):
        self._make_post("draft-post", timezone.now(), live=False)
        xml = self.client.get("/blog/rss/").content.decode()
        self.assertNotIn("draft-post", xml)

    def test_atom_feed_excludes_draft_post(self):
        self._make_post("draft-post", timezone.now(), live=False)
        xml = self.client.get("/blog/atom/").content.decode()
        self.assertNotIn("draft-post", xml)

    def test_atom_feed_has_subtitle(self):
        # Atom1Feed renders <subtitle> from a `subtitle` attribute, not
        # `description` — AtomBlogPostsFeed sets it explicitly.
        xml = self.client.get("/blog/atom/").content.decode()
        self.assertIn("<subtitle>", xml)
