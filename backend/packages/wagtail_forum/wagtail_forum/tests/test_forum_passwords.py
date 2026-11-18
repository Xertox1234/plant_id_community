"""Password-protected forums (todo 680; phpBB's forum password).

A locked forum's row is listed with a lock and nothing that reveals its
topics; its topics are hidden until the member unlocks it with the password
for their session. Wrong passwords count toward a per-member limit (429).
Search, digest and notifications leave a locked forum out. The flat
``/forum/boards/`` list leaves it out while it is locked for the request.
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


def test_a_locked_row_hides_its_rules_icon_and_image_until_unlocked(locked):
    # Owner decision 2026-11-01: a locked row shows its name and description
    # only. Rules, rules URL, icon and image appear once the session unlocks.
    from wagtail.images import get_image_model
    from wagtail.images.tests.utils import get_test_image_file

    forum = locked["forum"]
    forum.rules = "Members: be kind."
    forum.rules_url = "https://example.com/club-rules"
    forum.icon = "🔐"
    forum.image = get_image_model().objects.create(
        title="club", file=get_test_image_file()
    )
    forum.save()
    client, _ = _member()

    row = _row(client)
    assert row["is_locked"] is True
    assert (row["rules"], row["rules_url"], row["icon"]) == ("", "", "")
    assert row["image_url"] is None

    assert _unlock(client).status_code == 200

    row = _row(client)
    assert row["is_locked"] is False
    assert row["rules"] == "Members: be kind."
    assert row["rules_url"] == "https://example.com/club-rules"
    assert row["icon"] == "🔐"
    assert row["image_url"] is not None


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


# --- Unlock token for cookie-less clients (spec 2026-11-17 §7.4) -------------

TOPICS_URL = "/forum/boards/club/topics/"


def _token(client):
    resp = _unlock(client)
    assert resp.status_code == 200
    token = resp.json()["unlock_token"]
    assert isinstance(token, str) and token
    return token


def _no_session(user):
    """A client with no session at all: what the mobile app sends."""
    client = APIClient()
    client.force_authenticate(user)
    return client


def _row_with(client, token):
    rows = client.get("/forum/categories/", HTTP_X_FORUM_UNLOCK=token).json()
    return next(f for c in rows["results"] for f in c["forums"] if f["slug"] == "club")


def test_unlock_returns_a_token_that_opens_the_topic_list_without_a_session(locked):
    client, member = _member()
    token = _token(client)
    fresh = _no_session(member)

    assert fresh.get(TOPICS_URL).status_code == 403
    assert fresh.get(TOPICS_URL, HTTP_X_FORUM_UNLOCK=token).status_code == 200
    topic_url = f"/forum/topics/{locked['topic'].pk}/"
    assert fresh.get(topic_url, HTTP_X_FORUM_UNLOCK=token).status_code == 200


def test_token_of_another_member_is_refused(locked):
    client, _ = _member()
    token = _token(client)
    other = _no_session(User.objects.create_user(username="other"))

    resp = other.get(TOPICS_URL, HTTP_X_FORUM_UNLOCK=token)

    assert resp.status_code == 403
    assert resp.json()["code"] == "forum_locked"


def test_token_for_another_forum_is_refused(locked):
    make_forum(name="Den", slug="den", password_hash=make_password(PASSWORD))
    client, member = _member()
    den_token = client.post(
        "/forum/boards/den/unlock/", {"password": PASSWORD}, format="json"
    ).json()["unlock_token"]
    fresh = _no_session(member)

    assert fresh.get(TOPICS_URL, HTTP_X_FORUM_UNLOCK=den_token).status_code == 403
    assert (
        fresh.get("/forum/boards/den/topics/", HTTP_X_FORUM_UNLOCK=den_token)
    ).status_code == 200


def test_token_dies_when_the_password_changes(locked):
    client, member = _member()
    token = _token(client)
    forum = locked["forum"]
    forum.password_hash = make_password(
        "a-rotated-fake-password"
    )  # pragma: allowlist secret
    forum.save(update_fields=["password_hash"])

    resp = _no_session(member).get(TOPICS_URL, HTTP_X_FORUM_UNLOCK=token)

    assert resp.status_code == 403


def test_token_dies_when_the_password_is_removed_and_set_again(locked):
    client, member = _member()
    token = _token(client)
    forum = locked["forum"]
    forum.password_hash = ""
    forum.save(update_fields=["password_hash"])
    forum.password_hash = make_password(PASSWORD)  # a new salt: a new hash
    forum.save(update_fields=["password_hash"])

    assert (
        _no_session(member).get(TOPICS_URL, HTTP_X_FORUM_UNLOCK=token).status_code
        == 403
    )


def test_expired_token_is_refused(locked):
    import time as real_time

    from wagtail_forum.services.forum_permissions import make_unlock_token

    client, member = _member()
    month_ago = real_time.time() - 31 * 24 * 60 * 60
    with mock.patch("django.core.signing.time.time", return_value=month_ago):
        old = _token(client)  # the endpoint's own token, signed 31 days ago
    fresh = _no_session(member)

    assert fresh.get(TOPICS_URL, HTTP_X_FORUM_UNLOCK=old).status_code == 403
    new = make_unlock_token(member, locked["forum"])
    assert fresh.get(TOPICS_URL, HTTP_X_FORUM_UNLOCK=new).status_code == 200
    with override_settings(WAGTAILFORUM_FORUM_UNLOCK_TOKEN_MAX_AGE_SECONDS=60):
        assert fresh.get(TOPICS_URL, HTTP_X_FORUM_UNLOCK=new).status_code == 200
    with override_settings(
        WAGTAILFORUM_FORUM_UNLOCK_TOKEN_MAX_AGE_SECONDS=32 * 24 * 60 * 60
    ):
        assert fresh.get(TOPICS_URL, HTTP_X_FORUM_UNLOCK=old).status_code == 200


def test_anonymous_request_with_a_token_stays_locked_and_cacheable(locked):
    client, _ = _member()
    token = _token(client)
    guest = APIClient()

    assert guest.get(TOPICS_URL, HTTP_X_FORUM_UNLOCK=token).status_code == 403
    resp = guest.get("/forum/categories/", HTTP_X_FORUM_UNLOCK=token)
    row = next(
        f for c in resp.json()["results"] for f in c["forums"] if f["slug"] == "club"
    )
    assert row["is_locked"] is True
    assert resp["Cache-Control"].startswith("public")
    assert "x-forum-unlock" not in resp.get("Vary", "").lower()


def test_garbage_and_too_many_tokens_are_ignored(locked):
    client, member = _member()
    token = _token(client)
    fresh = _no_session(member)

    for junk in ("garbage", ",,,", "a:b:c", "éé", "x" * 5000, " , "):
        assert fresh.get(TOPICS_URL, HTTP_X_FORUM_UNLOCK=junk).status_code == 403
    # A well-signed value that is not our payload shape.
    from django.core import signing

    for payload in ([1, 2], {"u": member.pk}, {"u": str(member.pk), "f": 1, "p": 1}):
        odd = signing.dumps(payload, salt="wagtail_forum.forum_unlock_token")
        assert fresh.get(TOPICS_URL, HTTP_X_FORUM_UNLOCK=odd).status_code == 403
    # A token signed with another salt (a session-style value) is refused.
    forged = signing.dumps(
        {"u": member.pk, "f": locked["forum"].pk, "p": "x"}, salt="other"
    )
    assert fresh.get(TOPICS_URL, HTTP_X_FORUM_UNLOCK=forged).status_code == 403
    assert (
        fresh.get(TOPICS_URL, HTTP_X_FORUM_UNLOCK=f" junk , {token} ").status_code
        == 200
    )


def test_only_the_first_twenty_tokens_are_read(locked):
    client, member = _member()
    token = _token(client)
    fresh = _no_session(member)

    twenty_first = ",".join(["junk"] * 20 + [token])
    assert fresh.get(TOPICS_URL, HTTP_X_FORUM_UNLOCK=twenty_first).status_code == 403
    twentieth = ",".join(["junk"] * 19 + [token, "junk"])
    assert fresh.get(TOPICS_URL, HTTP_X_FORUM_UNLOCK=twentieth).status_code == 200


def test_a_client_with_no_session_unlocks_and_gets_a_token(locked):
    # The mobile app's own flow: no cookie session before the unlock, and
    # the token used later from another client that carries no cookie.
    _, member = _member()
    app = _no_session(member)

    resp = app.post(TOPICS_URL.replace("topics/", "unlock/"), {"password": PASSWORD})
    token = resp.json()["unlock_token"]
    later = _no_session(member)

    assert resp.status_code == 200
    assert isinstance(token, str) and token
    assert later.get(TOPICS_URL).status_code == 403
    assert later.get(TOPICS_URL, HTTP_X_FORUM_UNLOCK=token).status_code == 200


def test_resolving_tokens_costs_one_query_whatever_their_number(locked):
    from django.db import connection
    from django.test import RequestFactory
    from django.test.utils import CaptureQueriesContext
    from wagtail_forum.services.forum_permissions import (
        make_unlock_token,
        unlocked_forum_ids,
    )

    member = User.objects.create_user(username="counted")
    forums = [locked["forum"]] + [
        make_forum(name=f"F{i}", slug=f"f{i}", password_hash=make_password(PASSWORD))
        for i in range(5)
    ]
    tokens = [make_unlock_token(member, forum) for forum in forums]

    def resolve(header):
        request = RequestFactory().get("/", HTTP_X_FORUM_UNLOCK=header)
        request.user = member
        with CaptureQueriesContext(connection) as ctx:
            ids = unlocked_forum_ids(request)
        return sorted(ids), len(ctx.captured_queries)

    one_ids, one_queries = resolve(tokens[0])
    all_ids, all_queries = resolve(",".join(tokens))

    assert one_ids == [forums[0].pk]
    assert all_ids == sorted(f.pk for f in forums)
    assert one_queries == all_queries == 1


def test_a_request_without_headers_or_session_does_not_crash(locked):
    from types import SimpleNamespace

    from wagtail_forum.services.forum_permissions import unlocked_forum_ids

    member = User.objects.create_user(username="bare")

    assert unlocked_forum_ids(SimpleNamespace(user=member)) == []


def test_member_can_create_a_topic_and_reply_with_a_token(locked):
    from wagtail_forum.models import ForumProfile, TrustLevel
    from wagtail_forum.workflow import ensure_default_workflow

    ensure_default_workflow()
    client, member = _member()
    profile = ForumProfile.for_user(member)
    profile.trust_level = TrustLevel.MEMBER
    profile.save(update_fields=["trust_level"])
    token = _token(client)
    fresh = _no_session(member)
    body = [{"type": "paragraph", "value": "<p>Hello there.</p>"}]

    created = fresh.post(
        TOPICS_URL,
        {"title": "A new topic", "slug": "new-topic", "body": body},
        format="json",
        HTTP_X_FORUM_UNLOCK=token,
    )
    assert created.status_code == 201, created.data
    reply = fresh.post(
        f"/forum/topics/{locked['topic'].pk}/posts/",
        {"body": body},
        format="json",
        HTTP_X_FORUM_UNLOCK=token,
    )
    assert reply.status_code == 201, reply.data
    # Without the token the same calls are refused.
    assert (
        fresh.post(
            f"/forum/topics/{locked['topic'].pk}/posts/", {"body": body}, format="json"
        ).status_code
        == 404
    )


@pytest.mark.parametrize("path", ["", "posts/", "latest-replies/"])
def test_a_topic_and_its_posts_open_with_a_token_and_no_session(locked, path):
    client, member = _member()
    token = _token(client)
    fresh = _no_session(member)
    url = f"/forum/topics/{locked['topic'].pk}/{path}"

    assert fresh.get(url).status_code == 404
    assert fresh.get(url, HTTP_X_FORUM_UNLOCK=token).status_code == 200


def test_categories_row_is_unlocked_with_a_token(locked):
    client, member = _member()
    token = _token(client)
    fresh = _no_session(member)

    assert _row_with(fresh, "")["is_locked"] is True
    row = _row_with(fresh, token)
    assert row["is_locked"] is False
    assert row["last_post_at"] is not None


def test_nothing_to_unlock_returns_null_token(locked):
    make_forum(name="Open", slug="open")
    client, _ = _member()

    open_resp = client.post(
        "/forum/boards/open/unlock/", {"password": "x"}, format="json"
    )
    assert open_resp.status_code == 200
    assert open_resp.json() == {"unlocked": True, "unlock_token": None}
    _token(client)
    again = _unlock(client)  # already unlocked in this session
    assert again.json() == {"unlocked": True, "unlock_token": None}


def test_session_unlock_still_works_without_a_token(locked):
    client, _ = _member()
    _token(client)

    assert client.get(TOPICS_URL).status_code == 200
    assert _row(client)["is_locked"] is False
