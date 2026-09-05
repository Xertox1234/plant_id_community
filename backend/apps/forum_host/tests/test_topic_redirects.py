"""Topic slug/board changes create Wagtail redirects (Wagtail quick wins, item 2).

``Topic.get_absolute_url`` is ``/forum/{board.id}-{board.slug}/{id}-{slug}``,
so both a slug edit and a board move change the public path. On this host
those paths are only ever a Wagtail 404 (the SPA serves them, and it resolves
by the leading id), so the rows are served two ways: by the redirect
middleware for a request that reaches this origin, and by the redirects API
(``/api/v2/redirects/find/?html_path=``) for a headless client.
"""

import pytest
from apps.forum_host.redirects import board_topic_prefix, redirect_board_topics
from django.db import connection
from django.db.models import F
from django.test.utils import CaptureQueriesContext
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


# --- board slug renames (todo 334) -------------------------------------------

# SELECT live topics; SAVEPOINT; SELECT manual shadowing rows (for the
# warning); DELETE shadowing; UPDATE chain collapse; DELETE self-loops;
# DELETE old-path rows; INSERT; RELEASE SAVEPOINT. Independent of how many
# topics the board holds (up to REDIRECT_BULK_CREATE_BATCH_SIZE per INSERT).
# +1 SELECT for manual rows only when the board holds a HIDDEN once-public topic
# (an empty `__in` is short-circuited without a query), so the fixture above
# — live topics only — stays at this count.
BOARD_RENAME_QUERIES = 9


def _topic_rows():
    """Our all-sites rows only — Wagtail's own page auto-redirects (if a Site
    ever covers /forum/) are site-bound and page-targeted."""
    return list(
        Redirect.objects.filter(site=None, redirect_page=None)
        .order_by("old_path")
        .values_list(
            "old_path", "redirect_link", "is_permanent", "automatically_created"
        )
    )


def _topic_links():
    return [(old, new) for old, new, *_ in _topic_rows()]


def _rename_board(board, slug, capture_on_commit):
    # page_slug_changed is sent from transaction.on_commit, which a
    # transactional test never reaches on its own.
    with capture_on_commit(execute=True):
        board.slug = slug
        board.save()


def test_board_prefix_matches_the_topic_url_shape():
    general, _ = _boards()
    topic = _topic(general, "x")
    prefix = board_topic_prefix(general.pk, general.slug)
    assert topic.get_absolute_url() == f"{prefix}{topic.pk}-x"


def test_board_rename_redirects_every_live_topic_and_no_drafts(
    django_capture_on_commit_callbacks,
):
    general, _ = _boards()
    live = [_topic(general, "aphids"), _topic(general, "mealybugs")]
    _topic(general, "draft", live=False)
    old_paths = [t.get_absolute_url() for t in live]

    _rename_board(general, "general-chat", django_capture_on_commit_callbacks)

    expected = sorted(
        (old, t.get_absolute_url(), True, True) for old, t in zip(old_paths, live)
    )
    assert _topic_rows() == expected
    assert all(
        new.startswith("/forum/%d-general-chat/" % general.pk)
        for _, new, *_ in expected
    )


def test_board_rename_old_topic_path_is_served_as_a_301(
    client, django_capture_on_commit_callbacks
):
    general, _ = _boards()
    topic = _topic(general, "aphids")
    old_path = topic.get_absolute_url()

    _rename_board(general, "general-chat", django_capture_on_commit_callbacks)

    resp = client.get(old_path)
    assert resp.status_code == 301
    assert resp["Location"] == topic.get_absolute_url()


def test_repeated_board_renames_collapse_chains(django_capture_on_commit_callbacks):
    general, _ = _boards()
    topic = _topic(general, "aphids")
    path_a = topic.get_absolute_url()
    _rename_board(general, "b", django_capture_on_commit_callbacks)
    path_b = topic.get_absolute_url()

    _rename_board(general, "c", django_capture_on_commit_callbacks)
    path_c = topic.get_absolute_url()

    assert _topic_links() == sorted([(path_a, path_c), (path_b, path_c)])


def test_board_rename_back_leaves_no_loop(django_capture_on_commit_callbacks):
    general, _ = _boards()
    topic = _topic(general, "aphids")
    path_a = topic.get_absolute_url()
    _rename_board(general, "b", django_capture_on_commit_callbacks)
    path_b = topic.get_absolute_url()

    _rename_board(general, "general", django_capture_on_commit_callbacks)

    assert topic.get_absolute_url() == path_a
    assert _topic_links() == [(path_b, path_a)]


