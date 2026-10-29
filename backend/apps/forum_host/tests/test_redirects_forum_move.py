"""Topics moved by the admin's forum delete / change type (todo 667) keep
their old URLs working: ``redirect_moved_topics`` writes the same rows the
per-topic receiver writes for a single board move."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from wagtail.contrib.redirects.models import Redirect
from wagtail_forum.models import Forum, Topic
from wagtail_forum.services import forum_structure
from wagtail_forum.signals import topics_moved
from wagtail_forum.tests.factories import make_forum

User = get_user_model()

pytestmark = pytest.mark.django_db


def _topic(board, slug, **kwargs):
    return Topic.objects.create(board=board, title="T", slug=slug, **kwargs)


def _links():
    return sorted(Redirect.objects.values_list("old_path", "redirect_link"))


def _fresh_url(topic):
    return Topic.objects.select_related("board").get(pk=topic.pk).get_absolute_url()


def test_admin_delete_with_move_redirects_every_old_topic_url(client):
    source = make_forum(name="Ferns", slug="ferns")
    target = make_forum(name="Pests", slug="pests")
    topics = [_topic(source, "a"), _topic(source, "b")]
    old_urls = [t.get_absolute_url() for t in topics]
    client.force_login(User.objects.create_superuser(username="root", email="r@x.io"))

    resp = client.post(
        reverse("wagtail_forum_forums:delete", args=(source.pk,)),
        {"topics_action": forum_structure.MOVE, "target": target.pk},
    )

    assert resp.status_code == 302
    new_urls = [_fresh_url(t) for t in topics]
    assert all(url.startswith(f"/forum/{target.pk}-pests/") for url in new_urls)
    assert _links() == sorted(zip(old_urls, new_urls))
    rows = Redirect.objects.all()
    assert all(r.is_permanent and r.automatically_created for r in rows)
    assert all(r.site_id is None for r in rows)
    # The redirect middleware answers the old path with a 301 to the new one.
    client.logout()
    hop = client.get(old_urls[0])
    assert hop.status_code == 301
    assert hop["Location"] == new_urls[0]


def test_a_renamed_slug_redirects_to_its_new_path():
    source = make_forum(name="Ferns", slug="ferns")
    target = make_forum(name="Pests", slug="pests")
    _topic(target, "watering")
    clash = _topic(source, "watering")
    old = clash.get_absolute_url()

    forum_structure.move_topics(source, target)

    new = _fresh_url(clash)
    assert new == f"/forum/{target.pk}-pests/{clash.pk}-watering-{clash.pk}"
    assert _links() == [(old, new)]


def test_a_never_published_draft_gets_no_row_but_chains_still_collapse():
    source = make_forum(name="Ferns", slug="ferns")
    target = make_forum(name="Pests", slug="pests")
    draft = _topic(source, "draft", live=False)
    old = draft.get_absolute_url()
    Redirect.objects.create(old_path="/old-link", redirect_link=old)

    forum_structure.move_topics(source, target)

    assert _links() == [("/old-link", _fresh_url(draft))]


def test_moving_back_leaves_no_loop():
    first = make_forum(name="Ferns", slug="ferns")
    second = make_forum(name="Pests", slug="pests")
    topic = _topic(first, "a")
    path_in_first = topic.get_absolute_url()

    forum_structure.move_topics(first, second)
    path_in_second = _fresh_url(topic)
    forum_structure.move_topics(second, first)

    # A→B then B→A: only B→A stays; A→B would bounce the live path away.
    assert _fresh_url(topic) == path_in_first
    assert _links() == [(path_in_second, path_in_first)]


def test_a_refused_move_writes_no_redirect():
    source = make_forum(name="Ferns", slug="ferns")
    _topic(source, "a")
    category = Forum.objects.get(pk=source.parent_id)

    with pytest.raises(forum_structure.ValidationError):
        forum_structure.move_topics(source, category)

    assert _links() == []


def test_a_move_that_fails_after_the_signal_rolls_its_redirects_back():
    source = make_forum(name="Ferns", slug="ferns")
    target = make_forum(name="Pests", slug="pests")
    topic = _topic(source, "a")

    def fail_after_redirects(**kwargs):
        # Connected after forum_host's receiver, so the redirect rows are
        # already written when this raises inside the move's transaction.
        raise RuntimeError("later step failed")

    topics_moved.connect(fail_after_redirects, dispatch_uid="test-fail-after")
    try:
        with pytest.raises(RuntimeError):
            forum_structure.move_topics(source, target)
    finally:
        topics_moved.disconnect(dispatch_uid="test-fail-after")

    assert _links() == []
    assert Topic.objects.get(pk=topic.pk).board_id == source.pk
