from datetime import datetime
from datetime import timezone as dt_timezone

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext, override_settings
from rest_framework.test import APIClient
from wagtail_forum.api.direct_messages import (
    ConversationListView,
    ConversationMessagesView,
)
from wagtail_forum.models import (
    Conversation,
    ForumProfile,
    Message,
    Report,
    TrustLevel,
    UserBlock,
)
from wagtail_forum.spam.base import SpamBackend, SpamResult

# A stand-in for the AddField default a pre-migration row would hold.
_EPOCH_FOR_TEST = datetime(2000, 1, 1, tzinfo=dt_timezone.utc)

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


@pytest.mark.django_db
def test_send_creates_conversation_and_message():
    sender = User.objects.create_user(username="sender1")
    recipient = User.objects.create_user(username="recipient1")
    client = APIClient()
    client.force_authenticate(sender)

    resp = client.post(
        f"/forum/users/{recipient.username}/messages/", {"body": "hi there"}
    )

    assert resp.status_code == 201
    assert resp.data["body"] == "hi there"
    assert resp.data["sender"]["username"] == "sender1"
    conversation = Conversation.objects.get()
    assert {conversation.participant_a_id, conversation.participant_b_id} == {
        sender.pk,
        recipient.pk,
    }
    assert Message.objects.filter(conversation=conversation, sender=sender).count() == 1


@pytest.mark.django_db
def test_send_requires_authentication():
    recipient = User.objects.create_user(username="recipient-anon")
    client = APIClient()  # no credentials

    resp = client.post(f"/forum/users/{recipient.username}/messages/", {"body": "hi"})

    assert resp.status_code == 401
    assert not Message.objects.exists()


@pytest.mark.django_db
def test_second_send_reuses_the_same_conversation():
    sender = User.objects.create_user(username="sender2")
    recipient = User.objects.create_user(username="recipient2")
    client = APIClient()
    client.force_authenticate(sender)

    client.post(f"/forum/users/{recipient.username}/messages/", {"body": "first"})
    client.post(f"/forum/users/{recipient.username}/messages/", {"body": "second"})

    assert Conversation.objects.count() == 1
    assert Message.objects.count() == 2


@pytest.mark.django_db
def test_cannot_message_self():
    sender = User.objects.create_user(username="sender3")
    client = APIClient()
    client.force_authenticate(sender)

    resp = client.post(f"/forum/users/{sender.username}/messages/", {"body": "hi me"})

    assert resp.status_code == 400
    assert not Message.objects.exists()


@pytest.mark.django_db
def test_blocker_cannot_message_the_user_they_blocked():
    blocker = User.objects.create_user(username="blocker-dm")
    blocked = User.objects.create_user(username="blocked-dm")
    UserBlock.block(blocker, blocked)
    client = APIClient()
    client.force_authenticate(blocker)

    resp = client.post(f"/forum/users/{blocked.username}/messages/", {"body": "hi"})

    assert resp.status_code == 403
    assert not Message.objects.exists()


@pytest.mark.django_db
def test_blocked_user_cannot_message_their_blocker():
    """Reverse direction of the pair — the blocked party is also stopped from
    reaching the blocker (todo 319 AC1: both directions)."""
    blocker = User.objects.create_user(username="blocker-dm2")
    blocked = User.objects.create_user(username="blocked-dm2")
    UserBlock.block(blocker, blocked)
    client = APIClient()
    client.force_authenticate(blocked)

    resp = client.post(f"/forum/users/{blocker.username}/messages/", {"body": "hi"})

    assert resp.status_code == 403
    assert not Message.objects.exists()


@pytest.mark.django_db
def test_flagged_body_is_rejected_and_not_sent():
    sender = User.objects.create_user(username="sender-spam")
    recipient = User.objects.create_user(username="recipient-spam")
    client = APIClient()
    client.force_authenticate(sender)
    spammy = " ".join(["http://x.test"] * 4)  # SPAM_MAX_LINKS default is 3

    resp = client.post(f"/forum/users/{recipient.username}/messages/", {"body": spammy})

    assert resp.status_code == 400
    # apps.core.exceptions.custom_exception_handler nests a dict-shaped
    # ValidationError.detail under "errors" — the real backend reason (not a
    # generic message) surfaces there.
    assert "link" in resp.data["errors"]["detail"].lower()
    assert not Message.objects.exists()


