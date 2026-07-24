import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient
from wagtail.models import Page, PageViewRestriction
from wagtail_forum.models import (
    ForumBoard,
    ForumIndex,
    ForumProfile,
    Notification,
    NotificationVerb,
    Post,
    Topic,
    TrustLevel,
)
from wagtail_forum.notifications import create_notifications

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


def _board(slug="general"):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug=f"forum-{slug}"))
    return index.add_child(instance=ForumBoard(title="General", slug=slug))


def _topic_and_post(board, topic_author, post_author=None, slug="t"):
    topic = Topic.objects.create(board=board, title="T", slug=slug, author=topic_author)
    post = Post.objects.create(topic=topic, author=post_author or topic_author)
    return topic, post


def _notify(recipient, actor, topic, post):
    create_notifications(
        recipients=[recipient],
        verb=NotificationVerb.REPLY,
        actor=actor,
        topic=topic,
        post=post,
    )
    # bulk_create(ignore_conflicts=True) does not populate .pk on its returned
    # instances (Django cannot map ON CONFLICT DO NOTHING rows back to inputs)
    # — re-fetch so callers get a real, usable pk.
    return Notification.objects.get(recipient=recipient, post=post)


# ---- list --------------------------------------------------------------------


@pytest.mark.django_db
def test_notification_list_returns_only_own_notifications():
    recipient = User.objects.create_user(username="recipient")
    other = User.objects.create_user(username="other")
    actor = User.objects.create_user(username="actor")
    board = _board()
    topic, post = _topic_and_post(board, recipient, actor, slug="t1")
    _notify(recipient, actor, topic, post)
    other_topic, other_post = _topic_and_post(board, other, actor, slug="t2")
    _notify(other, actor, other_topic, other_post)

    client = APIClient()
    client.force_authenticate(recipient)
    resp = client.get("/forum/notifications/")

    assert resp.status_code == 200
    results = resp.data["results"]
    assert len(results) == 1
    assert results[0]["verb"] == "reply"
    assert results[0]["actor"]["username"] == "actor"
    assert results[0]["topic"]["id"] == topic.id
    assert results[0]["topic"]["slug"] == "t1"
    assert results[0]["topic"]["board_id"] == board.id
    assert results[0]["topic"]["board_slug"] == "general"
    assert results[0]["read_at"] is None


@pytest.mark.django_db
def test_notification_list_requires_auth():
    resp = APIClient().get("/forum/notifications/")
    assert resp.status_code == 401


@pytest.mark.django_db
def test_notification_list_query_count_pinned():
    recipient = User.objects.create_user(username="recipient2")
    actor = User.objects.create_user(username="actor2")
    topic, post = _topic_and_post(_board("general2"), recipient, actor)
    _notify(recipient, actor, topic, post)

    client = APIClient()
    client.force_authenticate(recipient)

    with CaptureQueriesContext(connection) as ctx:
        resp = client.get("/forum/notifications/")

    assert resp.status_code == 200
    # Pinned EXACTLY (docs/rules/testing.md): TWO queries — select_related
    # (actor/topic/board) folds the notification fetch into one SELECT, plus
    # one .public() PageViewRestriction lookup for board__in=_visible_boards()
    # (todo 253 slice 3 — load-bearing now that fan-out reaches subscriber
    # recipients beyond the topic's own author). DRF CursorPagination fetches
    # page_size+1 rows instead of a separate COUNT. force_authenticate
    # bypasses session/cookie auth entirely, so there's no auth-lookup query
    # to account for. If this changes, explain the new count here.
    assert len(ctx.captured_queries) == 2


@pytest.mark.django_db
def test_notification_list_actor_deleted_renders_placeholder():
    recipient = User.objects.create_user(username="recipient3")
    actor = User.objects.create_user(username="actor3")
    topic, post = _topic_and_post(_board("general3"), recipient, actor)
    _notify(recipient, actor, topic, post)
    actor.delete()  # Notification.actor is SET_NULL

    client = APIClient()
    client.force_authenticate(recipient)
    resp = client.get("/forum/notifications/")

    assert resp.status_code == 200
    assert resp.data["results"][0]["actor"]["username"] == "[deleted]"


@pytest.mark.django_db
def test_notification_list_excludes_unpublished_topic():
    """A notification whose topic was taken down (unpublished) after the
    notification was created must not appear in the list or count."""
    recipient = User.objects.create_user(username="recipient12")
    actor = User.objects.create_user(username="actor12")
    topic, post = _topic_and_post(_board("general12"), recipient, actor)
    _notify(recipient, actor, topic, post)
    topic.live = False
    topic.save(update_fields=["live"])

    client = APIClient()
    client.force_authenticate(recipient)

    list_resp = client.get("/forum/notifications/")
    assert list_resp.data["results"] == []

    count_resp = client.get("/forum/notifications/unread-count/")
    assert count_resp.data == {"count": 0}


