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
from wagtail_forum.api import bookmarks as forum_bookmark_views
from wagtail_forum.api import direct_messages as forum_direct_message_views
from wagtail_forum.api import notifications as forum_notification_views
from wagtail_forum.api import polls as forum_poll_views
from wagtail_forum.api import solutions as forum_solution_views
from wagtail_forum.api import subscriptions as forum_subscription_views
from wagtail_forum.api import user_blocks as forum_user_block_views
from wagtail_forum.api import user_mutes as forum_user_mute_views
from wagtail_forum.api import user_search as forum_user_search_views
from wagtail_forum.api import views as forum_views

from .constants import DEFAULT_FORUM_RATELIMITS
from .search_hits import record_query_hit
from .semantic_search import SemanticSearchMixin


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
class SearchView(SemanticSearchMixin, forum_views.SearchView):
    # The mixin adds the opt-in premium `semantic` section (todo 275 / M12); it
    # must precede the package view in the MRO so its `get` wraps the FTS one.
    # `_throttled` is applied to THIS class, so it wraps the already-composed
    # `get` — a subclass that overrode `get` instead would silently drop the
    # throttle.

    def record_search(self, request, *, query, page):
        # Wagtail search-terms report (quick wins, item 5). First page only:
        # later pages are the same search, not a new one. record_query_hit
        # swallows its own failures. Overriding the hook, not `get`, keeps
        # the throttle above and the mixin's `semantic` section untouched.
        if page == 1:
            record_query_hit(query)


@_throttled("sync", "GET", key=client_ip_key)
class SyncView(forum_views.SyncView):
    pass


# GET-only, public, but a polling target since todo 346 (`?peek=1` from the
# web thread page every 30 s per visible tab) — the same per-IP floor as
# sync/, so a misbehaving client cannot hammer the join-heavy detail query.
@_throttled("topic_detail", "GET", key=client_ip_key)
class TopicDetailView(forum_views.TopicDetailView):
    pass


# NotificationListView has no wrapper here — GET (list) is public-shape (auth
# required, but not a polling target) and mounted straight from the package in
# api_urls.py, same as BoardListView.


@_throttled("notification_unread_count", "GET")
class NotificationUnreadCountView(forum_notification_views.NotificationUnreadCountView):
    pass


@_throttled("notification_mark_read", "POST")
class NotificationMarkReadView(forum_notification_views.NotificationMarkReadView):
    pass


@_throttled("subscription_create", "POST")
@_throttled("subscription_delete", "DELETE")
class TopicSubscriptionView(forum_subscription_views.TopicSubscriptionView):
    pass


@_throttled("bookmark_create", "POST")
@_throttled("bookmark_delete", "DELETE")
class TopicBookmarkView(forum_bookmark_views.TopicBookmarkView):
    pass


# TopicBookmarkListView has no wrapper here — GET (list) is a page load, not a
# polling target, same treatment as NotificationListView above — mounted
# straight from the package in api_urls.py.


@_throttled("block_create", "POST")
@_throttled("block_delete", "DELETE")
class UserBlockView(forum_user_block_views.UserBlockView):
    pass


@_throttled("mute_create", "POST")
@_throttled("mute_delete", "DELETE")
class UserMuteView(forum_user_mute_views.UserMuteView):
    pass


# MyMutesView has no wrapper here — GET (list) is a page load, like
# MyBlocksView above — mounted straight from the package in api_urls.py.


# MyBlocksView has no wrapper here — GET (list) is a page load, not a polling
# target, same treatment as TopicBookmarkListView above — mounted straight
# from the package in api_urls.py.


@_throttled("poll_vote", "POST")
class PollVoteView(forum_poll_views.PollVoteView):
    pass


@_throttled("solution_mark", "POST")
@_throttled("solution_clear", "DELETE")
class TopicSolutionView(forum_solution_views.TopicSolutionView):
    pass


@_throttled("mention_user_search", "GET", key="user")
class UserMentionSearchView(forum_user_search_views.UserMentionSearchView):
    pass


@_throttled("message_send", "POST")
class MessageSendView(forum_direct_message_views.MessageSendView):
    pass


@_throttled("report_create", "POST")
class MessageReportView(forum_direct_message_views.MessageReportView):
    pass


# ConversationListView/ConversationMessagesView have no wrapper here — GET
# (list) is a page load, not a polling target, same treatment as
# NotificationListView/TopicBookmarkListView/MyBlocksView above — mounted
# straight from the package in api_urls.py.