@pytest.mark.django_db
def test_empty_body_is_rejected():
    sender = User.objects.create_user(username="sender-empty")
    recipient = User.objects.create_user(username="recipient-empty")
    client = APIClient()
    client.force_authenticate(sender)

    resp = client.post(f"/forum/users/{recipient.username}/messages/", {"body": "   "})

    assert resp.status_code == 400
    assert not Message.objects.exists()


@pytest.mark.django_db
def test_conversation_list_requires_authentication():
    client = APIClient()  # no credentials
    resp = client.get("/forum/conversations/")
    assert resp.status_code == 401


@pytest.mark.django_db
def test_conversation_list_returns_only_my_conversations():
    a = User.objects.create_user(username="a-list")
    b = User.objects.create_user(username="b-list")
    c = User.objects.create_user(username="c-list")
    Conversation.between(a, b)
    Conversation.between(b, c)  # a is not a participant
    client = APIClient()
    client.force_authenticate(a)

    resp = client.get("/forum/conversations/")

    assert resp.status_code == 200
    assert len(resp.data["results"]) == 1
    assert resp.data["results"][0]["other_participant"]["username"] == "b-list"


@pytest.mark.django_db
def test_conversation_list_visible_from_the_later_created_participant_too():
    """Conversation.between() always assigns the LOWER-pk user to
    participant_a — every other test in this file authenticates as that user.
    This one authenticates as participant_b so the `Q(participant_b=user)`
    arm of the list filter (and the equivalent membership arm in
    ConversationMessagesView) is actually exercised — deleting either OR arm
    must turn this test red."""
    a = User.objects.create_user(username="a-partb")
    b = User.objects.create_user(username="b-partb")
    conversation = Conversation.between(a, b)
    later_participant = b if conversation.participant_b_id == b.pk else a
    client = APIClient()
    client.force_authenticate(later_participant)

    resp = client.get("/forum/conversations/")
    assert resp.status_code == 200
    assert len(resp.data["results"]) == 1

    resp = client.get(f"/forum/conversations/{conversation.pk}/messages/")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_conversation_list_excludes_a_blocked_pair():
    a = User.objects.create_user(username="a-blocked-list")
    b = User.objects.create_user(username="b-blocked-list")
    Conversation.between(a, b)
    UserBlock.block(a, b)
    client = APIClient()
    client.force_authenticate(a)

    resp = client.get("/forum/conversations/")

    assert resp.status_code == 200
    assert resp.data["results"] == []


@pytest.mark.django_db
def test_conversation_list_query_count_is_flat():
    """`cache.clear()` up front: UnversionedForumAPIMixin's presence-touch
    (TouchLastSeenMixin) throttles its `last_seen` UPDATE via `cache.add()`
    keyed per-user-pk, so whether it fires — and therefore the query count —
    depends on whatever's already in cache from an earlier test in this
    process. Without clearing first, this pin is flaky by cache state, not
    by the code under test (mirrors test_ratelimits.py's clear_ratelimit_cache
    fixture)."""
    from wagtail.images import get_image_model
    from wagtail.images.tests.utils import get_test_image_file
    from wagtail_forum.collections import get_forum_image_collection

    cache.clear()
    user = User.objects.create_user(username="qcount-list")
    for i in range(3):
        other = User.objects.create_user(username=f"qcount-other-{i}")
        # Every other side gets an avatar so the select_related chain's last
        # leg (`__avatar`) is really traversed — a fixture without avatars
        # never exercises it and the pin would survive dropping it
        # (Pattern 30, query-optimization.md; review finding, todo 339).
        profile = ForumProfile.for_user(other)
        profile.avatar = get_image_model().objects.create(
            title=f"qcount-avatar-{i}",
            file=get_test_image_file(),
            collection=get_forum_image_collection(),
            uploaded_by_user=other,
        )
        profile.save(update_fields=["avatar"])
        conversation = Conversation.between(user, other)
        Message.objects.create(conversation=conversation, sender=other, body="hi")
    client = APIClient()
    client.force_authenticate(user)

    with CaptureQueriesContext(connection) as ctx:
        resp = client.get("/forum/conversations/")

    assert resp.status_code == 200
    assert len(resp.data["results"]) == 3
    assert all(r["other_participant"]["avatar"] for r in resp.data["results"])
    assert all(r["unread_count"] == 1 for r in resp.data["results"])
    # presence-touch UPDATE (first hit this window) + 2 blocked-id lookups
    # (blocker=user, blocked=user) + 1 page query — the inbox annotations
    # (unread count, preview subqueries, todo 339) ride that one query. No
    # separate cursor-pagination count query — CursorPagination doesn't
    # issue one.
    assert len(ctx.captured_queries) == 4


