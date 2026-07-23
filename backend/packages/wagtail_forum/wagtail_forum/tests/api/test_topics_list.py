import datetime

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex, ForumProfile, Topic, TopicRead

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


def _board():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    return index.add_child(instance=ForumBoard(title="General", slug="general"))


@pytest.mark.django_db
def test_topics_list_is_cursor_paginated_with_bounded_queries():
    board = _board()
    author = User.objects.create_user(username="ada")
    # Live topics with DISTINCT last_post_at so the activity-ordered cursor is
    # deterministic. t0 is the most recent.
    base = timezone.now()
    for i in range(25):
        Topic.objects.create(
            board=board,
            title=f"T{i}",
            slug=f"t{i}",
            author=author,
            live=True,
            last_post_at=base - datetime.timedelta(minutes=i),
        )

    client = APIClient()
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get(f"/forum/boards/{board.slug}/topics/")

    assert resp.status_code == 200
    assert len(resp.data["results"]) == 20  # page_size
    assert resp.data["next"] is not None  # cursor link
    assert resp.data["results"][0]["slug"] == "t0"  # most-recent activity first
    # Exactly 3: board lookup (live+public), topics page (select_related pulls
    # author/last_post_author in the same query), cursor has-next probe.
    # Pinned EXACTLY (docs/rules/testing.md) — an N+1 hiding under a <= ceiling
    # passes silently; if this changes, explain the new number here.
    assert len(ctx.captured_queries) == 3


@pytest.mark.django_db
def test_pinned_topics_float_above_activity_ordering():
    # Audit 2026-07-11 H5: the cursor ordering ignored is_pinned, so a
    # moderator-pinned topic sank as normal activity accrued.
    board = _board()
    author = User.objects.create_user(username="ada")
    base = timezone.now()
    Topic.objects.create(
        board=board,
        title="Board rules",
        slug="rules",
        author=author,
        live=True,
        is_pinned=True,
        last_post_at=base - datetime.timedelta(days=30),  # stale activity
    )
    Topic.objects.create(
        board=board,
        title="Fresh question",
        slug="fresh",
        author=author,
        live=True,
        last_post_at=base,
    )

    resp = APIClient().get(f"/forum/boards/{board.slug}/topics/")

    assert resp.status_code == 200
    assert [t["slug"] for t in resp.data["results"]] == ["rules", "fresh"]


@pytest.mark.django_db
def test_list_payload_includes_locked_flag():
    # Audit 2026-07-11 L3: the write guard is `is_closed OR locked`, but the
    # list serializer omitted `locked` — a Wagtail-locked-but-open topic showed
    # no lock badge until opened.
    board = _board()
    author = User.objects.create_user(username="ada")
    Topic.objects.create(
        board=board,
        title="Locked topic",
        slug="locked-topic",
        author=author,
        live=True,
        locked=True,
        last_post_at=timezone.now(),
    )

    resp = APIClient().get(f"/forum/boards/{board.slug}/topics/")

    assert resp.status_code == 200
    item = resp.data["results"][0]
    assert item["locked"] is True
    assert item["is_closed"] is False  # distinct flags, both serialized


@pytest.mark.django_db
def test_ordering_query_param_is_inert():
    # Phase 6 review (2026-07-11 audit): the views inherited the host's global
    # OrderingFilter, so a client ?ordering= replaced the cursor tuple entirely
    # (un-pinning pinned topics) and ?ordering=author__get_username — a dotted
    # serializer source, not a column — raised FieldError → an unauthenticated
    # 500 (both reproduced). filter_backends=[] makes list order a fixed
    # package contract regardless of host DEFAULT_FILTER_BACKENDS.
    board = _board()
    author = User.objects.create_user(username="ada")
    base = timezone.now()
    Topic.objects.create(
        board=board,
        title="AAA rules",  # alphabetically FIRST so -title would reorder
        slug="rules",
        author=author,
        live=True,
        is_pinned=True,
        last_post_at=base - datetime.timedelta(days=30),
    )
    Topic.objects.create(
        board=board,
        title="ZZZ fresh",
        slug="fresh",
        author=author,
        live=True,
        last_post_at=base,
    )

    client = APIClient()
    resp = client.get(f"/forum/boards/{board.slug}/topics/", {"ordering": "-title"})
    assert resp.status_code == 200
    assert [t["slug"] for t in resp.data["results"]] == ["rules", "fresh"]

    resp = client.get(
        f"/forum/boards/{board.slug}/topics/", {"ordering": "author__get_username"}
    )
    assert resp.status_code == 200  # was a FieldError 500
    assert [t["slug"] for t in resp.data["results"]] == ["rules", "fresh"]


