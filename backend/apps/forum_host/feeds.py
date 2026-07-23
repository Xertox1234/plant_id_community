"""RSS feed of the forum's live topics (todo 256 H9).

Items link to the SPA canonical topic URLs (``settings.SITE_URL`` +
``get_absolute_url``) — the same convention as the sitemap and the
reply-notification emails. Only live topics on live + **public** boards are
included; a hidden/view-restricted board's topics never leak (shares the
``_visible_boards`` boundary).
"""

from django.conf import settings
from django.contrib.syndication.views import Feed
from django.utils.feedgenerator import Rss201rev2Feed
from wagtail_forum.api.views import _visible_boards
from wagtail_forum.models import Topic

from .constants import FORUM_RSS_MAX_ITEMS


def _site_url():
    # Read SITE_URL at CALL time (matches tasks.py's email deep-link convention)
    # so a misconfigured or test-overridden value is always honored.
    return settings.SITE_URL.rstrip("/")


class ForumTopicsFeed(Feed):
    feed_type = Rss201rev2Feed
    title = "Plant Community — forum topics"
    description = "The latest topics from the Plant Community forum."

    def link(self):
        return f"{_site_url()}/forum"

    def items(self):
        return (
            Topic.objects.filter(live=True, board__in=_visible_boards())
            .select_related("board")
            .order_by("-last_post_at", "-id")[:FORUM_RSS_MAX_ITEMS]
        )

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        return f"A topic in {item.board.title}."

    def item_link(self, item):
        # Full frontend URL — Django leaves an already-absolute link untouched.
        return f"{_site_url()}{item.get_absolute_url()}"

    def item_pubdate(self, item):
        return item.last_post_at or item.updated_at
