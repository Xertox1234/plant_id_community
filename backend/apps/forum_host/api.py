"""Rate-limited wrappers around the wagtail_forum API views (audit H1).

The package is deliberately host-agnostic and leaves throttling to the host
(plan 1C/1D); this module is where the host applies it. `api_urls.py` mounts
these in place of `wagtail_forum.api.urls`. Rates resolve through
`settings.FORUM_RATELIMITS` at request time so deployments (and tests) can
override them without re-importing the decorators.
"""

from apps.core.ratelimit import ratelimit
from django.conf import settings
from django.utils.decorators import method_decorator
from wagtail_forum.api import views as forum_views

from .constants import DEFAULT_FORUM_RATELIMITS


def _rate(name):
    def resolve(group, request):
        overrides = getattr(settings, "FORUM_RATELIMITS", {})
        return {**DEFAULT_FORUM_RATELIMITS, **overrides}[name]

    return resolve


@method_decorator(
    ratelimit(key="user", rate=_rate("topic_create"), method="POST"), name="post"
)
class TopicCreateView(forum_views.TopicCreateView):
    pass


@method_decorator(
    ratelimit(key="user", rate=_rate("reply_create"), method="POST"), name="post"
)
class ReplyCreateView(forum_views.ReplyCreateView):
    pass


@method_decorator(
    ratelimit(key="user", rate=_rate("reaction_toggle"), method="POST"), name="post"
)
class ReactionToggleView(forum_views.ReactionToggleView):
    pass


@method_decorator(
    ratelimit(key="user", rate=_rate("profile_update"), method="PATCH"), name="patch"
)
class MeProfileView(forum_views.MeProfileView):
    pass


@method_decorator(ratelimit(key="ip", rate=_rate("search"), method="GET"), name="get")
class SearchView(forum_views.SearchView):
    pass


@method_decorator(ratelimit(key="ip", rate=_rate("sync"), method="GET"), name="get")
class SyncView(forum_views.SyncView):
    pass
