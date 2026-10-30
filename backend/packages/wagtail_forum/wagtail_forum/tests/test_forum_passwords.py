"""Password-protected forums (todo 680; phpBB's forum password).

A locked forum's row is listed with a lock and nothing that reveals its
topics; its topics are hidden until the member unlocks it with the password
for their session. Wrong passwords count toward a per-member limit (429).
Search, digest and notifications leave a locked forum out. The flat
``/forum/boards/`` list (the Flutter app) leaves it out until the app has an
unlock screen (owner decision 2026-10-30).
"""

from datetime import timedelta
from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from wagtail_forum.digest import build_digest
from wagtail_forum.models import Notification, NotificationVerb, Post, Topic
from wagtail_forum.tests.factories import make_forum

User = get_user_model()
pytestmark = [pytest.mark.django_db, pytest.mark.urls("wagtail_forum.tests.api.urls")]

# An obviously fake test value.
PASSWORD = "fake-test-password-680"  # pragma: allowlist secret
WORD = "monstera"


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def locked():
    forum = make_forum(
        name="Club",
        slug="club",
        password_hash=make_password(PASSWORD),
        topic_template="Members only: our meeting notes",
    )
    author = User.objects.create_user(username="author")
    topic = Topic.objects.create(
        board=forum,
        title=f"Club {WORD}",
        slug="club-topic",
        author=author,
        live=True,
        last_post_at=timezone.now(),
    )
    post = Post.objects.create(
        topic=topic,
        author=author,
        is_opening_post=True,
        live=True,
        body=[{"type": "paragraph", "value": f"<p>{WORD}</p>"}],
    )
    return {"forum": forum, "topic": topic, "post": post, "author": author}


def _member(username="member"):
    client = APIClient()
    user = User.objects.create_user(username=username)
    client.force_login(user)  # a real session: the unlock lives in it
    return client, user


def _unlock(client, password=PASSWORD):
    return client.post(
        "/forum/boards/club/unlock/", {"password": password}, format="json"
    )


def _row(client):
    rows = client.get("/forum/categories/").json()["results"]
    return next(f for c in rows for f in c["forums"] if f["slug"] == "club")


def test_a_locked_forum_hides_its_topics_until_unlocked(locked):
    client, _ = _member()
    topic_url = f"/forum/topics/{locked['topic'].pk}/"

    row = _row(client)
    assert row["is_locked"] is True
    assert row["last_post_at"] is None
    assert row["topic_template"] == ""
    listed = client.get("/forum/boards/club/topics/")
    assert listed.status_code == 403
    assert listed.json()["code"] == "forum_locked"
    assert client.get(topic_url).status_code == 404

    assert _unlock(client).status_code == 200

    assert _row(client)["is_locked"] is False
    assert _row(client)["topic_template"] == "Members only: our meeting notes"
    assert client.get("/forum/boards/club/topics/").status_code == 200
    assert client.get(topic_url).status_code == 200


def test_wrong_passwords_count_toward_the_limit_and_return_429(locked):
    client, _ = _member()

    with override_settings(WAGTAILFORUM_FORUM_UNLOCK_MAX_FAILURES=3):
        statuses = [_unlock(client, "wrong").status_code for _ in range(3)]
        # Past the limit even the right password is refused for the window.
        blocked = _unlock(client)
        other_client, _ = _member("other")
        other = _unlock(other_client)

    assert statuses == [400, 400, 400]
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "throttled"
    assert "Retry-After" in blocked
    assert other.status_code == 200  # the count is per member


def test_the_unlock_lasts_for_the_session_only(locked):
    client, user = _member()
    assert _unlock(client).status_code == 200
    topic_url = f"/forum/topics/{locked['topic'].pk}/"
    assert client.get(topic_url).status_code == 200

    new_session = APIClient()
    new_session.force_login(user)
    signed_out = APIClient()

    assert new_session.get(topic_url).status_code == 404
    assert signed_out.get(topic_url).status_code == 404
    client.logout()
    client.force_login(user)
    assert client.get(topic_url).status_code == 404


