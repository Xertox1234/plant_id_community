"""Poll creation, voting, results, and the topic-detail query pins (todo 283 / M8)."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.models import (
    ForumBoard,
    ForumIndex,
    Poll,
    PollOption,
    PollVote,
    Post,
    Topic,
)

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


def _board(slug="general"):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug=f"forum-{slug}"))
    return index.add_child(instance=ForumBoard(title="General", slug=slug))


def _topic(slug="t", live=True, board=None, author=None):
    board = board or _board(slug)
    topic = Topic.objects.create(
        board=board, title="T", slug=slug, live=live, author=author
    )
    Post.objects.create(topic=topic, author=author, is_opening_post=True, live=True)
    return topic


def _poll(topic, question="Best soil?", options=("Peat", "Coir"), closes_at=None):
    poll = Poll.objects.create(topic=topic, question=question, closes_at=closes_at)
    for index, text in enumerate(options):
        PollOption.objects.create(poll=poll, text=text, order=index)
    return poll


def _create_topic(client, board, poll=None, slug="poll-thread"):
    payload = {
        "title": "Poll thread",
        "slug": slug,
        "body": [{"type": "paragraph", "value": "<p>Vote below.</p>"}],
    }
    if poll is not None:
        payload["poll"] = poll
    return client.post(f"/forum/boards/{board.slug}/topics/", payload, format="json")


# --------------------------------------------------------------------------
# Creation (composer only)
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_compose_a_topic_with_a_poll():
    board = _board("pc1")
    author = User.objects.create_user(username="pc1-author")
    client = APIClient()
    client.force_authenticate(author)

    resp = _create_topic(
        client,
        board,
        poll={"question": "Best soil?", "options": ["Peat", "Coir", "Bark"]},
    )

    assert resp.status_code == 201
    poll = Poll.objects.get(topic_id=resp.data["id"])
    assert poll.question == "Best soil?"
    # Submitted order becomes display order.
    assert [o.text for o in poll.options.all()] == ["Peat", "Coir", "Bark"]
    assert [o.order for o in poll.options.all()] == [0, 1, 2]
    assert poll.closes_at is None


@pytest.mark.django_db
def test_compose_without_a_poll_creates_none():
    board = _board("pc2")
    author = User.objects.create_user(username="pc2-author")
    client = APIClient()
    client.force_authenticate(author)

    resp = _create_topic(client, board)

    assert resp.status_code == 201
    assert not Poll.objects.exists()


@pytest.mark.django_db
def test_blank_options_are_dropped_not_rejected():
    """A composer with a fixed number of option inputs sends empties for the
    ones left untouched — a normal submission, not a malformed one."""
    board = _board("pc3")
    author = User.objects.create_user(username="pc3-author")
    client = APIClient()
    client.force_authenticate(author)

    resp = _create_topic(
        client,
        board,
        poll={"question": "Best soil?", "options": ["Peat", "", "Coir", "   "]},
    )

    assert resp.status_code == 201
    poll = Poll.objects.get(topic_id=resp.data["id"])
    assert [o.text for o in poll.options.all()] == ["Peat", "Coir"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "poll,reason",
    [
        ({"question": "Q?", "options": ["Only one"]}, "fewer than POLL_MIN_OPTIONS"),
        ({"question": "Q?", "options": ["", "  "]}, "all options blank"),
        ({"question": "   ", "options": ["A", "B"]}, "blank question"),
        ({"question": "Q?", "options": ["Same", "same"]}, "duplicate options"),
        (
            {"question": "Q?", "options": [f"Option {i}" for i in range(11)]},
            "more than POLL_MAX_OPTIONS",
        ),
        ({"question": "Q?" * 500, "options": ["A", "B"]}, "question too long"),
        ({"question": "Q?", "options": ["A" * 500, "B"]}, "option too long"),
    ],
)
def test_invalid_poll_is_rejected_and_creates_no_topic(poll, reason):
    board = _board(f"pc-invalid-{abs(hash(reason)) % 10000}")
    author = User.objects.create_user(username=f"author-{abs(hash(reason)) % 10000}")
    client = APIClient()
    client.force_authenticate(author)

    resp = _create_topic(client, board, poll=poll)

    assert resp.status_code == 400, reason
    # Validation runs before creation, so a bad poll takes the whole request
    # down rather than leaving a poll-less topic behind.
    assert not Topic.objects.exists(), reason
    assert not Poll.objects.exists(), reason


@pytest.mark.django_db
def test_a_close_time_in_the_past_is_rejected():
    board = _board("pc4")
    author = User.objects.create_user(username="pc4-author")
    client = APIClient()
    client.force_authenticate(author)

    resp = _create_topic(
        client,
        board,
        poll={
            "question": "Best soil?",
            "options": ["Peat", "Coir"],
            "closes_at": (timezone.now() - timedelta(days=1)).isoformat(),
        },
    )

    assert resp.status_code == 400
    assert not Poll.objects.exists()


@pytest.mark.django_db
def test_a_vote_count_in_the_create_payload_is_ignored():
    """AC 5, creation half: there is no writable count anywhere in the poll
    write shape, so a caller cannot seed results at compose time either."""
    board = _board("pc5")
    author = User.objects.create_user(username="pc5-author")
    client = APIClient()
    client.force_authenticate(author)

    resp = _create_topic(
        client,
        board,
        poll={
            "question": "Best soil?",
            "options": ["Peat", "Coir"],
            "total_votes": 500,
            "vote_count": 500,
        },
    )

    assert resp.status_code == 201
    detail = APIClient().get(f"/forum/topics/{resp.data['id']}/")
    assert detail.data["poll"]["total_votes"] == 0
    assert all(o["vote_count"] == 0 for o in detail.data["poll"]["options"])
    assert not PollVote.objects.exists()


# --------------------------------------------------------------------------
# Voting
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_vote_records_the_choice_and_returns_computed_results():
    board = _board("pv")
    author = User.objects.create_user(username="pv-author")
    voter = User.objects.create_user(username="pv-voter")
    topic = _topic("pv-t", board=board, author=author)
    poll = _poll(topic)
    peat = poll.options.get(text="Peat")

    client = APIClient()
    client.force_authenticate(voter)
    resp = client.post(f"/forum/topics/{topic.id}/poll/vote/", {"option_id": peat.id})

    assert resp.status_code == 200
    assert resp.data["total_votes"] == 1
    assert resp.data["my_vote_option_id"] == peat.id
    counts = {option["text"]: option["vote_count"] for option in resp.data["options"]}
    assert counts == {"Peat": 1, "Coir": 0}
    assert PollVote.objects.filter(poll=poll, user=voter, option=peat).count() == 1


@pytest.mark.django_db
def test_second_vote_by_same_user_is_rejected_not_replaced():
    """AC 4. The choice recorded in the todo-283 Work Log is REJECT (409), so
    the first vote must survive and the totals must not move."""
    board = _board("pv2")
    author = User.objects.create_user(username="pv2-author")
    voter = User.objects.create_user(username="pv2-voter")
    topic = _topic("pv2-t", board=board, author=author)
    poll = _poll(topic)
    peat = poll.options.get(text="Peat")
    coir = poll.options.get(text="Coir")

    client = APIClient()
    client.force_authenticate(voter)
    client.post(f"/forum/topics/{topic.id}/poll/vote/", {"option_id": peat.id})
    second = client.post(f"/forum/topics/{topic.id}/poll/vote/", {"option_id": coir.id})

    assert second.status_code == 409
    # The first vote stands — not replaced, not duplicated.
    assert PollVote.objects.filter(poll=poll, user=voter).count() == 1
    assert PollVote.objects.get(poll=poll, user=voter).option_id == peat.id
    # And the totals are unmoved.
    detail = APIClient().get(f"/forum/topics/{topic.id}/")
    assert detail.data["poll"]["total_votes"] == 1


@pytest.mark.django_db
def test_two_different_users_both_count():
    board = _board("pv3")
    author = User.objects.create_user(username="pv3-author")
    topic = _topic("pv3-t", board=board, author=author)
    poll = _poll(topic)
    peat = poll.options.get(text="Peat")
    coir = poll.options.get(text="Coir")

    for username, option in (("pv3-a", peat), ("pv3-b", coir)):
        client = APIClient()
        client.force_authenticate(User.objects.create_user(username=username))
        client.post(f"/forum/topics/{topic.id}/poll/vote/", {"option_id": option.id})

    detail = APIClient().get(f"/forum/topics/{topic.id}/")
    assert detail.data["poll"]["total_votes"] == 2
    counts = {o["text"]: o["vote_count"] for o in detail.data["poll"]["options"]}
    assert counts == {"Peat": 1, "Coir": 1}


@pytest.mark.django_db
def test_forged_vote_count_in_the_request_is_ignored():
    """AC 5. Results are aggregated from PollVote rows, so a client that posts
    its own counts cannot move them — the extra keys are simply not part of the
    write shape."""
    board = _board("pv4")
    author = User.objects.create_user(username="pv4-author")
    voter = User.objects.create_user(username="pv4-voter")
    topic = _topic("pv4-t", board=board, author=author)
    poll = _poll(topic)
    peat = poll.options.get(text="Peat")

    client = APIClient()
    client.force_authenticate(voter)
    resp = client.post(
        f"/forum/topics/{topic.id}/poll/vote/",
        {
            "option_id": peat.id,
            "vote_count": 9999,
            "total_votes": 9999,
            "options": [{"id": peat.id, "vote_count": 9999}],
        },
        format="json",
    )

    assert resp.status_code == 200
    # The real row count, not the forged one.
    assert resp.data["total_votes"] == 1
    assert {o["text"]: o["vote_count"] for o in resp.data["options"]} == {
        "Peat": 1,
        "Coir": 0,
    }
    # And nothing was persisted from the forged fields.
    assert PollVote.objects.filter(poll=poll).count() == 1


@pytest.mark.django_db
def test_vote_for_another_polls_option_is_rejected():
    """Without the option-belongs-to-this-poll check a caller could pass any
    option id in the table: the unique constraint is on (poll, user), so
    nothing else would stop the vote landing on a different topic's poll."""
    board = _board("pv5")
    author = User.objects.create_user(username="pv5-author")
    voter = User.objects.create_user(username="pv5-voter")
    mine = _topic("pv5-mine", board=board, author=author)
    theirs = _topic("pv5-theirs", board=board, author=author)
    _poll(mine)
    other_poll = _poll(theirs, question="Other?", options=("X", "Y"))
    foreign_option = other_poll.options.first()

    client = APIClient()
    client.force_authenticate(voter)
    resp = client.post(
        f"/forum/topics/{mine.id}/poll/vote/", {"option_id": foreign_option.id}
    )

    assert resp.status_code == 400
    assert not PollVote.objects.exists()


