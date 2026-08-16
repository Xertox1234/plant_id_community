"""Community experts rail: GET users/experts/ (Task 6, Canopy PR)."""

import re

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext, override_settings
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex, ForumProfile

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


def _board(board_slug="general", board_title="General"):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    return index.add_child(instance=ForumBoard(title=board_title, slug=board_slug))


@pytest.mark.django_db
def test_experts_empty_forum_returns_empty_results():
    """No users at all -> the flat envelope with an empty list."""
    _board()  # create forum structure
    resp = APIClient().get("/forum/users/experts/")
    assert resp.status_code == 200
    assert resp.data == {"results": []}


@pytest.mark.django_db
def test_experts_filters_by_trust_level_and_orders_by_trust_then_post_count():
    """Only users at trust_level >= EXPERTS_MIN_TRUST_LEVEL; ordered by
    -trust_level then -post_count, each row carries title."""
    _board()  # create forum structure

    # Create profiles with different trust levels and post counts
    # trust_level=4, post_count=10
    user_4_10 = User.objects.create_user(username="user_4_10")
    profile_4_10 = ForumProfile.for_user(user_4_10)
    profile_4_10.trust_level = 4
    profile_4_10.post_count = 10
    profile_4_10.save()

    # trust_level=4, post_count=5
    user_4_5 = User.objects.create_user(username="user_4_5")
    profile_4_5 = ForumProfile.for_user(user_4_5)
    profile_4_5.trust_level = 4
    profile_4_5.post_count = 5
    profile_4_5.save()

    # trust_level=3, post_count=20 (should be included, but after trust_level=4)
    user_3_20 = User.objects.create_user(username="user_3_20")
    profile_3_20 = ForumProfile.for_user(user_3_20)
    profile_3_20.trust_level = 3
    profile_3_20.post_count = 20
    profile_3_20.save()

    # trust_level=2, post_count=100 (should be excluded)
    user_2_100 = User.objects.create_user(username="user_2_100")
    profile_2_100 = ForumProfile.for_user(user_2_100)
    profile_2_100.trust_level = 2
    profile_2_100.post_count = 100
    profile_2_100.save()

    # trust_level=0 (should be excluded)
    user_0 = User.objects.create_user(username="user_0")
    profile_0 = ForumProfile.for_user(user_0)
    profile_0.trust_level = 0
    profile_0.save()

    resp = APIClient().get("/forum/users/experts/")
    assert resp.status_code == 200
    results = resp.data["results"]

    # Should return 3 users (trust_level >= 3) in order: 4/10, 4/5, 3/20
    assert len(results) == 3
    assert [r["username"] for r in results] == ["user_4_10", "user_4_5", "user_3_20"]

    # Verify each row has title
    for row in results:
        assert "title" in row
        assert isinstance(row["title"], str)


@pytest.mark.django_db
def test_experts_ties_break_by_id_descending():
    """Two profiles sharing the same trust_level and post_count -> higher
    profile id wins.

    Mirrors RecentTopicsView's `-last_post_at, -id` tie-break convention
    (review finding #2) so ties resolve deterministically instead of
    depending on incidental DB/plan-dependent scan order.

    Asserted directly on the issued SQL's ORDER BY clause, not on the HTTP
    response row order: empirically, Postgres's plan for this specific
    query (a JOIN against auth_user via select_related) already returns
    ties in id-descending order on this dataset size EVEN WITHOUT an
    explicit `-id` tie-break, in both this repo's pytest-django harness and
    a standalone reproduction — so a response-order assertion alone passes
    whether or not the tie-break is in the code and would not have caught
    this review finding. The generated SQL's ORDER BY clause is what the
    code review finding is actually about, so that's what's pinned here.
    """
    _board()  # create forum structure

    user_a = User.objects.create_user(username="user_a")
    profile_a = ForumProfile.for_user(user_a)
    profile_a.trust_level = 3
    profile_a.post_count = 10
    profile_a.save()

    user_b = User.objects.create_user(username="user_b")
    profile_b = ForumProfile.for_user(user_b)
    profile_b.trust_level = 3
    profile_b.post_count = 10
    profile_b.save()

    assert profile_b.pk > profile_a.pk  # sanity: creation order held

    with CaptureQueriesContext(connection) as ctx:
        resp = APIClient().get("/forum/users/experts/")
    assert resp.status_code == 200
    assert [r["username"] for r in resp.data["results"]] == ["user_b", "user_a"]

    profile_queries = [
        q["sql"]
        for q in ctx.captured_queries
        if "wagtail_forum_forumprofile" in q["sql"]
    ]
    assert len(profile_queries) == 1
    assert re.search(
        r'ORDER BY .*"wagtail_forum_forumprofile"\."id" DESC', profile_queries[0]
    ), profile_queries[0]


@pytest.mark.django_db
def test_experts_excludes_inactive_users():
    """Inactive users (is_active=False) are excluded from results."""
    _board()  # create forum structure

    # Active user, trust_level=3
    user_active = User.objects.create_user(username="active", is_active=True)
    profile_active = ForumProfile.for_user(user_active)
    profile_active.trust_level = 3
    profile_active.save()

    # Inactive user, trust_level=3
    user_inactive = User.objects.create_user(username="inactive", is_active=False)
    profile_inactive = ForumProfile.for_user(user_inactive)
    profile_inactive.trust_level = 3
    profile_inactive.save()

    resp = APIClient().get("/forum/users/experts/")
    assert resp.status_code == 200
    results = resp.data["results"]

    assert len(results) == 1
    assert results[0]["username"] == "active"


@pytest.mark.django_db
@override_settings(WAGTAILFORUM_EXPERTS_LIMIT=2)
def test_experts_limit_is_respected():
    """The EXPERTS_LIMIT cap is enforced; a fifth qualifying profile is cut."""
    _board()  # create forum structure

    # Create 5 active users with trust_level=3
    for i in range(5):
        user = User.objects.create_user(username=f"user_{i}")
        profile = ForumProfile.for_user(user)
        profile.trust_level = 3
        profile.post_count = 100 - i  # Descending post counts for deterministic order
        profile.save()

    resp = APIClient().get("/forum/users/experts/")
    assert resp.status_code == 200
    results = resp.data["results"]

    # Only 2 results due to the overridden limit
    assert len(results) == 2


@pytest.mark.django_db
def test_experts_route_does_not_fall_into_username_capture():
    """GET users/experts/ resolves to ExpertsView, not PublicProfileView.

    Proves that users/experts/ is ordered before users/<str:username>/ so
    "experts" is not captured as a username (which would 404 or return
    a non-existent profile). This is the route-sanity test that verifies
    the ordering comment's load-bearing claim."""
    _board()  # create forum structure

    # Create one expert user
    user = User.objects.create_user(username="expert_user")
    profile = ForumProfile.for_user(user)
    profile.trust_level = 3
    profile.save()

    # GET users/experts/ should return a 200 with a "results" key (ExpertsView)
    resp = APIClient().get("/forum/users/experts/")
    assert resp.status_code == 200
    assert "results" in resp.data
    assert isinstance(resp.data["results"], list)
