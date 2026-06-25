import pytest
from wagtail.models import Collection
from wagtail_forum.collections import get_forum_image_collection


@pytest.mark.django_db
def test_get_forum_image_collection_is_idempotent():
    first = get_forum_image_collection()
    second = get_forum_image_collection()

    assert first.pk == second.pk
    assert first.name == "Forum Images"
    assert first.is_descendant_of(Collection.get_first_root_node())
    # A second call must not create a duplicate sibling.
    root = Collection.get_first_root_node()
    assert root.get_children().filter(name="Forum Images").count() == 1
