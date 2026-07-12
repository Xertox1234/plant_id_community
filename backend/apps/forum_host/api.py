"""Rate-limited wrappers around the wagtail_forum API views (audit H1).

The package is deliberately host-agnostic and leaves throttling to the host
(plan 1C/1D); this module is where the host applies it. `api_urls.py` mounts
these in place of `wagtail_forum.api.urls`. Rates resolve through
`settings.FORUM_RATELIMITS` at request time so deployments (and tests) can
override them without re-importing the decorators.
"""

from apps.core.ratelimit import client_ip_key, ratelimit
from django.conf import settings
from django.utils.decorators import method_decorator
from wagtail_forum.api import views as forum_views

from .constants import DEFAULT_FORUM_RATELIMITS


def _rate(name):
    def resolve(group, request):
        overrides = getattr(settings, "FORUM_RATELIMITS", {})
        return {**DEFAULT_FORUM_RATELIMITS, **overrides}[name]

    return resolve


def _throttled(rate_name, http_method, *, key="user"):
    """Rate-limit ONE HTTP method of a host forum view AND flag it for the schema.

    Behaviourally identical to the prior inline
    ``@method_decorator(ratelimit(...), name=<method>)`` — same key, rate and
    method — it additionally records the method on ``_forum_throttled_methods`` so
    the OpenAPI hooks (``api_schema.record_throttled_operations`` /
    ``document_throttle_429``) document a 429 for exactly that operation, and only
    those (todo 254). New throttled wrappers get their 429 documented for free.
    """

    def decorate(cls):
        cls = method_decorator(
            ratelimit(key=key, rate=_rate(rate_name), method=http_method),
            name=http_method.lower(),
        )(cls)
        cls._forum_throttled_methods = {
            *getattr(cls, "_forum_throttled_methods", ()),
            http_method.upper(),
        }
        return cls

    return decorate


@_throttled("topic_create", "POST")
class TopicListView(forum_views.TopicListView):
    # GET (list) is public + unthrottled; only the merged POST (create) is rated.
    pass


@_throttled("reply_create", "POST")
class PostListView(forum_views.PostListView):
    # GET (list) is public + unthrottled; only the merged POST (reply) is rated.
    pass


@_throttled("post_update", "PATCH")
@_throttled("post_delete", "DELETE")
class PostWriteView(forum_views.PostWriteView):
    pass


@_throttled("image_upload", "POST")
class PostImageUploadView(forum_views.PostImageUploadView):
    pass


@_throttled("reaction_toggle", "POST")
class ReactionToggleView(forum_views.ReactionToggleView):
    pass


@_throttled("report_create", "POST")
class PostReportView(forum_views.PostReportView):
    pass


@_throttled("profile_update", "PATCH")
class MeProfileView(forum_views.MeProfileView):
    pass


@_throttled("search", "GET", key=client_ip_key)
class SearchView(forum_views.SearchView):
    pass


@_throttled("sync", "GET", key=client_ip_key)
class SyncView(forum_views.SyncView):
    pass