def test_board_rename_collapses_a_topic_rename_onto_the_new_board_path(
    django_capture_on_commit_callbacks,
):
    """A topic slug change (x→y) then a board rename: the x row must follow
    the topic to the new board path, not stop at the old board's y."""
    general, _ = _boards()
    topic = _topic(general, "x")
    path_x = topic.get_absolute_url()
    topic.slug = "y"
    topic.save()
    path_y_old_board = topic.get_absolute_url()

    _rename_board(general, "general-chat", django_capture_on_commit_callbacks)
    path_y_new_board = topic.get_absolute_url()

    assert _topic_links() == sorted(
        [(path_x, path_y_new_board), (path_y_old_board, path_y_new_board)]
    )


def test_board_rename_removes_a_manual_row_from_a_topics_new_path(
    caplog, django_capture_on_commit_callbacks
):
    import logging

    general, _ = _boards()
    topic = _topic(general, "aphids")
    new_path = topic.get_absolute_url().replace("-general/", "-general-chat/")
    Redirect.add_redirect(new_path, "/somewhere-else/")  # manual

    log = logging.getLogger("apps.forum_host.redirects")
    log.addHandler(caplog.handler)
    try:
        with caplog.at_level(logging.WARNING, logger=log.name):
            _rename_board(general, "general-chat", django_capture_on_commit_callbacks)
    finally:
        log.removeHandler(caplog.handler)

    assert topic.get_absolute_url() == new_path
    assert _topic_links() == [
        (new_path.replace("-general-chat/", "-general/"), new_path)
    ]
    assert any(new_path in r.getMessage() for r in caplog.records)


def test_board_rename_query_count_is_flat_in_topic_count():
    general, pests = _boards()
    Topic.objects.bulk_create(
        [Topic(board=general, title="T", slug=f"t-{i}") for i in range(3)]
    )
    Topic.objects.bulk_create(
        [Topic(board=pests, title="T", slug=f"t-{i}") for i in range(1000)]
    )

    def rename(board, slug):
        before = ForumBoard.objects.get(pk=board.pk)
        board.slug = slug
        with CaptureQueriesContext(connection) as ctx:
            redirect_board_topics(before, board)
        return len(ctx.captured_queries)

    small = rename(general, "general-2")
    big = rename(pests, "pests-2")

    assert (small, big) == (BOARD_RENAME_QUERIES, BOARD_RENAME_QUERIES)
    assert Redirect.objects.filter(site=None).count() == 1003


def test_board_rename_with_no_live_topics_writes_nothing(
    django_capture_on_commit_callbacks,
):
    general, _ = _boards()
    _topic(general, "draft", live=False)

    _rename_board(general, "general-chat", django_capture_on_commit_callbacks)

    assert _topic_rows() == []


def test_board_rename_through_the_admin_publish_path(
    django_capture_on_commit_callbacks,
):
    """The promote-tab edit lands via save_revision().publish(), not a bare
    save(); the signal must fire from that path too."""
    general, _ = _boards()
    topic = _topic(general, "aphids")
    old_path = topic.get_absolute_url()

    with django_capture_on_commit_callbacks(execute=True):
        general.slug = "general-chat"
        general.save_revision().publish()

    general.refresh_from_db()
    assert general.slug == "general-chat"
    assert _topic_links() == [
        (old_path, f"/forum/{general.pk}-general-chat/{topic.pk}-aphids")
    ]


# --- review round 1 (code-review, 2026-09-04) ---------------------------------


def test_board_rename_back_after_a_topic_was_unpublished_leaves_no_self_loop(
    django_capture_on_commit_callbacks,
):
    """Rename A→B writes rows for both topics; topic 2 is then unpublished, so
    the rename back B→A skips its new path in the shadowing delete — and the
    prefix collapse would fold its A→B row into A→A. That row must go."""
    general, _ = _boards()
    live_topic = _topic(general, "live")
    later_draft = _topic(general, "draft")
    path_a_live = live_topic.get_absolute_url()
    _rename_board(general, "general-chat", django_capture_on_commit_callbacks)
    path_b_live = live_topic.get_absolute_url()
    later_draft.live = False
    later_draft.save(update_fields=["live"])

    _rename_board(general, "general", django_capture_on_commit_callbacks)

    assert not Redirect.objects.filter(redirect_link=F("old_path")).exists()
    assert _topic_links() == [(path_b_live, path_a_live)]


def test_board_rename_back_with_no_live_topics_still_repairs_stale_rows(
    django_capture_on_commit_callbacks,
):
    """With every topic unpublished there is nothing to write, but the row an
    earlier rename left (A→B) would otherwise send the topic's own canonical
    URL to a dead path the moment it is republished."""
    general, _ = _boards()
    topic = _topic(general, "aphids")
    _rename_board(general, "general-chat", django_capture_on_commit_callbacks)
    topic.live = False
    topic.save(update_fields=["live"])

    _rename_board(general, "general", django_capture_on_commit_callbacks)

    assert _topic_links() == []


# --- audit 2026-09-04 M1: once-public paths of hidden topics -------------------


