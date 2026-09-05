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


def _poll(
    topic,
    question="Best soil?",
    options=("Peat", "Coir"),
    closes_at=None,
    max_choices=1,
):
    poll = Poll.objects.create(
        topic=topic, question=question, closes_at=closes_at, max_choices=max_choices
    )
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
    # The envelope's message is what NewThreadPage renders verbatim: a readable
    # "poll.<field>: <text>" sentence from the nested serializer, never
    # str(exc)'s ErrorDetail dict repr (todo 320). The structured field error
    # still rides under errors["poll"].
    message = resp.data["message"]
    # "poll.<field>: ..." for a named subfield; a malformed poll shape would
    # collapse to "poll: ..." — either way it names the poll, readably.
    assert message.startswith("poll"), message
    assert "ErrorDetail" not in message and "{'" not in message, message
    assert "poll" in resp.data["errors"], reason


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
    assert resp.data["my_vote_option_ids"] == [peat.id]
    assert resp.data["max_choices"] == 1
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
    """PollVoteView and TopicDetailSerializer.get_poll both return
    Poll.serialize()'s shape (todo 320 #3) — full field-by-field equality,
    not just key-set plus two scalars, since a shared implementation can
    still be called with the wrong argument at one of the two call sites."""
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

    assert vote_resp.data == detail_resp.data["poll"]


# --------------------------------------------------------------------------
# Multi-choice (todo 349)
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_compose_a_multi_choice_poll_stores_max_choices():
    board = _board("mc1")
    author = User.objects.create_user(username="mc1-author")
    client = APIClient()
    client.force_authenticate(author)

    resp = _create_topic(
        client,
        board,
        poll={
            "question": "Pests seen?",
            "options": ["Aphids", "Mites", "Scale"],
            "max_choices": 2,
        },
    )

    assert resp.status_code == 201, resp.data
    poll = Poll.objects.get()
    assert poll.max_choices == 2
    detail = APIClient().get(f"/forum/topics/{poll.topic_id}/")
    assert detail.data["poll"]["max_choices"] == 2


@pytest.mark.django_db
def test_max_choices_defaults_to_single_choice():
    board = _board("mc2")
    author = User.objects.create_user(username="mc2-author")
    client = APIClient()
    client.force_authenticate(author)

    resp = _create_topic(client, board, poll={"question": "Q?", "options": ["A", "B"]})

    assert resp.status_code == 201, resp.data
    assert Poll.objects.get().max_choices == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    "poll, reason",
    [
        (
            {"question": "Q?", "options": ["A", "B"], "max_choices": 3},
            "more than options",
        ),
        (
            {"question": "Q?", "options": ["A", "B", ""], "max_choices": 3},
            "blanks don't count",
        ),
        ({"question": "Q?", "options": ["A", "B"], "max_choices": 0}, "zero"),
    ],
)
def test_invalid_max_choices_is_rejected_and_creates_no_topic(poll, reason):
    board = _board(f"mc3-{abs(hash(reason)) % 10000}")
    author = User.objects.create_user(username=f"mc3-{abs(hash(reason)) % 10000}")
    client = APIClient()
    client.force_authenticate(author)

    resp = _create_topic(client, board, poll=poll)

    assert resp.status_code == 400, reason
    assert "max_choices" in str(resp.data["errors"]["poll"]), reason
    assert not Topic.objects.exists() and not Poll.objects.exists(), reason


@pytest.mark.django_db
def test_multi_choice_vote_records_each_option_and_counts_the_voter_once():
    board = _board("mv1")
    author = User.objects.create_user(username="mv1-author")
    first, second = (User.objects.create_user(username=f"mv1-v{i}") for i in range(2))
    topic = _topic("mv1-t", board=board, author=author)
    poll = _poll(topic, options=("Aphids", "Mites", "Scale"), max_choices=2)
    aphids, mites, scale = poll.options.all()

    client = APIClient()
    client.force_authenticate(first)
    resp = client.post(
        f"/forum/topics/{topic.id}/poll/vote/",
        {"option_ids": [mites.id, aphids.id]},
        format="json",
    )

    assert resp.status_code == 200, resp.data
    assert resp.data["my_vote_option_ids"] == [aphids.id, mites.id]
    assert resp.data["total_votes"] == 1  # one voter, two rows
    counts = {o["text"]: o["vote_count"] for o in resp.data["options"]}
    assert counts == {"Aphids": 1, "Mites": 1, "Scale": 0}
    assert PollVote.objects.filter(poll=poll, user=first).count() == 2

    client.force_authenticate(second)
    resp = client.post(
        f"/forum/topics/{topic.id}/poll/vote/",
        {"option_ids": [mites.id]},
        format="json",
    )
    assert resp.data["total_votes"] == 2
    assert {o["text"]: o["vote_count"] for o in resp.data["options"]} == {
        "Aphids": 1,
        "Mites": 2,
        "Scale": 0,
    }
    # And the detail view agrees with the vote response, ballot included.
    detail = client.get(f"/forum/topics/{topic.id}/")
    assert detail.data["poll"] == resp.data
    assert detail.data["poll"]["my_vote_option_ids"] == [mites.id]


