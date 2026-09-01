"""Host mount of the forum API with rate-limited views (audit H1).

Mirrors `wagtail_forum.api.urls` exactly — same routes, same names, same
`app_name` — substituting the throttled wrappers from `api.py`. A parity test
(`tests/test_ratelimits.py`) asserts the route sets stay identical so a new
package endpoint cannot silently ship unmounted or unthrottled.
"""

from django.urls import path

# Same treatment as NotificationListView — a page load, not a polling target.
from wagtail_forum.api.bookmarks import TopicBookmarkListView

# GET-only, page-load views — no throttle wrapper, same treatment as
# NotificationListView/TopicBookmarkListView/MyBlocksView (todo 319/M10).
from wagtail_forum.api.direct_messages import (
    ConversationListView,
    ConversationMessagesView,
)

# The notification list is auth-gated but not a polling target — mounted
# straight from the package like BoardListView/TopicDetailView above.
from wagtail_forum.api.notifications import NotificationListView

# Same treatment as TopicBookmarkListView — a page load, not a polling target.
from wagtail_forum.api.user_blocks import MyBlocksView

# GET-only views are mounted straight from the package (no throttle); views with
# a throttled write handler come from the host wrappers in .api.
from wagtail_forum.api.views import (
    BoardListView,
    EventHeroView,
    ExpertsView,
    MeStatsView,
    PostRevisionDetailView,
    PostRevisionListView,
    PublicProfileView,
    RecentTopicsView,
    TopicDetailView,
)

from .api import (
    MeProfileView,
    MessageReportView,
    MessageSendView,
    NotificationMarkReadView,
    NotificationUnreadCountView,
    PollVoteView,
    PostImageUploadView,
    PostListView,
    PostReportView,
    PostWriteView,
    ReactionToggleView,
    SearchView,
    SyncView,
    TopicBookmarkView,
    TopicListView,
    TopicSolutionView,
    TopicSubscriptionView,
    UserBlockView,
    UserMentionSearchView,
)

# Host-only AI routes (todo 255 slice 3 / H14, slice 4 / H15; todo 275 / M14) —
# no package counterpart; their logic reuses the blog app's AI helpers, which the
# package may not import. The route-drift guard allow-lists these host-only
# additions (see HOST_ONLY_ROUTES in tests/test_ratelimits.py).
from .compose_assist import ComposeAssistView
from .rag import PlantCareAnswerReportView, PlantCareAskView
from .similar import SimilarTopicsView
from .summary import TopicSummaryView

app_name = "wagtail_forum_api"

urlpatterns = [
    path(
        "compose/assist/",
        ComposeAssistView.as_view(),
        name="compose-assist",
    ),
    # RAG plant-care answers (todo 289 / M13) — host-only, dormant behind
    # FORUM_RAG_ENABLED + FORUM_VECTOR_SEARCH_ENABLED. The report route is
    # deliberately NOT flag-gated (see rag.py).
    path("care/ask/", PlantCareAskView.as_view(), name="care-ask"),
    path(
        "care/answers/<int:answer_id>/report/",
        PlantCareAnswerReportView.as_view(),
        name="care-answer-report",
    ),
    path("boards/", BoardListView.as_view(), name="board-list"),
    path("boards/<slug:slug>/topics/", TopicListView.as_view(), name="topic-list"),
    # GET-only + AllowAny, mounted straight from the package (no throttle
    # wrapper) — same treatment as BoardListView/TopicDetailView above. Before
    # topics/<int:topic_id>/, mirroring the package's literal-over-capture order.
    path("topics/recent/", RecentTopicsView.as_view(), name="topics-recent"),
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
        "topics/<int:topic_id>/poll/vote/",
        PollVoteView.as_view(),
        name="topic-poll-vote",
    ),
    path(
        "topics/<int:topic_id>/solution/",
        TopicSolutionView.as_view(),
        name="topic-solution",
    ),
    path("topics/<int:topic_id>/posts/", PostListView.as_view(), name="post-list"),
    path(
        "topics/<int:topic_id>/summary/",
        TopicSummaryView.as_view(),
        name="topic-summary",
    ),
    path(
        "topics/similar/",
        SimilarTopicsView.as_view(),
        name="topic-similar",
    ),
    path("images/", PostImageUploadView.as_view(), name="image-upload"),
    path("posts/<int:post_id>/", PostWriteView.as_view(), name="post-detail"),
    # GET-only, so mounted straight from the package (no throttled wrapper) —
    # same treatment as the other read views here.
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
    path("me/blocks/", MyBlocksView.as_view(), name="me-blocks"),
    # GET-only + AllowAny — mounted straight from the package (no throttle
    # wrapper), mirrors RecentTopicsView/ExpertsView.
    path("event/", EventHeroView.as_view(), name="event-hero"),
    path("search/", SearchView.as_view(), name="search"),
    path("sync/", SyncView.as_view(), name="sync"),
    path("users/search/", UserMentionSearchView.as_view(), name="user-mention-search"),
    # After users/search/ so the literals aren't captured as usernames (mirrors
    # the package). GET-only + AllowAny — mounted straight, no throttle wrapper.
    path("users/experts/", ExpertsView.as_view(), name="users-experts"),
    path("users/<str:username>/", PublicProfileView.as_view(), name="user-profile"),
    path("users/<str:username>/block/", UserBlockView.as_view(), name="user-block"),
    path(
        "users/<str:username>/messages/",
        MessageSendView.as_view(),
        name="user-message-send",
    ),
    # Private messaging (todo 319/M10). List views are GET-only page loads —
    # mounted straight from the package, same treatment as MyBlocksView above.
    path("conversations/", ConversationListView.as_view(), name="conversation-list"),
    path(
        "conversations/<int:conversation_id>/messages/",
        ConversationMessagesView.as_view(),
        name="conversation-messages",
    ),
    path(
        "messages/<int:message_id>/report/",
        MessageReportView.as_view(),
        name="message-report",
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