@pytest.mark.django_db
def test_vote_on_a_closed_poll_is_rejected():
    board = _board("pv6")
    author = User.objects.create_user(username="pv6-author")
    voter = User.objects.create_user(username="pv6-voter")
    topic = _topic("pv6-t", board=board, author=author)
    poll = _poll(topic, closes_at=timezone.now() - timedelta(hours=1))
    peat = poll.options.get(text="Peat")

    client = APIClient()
    client.force_authenticate(voter)
    resp = client.post(f"/forum/topics/{topic.id}/poll/vote/", {"option_id": peat.id})

    assert resp.status_code == 409
    assert not PollVote.objects.exists()


@pytest.mark.django_db
def test_vote_requires_authentication():
    board = _board("pv7")
    author = User.objects.create_user(username="pv7-author")
    topic = _topic("pv7-t", board=board, author=author)
    poll = _poll(topic)

    resp = APIClient().post(
        f"/forum/topics/{topic.id}/poll/vote/",
        {"option_id": poll.options.first().id},
    )

    assert resp.status_code == 401
    assert not PollVote.objects.exists()


@pytest.mark.django_db
def test_vote_on_a_hidden_topic_404s_without_leaking_existence():
    board = _board("pv8")
    author = User.objects.create_user(username="pv8-author")
    voter = User.objects.create_user(username="pv8-voter")
    topic = _topic("pv8-t", board=board, author=author, live=False)
    poll = _poll(topic)

    client = APIClient()
    client.force_authenticate(voter)
    resp = client.post(
        f"/forum/topics/{topic.id}/poll/vote/", {"option_id": poll.options.first().id}
    )

    assert resp.status_code == 404
    assert not PollVote.objects.exists()


