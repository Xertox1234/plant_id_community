import pytest
from wagtail.search.backends import get_search_backend
from wagtail_forum.models import Topic
from wagtail_forum.tests.factories import make_forum


@pytest.mark.django_db
def test_topic_is_searchable_by_title():
    board = make_forum(name="General", slug="general")
    Topic.objects.create(board=board, title="Monstera propagation", slug="monstera")

    backend = get_search_backend()
    results = backend.search("Monstera", Topic)

    assert any(t.slug == "monstera" for t in results)
