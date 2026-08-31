"""RSS/Atom feeds of the blog's live, public posts (todo 322).

Items link to the SPA canonical blog URLs (settings.SITE_URL + "/blog/{slug}")
— the same flat-route convention BlogCard.tsx and BlogDetailPage.tsx already
use — NOT item.get_absolute_url(), which (unlike wagtail_forum.Topic)
BlogPostPage does not override, so it would return the Wagtail page-tree path
instead of the SPA route shape.
"""

from django.conf import settings
from django.contrib.syndication.views import Feed
from django.utils.feedgenerator import Atom1Feed, Rss201rev2Feed

from .constants import BLOG_RSS_MAX_ITEMS
from .models import BlogPostPage


def _site_url():
    # Read SITE_URL at CALL time (matches forum_host/feeds.py's convention)
    # so a misconfigured or test-overridden value is always honored.
    return settings.SITE_URL.rstrip("/")


class BlogPostsFeed(Feed):
    feed_type = Rss201rev2Feed
    title = "Houseplant MD — blog"
    description = "Guides, experiments, and honest failures from the community garden."

    def link(self):
        return f"{_site_url()}/blog"

    def items(self):
        return (
            BlogPostPage.objects.live()
            .public()
            .select_related("author")
            .order_by("-first_published_at", "-id")[:BLOG_RSS_MAX_ITEMS]
        )

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        return item.introduction or ""

    def item_link(self, item):
        return f"{_site_url()}/blog/{item.slug}"

    def item_pubdate(self, item):
        # add_child()-created posts (test factories) don't set
        # first_published_at until a real publish() call — fall back to the
        # latest revision timestamp so pubdate is never silently None.
        return item.first_published_at or item.latest_revision_created_at


class AtomBlogPostsFeed(BlogPostsFeed):
    feed_type = Atom1Feed
    # Atom1Feed renders <subtitle> from `subtitle`, not `description` —
    # verified in django.utils.feedgenerator.Atom1Feed.add_root_elements.
    subtitle = BlogPostsFeed.description
