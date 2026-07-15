"""Host mount of the forum API with rate-limited views (audit H1).

Mirrors `wagtail_forum.api.urls` exactly — same routes, same names, same
`app_name` — substituting the throttled wrappers from `api.py`. A parity test
(`tests/test_ratelimits.py`) asserts the route sets stay identical so a new
package endpoint cannot silently ship unmounted or unthrottled.
"""

from django.urls import path

# The notification list is auth-gated but not a polling target — mounted
# straight from the package like BoardListView/TopicDetailView above.
from wagtail_forum.api.notifications import NotificationListView

# GET-only views are mounted straight from the package (no throttle); views with
# a throttled write handler come from the host wrappers in .api.
from wagtail_forum.api.views import BoardListView, TopicDetailView

from .api import (
    MeProfileView,
    NotificationMarkReadView,
    NotificationUnreadCountView,
    PostImageUploadView,
    PostListView,
    PostReportView,
    PostWriteView,
    ReactionToggleView,
    SearchView,
    SyncView,
    TopicListView,
    TopicSubscriptionView,
    UserMentionSearchView,
)

app_name = "wagtail_forum_api"

urlpatterns = [
    path("boards/", BoardListView.as_view(), name="board-list"),
    path("boards/<slug:slug>/topics/", TopicListView.as_view(), name="topic-list"),
    path("topics/<int:topic_id>/", TopicDetailView.as_view(), name="topic-detail"),
    path(
        "topics/<int:topic_id>/subscription/",
        TopicSubscriptionView.as_view(),
        name="topic-subscription",
    ),
    path("topics/<int:topic_id>/posts/", PostListView.as_view(), name="post-list"),
    path("images/", PostImageUploadView.as_view(), name="image-upload"),
    path("posts/<int:post_id>/", PostWriteView.as_view(), name="post-detail"),
    path(
        "posts/<int:post_id>/reactions/",
        ReactionToggleView.as_view(),
        name="reaction-toggle",
    ),
    path(
        "posts/<int:post_id>/reports/",
        PostReportView.as_view(),
        name="post-report",
    ),
    path("me/profile/", MeProfileView.as_view(), name="me-profile"),
    path("search/", SearchView.as_view(), name="search"),
    path("sync/", SyncView.as_view(), name="sync"),
    path("users/search/", UserMentionSearchView.as_view(), name="user-mention-search"),
    path("notifications/", NotificationListView.as_view(), name="notification-list"),
    path(
        "notifications/unread-count/",
        NotificationUnreadCountView.as_view(),
        name="notification-unread-count",
    ),
    path(
        "notifications/mark-read/",
        NotificationMarkReadView.as_view(),
        name="notification-mark-read",
    ),
]
