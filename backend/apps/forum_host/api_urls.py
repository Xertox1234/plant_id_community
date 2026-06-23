"""Host mount of the forum API with rate-limited views (audit H1).

Mirrors `wagtail_forum.api.urls` exactly — same routes, same names, same
`app_name` — substituting the throttled wrappers from `api.py`. A parity test
(`tests/test_ratelimits.py`) asserts the route sets stay identical so a new
package endpoint cannot silently ship unmounted or unthrottled.
"""

from django.urls import path

# GET-only views are mounted straight from the package (no throttle); views with
# a throttled write handler come from the host wrappers in .api.
from wagtail_forum.api.views import BoardListView, TopicDetailView

from .api import (
    MeProfileView,
    PostListView,
    PostWriteView,
    ReactionToggleView,
    SearchView,
    SyncView,
    TopicListView,
)

app_name = "wagtail_forum_api"

urlpatterns = [
    path("boards/", BoardListView.as_view(), name="board-list"),
    path("boards/<slug:slug>/topics/", TopicListView.as_view(), name="topic-list"),
    path("topics/<int:topic_id>/", TopicDetailView.as_view(), name="topic-detail"),
    path("topics/<int:topic_id>/posts/", PostListView.as_view(), name="post-list"),
    path("posts/<int:post_id>/", PostWriteView.as_view(), name="post-detail"),
    path(
        "posts/<int:post_id>/reactions/",
        ReactionToggleView.as_view(),
        name="reaction-toggle",
    ),
    path("me/profile/", MeProfileView.as_view(), name="me-profile"),
    path("search/", SearchView.as_view(), name="search"),
    path("sync/", SyncView.as_view(), name="sync"),
]