@pytest.mark.django_db
def test_sort_param_reorders_by_view_count():
    # todo 256 H8: the web ThreadListPage <select> drives ?sort= through the
    # cursor paginator's get_ordering. Unlike ?ordering= (inert, test above), a
    # whitelisted ?sort= value actually reorders the list.
    board = _board()
    author = User.objects.create_user(username="ada")
    base = timezone.now()
    Topic.objects.create(
        board=board,
        title="low views",
        slug="low",
        author=author,
        live=True,
        view_count=1,
        last_post_at=base,  # newer activity...
    )
    Topic.objects.create(
        board=board,
        title="high views",
        slug="high",
        author=author,
        live=True,
        view_count=99,
        last_post_at=base - datetime.timedelta(days=1),  # ...but older
    )

    resp = APIClient().get(f"/forum/boards/{board.slug}/topics/?sort=-view_count")

    assert resp.status_code == 200
    # -view_count wins over the default -last_post_at (low has newer activity but
    # fewer views), proving ?sort= reorders the query rather than being ignored.
    assert [t["slug"] for t in resp.data["results"]] == ["high", "low"]


@pytest.mark.django_db
def test_unknown_sort_param_falls_back_to_default_ordering():
    # A bogus ?sort= must not 500 — it falls back to the default pinned+activity
    # ordering (mirrors the ?ordering= inert contract).
    board = _board()
    author = User.objects.create_user(username="ada")
    base = timezone.now()
    Topic.objects.create(
        board=board,
        title="Pinned",
        slug="pinned",
        author=author,
        live=True,
        is_pinned=True,
        last_post_at=base - datetime.timedelta(days=10),
    )
    Topic.objects.create(
        board=board,
        title="Fresh",
        slug="fresh",
        author=author,
        live=True,
        last_post_at=base,
    )

    resp = APIClient().get(f"/forum/boards/{board.slug}/topics/?sort=bogus")

    assert resp.status_code == 200
    assert [t["slug"] for t in resp.data["results"]] == ["pinned", "fresh"]


@pytest.mark.django_db
def test_sort_param_survives_across_cursor_pages():
    # The riskiest path: ?sort= must ride along in the next/previous cursor links
    # (DRF bakes the full request URL into base_url), or page 2 silently reverts
    # to the default ordering and dupes/skips topics across the page boundary.
    # Seed >1 page of topics with DISTINCT view_counts, follow every cursor, and
    # assert the whole traversal stays view-count-ordered with no dupes/omissions.
    board = _board()
    author = User.objects.create_user(username="ada")
    base = timezone.now()
    for i in range(25):
        Topic.objects.create(
            board=board,
            title=f"T{i}",
            slug=f"t{i}",
            author=author,
            live=True,
            view_count=i,  # distinct, ascending
            last_post_at=base - datetime.timedelta(minutes=i),
        )

    client = APIClient()
    resp = client.get(f"/forum/boards/{board.slug}/topics/?sort=-view_count")
    assert resp.status_code == 200
    view_counts = [t["view_count"] for t in resp.data["results"]]
    slugs = [t["slug"] for t in resp.data["results"]]

    # Follow the absolute cursor URL verbatim (docs/rules/api.md).
    while resp.data["next"]:
        resp = client.get(resp.data["next"])
        assert resp.status_code == 200
        view_counts.extend(t["view_count"] for t in resp.data["results"])
        slugs.extend(t["slug"] for t in resp.data["results"])

    # All 25 topics, each exactly once, in strictly-descending view_count order —
    # proving the sort survived every cursor hop, not just page 1.
    assert len(slugs) == 25
    assert len(set(slugs)) == 25
    assert view_counts == sorted(view_counts, reverse=True)


@pytest.mark.django_db
def test_pinned_ordering_is_cursor_stable_across_pages():
    # The pinned-first ordering must not break cursor traversal: every topic
    # appears exactly once across pages, pinned ones all on page 1's head.
    board = _board()
    author = User.objects.create_user(username="ada")
    base = timezone.now()
    Topic.objects.create(
        board=board,
        title="Pinned old",
        slug="pinned-old",
        author=author,
        live=True,
        is_pinned=True,
        last_post_at=base - datetime.timedelta(days=30),
    )
    for i in range(25):
        Topic.objects.create(
            board=board,
            title=f"T{i}",
            slug=f"t{i}",
            author=author,
            live=True,
            last_post_at=base - datetime.timedelta(minutes=i),
        )

    client = APIClient()
    resp = client.get(f"/forum/boards/{board.slug}/topics/")
    assert resp.status_code == 200
    slugs = [t["slug"] for t in resp.data["results"]]
    assert slugs[0] == "pinned-old"  # pinned heads page 1 despite stale activity

    # Follow the absolute cursor URL verbatim (docs/rules/api.md).
    while resp.data["next"]:
        resp = client.get(resp.data["next"])
        assert resp.status_code == 200
        slugs.extend(t["slug"] for t in resp.data["results"])

    assert len(slugs) == 26
    assert len(set(slugs)) == 26  # no duplicates, no omissions across pages


