from django.urls import path

from .views import BoardListView, TopicCreateView, TopicListView

app_name = "wagtail_forum_api"

urlpatterns = [
    path("boards/", BoardListView.as_view(), name="board-list"),
    path("boards/<slug:slug>/topics/", TopicListView.as_view(), name="topic-list"),
    path(
        "boards/<slug:slug>/topics/create/",
        TopicCreateView.as_view(),
        name="topic-create",
    ),
]