@pytest.mark.django_db
def test_conversation_messages_requires_authentication():
    a = User.objects.create_user(username="a-anon-msgs")
    b = User.objects.create_user(username="b-anon-msgs")
    conversation = Conversation.between(a, b)
    client = APIClient()  # no credentials

    resp = client.get(f"/forum/conversations/{conversation.pk}/messages/")
    assert resp.status_code == 401


@pytest.mark.django_db
def test_conversation_messages_lists_newest_first_and_marks_read():
    """Newest first (todo 339): a chat thread opens on its latest page and
    pages older. Reading marks the caller's side read — and only theirs."""
    a = User.objects.create_user(username="a-msgs")
    b = User.objects.create_user(username="b-msgs")
    conversation = Conversation.between(a, b)
    Message.objects.create(conversation=conversation, sender=a, body="one")
    Message.objects.create(conversation=conversation, sender=b, body="two")
    client = APIClient()
    client.force_authenticate(a)

    resp = client.get(f"/forum/conversations/{conversation.pk}/messages/")

    assert resp.status_code == 200
    assert [m["body"] for m in resp.data["results"]] == ["two", "one"]
    conversation.refresh_from_db()
    assert conversation.read_field_for(a) == "participant_a_read_at"
    assert conversation.participant_a_read_at is not None
    assert conversation.participant_b_read_at is None


@pytest.mark.django_db
def test_conversation_messages_404s_for_a_non_participant():
    a = User.objects.create_user(username="a-priv")
    b = User.objects.create_user(username="b-priv")
    stranger = User.objects.create_user(username="stranger-priv")
    conversation = Conversation.between(a, b)
    client = APIClient()
    client.force_authenticate(stranger)

    resp = client.get(f"/forum/conversations/{conversation.pk}/messages/")

    assert resp.status_code == 404


@pytest.mark.django_db
def test_conversation_messages_404s_once_either_side_has_blocked():
    a = User.objects.create_user(username="a-blocked-msgs")
    b = User.objects.create_user(username="b-blocked-msgs")
    conversation = Conversation.between(a, b)
    Message.objects.create(conversation=conversation, sender=a, body="hi")
    UserBlock.block(b, a)  # the OTHER side blocks — enforcement is symmetric
    client = APIClient()
    client.force_authenticate(a)

    resp = client.get(f"/forum/conversations/{conversation.pk}/messages/")

    assert resp.status_code == 404


@pytest.mark.django_db
def test_report_message_requires_authentication():
    sender = User.objects.create_user(username="sender-anon-report")
    recipient = User.objects.create_user(username="recipient-anon-report")
    conversation = Conversation.between(sender, recipient)
    message = Message.objects.create(
        conversation=conversation, sender=sender, body="hi"
    )
    client = APIClient()  # no credentials

    resp = client.post(f"/forum/messages/{message.pk}/report/", {"reason": "spam"})
    assert resp.status_code == 401
    assert not Report.objects.exists()


