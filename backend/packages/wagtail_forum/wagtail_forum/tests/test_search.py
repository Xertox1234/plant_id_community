import pytest
from wagtail.models import Page
from wagtail.search.backends import get_search_backend
from wagtail_forum.models import ForumBoard, ForumIndex, Topic


@pytest.mark.django_db
def test_topic_is_searchable_by_title():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    Topic.objects.create(board=board, title="Monstera propagation", slug="monstera")

    backend = get_search_backend()
    results = backend.search("Monstera", Topic)

    assert any(t.slug == "monstera" for t in results)