@pytest.mark.django_db
def test_notification_list_excludes_restricted_board_topic():
    """A restricted board's PageViewRestriction is a real access boundary,
    not just a fan-out edge case (todo 253 slice 3): a notification whose
    topic sits on a board that later gained a PageViewRestriction must not
    leak, exactly like an unpublished topic. Also proves the null-topic
    OR-clause survived adding board__in=_visible_boards() as ONE combined Q
    — a separately-chained .filter() would have dropped null-topic rows too."""
    recipient = User.objects.create_user(username="recipient13")
    actor = User.objects.create_user(username="actor13")
    board = _board("general13")
    topic, post = _topic_and_post(board, recipient, actor)
    _notify(recipient, actor, topic, post)
    PageViewRestriction.objects.create(page=board, restriction_type="login")

    client = APIClient()
    client.force_authenticate(recipient)

    list_resp = client.get("/forum/notifications/")
    assert list_resp.data["results"] == []

    count_resp = client.get("/forum/notifications/unread-count/")
    assert count_resp.data == {"count": 0}


# ---- unread-count --------------------------------------------------------------


@pytest.mark.django_db
def test_unread_count_counts_only_unread():
    recipient = User.objects.create_user(username="recipient4")
    actor = User.objects.create_user(username="actor4")
    board = _board("general4")
    topic, post = _topic_and_post(board, recipient, actor, slug="t1")
    _notify(recipient, actor, topic, post)
    topic2, post2 = _topic_and_post(board, recipient, actor, slug="t2")
    read_one = _notify(recipient, actor, topic2, post2)
    read_one.read_at = timezone.now()
    read_one.save(update_fields=["read_at"])

    client = APIClient()
    client.force_authenticate(recipient)
    resp = client.get("/forum/notifications/unread-count/")

    assert resp.status_code == 200
    assert resp.data == {"count": 1}


@pytest.mark.django_db
def test_unread_count_requires_auth():
    resp = APIClient().get("/forum/notifications/unread-count/")
    assert resp.status_code == 401


# ---- mark-read -----------------------------------------------------------------


@pytest.mark.django_db
def test_mark_read_with_no_body_marks_all_unread():
    recipient = User.objects.create_user(username="recipient5")
    actor = User.objects.create_user(username="actor5")
    board = _board("general5")
    topic1, post1 = _topic_and_post(board, recipient, actor, slug="t1")
    topic2, post2 = _topic_and_post(board, recipient, actor, slug="t2")
    _notify(recipient, actor, topic1, post1)
    _notify(recipient, actor, topic2, post2)

    client = APIClient()
    client.force_authenticate(recipient)
    resp = client.post("/forum/notifications/mark-read/", {}, format="json")

    assert resp.status_code == 200
    assert resp.data == {"updated": 2}
    unread = client.get("/forum/notifications/unread-count/")
    assert unread.data == {"count": 0}


@pytest.mark.django_db
def test_mark_read_with_ids_marks_only_those():
    recipient = User.objects.create_user(username="recipient6")
    actor = User.objects.create_user(username="actor6")
    board = _board("general6")
    topic1, post1 = _topic_and_post(board, recipient, actor, slug="t1")
    topic2, post2 = _topic_and_post(board, recipient, actor, slug="t2")
    n1 = _notify(recipient, actor, topic1, post1)
    _notify(recipient, actor, topic2, post2)

    client = APIClient()
    client.force_authenticate(recipient)
    resp = client.post(
        "/forum/notifications/mark-read/", {"ids": [n1.id]}, format="json"
    )

    assert resp.status_code == 200
    assert resp.data == {"updated": 1}
    unread = client.get("/forum/notifications/unread-count/")
    assert unread.data == {"count": 1}


@pytest.mark.django_db
def test_mark_read_with_empty_ids_marks_nothing():
    recipient = User.objects.create_user(username="recipient7")
    actor = User.objects.create_user(username="actor7")
    topic, post = _topic_and_post(_board("general7"), recipient, actor)
    _notify(recipient, actor, topic, post)

    client = APIClient()
    client.force_authenticate(recipient)
    resp = client.post("/forum/notifications/mark-read/", {"ids": []}, format="json")

    assert resp.status_code == 200
    assert resp.data == {"updated": 0}


@pytest.mark.django_db
def test_mark_read_rejects_non_integer_ids():
    recipient = User.objects.create_user(username="recipient8")
    client = APIClient()
    client.force_authenticate(recipient)

    resp = client.post(
        "/forum/notifications/mark-read/", {"ids": ["not-an-int"]}, format="json"
    )

    assert resp.status_code == 400