@pytest.mark.django_db
def test_a_ballot_with_more_choices_than_allowed_is_rejected_whole():
    board = _board("mv2")
    author = User.objects.create_user(username="mv2-author")
    voter = User.objects.create_user(username="mv2-voter")
    topic = _topic("mv2-t", board=board, author=author)
    poll = _poll(topic, options=("A", "B", "C"), max_choices=2)
    ids = [o.id for o in poll.options.all()]

    client = APIClient()
    client.force_authenticate(voter)
    resp = client.post(
        f"/forum/topics/{topic.id}/poll/vote/", {"option_ids": ids}, format="json"
    )

    assert resp.status_code == 400
    assert "option_ids" in resp.data["errors"]
    assert not PollVote.objects.exists()


@pytest.mark.django_db
def test_a_single_choice_poll_rejects_a_two_option_ballot():
    """max_choices=1 (every pre-349 poll) keeps its exact contract: the array
    form is accepted, but only with one id."""
    board = _board("mv3")
    author = User.objects.create_user(username="mv3-author")
    voter = User.objects.create_user(username="mv3-voter")
    topic = _topic("mv3-t", board=board, author=author)
    poll = _poll(topic)
    ids = [o.id for o in poll.options.all()]

    client = APIClient()
    client.force_authenticate(voter)
    two = client.post(
        f"/forum/topics/{topic.id}/poll/vote/", {"option_ids": ids}, format="json"
    )
    one = client.post(
        f"/forum/topics/{topic.id}/poll/vote/", {"option_ids": ids[:1]}, format="json"
    )

    assert two.status_code == 400
    assert one.status_code == 200
    assert one.data["my_vote_option_ids"] == ids[:1]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "payload, reason",
    [
        ({"option_ids": []}, "empty ballot"),
        ({}, "no option at all"),
        ({"option_ids": "1"}, "not a list"),
    ],
)
def test_malformed_ballots_are_rejected(payload, reason):
    board = _board(f"mv4-{abs(hash(reason)) % 10000}")
    author = User.objects.create_user(username=f"mv4-a-{abs(hash(reason)) % 10000}")
    voter = User.objects.create_user(username=f"mv4-v-{abs(hash(reason)) % 10000}")
    topic = _topic(f"mv4-t-{abs(hash(reason)) % 10000}", board=board, author=author)
    _poll(topic, max_choices=2)

    client = APIClient()
    client.force_authenticate(voter)
    resp = client.post(f"/forum/topics/{topic.id}/poll/vote/", payload, format="json")

    assert resp.status_code == 400, reason
    assert not PollVote.objects.exists(), reason


@pytest.mark.django_db
def test_repeating_an_option_or_mixing_the_two_forms_is_rejected():
    board = _board("mv5")
    author = User.objects.create_user(username="mv5-author")
    voter = User.objects.create_user(username="mv5-voter")
    topic = _topic("mv5-t", board=board, author=author)
    poll = _poll(topic, max_choices=2)
    peat = poll.options.first()

    client = APIClient()
    client.force_authenticate(voter)
    repeated = client.post(
        f"/forum/topics/{topic.id}/poll/vote/",
        {"option_ids": [peat.id, peat.id]},
        format="json",
    )
    mixed = client.post(
        f"/forum/topics/{topic.id}/poll/vote/",
        {"option_id": peat.id, "option_ids": [peat.id]},
        format="json",
    )

    assert repeated.status_code == 400
    # The dedup validator's own text, not just its status: the view's
    # option-count mismatch check also 400s this payload (filter(id__in)
    # collapses the duplicate), so a bare 400 would survive deleting the
    # validator (cross-cutting review).
    assert "Each option may be chosen at most once." in str(
        repeated.data["errors"]["option_ids"]
    )
    assert mixed.status_code == 400
    assert not PollVote.objects.exists()