@pytest.mark.django_db
def test_report_message_reuses_report_model():
    sender = User.objects.create_user(username="sender-report")
    recipient = User.objects.create_user(username="recipient-report")
    conversation = Conversation.between(sender, recipient)
    message = Message.objects.create(
        conversation=conversation, sender=sender, body="spam-ish"
    )
    client = APIClient()
    client.force_authenticate(recipient)

    resp = client.post(
        f"/forum/messages/{message.pk}/report/",
        {"reason": Report.SPAM, "detail": "spam"},
    )

    assert resp.status_code == 200
    report = Report.objects.get()
    assert report.message_id == message.pk
    assert report.post_id is None
    assert report.reporter_id == recipient.pk


@pytest.mark.django_db
def test_cannot_report_own_message():
    sender = User.objects.create_user(username="sender-selfreport")
    recipient = User.objects.create_user(username="recipient-selfreport")
    conversation = Conversation.between(sender, recipient)
    message = Message.objects.create(
        conversation=conversation, sender=sender, body="hi"
    )
    client = APIClient()
    client.force_authenticate(sender)

    resp = client.post(f"/forum/messages/{message.pk}/report/", {"reason": Report.SPAM})

    assert resp.status_code == 400
    assert not Report.objects.exists()


@pytest.mark.django_db
def test_a_non_participant_cannot_report_a_message():
    """The membership guard's denied case — without this, deleting the guard
    would let any authenticated user report any message by id with no test
    turning red."""
    sender = User.objects.create_user(username="sender-strangereport")
    recipient = User.objects.create_user(username="recipient-strangereport")
    stranger = User.objects.create_user(username="stranger-report")
    conversation = Conversation.between(sender, recipient)
    message = Message.objects.create(
        conversation=conversation, sender=sender, body="hi"
    )
    client = APIClient()
    client.force_authenticate(stranger)

    resp = client.post(f"/forum/messages/{message.pk}/report/", {"reason": Report.SPAM})

    assert resp.status_code == 404
    assert not Report.objects.exists()


def test_conversation_list_swagger_fake_view_guard():
    view = ConversationListView()
    view.swagger_fake_view = True
    assert list(view.get_queryset()) == []


def test_conversation_messages_swagger_fake_view_guard():
    view = ConversationMessagesView()
    view.swagger_fake_view = True
    assert list(view.get_queryset()) == []


# ---------------------------------------------------------------------------
# DM spam screening is TRUST-ROUTED (todo 280)
#
# Posts only reach the configured backend when the author is untrusted
# (workflow.py::_route_revision_by_trust); DMs used to reach it for every
# sender at every trust level. With an LLM backend configured that put a
# synchronous, billable provider call on every DM send, and — because a
# Message has no revision/workflow state to hold — a fail-closed verdict
# REJECTS the send outright instead of queueing it for review.
#
# The heuristic floor still screens everyone; only the configured backend's
# extra pass is trust-gated.
# ---------------------------------------------------------------------------


class _RecordingSpamBackend(SpamBackend):
    """Rejects everything and records that it was consulted.

    Rejecting (rather than passing) makes "was this backend reached?" visible
    in the response status as well as in ``calls``, so a test cannot pass
    because the assertion silently looked at the wrong signal.
    """

    calls: list = []

    def check(self, obj) -> SpamResult:
        type(self).calls.append(self.extract_text(obj))
        return SpamResult(False, "AI: recorded")


@pytest.fixture
def recording_backend():
    _RecordingSpamBackend.calls = []
    yield _RecordingSpamBackend
    _RecordingSpamBackend.calls = []


_RECORDING_PATH = (
    "wagtail_forum.tests.api.test_direct_messages_api._RecordingSpamBackend"
)


@override_settings(WAGTAILFORUM_SPAM_BACKEND=_RECORDING_PATH)
@pytest.mark.django_db
def test_untrusted_sender_dm_is_screened_by_the_configured_backend(recording_backend):
    sender = User.objects.create_user(username="dm-untrusted")
    recipient = User.objects.create_user(username="dm-untrusted-rcpt")
    profile = ForumProfile.for_user(sender)
    assert profile.trust_level == TrustLevel.NEW  # below TRUST_AUTOPUBLISH_LEVEL
    client = APIClient()
    client.force_authenticate(sender)

    resp = client.post(
        f"/forum/users/{recipient.username}/messages/", {"body": "buy my thing"}
    )

    assert resp.status_code == 400
    assert resp.data["errors"]["detail"] == "AI: recorded"
    assert recording_backend.calls == ["buy my thing"]
    assert not Message.objects.exists()


