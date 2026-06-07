from django.urls import path

from .views import BoardListView, TopicListView

app_name = "wagtail_forum_api"

urlpatterns = [
    path("boards/", BoardListView.as_view(), name="board-list"),
    path("boards/<slug:slug>/topics/", TopicListView.as_view(), name="topic-list"),
]