@pytest.mark.django_db
def test_vote_on_a_topic_without_a_poll_404s():
    board = _board("pv9")
    author = User.objects.create_user(username="pv9-author")
    voter = User.objects.create_user(username="pv9-voter")
    topic = _topic("pv9-t", board=board, author=author)

    client = APIClient()
    client.force_authenticate(voter)
    resp = client.post(f"/forum/topics/{topic.id}/poll/vote/", {"option_id": 1})

    assert resp.status_code == 404


@pytest.mark.django_db
def test_vote_response_matches_topic_detail_poll_shape():
    """PollVoteView._poll_payload rebuilds what TopicDetailSerializer.get_poll
    returns (it is bound to a Poll, not a Topic). This fails if they drift."""
    board = _board("pv10")
    author = User.objects.create_user(username="pv10-author")
    voter = User.objects.create_user(username="pv10-voter")
    topic = _topic("pv10-t", board=board, author=author)
    poll = _poll(topic)

    client = APIClient()
    client.force_authenticate(voter)
    vote_resp = client.post(
        f"/forum/topics/{topic.id}/poll/vote/",
        {"option_id": poll.options.first().id},
    )
    detail_resp = client.get(f"/forum/topics/{topic.id}/")

    assert set(vote_resp.data.keys()) == set(detail_resp.data["poll"].keys())
    assert vote_resp.data["total_votes"] == detail_resp.data["poll"]["total_votes"]
    assert (
        vote_resp.data["my_vote_option_id"]
        == detail_resp.data["poll"]["my_vote_option_id"]
    )