@override_settings(WAGTAILFORUM_SPAM_BACKEND=_RECORDING_PATH)
@pytest.mark.django_db
def test_trusted_sender_dm_skips_the_configured_backend(recording_backend):
    sender = User.objects.create_user(username="dm-trusted")
    recipient = User.objects.create_user(username="dm-trusted-rcpt")
    profile = ForumProfile.for_user(sender)
    profile.trust_level = TrustLevel.MEMBER  # == TRUST_AUTOPUBLISH_LEVEL
    profile.save(update_fields=["trust_level"])
    client = APIClient()
    client.force_authenticate(sender)

    resp = client.post(
        f"/forum/users/{recipient.username}/messages/", {"body": "hello friend"}
    )

    assert resp.status_code == 201
    assert recording_backend.calls == []  # no billable provider call
    assert Message.objects.get().body == "hello friend"


@override_settings(WAGTAILFORUM_SPAM_BACKEND=_RECORDING_PATH)
@pytest.mark.django_db
def test_trusted_sender_dm_still_gets_the_heuristic_floor(recording_backend):
    """Trust gates the CONFIGURED backend, never the deterministic floor.

    Without this the gate would silently drop link-flood/banned-word screening
    for every established member's DMs — trading one problem for a worse one.
    """
    sender = User.objects.create_user(username="dm-trusted-spammy")
    recipient = User.objects.create_user(username="dm-trusted-spammy-rcpt")
    profile = ForumProfile.for_user(sender)
    profile.trust_level = TrustLevel.LEADER
    profile.save(update_fields=["trust_level"])
    client = APIClient()
    client.force_authenticate(sender)
    spammy = " ".join(["http://x.test"] * 4)  # SPAM_MAX_LINKS default is 3

    resp = client.post(f"/forum/users/{recipient.username}/messages/", {"body": spammy})

    assert resp.status_code == 400
    assert "link" in resp.data["errors"]["detail"].lower()
    assert recording_backend.calls == []
    assert not Message.objects.exists()


@override_settings(WAGTAILFORUM_SPAM_BACKEND=_RECORDING_PATH)
@pytest.mark.django_db
def test_untrusted_sender_dm_floor_comes_from_the_configured_backend(
    recording_backend,
):
    """The gate does NOT bolt the heuristic onto the untrusted branch.

    An untrusted sender reaches the configured backend alone — the package's
    contract before the gate and after it. Both backends shipped in this repo
    chain the heuristic themselves, so the floor holds in practice; this pins
    that it is the BACKEND's property, not something `_screen_dm_body`
    enforces, so a host configuring a non-chaining backend is not silently
    relying on a guarantee this call site never made.
    """
    sender = User.objects.create_user(username="dm-untrusted-links")
    recipient = User.objects.create_user(username="dm-untrusted-links-rcpt")
    assert ForumProfile.for_user(sender).trust_level == TrustLevel.NEW
    client = APIClient()
    client.force_authenticate(sender)
    spammy = " ".join(["http://x.test"] * 4)  # would trip the heuristic floor

    resp = client.post(f"/forum/users/{recipient.username}/messages/", {"body": spammy})

    assert resp.status_code == 400
    # The configured backend's verdict, NOT the heuristic's "Too many links".
    assert resp.data["errors"]["detail"] == "AI: recorded"
    assert recording_backend.calls == [spammy]
    assert not Message.objects.exists()


# --- Inbox contract (todo 339) -------------------------------------------


def _send(sender, recipient, body):
    client = APIClient()
    client.force_authenticate(sender)
    resp = client.post(f"/forum/users/{recipient.username}/messages/", {"body": body})
    assert resp.status_code == 201, resp.data
    return resp.data