@pytest.mark.django_db
def test_an_oversized_ballot_is_refused_before_per_item_parsing():
    from wagtail_forum.api.serializers import MAX_POLL_OPTION_LIST_ITEMS

    board = _board("mv8")
    author = User.objects.create_user(username="mv8-author")
    voter = User.objects.create_user(username="mv8-voter")
    topic = _topic("mv8-t", board=board, author=author)
    _poll(topic, max_choices=2)

    client = APIClient()
    client.force_authenticate(voter)
    # Not integers on purpose: a per-item parse would 400 on "x" — the
    # length gate must answer first, with its own message.
    resp = client.post(
        f"/forum/topics/{topic.id}/poll/vote/",
        {"option_ids": ["x"] * (MAX_POLL_OPTION_LIST_ITEMS + 1)},
        format="json",
    )

    assert resp.status_code == 400
    assert "Too many options in one ballot." in str(resp.data["errors"]["option_ids"])


@pytest.mark.django_db
def test_locked_recheck_refuses_a_ballot_the_fast_path_missed(monkeypatch):
    """Deterministic stand-in for the concurrent double-submit (docs/rules/
    database.md, test_collections.py precedent): the fast, unlocked read is
    made to miss once, so only the re-read under the poll row lock stands
    between a second ballot and a duplicate. Deleting that re-check turns
    this red (200 and two ballots)."""
    from wagtail_forum.api import polls as polls_module

    board = _board("mv9")
    author = User.objects.create_user(username="mv9-author")
    voter = User.objects.create_user(username="mv9-voter")
    topic = _topic("mv9-t", board=board, author=author)
    poll = _poll(topic, options=("A", "B", "C"), max_choices=2)
    a, b, c = poll.options.all()

    client = APIClient()
    client.force_authenticate(voter)
    assert (
        client.post(
            f"/forum/topics/{topic.id}/poll/vote/",
            {"option_ids": [a.id]},
            format="json",
        ).status_code
        == 200
    )

    real = polls_module._existing_ballot
    calls = {"n": 0}

    def miss_once(poll_, user):
        calls["n"] += 1
        return [] if calls["n"] == 1 else real(poll_, user)

    monkeypatch.setattr(polls_module, "_existing_ballot", miss_once)
    second = client.post(
        f"/forum/topics/{topic.id}/poll/vote/",
        {"option_ids": [b.id, c.id]},
        format="json",
    )

    assert calls["n"] == 2  # the fast path missed, the locked re-check ran
    assert second.status_code == 409
    assert list(
        PollVote.objects.filter(poll=poll, user=voter).values_list(
            "option_id", flat=True
        )
    ) == [a.id]


@pytest.mark.django_db
def test_a_ballot_is_written_under_a_poll_row_lock():
    """Pins the lock itself, which no sequential test can exercise: the
    write transaction must SELECT the poll row FOR UPDATE before inserting."""
    board = _board("mv10")
    author = User.objects.create_user(username="mv10-author")
    voter = User.objects.create_user(username="mv10-voter")
    topic = _topic("mv10-t", board=board, author=author)
    poll = _poll(topic, max_choices=2)

    client = APIClient()
    client.force_authenticate(voter)
    with CaptureQueriesContext(connection) as ctx:
        resp = client.post(
            f"/forum/topics/{topic.id}/poll/vote/",
            {"option_ids": [poll.options.first().id]},
            format="json",
        )

    assert resp.status_code == 200
    locking = [
        q["sql"]
        for q in ctx.captured_queries
        if "FOR UPDATE" in q["sql"] and "wagtail_forum_poll" in q["sql"]
    ]
    assert len(locking) == 1, [q["sql"][:80] for q in ctx.captured_queries]


@pytest.mark.django_db
def test_multi_choice_poll_costs_no_more_queries_than_single_choice():
    """The distinct-voter total rides the options query as a subquery, so a
    multi-choice poll's topic detail — and its vote response — cost exactly
    what a single-choice poll's do (cross-cutting review: pin the cost, not
    just the number)."""
    board = _board("mv11")
    author = User.objects.create_user(username="mv11-author")
    single_topic = _topic("mv11-single", board=board, author=author)
    _poll(single_topic)
    multi_topic = _topic("mv11-multi", board=board, author=author)
    multi = _poll(multi_topic, options=("A", "B", "C"), max_choices=2)
    for i in range(3):
        u = User.objects.create_user(username=f"mv11-v{i}")
        PollVote.objects.create(poll=multi, option=multi.options.all()[i], user=u)
        PollVote.objects.create(
            poll=multi, option=multi.options.all()[(i + 1) % 3], user=u
        )

    anon = APIClient()
    with CaptureQueriesContext(connection) as single_ctx:
        anon.get(f"/forum/topics/{single_topic.id}/")
    with CaptureQueriesContext(connection) as multi_ctx:
        detail = anon.get(f"/forum/topics/{multi_topic.id}/")

    assert detail.data["poll"]["total_votes"] == 3  # 3 voters, 6 rows
    assert [o["vote_count"] for o in detail.data["poll"]["options"]] == [2, 2, 2]
    assert len(multi_ctx.captured_queries) == len(single_ctx.captured_queries)