# ---- is_unread (todo 253 slice 5, H10) -------------------------------------


@pytest.mark.django_db
def test_topics_list_authenticated_query_count_is_still_pinned_at_3():
    """The is_unread annotation (_annotate_topic_unread) adds two correlated
    Subquery lookups, but they fold into the single topics-page SELECT as
    scalar subquery expressions — zero added Python-level round-trips. Same
    pin as the anonymous case above, not a new number."""
    board = _board()
    author = User.objects.create_user(username="ada-auth")
    viewer = User.objects.create_user(username="viewer-auth")
    for i in range(25):
        Topic.objects.create(
            board=board,
            title=f"T{i}",
            slug=f"auth-t{i}",
            author=author,
            live=True,
            last_post_at=timezone.now() - datetime.timedelta(minutes=i),
        )

    client = APIClient()
    client.force_authenticate(viewer)
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get(f"/forum/boards/{board.slug}/topics/")

    assert resp.status_code == 200
    # Pinned EXACTLY (docs/rules/testing.md) — same 3 as the anonymous pin;
    # if this changes, explain the new number here.
    assert len(ctx.captured_queries) == 3


@pytest.mark.django_db
def test_is_unread_false_for_anonymous_request():
    board = _board()
    Topic.objects.create(
        board=board,
        title="New",
        slug="anon-new",
        live=True,
        last_post_at=timezone.now(),
    )

    resp = APIClient().get(f"/forum/boards/{board.slug}/topics/")

    assert resp.data["results"][0]["is_unread"] is False


@pytest.mark.django_db
def test_is_unread_false_for_topic_older_than_watermark():
    board = _board()
    user = User.objects.create_user(username="caught-up")
    profile = ForumProfile.for_user(user)
    profile.read_watermark_at = timezone.now() - datetime.timedelta(days=1)
    profile.save(update_fields=["read_watermark_at"])
    Topic.objects.create(
        board=board,
        title="Old",
        slug="old-topic",
        live=True,
        last_post_at=timezone.now() - datetime.timedelta(days=30),
    )

    client = APIClient()
    client.force_authenticate(user)
    resp = client.get(f"/forum/boards/{board.slug}/topics/")

    assert resp.data["results"][0]["is_unread"] is False


@pytest.mark.django_db
def test_is_unread_true_for_never_read_topic_newer_than_watermark():
    board = _board()
    user = User.objects.create_user(username="behind")
    profile = ForumProfile.for_user(user)
    profile.read_watermark_at = timezone.now() - datetime.timedelta(days=1)
    profile.save(update_fields=["read_watermark_at"])
    Topic.objects.create(
        board=board,
        title="Fresh",
        slug="fresh-topic",
        live=True,
        last_post_at=timezone.now(),
    )

    client = APIClient()
    client.force_authenticate(user)
    resp = client.get(f"/forum/boards/{board.slug}/topics/")

    assert resp.data["results"][0]["is_unread"] is True


@pytest.mark.django_db
def test_is_unread_false_after_read_with_no_new_reply():
    board = _board()
    user = User.objects.create_user(username="reader1")
    topic = Topic.objects.create(
        board=board,
        title="Read",
        slug="read-topic",
        live=True,
        last_post_at=timezone.now() - datetime.timedelta(hours=2),
    )
    TopicRead.mark_read(
        user, topic.id, when=timezone.now() - datetime.timedelta(hours=1)
    )

    client = APIClient()
    client.force_authenticate(user)
    resp = client.get(f"/forum/boards/{board.slug}/topics/")

    assert resp.data["results"][0]["is_unread"] is False


@pytest.mark.django_db
def test_is_unread_true_after_new_reply_since_last_read():
    board = _board()
    user = User.objects.create_user(username="reader2")
    topic = Topic.objects.create(
        board=board,
        title="Replied",
        slug="replied-topic",
        live=True,
        last_post_at=timezone.now() - datetime.timedelta(hours=2),
    )
    TopicRead.mark_read(
        user, topic.id, when=timezone.now() - datetime.timedelta(hours=3)
    )

    client = APIClient()
    client.force_authenticate(user)
    resp = client.get(f"/forum/boards/{board.slug}/topics/")

    assert resp.data["results"][0]["is_unread"] is True


