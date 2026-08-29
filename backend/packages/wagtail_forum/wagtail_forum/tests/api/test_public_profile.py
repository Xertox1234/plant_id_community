import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.models import (
    ForumBoard,
    ForumIndex,
    ForumProfile,
    Post,
    Topic,
    TrustLevel,
)

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


def _board(slug="general"):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    return index.add_child(instance=ForumBoard(title="General", slug=slug))


@pytest.mark.django_db
def test_public_profile_returns_identity_and_recent_activity():
    board = _board()
    ada = User.objects.create_user(username="ada")
    profile = ForumProfile.for_user(ada)
    profile.display_name = "Ada L."
    profile.bio = "I like ferns."
    profile.signature = "— Ada"
    profile.trust_level = TrustLevel.REGULAR  # 3
    profile.post_count = 42
    profile.save()

    topic = Topic.objects.create(
        board=board, title="Fern care", slug="fern-care", author=ada, live=True
    )
    # An opening post (excluded from recent_posts) + a reply (included).
    Post.objects.create(topic=topic, author=ada, is_opening_post=True, live=True)
    reply = Post.objects.create(
        topic=topic,
        author=ada,
        is_opening_post=False,
        live=True,
        body=[{"type": "paragraph", "value": "<p>water weekly</p>"}],
    )

    resp = APIClient().get("/forum/users/ada/")
    assert resp.status_code == 200
    assert resp.data["username"] == "ada"
    assert resp.data["display_name"] == "Ada L."
    assert resp.data["bio"] == "I like ferns."
    assert resp.data["signature"] == "— Ada"
    assert resp.data["trust_level"] == 3
    assert resp.data["post_count"] == 42  # lifetime stat, not a sum of recent
    assert resp.data["avatar"] is None
    assert resp.data["joined_at"] is not None

    assert [t["slug"] for t in resp.data["recent_topics"]] == ["fern-care"]
    assert resp.data["recent_topics"][0]["board_slug"] == "general"
    # recent_posts excludes the opening post (that's covered by recent_topics).
    assert [p["id"] for p in resp.data["recent_posts"]] == [reply.id]
    assert resp.data["recent_posts"][0]["topic_slug"] == "fern-care"


@pytest.mark.django_db
def test_public_profile_404_for_missing_user():
    assert APIClient().get("/forum/users/ghost/").status_code == 404


@pytest.mark.django_db
def test_public_profile_404_for_inactive_user():
    User.objects.create_user(username="banned", is_active=False)
    assert APIClient().get("/forum/users/banned/").status_code == 404


@pytest.mark.django_db
def test_public_profile_profileless_user_returns_defaults_not_404():
    # A real user who never got a ForumProfile row → defaults, NOT a 404, and the
    # endpoint must NOT create a profile for them (read-only).
    User.objects.create_user(username="lurker")
    resp = APIClient().get("/forum/users/lurker/")
    assert resp.status_code == 200
    assert resp.data["username"] == "lurker"
    assert resp.data["display_name"] == "lurker"  # username fallback
    assert resp.data["trust_level"] is None
    assert resp.data["post_count"] == 0
    assert resp.data["bio"] == ""
    assert resp.data["recent_topics"] == []
    assert not ForumProfile.objects.filter(user__username="lurker").exists()


@pytest.mark.django_db
def test_public_profile_never_leaks_fcm_token_or_flags_received():
    ada = User.objects.create_user(username="ada")
    profile = ForumProfile.for_user(ada)
    profile.fcm_token = "device-secret"
    profile.flags_received = 3
    profile.save()

    resp = APIClient().get("/forum/users/ada/")
    assert resp.status_code == 200
    assert "fcm_token" not in resp.data  # credential
    assert "flags_received" not in resp.data  # moderation-proximity signal (L12)


@pytest.mark.django_db
def test_public_profile_hides_non_live_activity():
    board = _board()
    ada = User.objects.create_user(username="ada")
    live_topic = Topic.objects.create(
        board=board, title="Live", slug="live", author=ada, live=True
    )
    Topic.objects.create(
        board=board, title="Draft", slug="draft", author=ada, live=False
    )

    resp = APIClient().get("/forum/users/ada/")
    assert resp.status_code == 200
    assert [t["slug"] for t in resp.data["recent_topics"]] == ["live"]
    assert live_topic.slug == "live"