@pytest.mark.django_db
def test_a_ballot_with_a_foreign_option_is_rejected_whole():
    board = _board("mv6")
    author = User.objects.create_user(username="mv6-author")
    voter = User.objects.create_user(username="mv6-voter")
    mine = _topic("mv6-mine", board=board, author=author)
    theirs = _topic("mv6-theirs", board=board, author=author)
    poll = _poll(mine, max_choices=2)
    other = _poll(theirs, question="Other?", options=("X", "Y"))

    client = APIClient()
    client.force_authenticate(voter)
    resp = client.post(
        f"/forum/topics/{mine.id}/poll/vote/",
        {"option_ids": [poll.options.first().id, other.options.first().id]},
        format="json",
    )

    assert resp.status_code == 400
    assert not PollVote.objects.exists()  # nothing partial


@pytest.mark.django_db
def test_second_submission_on_a_multi_choice_poll_is_rejected_not_merged():
    """The todo-283 decision carried over (todo 349 Work Log): one final
    submission per voter, whatever its size — no top-up, no replacement."""
    board = _board("mv7")
    author = User.objects.create_user(username="mv7-author")
    voter = User.objects.create_user(username="mv7-voter")
    topic = _topic("mv7-t", board=board, author=author)
    poll = _poll(topic, options=("A", "B", "C"), max_choices=3)
    a, b, c = poll.options.all()

    client = APIClient()
    client.force_authenticate(voter)
    client.post(
        f"/forum/topics/{topic.id}/poll/vote/", {"option_ids": [a.id]}, format="json"
    )
    top_up = client.post(
        f"/forum/topics/{topic.id}/poll/vote/",
        {"option_ids": [b.id, c.id]},
        format="json",
    )

    assert top_up.status_code == 409
    assert str(a.id) in top_up.data["message"]
    assert list(
        PollVote.objects.filter(poll=poll, user=voter).values_list(
            "option_id", flat=True
        )
    ) == [a.id]
    assert (
        APIClient().get(f"/forum/topics/{topic.id}/").data["poll"]["total_votes"] == 1
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
    assert anon.data["poll"]["my_vote_option_ids"] == []
    # The aggregate is public; the individual choice is not.
    assert anon.data["poll"]["total_votes"] == 1

    client = APIClient()
    client.force_authenticate(onlooker)
    assert (
        client.get(f"/forum/topics/{topic.id}/").data["poll"]["my_vote_option_ids"]
        == []
    )


@pytest.mark.django_db
def test_a_poll_less_topic_detail_query_count_is_unchanged_by_the_poll_field():
    """The poll field must cost NOTHING for the overwhelmingly common
    poll-less topic. `poll` is a reverse OneToOne that the view
    select_relateds, so the null check is answered by the row already fetched
    and get_poll returns before touching options.

    Pinned EXACTLY (docs/rules/testing.md) against the SAME counts
    test_topic_detail.py asserts without any poll in the picture: 5 anonymous,
    10 for an authenticated non-author (the base 5 + a subscription check + a
    bookmark check + the two can_mark_solution permission-table reads, per
    that file's own breakdown — todo 283/293 landed after this test was
    first written and raised the authenticated count from 8 to 10; the poll
    field itself adds none of it). If either moves, the select_related has
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
    assert len(auth_ctx.captured_queries) == 10


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


def test_poll_option_bounds_defaults_match_the_web_composer_constants():
    """todo 320 #5: NewThreadPage.tsx hardcodes MIN_POLL_OPTIONS/
    MAX_POLL_OPTIONS as literals mirroring these defaults rather than
    fetching them, so nothing else catches the two silently diverging. Pin
    both here so a future change to either default fails loudly."""
    from wagtail_forum.conf import get_setting

    ts_constants = (
        "web/src/pages/forum/NewThreadPage.tsx "
        "(MIN_POLL_OPTIONS, MAX_POLL_OPTIONS) must be updated to match"
    )
    assert get_setting("POLL_MIN_OPTIONS") == 2, ts_constants
    assert get_setting("POLL_MAX_OPTIONS") == 10, ts_constants