@pytest.mark.django_db
def test_inbox_rows_carry_unread_count_preview_and_activity_order():
    me = User.objects.create_user(username="inbox-me")
    alice = User.objects.create_user(username="inbox-alice")
    bob = User.objects.create_user(username="inbox-bob")
    _send(alice, me, "first from alice")
    _send(alice, me, "second from alice")
    _send(bob, me, "hello from bob")  # newer activity -> first in the inbox
    client = APIClient()
    client.force_authenticate(me)

    resp = client.get("/forum/conversations/")

    assert resp.status_code == 200
    rows = resp.data["results"]
    assert [r["other_participant"]["username"] for r in rows] == [
        "inbox-bob",
        "inbox-alice",
    ]
    assert [r["unread_count"] for r in rows] == [1, 2]
    assert rows[1]["last_message"] == {
        "body": "second from alice",
        "is_mine": False,
        "created_at": rows[1]["last_message_at"],
    }
    assert "count" not in resp.data  # cursor page, no total

    # Activity, not creation, orders the inbox: a new message in the OLDER
    # conversation moves it to the top; my own message is never unread to me
    # and the preview says so.
    _send(me, alice, "reply to alice")
    rows = client.get("/forum/conversations/").data["results"]
    assert [r["other_participant"]["username"] for r in rows] == [
        "inbox-alice",
        "inbox-bob",
    ]
    assert rows[0]["unread_count"] == 2  # alice's two are still unread to me
    assert rows[0]["last_message"]["is_mine"] is True
    assert rows[0]["last_message"]["body"] == "reply to alice"


@pytest.mark.django_db
def test_reading_the_thread_clears_my_unread_only():
    me = User.objects.create_user(username="read-me")
    alice = User.objects.create_user(username="read-alice")
    _send(alice, me, "ping")
    conversation = Conversation.objects.get()
    client = APIClient()
    client.force_authenticate(me)
    assert client.get("/forum/conversations/").data["results"][0]["unread_count"] == 1

    client.get(f"/forum/conversations/{conversation.pk}/messages/")

    assert client.get("/forum/conversations/").data["results"][0]["unread_count"] == 0
    # Alice's side is untouched: my reply is unread to HER until she opens it.
    _send(me, alice, "pong")
    other = APIClient()
    other.force_authenticate(alice)
    assert other.get("/forum/conversations/").data["results"][0]["unread_count"] == 1


@pytest.mark.django_db
def test_unread_count_counts_conversations_not_messages_and_excludes_blocked():
    me = User.objects.create_user(username="uc-me")
    alice = User.objects.create_user(username="uc-alice")
    bob = User.objects.create_user(username="uc-bob")
    carol = User.objects.create_user(username="uc-carol")
    _send(alice, me, "a1")
    _send(alice, me, "a2")
    _send(bob, me, "b1")
    _send(carol, me, "c1")
    UserBlock.objects.create(blocker=me, blocked=carol)
    client = APIClient()
    client.force_authenticate(me)

    resp = client.get("/forum/conversations/unread-count/")

    assert resp.status_code == 200
    assert resp.data == {"count": 2}  # alice (2 msgs) + bob; carol blocked
    assert APIClient().get("/forum/conversations/unread-count/").status_code == 401


@pytest.mark.django_db
def test_conversation_with_user_resolves_the_thread_or_404s():
    me = User.objects.create_user(username="with-me")
    alice = User.objects.create_user(username="with-alice")
    bob = User.objects.create_user(username="with-bob")
    client = APIClient()
    client.force_authenticate(me)

    assert client.get("/forum/conversations/with/with-alice/").status_code == 404
    _send(alice, me, "hi")
    resp = client.get("/forum/conversations/with/with-alice/")
    assert resp.status_code == 200
    assert resp.data["id"] == Conversation.objects.get().pk
    assert resp.data["other_participant"]["username"] == "with-alice"
    assert resp.data["unread_count"] == 1
    # Unknown user, self, and a blocked pair are all 404 — no existence leak.
    assert client.get("/forum/conversations/with/nobody/").status_code == 404
    assert client.get("/forum/conversations/with/with-me/").status_code == 404
    _send(bob, me, "hey")
    UserBlock.objects.create(blocker=bob, blocked=me)
    assert client.get("/forum/conversations/with/with-bob/").status_code == 404
    assert APIClient().get("/forum/conversations/with/with-alice/").status_code == 401