@pytest.mark.django_db
def test_public_profile_hides_restricted_board_activity():
    # The other half of recent-activity visibility (besides live=False): content
    # on a board behind a Wagtail PageViewRestriction must not surface, since the
    # endpoint is public. Guards the `board__in=_visible_boards()` filter.
    from wagtail.models import PageViewRestriction

    board = _board()
    PageViewRestriction.objects.create(page=board, restriction_type="login")
    ada = User.objects.create_user(username="ada")
    topic = Topic.objects.create(
        board=board, title="Secret", slug="secret", author=ada, live=True
    )
    Post.objects.create(
        topic=topic,
        author=ada,
        is_opening_post=False,
        live=True,
        body=[{"type": "paragraph", "value": "<p>hi</p>"}],
    )

    resp = APIClient().get("/forum/users/ada/")
    assert resp.status_code == 200
    assert resp.data["recent_topics"] == []  # restricted board → invisible
    assert resp.data["recent_posts"] == []


@pytest.mark.django_db
def test_public_profile_search_route_is_not_shadowed():
    # The literal users/search/ must still resolve to the mention search, not to
    # PublicProfileView with username="search".
    me = User.objects.create_user(username="me")
    User.objects.create_user(username="searcher")
    client = APIClient()
    client.force_authenticate(me)
    resp = client.get("/forum/users/search/?q=sea")
    assert resp.status_code == 200
    assert isinstance(resp.data, list)  # search returns a list, not a profile object


@pytest.mark.django_db
def test_public_profile_query_count_is_bounded():
    board = _board()
    ada = User.objects.create_user(username="ada")
    ForumProfile.for_user(ada)
    # 15 topics + 15 replies — more than RECENT_LIMIT (10), to prove the count is
    # bounded by the LIMIT and flat regardless of activity volume (no N+1).
    for i in range(15):
        t = Topic.objects.create(
            board=board, title=f"T{i}", slug=f"t{i}", author=ada, live=True
        )
        Post.objects.create(topic=t, author=ada, is_opening_post=True, live=True)
        Post.objects.create(
            topic=t,
            author=ada,
            is_opening_post=False,
            live=True,
            body=[{"type": "paragraph", "value": "<p>hi</p>"}],
        )

    with CaptureQueriesContext(connection) as ctx:
        resp = APIClient().get("/forum/users/ada/")
    assert resp.status_code == 200
    assert len(resp.data["recent_topics"]) == 10  # bounded by RECENT_LIMIT
    assert len(resp.data["recent_posts"]) == 10
    # Pinned EXACTLY (docs/rules/testing.md): user+profile+avatar (1 joined),
    # the .public() view-restriction lookup for _visible_boards (1, once),
    # recent_topics (1, board__in subquery inline), recent_posts (1, topic__board
    # subquery inline) = 4. FLAT under N activity (15 topics + 30 posts here still
    # 4 — bounded by RECENT_LIMIT, no N+1); explain any change here.
    # Unaffected by todo 284/M9: this request is anonymous, and is_blocked's
    # `request.user.is_authenticated and ...` short-circuits before any
    # query; can_block is pure Python (no DB hit).
    assert len(ctx.captured_queries) == 4


@pytest.mark.django_db
def test_public_profile_flags_blocked_but_still_viewable():
    """The profile stays viewable (so the Block/Unblock control has
    somewhere to live) but activity is empty when blocked (todo 284/M9)."""
    from wagtail_forum.models import UserBlock

    board = _board()
    blocked = User.objects.create_user(username="blocked-profile")
    viewer = User.objects.create_user(username="profile-viewer")
    UserBlock.block(viewer, blocked)
    topic = Topic.objects.create(
        board=board, title="T", slug="blocked-profile-t", author=blocked, live=True
    )
    Post.objects.create(topic=topic, author=blocked, is_opening_post=True, live=True)

    client = APIClient()
    client.force_authenticate(viewer)
    resp = client.get(f"/forum/users/{blocked.username}/")

    assert resp.status_code == 200
    assert resp.data["is_blocked"] is True
    assert resp.data["recent_topics"] == []
    assert resp.data["recent_posts"] == []


@pytest.mark.django_db
def test_public_profile_can_block_true_when_not_blocked():
    board = _board()
    target = User.objects.create_user(username="unblocked-profile")
    viewer = User.objects.create_user(username="profile-viewer2")
    Topic.objects.create(
        board=board, title="T", slug="unblocked-profile-t", author=target, live=True
    )

    client = APIClient()
    client.force_authenticate(viewer)
    resp = client.get(f"/forum/users/{target.username}/")

    assert resp.status_code == 200
    assert resp.data["is_blocked"] is False
    assert resp.data["can_block"] is True
    assert len(resp.data["recent_topics"]) == 1


@pytest.mark.django_db
def test_public_profile_can_block_false_for_own_profile():
    board = _board()
    user = User.objects.create_user(username="own-profile")
    Topic.objects.create(board=board, title="T", slug="own-t", author=user, live=True)

    client = APIClient()
    client.force_authenticate(user)
    resp = client.get(f"/forum/users/{user.username}/")

    assert resp.status_code == 200
    assert resp.data["can_block"] is False
    assert resp.data["is_blocked"] is False
