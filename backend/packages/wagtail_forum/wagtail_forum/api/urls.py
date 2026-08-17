from django.urls import path

from .bookmarks import TopicBookmarkListView, TopicBookmarkView
from .notifications import (
    NotificationListView,
    NotificationMarkReadView,
    NotificationUnreadCountView,
)
from .solutions import TopicSolutionView
from .subscriptions import TopicSubscriptionView
from .user_search import UserMentionSearchView
from .views import (
    BoardListView,
    ExpertsView,
    MeProfileView,
    MeStatsView,
    PostImageUploadView,
    PostListView,
    PostReportView,
    PostRevisionDetailView,
    PostRevisionListView,
    PostWriteView,
    PublicProfileView,
    ReactionToggleView,
    RecentTopicsView,
    SearchView,
    SyncView,
    TopicDetailView,
    TopicListView,
)

app_name = "wagtail_forum_api"

urlpatterns = [
    path("boards/", BoardListView.as_view(), name="board-list"),
    path("boards/<slug:slug>/topics/", TopicListView.as_view(), name="topic-list"),
    path("topics/recent/", RecentTopicsView.as_view(), name="topics-recent"),
    # MUST come before topics/<int:topic_id>/ — literal-over-capture, same rule
    # this file already documents for users/search/ vs users/<str:username>/.
    path("topics/<int:topic_id>/", TopicDetailView.as_view(), name="topic-detail"),
    path(
        "topics/<int:topic_id>/subscription/",
        TopicSubscriptionView.as_view(),
        name="topic-subscription",
    ),
    path(
        "topics/<int:topic_id>/bookmark/",
        TopicBookmarkView.as_view(),
        name="topic-bookmark",
    ),
    path(
        "topics/<int:topic_id>/solution/",
        TopicSolutionView.as_view(),
        name="topic-solution",
    ),
    path("topics/<int:topic_id>/posts/", PostListView.as_view(), name="post-list"),
    path("images/", PostImageUploadView.as_view(), name="image-upload"),
    path("posts/<int:post_id>/", PostWriteView.as_view(), name="post-detail"),
    path(
        "posts/<int:post_id>/revisions/",
        PostRevisionListView.as_view(),
        name="post-revision-list",
    ),
    path(
        "posts/<int:post_id>/revisions/<int:revision_id>/",
        PostRevisionDetailView.as_view(),
        name="post-revision-detail",
    ),
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
    path("me/stats/", MeStatsView.as_view(), name="me-stats"),
    path("me/bookmarks/", TopicBookmarkListView.as_view(), name="me-bookmarks"),
    path("search/", SearchView.as_view(), name="search"),
    path("sync/", SyncView.as_view(), name="sync"),
    path("users/search/", UserMentionSearchView.as_view(), name="user-mention-search"),
    # MUST come after users/search/ and users/experts/ — literal paths win over
    # <str:username> so "search" and "experts" aren't captured as usernames
    # (Django resolves in order).
    path("users/experts/", ExpertsView.as_view(), name="users-experts"),
    path(
        "users/<str:username>/",
        PublicProfileView.as_view(),
        name="user-profile",
    ),
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
