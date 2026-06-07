from django.urls import path

from .views import (
    BoardListView,
    MeProfileView,
    ReactionToggleView,
    ReplyCreateView,
    TopicCreateView,
    TopicListView,
)

app_name = "wagtail_forum_api"

urlpatterns = [
    path("boards/", BoardListView.as_view(), name="board-list"),
    path("boards/<slug:slug>/topics/", TopicListView.as_view(), name="topic-list"),
    path(
        "boards/<slug:slug>/topics/create/",
        TopicCreateView.as_view(),
        name="topic-create",
    ),
    path(
        "topics/<int:topic_id>/posts/create/",
        ReplyCreateView.as_view(),
        name="reply-create",
    ),
    path(
        "posts/<int:post_id>/reactions/",
        ReactionToggleView.as_view(),
        name="reaction-toggle",
    ),
    path("me/profile/", MeProfileView.as_view(), name="me-profile"),
]