# --------------------------------------------------------------------------
# Topic detail rendering + query pins
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_topic_detail_poll_is_null_when_absent():
    board = _board("pd1")
    author = User.objects.create_user(username="pd1-author")
    topic = _topic("pd1-t", board=board, author=author)

    resp = APIClient().get(f"/forum/topics/{topic.id}/")

    assert resp.data["poll"] is None


@pytest.mark.django_db
def test_my_vote_is_null_for_anonymous_and_never_leaks_another_users_choice():
    board = _board("pd2")
    author = User.objects.create_user(username="pd2-author")
    voter = User.objects.create_user(username="pd2-voter")
    onlooker = User.objects.create_user(username="pd2-onlooker")
    topic = _topic("pd2-t", board=board, author=author)
    poll = _poll(topic)
    PollVote.objects.create(poll=poll, option=poll.options.first(), user=voter)

    anon = APIClient().get(f"/forum/topics/{topic.id}/")
    assert anon.data["poll"]["my_vote_option_id"] is None
    # The aggregate is public; the individual choice is not.
    assert anon.data["poll"]["total_votes"] == 1

    client = APIClient()
    client.force_authenticate(onlooker)
    assert (
        client.get(f"/forum/topics/{topic.id}/").data["poll"]["my_vote_option_id"]
        is None
    )


@pytest.mark.django_db
def test_a_poll_less_topic_detail_query_count_is_unchanged_by_the_poll_field():
    """The poll field must cost NOTHING for the overwhelmingly common
    poll-less topic. `poll` is a reverse OneToOne that the view
    select_relateds, so the null check is answered by the row already fetched
    and get_poll returns before touching options.

    Pinned EXACTLY (docs/rules/testing.md) against the SAME counts
    test_topic_detail.py asserts without any poll in the picture: 5 anonymous,
    8 for an authenticated non-author. If either moves, the select_related has
    been replaced by a prefetch (which runs its query for every request) and
    the change must be explained in both places.
    """
    board = _board("pd3")
    author = User.objects.create_user(username="pd3-author")
    viewer = User.objects.create_user(username="pd3-viewer")
    topic = _topic("pd3-t", board=board, author=author)

    with CaptureQueriesContext(connection) as anon_ctx:
        anon = APIClient().get(f"/forum/topics/{topic.id}/")
    assert anon.data["poll"] is None
    assert len(anon_ctx.captured_queries) == 5

    client = APIClient()
    client.force_authenticate(viewer)
    with CaptureQueriesContext(connection) as auth_ctx:
        auth = client.get(f"/forum/topics/{topic.id}/")
    assert auth.data["poll"] is None
    assert len(auth_ctx.captured_queries) == 8


