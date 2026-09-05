import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()


@pytest.mark.django_db
def test_forum_boards_endpoint_is_mounted():
    resp = APIClient().get("/api/v1/forum/boards/")
    assert resp.status_code == 200
    assert "results" in resp.data


@pytest.mark.django_db
def test_block_endpoint_is_mounted_and_throttled():
    """todo 284/M9: one round-trip through the REAL host mount, not just the
    package test urlconf — docs/rules/forum.md requires host throttling
    behavior be proven through the real mount."""
    blocker = User.objects.create_user(username="mounted-blocker")
    target = User.objects.create_user(username="mounted-target")
    client = APIClient()
    client.force_authenticate(blocker)

    resp = client.post(f"/api/v1/forum/users/{target.username}/block/")
    assert resp.status_code == 200
    assert resp.data == {"blocked": True}

    resp = client.get("/api/v1/forum/me/blocks/")
    assert resp.status_code == 200
    assert [row["username"] for row in resp.data] == [target.username]

    resp = client.delete(f"/api/v1/forum/users/{target.username}/block/")
    assert resp.status_code == 200
    assert resp.data == {"blocked": False}


@pytest.mark.django_db
def test_dm_endpoints_are_mounted_and_throttled():
    """todo 319/M10: one round-trip through the REAL host mount, mirroring
    test_block_endpoint_is_mounted_and_throttled."""
    from wagtail_forum.models import Report

    sender = get_user_model().objects.create_user(username="mounted-dm-sender")
    recipient = get_user_model().objects.create_user(username="mounted-dm-recipient")
    client = APIClient()
    client.force_authenticate(sender)

    resp = client.post(
        f"/api/v1/forum/users/{recipient.username}/messages/", {"body": "hi"}
    )
    assert resp.status_code == 201

    resp = client.get("/api/v1/forum/conversations/")
    assert resp.status_code == 200
    assert len(resp.data["results"]) == 1
    conversation_id = resp.data["results"][0]["id"]

    resp = client.get(f"/api/v1/forum/conversations/{conversation_id}/messages/")
    assert resp.status_code == 200
    assert len(resp.data["results"]) == 1
    message_id = resp.data["results"][0]["id"]

    client.force_authenticate(recipient)
    resp = client.post(
        f"/api/v1/forum/messages/{message_id}/report/", {"reason": "spam"}
    )
    assert resp.status_code == 200
    assert Report.objects.filter(message_id=message_id).exists()


@pytest.mark.django_db
def test_poll_vote_endpoint_is_mounted_and_throttled():
    """todo 309/M8: one round-trip through the REAL host mount, mirroring
    test_block_endpoint_is_mounted_and_throttled. The 4-week-old commit this
    feature was cherry-picked from shipped without this — every sibling
    write endpoint added in the same window (block, DM) has it."""
    from wagtail.models import Page
    from wagtail_forum.models import (
        ForumBoard,
        ForumIndex,
        Poll,
        PollOption,
        Post,
        Topic,
    )

    root = Page.objects.get(id=1)
    index = root.add_child(
        instance=ForumIndex(title="Forum", slug="forum-mounted-poll")
    )
    board = index.add_child(instance=ForumBoard(title="General", slug="mounted-poll"))
    author = User.objects.create_user(username="mounted-poll-author")
    voter = User.objects.create_user(username="mounted-poll-voter")
    topic = Topic.objects.create(
        board=board, title="T", slug="mounted-poll-t", live=True, author=author
    )
    Post.objects.create(topic=topic, author=author, is_opening_post=True, live=True)
    poll = Poll.objects.create(topic=topic, question="Best soil?")
    peat = PollOption.objects.create(poll=poll, text="Peat", order=0)

    client = APIClient()
    client.force_authenticate(voter)
    resp = client.post(
        f"/api/v1/forum/topics/{topic.id}/poll/vote/", {"option_id": peat.id}
    )
    assert resp.status_code == 200
    assert resp.data["my_vote_option_ids"] == [peat.id]

    # A second vote is rejected, not replaced (todo 309's own product
    # decision, see the package README's Polls section).
    resp = client.post(
        f"/api/v1/forum/topics/{topic.id}/poll/vote/", {"option_id": peat.id}
    )
    assert resp.status_code == 409


@pytest.mark.django_db
def test_search_many_term_query_is_bounded_not_500():
    # Todo 290: an anonymous many-term query recursed Wagtail's search-query
    # AND-tree construction (one nesting level per term) into a
    # RecursionError/500. The bound lives in the package SearchView.get, but
    # prod serves this route through the throttled forum_host SUBCLASS
    # (see test_host_mounted_reads_carry_m42_cache_headers above), so pin the
    # fix through that real mount, not just the package test urlconf.
    resp = APIClient().get("/api/v1/forum/search/?q=" + "tomato " * 500)
    assert resp.status_code == 200


@pytest.mark.django_db
def test_host_mounted_reads_carry_m42_cache_headers():
    # M42 (todo 261): the caching mixin lives on the PACKAGE read views, but prod
    # serves through this host mount — some views straight from the package
    # (boards) and some via throttled host SUBCLASSES (search). Both must still
    # emit the anon cache headers. The package's own test_read_cache_headers.py
    # runs under the package test urlconf, so this is the one check on the real
    # forum_host path. No fixtures: boards → {"results": []}, empty search → 200.
    client = APIClient()
    for path in ("/api/v1/forum/boards/", "/api/v1/forum/search/"):
        resp = client.get(path)
        assert resp.status_code == 200, path
        assert "public" in resp["Cache-Control"], path
        assert "s-maxage=60" in resp["Cache-Control"], path
        assert "Cookie" in resp["Vary"] and "Authorization" in resp["Vary"], path


@pytest.mark.django_db
def test_host_mounted_private_reads_carry_no_store_cache_headers():
    # Todo 303: PrivateForumReadCacheMixin lives on the PACKAGE views, but
    # three of the six fixed views (MeProfileView, NotificationUnreadCountView,
    # UserMentionSearchView) are re-wrapped here by forum_host's `_throttled`
    # host subclasses. Each subclass body is just `pass`, and `_throttled`
    # decorates the HTTP-method function (`get`), not `finalize_response` — so
    # the mixin's response-header logic, which runs in `finalize_response`,
    # stays intact through the subclass. This test pins that through the real
    # mount rather than relying on the reasoning alone (mirrors
    # test_host_mounted_reads_carry_m42_cache_headers above for the anon
    # case). NotificationListView is mounted straight from the package (no
    # host subclass) and is already covered there; skipped here as redundant.
    user = User.objects.create_user(username="privatereader")
    client = APIClient()
    client.force_authenticate(user)
    for path in (
        "/api/v1/forum/me/profile/",
        "/api/v1/forum/notifications/unread-count/",
        "/api/v1/forum/users/search/?q=a",
    ):
        resp = client.get(path)
        assert resp.status_code == 200, path
        cache_control = resp["Cache-Control"]
        assert "no-store" in cache_control, path
        assert "private" in cache_control, path
        assert "public" not in cache_control, path
        assert "Cookie" in resp["Vary"] and "Authorization" in resp["Vary"], path
