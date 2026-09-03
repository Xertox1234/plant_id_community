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
    cache.clear()
    user = User.objects.create_user(username="qcount-list")
    for i in range(3):
        other = User.objects.create_user(username=f"qcount-other-{i}")
        Conversation.between(user, other)
    client = APIClient()
    client.force_authenticate(user)

    with CaptureQueriesContext(connection) as ctx:
        resp = client.get("/forum/conversations/")

    assert resp.status_code == 200
    assert len(resp.data["results"]) == 3
    # presence-touch UPDATE (first hit this window) + 2 blocked-id lookups
    # (blocker=user, blocked=user) + 1 page query. No separate
    # cursor-pagination count query — CursorPagination doesn't issue one.
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
def test_conversation_messages_lists_oldest_first():
    a = User.objects.create_user(username="a-msgs")
    b = User.objects.create_user(username="b-msgs")
    conversation = Conversation.between(a, b)
    Message.objects.create(conversation=conversation, sender=a, body="one")
    Message.objects.create(conversation=conversation, sender=b, body="two")
    client = APIClient()
    client.force_authenticate(a)

    resp = client.get(f"/forum/conversations/{conversation.pk}/messages/")

    assert resp.status_code == 200
    assert [m["body"] for m in resp.data["results"]] == ["one", "two"]


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