@pytest.mark.django_db
def test_mark_read_rejects_non_list_ids():
    """A non-list `ids` (e.g. a bare int) must 400, not crash with an
    uncaught TypeError from downstream `isinstance(ids, list)` / iteration —
    the isinstance(ids, list) operand of the validation guard, distinct from
    the per-item type check test_mark_read_rejects_non_integer_ids covers."""
    recipient = User.objects.create_user(username="recipient10")
    client = APIClient()
    client.force_authenticate(recipient)

    resp = client.post("/forum/notifications/mark-read/", {"ids": 5}, format="json")

    assert resp.status_code == 400


@pytest.mark.django_db
def test_mark_read_rejects_boolean_ids():
    """isinstance(True, int) is True in Python (bool subclasses int) — a
    naive isinstance(i, int) check would accept {"ids": [true]} as "a list of
    integers" and silently match zero real notifications instead of 400ing."""
    recipient = User.objects.create_user(username="recipient11")
    client = APIClient()
    client.force_authenticate(recipient)

    resp = client.post(
        "/forum/notifications/mark-read/", {"ids": [True]}, format="json"
    )

    assert resp.status_code == 400


@pytest.mark.django_db
def test_mark_read_does_not_leak_other_users_notifications():
    recipient = User.objects.create_user(username="recipient9")
    other = User.objects.create_user(username="other9")
    actor = User.objects.create_user(username="actor9")
    topic, post = _topic_and_post(_board("general9"), other, actor)
    other_notification = _notify(other, actor, topic, post)

    client = APIClient()
    client.force_authenticate(recipient)
    resp = client.post(
        "/forum/notifications/mark-read/",
        {"ids": [other_notification.id]},
        format="json",
    )

    assert resp.status_code == 200
    assert resp.data == {"updated": 0}  # silently excluded, not a 403/404
    other_notification.refresh_from_db()
    assert other_notification.read_at is None


@pytest.mark.django_db
def test_mark_read_requires_auth():
    resp = APIClient().post("/forum/notifications/mark-read/", {}, format="json")
    assert resp.status_code == 401


# ---- post_id ---------------------------------------------------------------


@pytest.mark.django_db
def test_notification_list_includes_post_id():
    recipient = User.objects.create_user(username="postid_recipient")
    actor = User.objects.create_user(username="postid_actor")
    board = _board(slug="postid-board")
    topic, post = _topic_and_post(board, recipient, actor, slug="postid-t")
    _notify(recipient, actor, topic, post)

    client = APIClient()
    client.force_authenticate(recipient)
    resp = client.get("/forum/notifications/")

    assert resp.status_code == 200
    assert resp.data["results"][0]["post_id"] == post.pk


@pytest.mark.django_db
def test_notification_actor_carries_trust_level_and_display_name():
    recipient = User.objects.create_user(username="r")
    actor = User.objects.create_user(username="a")
    board = _board("gen-actor")
    topic, post = _topic_and_post(board, recipient, actor)
    _notify(recipient, actor, topic, post)
    # The actor now carries the SAME unified author object as topic/post authors
    # (todo 257 H26), including avatar — so give the actor one and assert it.
    from wagtail.images import get_image_model
    from wagtail.images.tests.utils import get_test_image_file
    from wagtail_forum.collections import get_forum_image_collection

    avatar = get_image_model().objects.create(
        title="ann-avatar",
        file=get_test_image_file(),
        collection=get_forum_image_collection(),
        uploaded_by_user=actor,
    )
    profile = ForumProfile.for_user(actor)
    profile.trust_level = TrustLevel.LEADER  # 4
    profile.display_name = "Ann"
    profile.avatar = avatar
    profile.save(update_fields=["trust_level", "display_name", "avatar"])

    client = APIClient()
    client.force_authenticate(recipient)
    resp = client.get("/forum/notifications/")
    assert resp.status_code == 200
    got = resp.data["results"][0]["actor"]
    assert got["username"] == "a"
    assert got["display_name"] == "Ann"
    assert got["trust_level"] == 4
    assert got["avatar"] == f"http://testserver{avatar.file.url}"


@pytest.mark.django_db
def test_notification_list_actor_profiles_add_no_per_row_queries():
    recipient = User.objects.create_user(username="r2")
    board = _board("gen-nplus1")
    for i in range(5):
        actor = User.objects.create_user(username=f"act{i}")
        topic, post = _topic_and_post(board, recipient, actor, slug=f"t{i}")
        _notify(recipient, actor, topic, post)

    client = APIClient()
    client.force_authenticate(recipient)
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get("/forum/notifications/")
    assert resp.status_code == 200
    assert len(resp.data["results"]) == 5
    # Pinned EXACTLY: the notification fetch + one .public() PageViewRestriction
    # lookup. actor + actor profile + topic + board all select_related, so 5
    # distinct actors add no per-row queries.
    assert len(ctx.captured_queries) == 2
