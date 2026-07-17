import pytest
from wagtail.models import Collection
from wagtail_forum.collections import get_forum_image_collection


@pytest.mark.django_db
def test_get_forum_image_collection_locked_recheck_reuses_existing(monkeypatch):
    # Audit 2026-07-17 L2: Collection.name has no unique constraint, so the
    # pre-fix check-then-create could race two concurrent first callers into
    # duplicate "Forum Images" collections. Simulate losing that race
    # deterministically: the unlocked fast-path check misses (patched to
    # return nothing once) while the collection already exists — the
    # select_for_update re-check must find it and NOT create a duplicate.
    # (Real threads would need django_db(transaction=True), whose teardown
    # flush deletes Wagtail's migration-seeded root rows and breaks later
    # tests — banned per tests/api/test_topic_detail.py. Cross-connection
    # serialization itself is provided by select_for_update semantics.)
    existing = get_forum_image_collection()

    orig_get_children = Collection.get_children
    state = {"missed": False}

    def miss_once(self):
        if not state["missed"]:
            state["missed"] = True
            return Collection.objects.none()
        return orig_get_children(self)

    monkeypatch.setattr(Collection, "get_children", miss_once)

    result = get_forum_image_collection()

    assert state["missed"] is True  # the fast path really did miss
    assert result.pk == existing.pk
    assert Collection.objects.filter(name="Forum Images").count() == 1


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