@pytest.mark.django_db
def test_poll_results_do_not_scale_with_option_or_vote_count():
    """Results are ONE aggregated query regardless of how many options or
    votes a poll has — a per-option count would be an N+1. Compared rather
    than hardcoded so the assertion is about flatness, not about the absolute
    pin (which the test above owns)."""
    board = _board("pd4")
    author = User.objects.create_user(username="pd4-author")
    small_topic = _topic("pd4-small", board=board, author=author)
    _poll(small_topic, options=("A", "B"))
    big_topic = _topic("pd4-big", board=board, author=author)
    big_poll = _poll(big_topic, options=tuple(f"Option {i}" for i in range(10)))
    for i in range(10):
        PollVote.objects.create(
            poll=big_poll,
            option=big_poll.options.all()[i],
            user=User.objects.create_user(username=f"pd4-voter-{i}"),
        )

    client = APIClient()
    with CaptureQueriesContext(connection) as small_ctx:
        client.get(f"/forum/topics/{small_topic.id}/")
    with CaptureQueriesContext(connection) as big_ctx:
        big = client.get(f"/forum/topics/{big_topic.id}/")

    assert big.data["poll"]["total_votes"] == 10
    assert len(big.data["poll"]["options"]) == 10
    assert len(big_ctx.captured_queries) == len(small_ctx.captured_queries)


@pytest.mark.django_db
def test_poll_options_render_in_author_defined_order():
    board = _board("pd5")
    author = User.objects.create_user(username="pd5-author")
    topic = _topic("pd5-t", board=board, author=author)
    _poll(topic, options=("Zulu", "Alpha", "Mike"))

    resp = APIClient().get(f"/forum/topics/{topic.id}/")

    # Submitted order, NOT alphabetical and NOT insertion-id-by-accident.
    assert [o["text"] for o in resp.data["poll"]["options"]] == [
        "Zulu",
        "Alpha",
        "Mike",
    ]


@pytest.mark.django_db
def test_is_closed_reflects_closes_at():
    board = _board("pd6")
    author = User.objects.create_user(username="pd6-author")
    open_topic = _topic("pd6-open", board=board, author=author)
    _poll(open_topic, closes_at=timezone.now() + timedelta(days=1))
    closed_topic = _topic("pd6-closed", board=board, author=author)
    _poll(closed_topic, closes_at=timezone.now() - timedelta(days=1))
    forever_topic = _topic("pd6-forever", board=board, author=author)
    _poll(forever_topic)

    client = APIClient()
    assert (
        client.get(f"/forum/topics/{open_topic.id}/").data["poll"]["is_closed"] is False
    )
    assert (
        client.get(f"/forum/topics/{closed_topic.id}/").data["poll"]["is_closed"]
        is True
    )
    assert (
        client.get(f"/forum/topics/{forever_topic.id}/").data["poll"]["is_closed"]
        is False
    )


@pytest.mark.django_db
def test_deleting_a_topic_removes_its_poll_and_votes():
    board = _board("pd7")
    author = User.objects.create_user(username="pd7-author")
    voter = User.objects.create_user(username="pd7-voter")
    topic = _topic("pd7-t", board=board, author=author)
    poll = _poll(topic)
    PollVote.objects.create(poll=poll, option=poll.options.first(), user=voter)

    topic.delete()

    assert not Poll.objects.exists()
    assert not PollOption.objects.exists()
    assert not PollVote.objects.exists()
