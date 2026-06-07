from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup

from .models import ForumProfile, Post, Topic


class TopicViewSet(SnippetViewSet):
    model = Topic
    icon = "form"
    menu_label = "Topics"
    list_display = ["title", "board", "author", "live", "reply_count"]
    search_fields = ["title"]


class PostViewSet(SnippetViewSet):
    model = Post
    icon = "comment"
    menu_label = "Posts"
    list_display = ["__str__", "topic", "author", "live"]


class ForumProfileViewSet(SnippetViewSet):
    model = ForumProfile
    icon = "user"
    menu_label = "Profiles"
    list_display = ["__str__", "trust_level", "post_count"]


class ForumViewSetGroup(SnippetViewSetGroup):
    items = (TopicViewSet, PostViewSet, ForumProfileViewSet)
    menu_icon = "group"
    menu_label = "Forum"
    menu_name = "forum"


register_snippet(ForumViewSetGroup)