def test_guests_cannot_unlock(locked):
    assert _unlock(APIClient()).status_code in (401, 403)


def test_search_digest_and_notifications_exclude_a_locked_forum(locked):
    client, user = _member()
    Notification.objects.create(
        recipient=user,
        actor=locked["author"],
        verb=NotificationVerb.REPLY,
        topic=locked["topic"],
        post=locked["post"],
    )

    searched = client.get(f"/forum/search/?q={WORD}").json()
    notes = client.get("/forum/notifications/").json()["results"]
    digest = build_digest(user, timezone.now() - timedelta(days=7))

    assert searched["topics"] == [] and searched["posts"] == []
    assert notes == []
    assert digest.watched == [] and digest.trending == []

    # Unlocked, search follows the session; the digest and the bell have no
    # session and keep leaving the forum out.
    _unlock(client)
    searched = client.get(f"/forum/search/?q={WORD}").json()
    assert [t["id"] for t in searched["topics"]] == [locked["topic"].pk]
    assert client.get("/forum/notifications/").json()["results"] == []


def test_the_flat_board_list_used_by_the_app_hides_a_locked_forum(locked):
    make_forum(name="Open", slug="open")
    client, _ = _member()

    slugs = [b["slug"] for b in client.get("/forum/boards/").json()["results"]]

    assert slugs == ["open"]


def test_moderators_and_staff_bypass_the_password(locked):
    staff = APIClient()
    staff.force_authenticate(User.objects.create_user(username="s", is_staff=True))

    assert staff.get(f"/forum/topics/{locked['topic'].pk}/").status_code == 200


def test_a_new_password_relocks_every_session_that_unlocked_the_old_one(locked):
    client, _ = _member()
    assert _unlock(client).status_code == 200
    topic_url = f"/forum/topics/{locked['topic'].pk}/"
    assert client.get(topic_url).status_code == 200

    forum = locked["forum"]
    forum.password_hash = make_password(
        "a-rotated-fake-password"
    )  # pragma: allowlist secret
    forum.save(update_fields=["password_hash"])

    assert client.get(topic_url).status_code == 404
    assert _row(client)["is_locked"] is True


def test_a_member_who_unlocked_the_forum_may_quote_and_bookmark_in_it(locked):
    # Round-2 review: the quote check and the Saved list ignored the
    # session's unlock, so a quote inside the forum was refused (400) and a
    # bookmark the member had just saved never appeared.
    from wagtail_forum.models import ForumProfile, TrustLevel
    from wagtail_forum.workflow import ensure_default_workflow

    ensure_default_workflow()
    client, user = _member()
    profile = ForumProfile.for_user(user)
    profile.trust_level = TrustLevel.MEMBER
    profile.save(update_fields=["trust_level"])
    assert _unlock(client).status_code == 200
    topic, quoted = locked["topic"], locked["post"]
    quote = {"type": "post_quote", "value": {"post": quoted.pk, "text": WORD}}

    reply = client.post(
        f"/forum/topics/{topic.pk}/posts/", {"body": [quote]}, format="json"
    )
    assert reply.status_code == 201, reply.data
    posts = client.get(f"/forum/topics/{topic.pk}/posts/").data["results"]
    read = next(
        b["value"] for p in posts for b in p["body"] if b["type"] == "post_quote"
    )
    assert read["available"] is True

    assert client.post(f"/forum/topics/{topic.pk}/bookmark/").status_code in (200, 201)
    saved = client.get("/forum/me/bookmarks/").data["results"]
    assert [t["id"] for t in saved] == [topic.pk]


def test_an_overlong_password_is_refused_before_it_is_hashed(locked):
    from wagtail_forum.models.boards import FORUM_PASSWORD_MAX_LENGTH

    client, _ = _member()
    with mock.patch("wagtail_forum.api.forum_rows.check_password") as check:
        resp = _unlock(client, "x" * (FORUM_PASSWORD_MAX_LENGTH + 1))

    assert resp.status_code == 400
    check.assert_not_called()
