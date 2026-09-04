"""Topic slug/board changes create Wagtail redirects (Wagtail quick wins, item 2).

``Topic.get_absolute_url`` is ``/forum/{board.id}-{board.slug}/{id}-{slug}``,
so both a slug edit and a board move change the public path. On this host
those paths are only ever a Wagtail 404 (the SPA serves them, and it resolves
by the leading id), so the rows are served two ways: by the redirect
middleware for a request that reaches this origin, and by the redirects API
(``/api/v2/redirects/find/?html_path=``) for a headless client.
"""

import pytest
from wagtail.contrib.redirects.models import Redirect
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex, Topic

pytestmark = pytest.mark.django_db


def _boards():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    general = index.add_child(instance=ForumBoard(title="General", slug="general"))
    pests = index.add_child(instance=ForumBoard(title="Pests", slug="pests"))
    return general, pests


def _topic(board, slug, **kwargs):
    return Topic.objects.create(board=board, title="T", slug=slug, **kwargs)


def _rows():
    return list(
        Redirect.objects.order_by("old_path").values_list(
            "old_path",
            "redirect_link",
            "is_permanent",
            "automatically_created",
            "site_id",
        )
    )


def _links():
    return [(old, new) for old, new, *_ in _rows()]


def test_slug_change_on_a_live_topic_creates_a_permanent_all_sites_redirect():
    general, _ = _boards()
    topic = _topic(general, "old-name")
    old_path = topic.get_absolute_url()

    topic.slug = "new-name"
    topic.save()

    assert _rows() == [(old_path, topic.get_absolute_url(), True, True, None)]


def test_board_move_creates_a_redirect():
    general, pests = _boards()
    topic = _topic(general, "aphids")
    old_path = topic.get_absolute_url()

    topic.board = pests
    topic.save()

    assert topic.get_absolute_url() != old_path
    assert _links() == [(old_path, topic.get_absolute_url())]


def test_saves_that_do_not_change_the_path_create_nothing():
    general, _ = _boards()
    topic = _topic(general, "same")

    topic.title = "Only the title changed"
    topic.save()
    topic.is_closed = True
    topic.save(update_fields=["is_closed"])

    assert Redirect.objects.count() == 0


def test_creating_a_topic_creates_nothing():
    general, _ = _boards()
    _topic(general, "fresh")
    assert Redirect.objects.count() == 0


def test_an_unpublished_topic_changing_slug_creates_nothing():
    general, _ = _boards()
    topic = _topic(general, "hidden", live=False)

    topic.slug = "still-hidden"
    topic.save()

    assert Redirect.objects.count() == 0


def test_renaming_back_removes_the_reverse_row_so_there_is_no_loop():
    general, _ = _boards()
    topic = _topic(general, "a")
    path_a = topic.get_absolute_url()
    topic.slug = "b"
    topic.save()
    path_b = topic.get_absolute_url()

    topic.slug = "a"
    topic.save()

    assert _links() == [(path_b, path_a)]


def test_a_chain_of_renames_collapses_onto_the_current_path():
    general, _ = _boards()
    topic = _topic(general, "a")
    path_a = topic.get_absolute_url()
    topic.slug = "b"
    topic.save()
    path_b = topic.get_absolute_url()

    topic.slug = "c"
    topic.save()
    path_c = topic.get_absolute_url()

    assert _links() == [(path_a, path_c), (path_b, path_c)]


def test_an_existing_row_for_the_old_path_is_re_pointed_not_duplicated():
    general, _ = _boards()
    topic = _topic(general, "a")
    path_a = topic.get_absolute_url()
    Redirect.add_redirect(path_a, "/somewhere-else/")

    topic.slug = "b"
    topic.save()

    assert _links() == [(path_a, topic.get_absolute_url())]


def test_the_old_path_is_served_as_a_301_on_this_host(client):
    general, _ = _boards()
    topic = _topic(general, "old-name")
    old_path = topic.get_absolute_url()
    topic.slug = "new-name"
    topic.save()

    resp = client.get(old_path)

    assert resp.status_code == 301
    assert resp["Location"] == topic.get_absolute_url()


def test_the_redirects_api_resolves_the_old_path_for_a_headless_client(client):
    general, _ = _boards()
    topic = _topic(general, "old-name")
    old_path = topic.get_absolute_url()
    topic.slug = "new-name"
    topic.save()

    resp = client.get("/api/v2/redirects/find/", {"html_path": old_path}, follow=True)

    assert resp.status_code == 200
    assert resp.json()["location"] == topic.get_absolute_url()


# --- review round 1 (code-review, 2026-09-04) ---------------------------------


def test_a_manual_row_from_the_new_path_is_removed_so_there_is_no_loop(caplog):
    """A hand-made redirect FROM the topic's new path (b→a) plus the auto row
    a→b is a loop on this host, where b is a 404; and the chain-collapse
    update would otherwise rewrite that manual row into b→b."""
    import logging

    general, _ = _boards()
    topic = _topic(general, "a")
    path_a = topic.get_absolute_url()
    path_b = path_a.rsplit("-", 1)[0] + "-b"
    Redirect.add_redirect(path_b, path_a)  # manual, automatically_created=False

    # The project's "apps" loggers don't propagate to root (settings.LOGGING),
    # so caplog only sees this logger with its handler attached directly.
    log = logging.getLogger("apps.forum_host.redirects")
    log.addHandler(caplog.handler)
    try:
        with caplog.at_level(logging.WARNING, logger=log.name):
            topic.slug = "b"
            topic.save()
    finally:
        log.removeHandler(caplog.handler)

    assert _links() == [(path_a, path_b)]
    assert any(path_b in r.getMessage() for r in caplog.records)


def test_duplicate_all_sites_rows_for_the_old_path_are_all_re_pointed():
    """Postgres does not enforce unique_together(old_path, site) when site IS
    NULL, so two identical all-sites rows can exist; a later path change must
    re-point both instead of raising MultipleObjectsReturned in post_save."""
    general, _ = _boards()
    topic = _topic(general, "a")
    path_a = topic.get_absolute_url()
    Redirect.objects.create(old_path=path_a, redirect_link="/x/", site=None)
    Redirect.objects.create(old_path=path_a, redirect_link="/y/", site=None)

    topic.slug = "b"
    topic.save()

    assert _links() == [(path_a, topic.get_absolute_url())] * 2
