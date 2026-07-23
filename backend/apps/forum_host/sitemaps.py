"""Forum sitemap: the /forum landing, boards, and live topics (todo 256 H9).

Every ``<loc>`` is emitted at the SPA **frontend** canonical URL
(``settings.SITE_URL`` + path) — the SAME base the reply-notification emails use
(``apps/forum_host/tasks.py``). The backend Wagtail board pages are only a
minimal crawler fallback (audit H17: "the SPA remains the real forum UI"), so the
frontend origin is canonical, not the backend host that serves this sitemap.

Security: only live topics on live + **public** boards are listed — a hidden or
view-restricted board's topics never leak into the sitemap. Mirrors the API's
visibility boundary.
"""

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from wagtail_forum.api.views import _visible_boards
from wagtail_forum.models import ForumIndex, Topic


def _frontend_parts():
    """(protocol, domain) of the SPA frontend origin, read at CALL time so a
    misconfigured or test-overridden SITE_URL is always honored — matches
    tasks.py's email deep-link convention (also a live settings.SITE_URL read)."""
    protocol, _, domain = settings.SITE_URL.partition("://")
    return (protocol or "https"), domain.rstrip("/")


class _FrontendSitemap(Sitemap):
    """Build every ``<loc>`` against the SPA frontend origin (SITE_URL), not the
    backend host this sitemap is served from."""

    def get_protocol(self, protocol=None):
        return _frontend_parts()[0]

    def get_domain(self, site=None):
        return _frontend_parts()[1]


class ForumBoardSitemap(_FrontendSitemap):
    changefreq = "daily"
    priority = 0.6

    def items(self):
        # The /forum landing (ForumIndex) plus every public board.
        return list(ForumIndex.objects.live().public()) + list(_visible_boards())

    def location(self, obj):
        # Frontend routes: /forum (index) and /forum/{id}-{slug} (board).
        if isinstance(obj, ForumIndex):
            return "/forum"
        return f"/forum/{obj.id}-{obj.slug}"


class ForumTopicSitemap(_FrontendSitemap):
    changefreq = "daily"
    priority = 0.5

    def items(self):
        return (
            Topic.objects.filter(live=True, board__in=_visible_boards())
            .select_related("board")
            .order_by("-last_post_at", "-id")
        )

    def location(self, obj):
        # Topic.get_absolute_url() -> /forum/{board_id}-{slug}/{id}-{slug}
        return obj.get_absolute_url()

    def lastmod(self, obj):
        return obj.last_post_at or obj.updated_at


forum_sitemaps = {
    "forum-boards": ForumBoardSitemap,
    "forum-topics": ForumTopicSitemap,
}