@pytest.mark.django_db
def test_is_unread_prefers_topic_read_over_profile_watermark_when_they_disagree():
    """TopicRead is the more specific signal and must win the COALESCE even
    when the profile watermark alone would say the opposite — proves the
    Coalesce argument order, not just that either baseline works alone."""
    board = _board()
    user = User.objects.create_user(username="conflicting")
    now = timezone.now()
    topic = Topic.objects.create(
        board=board,
        title="Conflict",
        slug="conflict-topic",
        live=True,
        last_post_at=now,
    )
    # Watermark alone would say unread (it predates the last post)...
    profile = ForumProfile.for_user(user)
    profile.read_watermark_at = now - datetime.timedelta(days=2)
    profile.save(update_fields=["read_watermark_at"])
    # ...but a specific TopicRead after the last post says read. TopicRead
    # must win: if the Coalesce args were ever swapped, this would flip to True.
    TopicRead.mark_read(user, topic.id, when=now + datetime.timedelta(hours=1))

    client = APIClient()
    client.force_authenticate(user)
    resp = client.get(f"/forum/boards/{board.slug}/topics/")

    assert resp.data["results"][0]["is_unread"] is False


@pytest.mark.django_db
@override_settings(WAGTAILFORUM_UNREAD_LAUNCH_AT="2020-06-15T00:00:00Z")
def test_is_unread_uses_launch_constant_for_profile_less_user():
    """A user with no ForumProfile row at all (never opened a topic, never
    hit /me/profile/, never received a push) falls all the way to the fixed
    launch constant — bounded to "unread only for topics active since
    launch," not the entire back-catalog."""
    board = _board()
    stranger = User.objects.create_user(username="stranger")
    assert not ForumProfile.objects.filter(user=stranger).exists()
    Topic.objects.create(
        board=board,
        title="Ancient",
        slug="ancient-topic",
        live=True,
        last_post_at=timezone.datetime(2019, 1, 1, tzinfo=datetime.timezone.utc),
    )
    Topic.objects.create(
        board=board,
        title="PostLaunch",
        slug="post-launch-topic",
        live=True,
        last_post_at=timezone.datetime(2021, 1, 1, tzinfo=datetime.timezone.utc),
    )

    client = APIClient()
    client.force_authenticate(stranger)
    resp = client.get(f"/forum/boards/{board.slug}/topics/")

    by_slug = {t["slug"]: t["is_unread"] for t in resp.data["results"]}
    assert by_slug["ancient-topic"] is False
    assert by_slug["post-launch-topic"] is True


@pytest.mark.django_db
@override_settings(WAGTAILFORUM_UNREAD_LAUNCH_AT="2020-06-15T00:00:00")
def test_is_unread_uses_launch_constant_when_naive_datetime_configured():
    """WAGTAILFORUM_UNREAD_LAUNCH_AT with no UTC offset parses (via
    parse_datetime) to a NAIVE datetime — _annotate_topic_unread must coerce
    it aware (timezone.make_aware) before comparing against the aware
    last_post_at column, rather than raising or silently miscomparing.
    Otherwise-identical to test_is_unread_uses_launch_constant_for_profile_less_user
    above, just with an offset-less setting value."""
    board = _board()
    stranger = User.objects.create_user(username="stranger-naive")
    assert not ForumProfile.objects.filter(user=stranger).exists()
    Topic.objects.create(
        board=board,
        title="Ancient",
        slug="ancient-topic-naive",
        live=True,
        last_post_at=timezone.datetime(2019, 1, 1, tzinfo=datetime.timezone.utc),
    )
    Topic.objects.create(
        board=board,
        title="PostLaunch",
        slug="post-launch-topic-naive",
        live=True,
        last_post_at=timezone.datetime(2021, 1, 1, tzinfo=datetime.timezone.utc),
    )

    client = APIClient()
    client.force_authenticate(stranger)
    resp = client.get(f"/forum/boards/{board.slug}/topics/")

    assert resp.status_code == 200
    by_slug = {t["slug"]: t["is_unread"] for t in resp.data["results"]}
    assert by_slug["ancient-topic-naive"] is False
    assert by_slug["post-launch-topic-naive"] is True


@pytest.mark.django_db
@override_settings(WAGTAILFORUM_UNREAD_LAUNCH_AT="not-a-real-datetime")
def test_is_unread_fails_loud_on_malformed_launch_setting():
    """A malformed WAGTAILFORUM_UNREAD_LAUNCH_AT must surface as a loud 500
    (via the project's custom exception handler, which logs and converts the
    raised ImproperlyConfigured), not silently degrade is_unread to False for
    every profile-less user."""
    board = _board()
    stranger = User.objects.create_user(username="stranger2")
    Topic.objects.create(board=board, title="X", slug="x-topic", live=True)

    client = APIClient()
    client.force_authenticate(stranger)
    resp = client.get(f"/forum/boards/{board.slug}/topics/")

    assert resp.status_code == 500