def _published_topic(board, slug):
    """A topic taken through a real publish so it carries
    ``first_published_at``, like every topic the moderation workflow makes
    live (``Topic.objects.create`` is born live but never "published").
    ``save_revision`` runs ``full_clean``, so it needs an author."""
    from django.contrib.auth import get_user_model

    author = get_user_model().objects.create_user(username=f"author-{slug}")
    topic = _topic(board, slug, author=author)
    topic.save_revision().publish()
    topic.refresh_from_db()
    return topic


def test_a_once_public_topic_renamed_while_unpublished_keeps_its_old_path():
    """The "hide it, fix the slug, republish it" moderation flow. Since Wagtail
    6.0 the admin saves a draft edit of an UNPUBLISHED snippet straight to the
    row (``form.save(commit=not live)``) and the Publish button is then a plain
    ``save()``: by that save the row already carries the new slug, so a
    receiver that waits for the publish sees old == new and writes nothing.
    The hidden save has to write the row, and the publish must leave it be."""
    general, _ = _boards()
    topic = _published_topic(general, "aphids")
    old_path = topic.get_absolute_url()
    topic.unpublish()
    assert topic.first_published_at is not None and not topic.live

    topic.slug = "aphids-fixed"
    topic.save()  # the edit view's write-through for a non-live object
    new_path = topic.get_absolute_url()
    assert _links() == [(old_path, new_path)]

    topic.save_revision().publish()  # the Publish button
    topic.refresh_from_db()
    assert topic.live
    assert _links() == [(old_path, new_path)]


def test_a_once_public_topic_old_path_is_served_as_a_301_after_republish(client):
    general, _ = _boards()
    topic = _published_topic(general, "old-name")
    old_path = topic.get_absolute_url()
    topic.unpublish()
    topic.slug = "new-name"
    topic.save()
    topic.save_revision().publish()

    resp = client.get(old_path)

    assert resp.status_code == 301
    assert resp["Location"] == topic.get_absolute_url()


def test_board_rename_writes_a_row_for_a_once_public_hidden_topic(
    django_capture_on_commit_callbacks,
):
    """Same reasoning in bulk: a topic that was public under the old board
    path and is hidden right now gets its row, so the old link is right the
    moment it is republished; a never-published draft still gets none."""
    general, _ = _boards()
    hidden = _published_topic(general, "aphids")
    hidden.unpublish()
    _topic(general, "draft", live=False)
    old_path = hidden.get_absolute_url()

    _rename_board(general, "general-chat", django_capture_on_commit_callbacks)

    hidden.refresh_from_db()
    assert _topic_links() == [(old_path, hidden.get_absolute_url())]


# --- code review round 2 (PR #629): an editor's row from the old path wins ----


def test_a_manual_row_from_a_hidden_topics_old_path_is_kept_not_rewritten(caplog):
    """A moderator sent a hidden duplicate's once-public URL to its canonical
    topic by hand. Fixing the duplicate's slug while it is hidden must not
    rewrite that row into a redirect to a hidden 404, nor relabel it
    auto-created — and must say so."""
    import logging

    general, _ = _boards()
    topic = _published_topic(general, "dup")
    dup_path = topic.get_absolute_url()
    canonical = f"/forum/{general.pk}-general/999-canonical"
    Redirect.add_redirect(dup_path, canonical)  # manual, automatically_created=False
    topic.unpublish()

    log = logging.getLogger("apps.forum_host.redirects")
    log.addHandler(caplog.handler)
    try:
        with caplog.at_level(logging.INFO, logger=log.name):
            topic.slug = "dup-2"
            topic.save()
    finally:
        log.removeHandler(caplog.handler)

    assert _rows() == [
        (Redirect.normalise_path(dup_path), canonical, True, False, None)
    ]
    assert any("Kept manual redirect" in r.getMessage() for r in caplog.records)


def test_board_rename_keeps_a_manual_row_from_a_hidden_topics_old_path(
    django_capture_on_commit_callbacks,
):
    """Same in bulk: the live topic gets its automatic row, the hidden
    duplicate's manual row survives (its link follows the board, as every row
    aimed under the old prefix does), and no automatic row competes with it."""
    general, _ = _boards()
    hidden = _published_topic(general, "dup")
    hidden.unpublish()
    live_topic = _topic(general, "aphids")
    dup_old = Redirect.normalise_path(hidden.get_absolute_url())
    live_old = live_topic.get_absolute_url()
    Redirect.add_redirect(dup_old, f"/forum/{general.pk}-general/999-canonical")

    _rename_board(general, "general-chat", django_capture_on_commit_callbacks)

    live_topic.refresh_from_db()
    manual = Redirect.objects.get(old_path=dup_old)
    assert manual.automatically_created is False
    assert manual.redirect_link == f"/forum/{general.pk}-general-chat/999-canonical"
    assert Redirect.objects.filter(old_path=dup_old).count() == 1
    assert (live_old, live_topic.get_absolute_url()) in _topic_links()