@pytest.mark.django_db
def test_send_bumps_activity_but_never_a_read_marker():
    """Only READING marks a side read; sending bumps the inbox order only —
    a reply fired from a profile must not silently mark the other side's
    earlier messages as seen."""
    me = User.objects.create_user(username="bump-me")
    alice = User.objects.create_user(username="bump-alice")
    _send(me, alice, "first")
    conversation = Conversation.objects.get()
    first = conversation.last_message_at
    assert first == Message.objects.get().created_at
    assert conversation.participant_a_read_at is None
    assert conversation.participant_b_read_at is None

    _send(alice, me, "second")

    conversation.refresh_from_db()
    assert conversation.last_message_at > first
    assert conversation.participant_a_read_at is None
    assert conversation.participant_b_read_at is None


@pytest.mark.django_db
def test_a_message_after_a_read_is_unread_again():
    """The second arm of the unread filter (`created_at > my_read_at`): once
    I have read the thread, a NEW message from the other side is unread —
    deleting that arm would make every thread read-forever after one open."""
    me = User.objects.create_user(username="again-me")
    alice = User.objects.create_user(username="again-alice")
    _send(alice, me, "first")
    conversation = Conversation.objects.get()
    client = APIClient()
    client.force_authenticate(me)
    client.get(f"/forum/conversations/{conversation.pk}/messages/")
    assert client.get("/forum/conversations/").data["results"][0]["unread_count"] == 0
    assert client.get("/forum/conversations/unread-count/").data == {"count": 0}

    _send(alice, me, "second")

    assert client.get("/forum/conversations/").data["results"][0]["unread_count"] == 1
    assert client.get("/forum/conversations/unread-count/").data == {"count": 1}


@pytest.mark.django_db
def test_unread_count_endpoint_query_count_is_pinned():
    """The badge poll (120/m per user) must stay cheap: no avatar joins, no
    preview subqueries — one COUNT with an EXISTS per row."""
    cache.clear()
    me = User.objects.create_user(username="ucq-me")
    for i in range(3):
        other = User.objects.create_user(username=f"ucq-other-{i}")
        _send(other, me, "hi")
    client = APIClient()
    client.force_authenticate(me)

    with CaptureQueriesContext(connection) as ctx:
        resp = client.get("/forum/conversations/unread-count/")

    assert resp.data == {"count": 3}
    # presence-touch UPDATE + 2 blocked-id lookups + 1 count query.
    assert len(ctx.captured_queries) == 4
    assert "avatar" not in ctx.captured_queries[-1]["sql"]
    assert "EXISTS" in ctx.captured_queries[-1]["sql"]


@pytest.mark.django_db
def test_migration_0032_backfills_last_message_at_from_the_newest_message():
    """Migration 0032's RunPython (todo 339): pre-existing conversations get
    `last_message_at` from their newest message, falling back to
    `created_at` for a conversation without messages. Calls the function
    against the real registry, as test_subscriptions.py does for 0014 —
    nothing after 0032 changes Conversation/Message's shape."""
    import importlib

    from django.apps import apps

    backfill = importlib.import_module(
        "wagtail_forum.migrations.0032_conversation_inbox_fields"
    ).backfill_last_message_at

    a = User.objects.create_user(username="mig-a")
    b = User.objects.create_user(username="mig-b")
    c = User.objects.create_user(username="mig-c")
    with_messages = Conversation.between(a, b)
    Message.objects.create(conversation=with_messages, sender=a, body="old")
    newest = Message.objects.create(conversation=with_messages, sender=b, body="new")
    empty = Conversation.between(a, c)  # bulk paths could leave one messageless
    # Simulate the pre-migration state: the column holds the AddField default.
    Conversation.objects.update(last_message_at=_EPOCH_FOR_TEST)

    backfill(apps, None)

    with_messages.refresh_from_db()
    empty.refresh_from_db()
    assert with_messages.last_message_at == newest.created_at
    assert empty.last_message_at == empty.created_at
