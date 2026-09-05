"""Group DMs (todo 350): creation, the conservative block policy, creator-
managed membership, inbox rows, unread counts and the participant backfill."""

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import IntegrityError, connection
from django.db.migrations.executor import MigrationExecutor
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient
from wagtail_forum.models import (
    Conversation,
    ConversationKind,
    ConversationParticipant,
    Message,
    UserBlock,
)
from wagtail_forum.spam.base import SpamBackend, SpamResult

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


def _users(*names):
    return [User.objects.create_user(username=n) for n in names]


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def _create_group(client, usernames, title="Seed swap", body="hello all"):
    return client.post(
        "/forum/conversations/",
        {"title": title, "usernames": usernames, "body": body},
        format="json",
    )


@pytest.mark.django_db
def test_create_group_returns_the_inbox_row_and_persists_members_and_first_message():
    me, ada, bob = _users("g-me", "g-ada", "g-bob")
    client = _client(me)

    resp = _create_group(client, ["g-ada", "g-bob", "g-ada", "g-me"])

    assert resp.status_code == 201, resp.data
    row = resp.data
    assert row["kind"] == "group" and row["title"] == "Seed swap"
    assert row["other_participant"] is None
    assert [p["username"] for p in row["participants"]] == ["g-me", "g-ada", "g-bob"]
    assert row["participant_count"] == 3
    assert row["created_by"]["username"] == "g-me" and row["can_manage"] is True
    assert row["unread_count"] == 0
    assert row["last_message"]["body"] == "hello all"
    assert row["last_message"]["is_mine"] is True
    assert row["last_message"]["sender"]["username"] == "g-me"
    assert resp["Location"].endswith(f"/forum/conversations/{row['id']}/messages/")
    conversation = Conversation.objects.get(pk=row["id"])
    assert conversation.kind == ConversationKind.GROUP
    assert (
        conversation.participant_a_id is None and conversation.participant_b_id is None
    )
    assert conversation.participant_ids() == {me.pk, ada.pk, bob.pk}
    assert Message.objects.get(conversation=conversation).sender == me
    # The other members see it too, unread, and NOT as creator.
    theirs = _client(ada).get("/forum/conversations/").data["results"]
    assert theirs[0]["id"] == row["id"] and theirs[0]["unread_count"] == 1
    assert theirs[0]["can_manage"] is False
    assert theirs[0]["last_message"]["is_mine"] is False


@pytest.mark.django_db
@pytest.mark.parametrize(
    "usernames, fragment",
    [
        (["g-one"], "at least two other members"),
        (["g-one", "g-two", "g-three"], "cannot be added"),  # g-three: missing
        (["g-one", "g-blocked"], "cannot be added"),  # block pair, either direction
        (["g-one", "g-inactive"], "cannot be added"),
    ],
)
def test_create_group_rejects_bad_member_sets_with_one_generic_message(
    usernames, fragment
):
    me, one, two, blocked, inactive = _users(
        "g-r-me", "g-one", "g-two", "g-blocked", "g-inactive"
    )
    UserBlock.objects.create(blocker=blocked, blocked=me)
    inactive.is_active = False
    inactive.save(update_fields=["is_active"])

    resp = _create_group(_client(me), usernames)

    assert resp.status_code == 400
    assert fragment in str(resp.data)
    assert Conversation.objects.count() == 0


@pytest.mark.django_db
@override_settings(WAGTAILFORUM_DM_GROUP_MAX_PARTICIPANTS=4)
def test_group_cap_counts_the_creator_and_is_a_host_setting():
    me = _users("g-cap-me")[0]
    _users("g-c1", "g-c2", "g-c3", "g-c4")

    too_many = _create_group(_client(me), ["g-c1", "g-c2", "g-c3", "g-c4"])
    assert too_many.status_code == 400
    assert "at most 4 members" in str(too_many.data)

    ok = _create_group(_client(me), ["g-c1", "g-c2", "g-c3"])
    assert ok.status_code == 201, ok.data
    assert ok.data["participant_count"] == 4


@pytest.mark.django_db
def test_create_group_honours_idempotency_key():
    cache.clear()  # the idempotency store outlives a rebuilt test DB
    me = _users("g-idem-me")[0]
    _users("g-i1", "g-i2")
    client = _client(me)
    headers = {"HTTP_IDEMPOTENCY_KEY": "group-1"}

    first = client.post(
        "/forum/conversations/",
        {"title": "Idem", "usernames": ["g-i1", "g-i2"], "body": "hi"},
        format="json",
        **headers,
    )
    second = client.post(
        "/forum/conversations/",
        {"title": "Idem", "usernames": ["g-i1", "g-i2"], "body": "hi"},
        format="json",
        **headers,
    )

    assert first.status_code == 201 and second.status_code == 201
    assert first.data["id"] == second.data["id"]
    assert Conversation.objects.count() == 1
    assert first["Location"] == second["Location"]


@pytest.mark.django_db
def test_send_by_id_works_for_groups_and_direct_and_404s_for_strangers():
    me, ada, bob, stranger = _users("g-s-me", "g-s-ada", "g-s-bob", "g-s-x")
    group_id = _create_group(_client(me), ["g-s-ada", "g-s-bob"]).data["id"]
    direct = Conversation.between(me, ada)

    sent = _client(ada).post(
        f"/forum/conversations/{group_id}/messages/",
        {"body": "from ada"},
        format="json",
    )
    assert sent.status_code == 201, sent.data
    assert sent.data["sender"]["username"] == "g-s-ada"
    assert (
        Conversation.objects.get(pk=group_id).last_message_at
        == Message.objects.get(pk=sent.data["id"]).created_at
    )

    direct_sent = _client(me).post(
        f"/forum/conversations/{direct.pk}/messages/",
        {"body": "direct by id"},
        format="json",
    )
    assert direct_sent.status_code == 201, direct_sent.data

    assert (
        _client(stranger)
        .post(
            f"/forum/conversations/{group_id}/messages/", {"body": "x"}, format="json"
        )
        .status_code
        == 404
    )
    assert (
        _client(stranger).get(f"/forum/conversations/{group_id}/messages/").status_code
        == 404
    )


@pytest.mark.django_db
def test_block_policy_in_a_group_filters_their_messages_and_refuses_sends():
    """Recorded policy (todo 350): a group stays visible to everyone in it; a
    member I blocked (either direction) has their messages hidden from ME
    and neither of us can send while both are in the room."""
    me, ada, bob = _users("g-b-me", "g-b-ada", "g-b-bob")
    group_id = _create_group(_client(me), ["g-b-ada", "g-b-bob"]).data["id"]
    _client(bob).post(
        f"/forum/conversations/{group_id}/messages/",
        {"body": "bob before"},
        format="json",
    )
    UserBlock.objects.create(blocker=me, blocked=bob)

    mine = _client(me).get(f"/forum/conversations/{group_id}/messages/")
    assert mine.status_code == 200
    assert [m["body"] for m in mine.data["results"]] == ["hello all"]
    # Ada, uninvolved in the block, still sees everything.
    adas = _client(ada).get(f"/forum/conversations/{group_id}/messages/")
    assert [m["body"] for m in adas.data["results"]] == ["bob before", "hello all"]

    refused = _client(me).post(
        f"/forum/conversations/{group_id}/messages/", {"body": "nope"}, format="json"
    )
    assert refused.status_code == 403
    assert "cannot message this group" in str(refused.data)
    assert (
        _client(bob)
        .post(
            f"/forum/conversations/{group_id}/messages/",
            {"body": "nope"},
            format="json",
        )
        .status_code
        == 403
    )
    # The group is still listed for me, its preview never Bob's words, and
    # Bob's message is not unread to me.
    rows = _client(me).get("/forum/conversations/").data["results"]
    assert rows[0]["id"] == group_id and rows[0]["unread_count"] == 0
    assert rows[0]["last_message"]["body"] == "hello all"
    assert _client(me).get("/forum/conversations/unread-count/").data["count"] == 0


@pytest.mark.django_db
def test_membership_rules_add_remove_leave():
    me, ada, bob, cat, dan = _users(
        "g-m-me", "g-m-ada", "g-m-bob", "g-m-cat", "g-m-dan"
    )
    group_id = _create_group(_client(me), ["g-m-ada", "g-m-bob"]).data["id"]
    url = f"/forum/conversations/{group_id}/participants/"

    # Only the creator adds.
    assert (
        _client(ada).post(url, {"username": "g-m-cat"}, format="json").status_code
        == 403
    )
    added = _client(me).post(url, {"username": "g-m-cat"}, format="json")
    assert added.status_code == 200, added.data
    assert [p["username"] for p in added.data["participants"]][-1] == "g-m-cat"
    # Re-adding is a no-op 200; a blocked pair is the generic 400.
    assert (
        _client(me).post(url, {"username": "g-m-cat"}, format="json").status_code == 200
    )
    UserBlock.objects.create(blocker=dan, blocked=me)
    blocked = _client(me).post(url, {"username": "g-m-dan"}, format="json")
    assert blocked.status_code == 400 and "cannot be added" in str(blocked.data)

    # A member may leave; the creator may remove others; nobody else may.
    assert _client(bob).delete(f"{url}g-m-ada/").status_code == 403
    assert _client(ada).delete(f"{url}g-m-ada/").status_code == 204
    assert _client(me).delete(f"{url}g-m-bob/").status_code == 204
    assert Conversation.objects.get(pk=group_id).participant_ids() == {me.pk, cat.pk}
    # Removed members no longer see it.
    assert (
        _client(ada).get(f"/forum/conversations/{group_id}/messages/").status_code
        == 404
    )
    assert all(
        r["id"] != group_id
        for r in _client(bob).get("/forum/conversations/").data["results"]
    )
    # The creator cannot leave while others remain; a non-member is a 404.
    stuck = _client(me).delete(f"{url}g-m-me/")
    assert stuck.status_code == 400 and "Transfer or close" in str(stuck.data)
    assert _client(me).delete(f"{url}g-m-dan/").status_code == 404
    # A direct thread has no membership surface at all.
    direct = Conversation.between(me, ada)
    assert (
        _client(me)
        .post(
            f"/forum/conversations/{direct.pk}/participants/",
            {"username": "g-m-cat"},
            format="json",
        )
        .status_code
        == 404
    )


@pytest.mark.django_db
def test_direct_threads_still_canonicalize_and_carry_two_participants():
    a, b = _users("g-d-a", "g-d-b")
    first = Conversation.between(a, b)
    second = Conversation.between(b, a)

    assert first.pk == second.pk and first.kind == ConversationKind.DIRECT
    assert first.participant_ids() == {a.pk, b.pk}
    assert ConversationParticipant.objects.filter(conversation=first).count() == 2
    # A pair exists as soon as `between()` ran (its participant rows are
    # eager), so the inbox lists it even before the first message.
    assert (
        _client(a).get("/forum/conversations/").data["results"][0]["kind"] == "direct"
    )
    _client(a).post("/forum/users/g-d-b/messages/", {"body": "hi"}, format="json")
    row = _client(b).get("/forum/conversations/").data["results"][0]
    assert row["kind"] == "direct" and row["other_participant"]["username"] == "g-d-a"
    assert row["participant_count"] == 2 and row["created_by"] is None
    assert row["can_manage"] is False


@pytest.mark.django_db
def test_inbox_query_count_stays_flat_across_group_sizes():
    me = _users("g-q-me")[0]
    _users("g-q1", "g-q2", "g-q3", "g-q4", "g-q5")
    # The creator has an avatar so the `created_by__…__avatar` leg of the
    # inbox select_related is really traversed (cross-cutting review).
    from wagtail.images import get_image_model
    from wagtail.images.tests.utils import get_test_image_file
    from wagtail_forum.models import ForumProfile

    profile = ForumProfile.for_user(me)
    profile.avatar = get_image_model().objects.create(
        title="leaf", file=get_test_image_file()
    )
    profile.save(update_fields=["avatar"])
    _create_group(_client(me), ["g-q1", "g-q2"], title="small")
    client = _client(me)
    with CaptureQueriesContext(connection) as small:
        assert client.get("/forum/conversations/").status_code == 200
    _create_group(client, ["g-q1", "g-q2", "g-q3", "g-q4", "g-q5"], title="big")
    _create_group(client, ["g-q3", "g-q4"], title="third")
    with CaptureQueriesContext(connection) as many:
        rows = client.get("/forum/conversations/").data["results"]
    assert len(rows) == 3
    assert len(many.captured_queries) == len(small.captured_queries)


# transaction=True is unavoidable for MigrationExecutor (DDL cannot run with
# pending trigger events inside the test transaction). serialized_rollback
# is NOT usable here: the host's post_migrate bootstrap re-creates the
# "Forum Moderators" group after the flush and the serialized snapshot
# inserts it again (UniqueViolation at setup). The full suite has been run
# with this marker and every later Page-dependent test passed (2026-09-05,
# 2242 + 2249 green) — the flush concern in docs/rules/testing.md does not
# bite for this app's seeded rows; re-check the full run if that changes.
@pytest.mark.django_db(transaction=True)
def test_migration_0036_backfills_participants_with_read_markers():
    """No data loss for existing pairs (AC1): each side becomes a participant
    row carrying its read marker; the reverse copies them back."""
    # Users live outside this app's migrations — create them with the real
    # model (the historical one lacks the uuid default), then wind the forum
    # app back to the pair-column schema and seed a row there.
    a, b = _users("mig-a", "mig-b")
    executor = MigrationExecutor(connection)
    executor.migrate([("wagtail_forum", "0035_notification_preferences")])
    apps = executor.loader.project_state(
        [("wagtail_forum", "0035_notification_preferences")]
    ).apps
    OldConversation = apps.get_model("wagtail_forum", "Conversation")
    read = timezone.now()
    old = OldConversation.objects.create(
        participant_a_id=a.pk, participant_b_id=b.pk, participant_a_read_at=read
    )

    executor = MigrationExecutor(connection)
    executor.migrate([("wagtail_forum", "0036_group_conversations")])

    conv = Conversation.objects.get(pk=old.pk)
    assert conv.kind == ConversationKind.DIRECT
    marks = dict(
        ConversationParticipant.objects.filter(conversation=conv).values_list(
            "user_id", "read_at"
        )
    )
    assert marks == {a.pk: read, b.pk: None}


@pytest.mark.django_db
def test_unread_count_excludes_only_the_blocked_members_messages():
    """Discriminates the per-message FILTER from a whole-row suppression
    (django review): one blocked-sender message and one ordinary message,
    both newer than my marker → exactly 1 unread, on the row and the badge."""
    me, ada, bob = _users("g-u-me", "g-u-ada", "g-u-bob")
    group_id = _create_group(_client(me), ["g-u-ada", "g-u-bob"]).data["id"]
    _client(me).get(f"/forum/conversations/{group_id}/messages/")  # mark read
    _client(bob).post(
        f"/forum/conversations/{group_id}/messages/", {"body": "bob"}, format="json"
    )
    _client(ada).post(
        f"/forum/conversations/{group_id}/messages/", {"body": "ada"}, format="json"
    )
    UserBlock.objects.create(blocker=me, blocked=bob)

    rows = _client(me).get("/forum/conversations/").data["results"]
    assert rows[0]["unread_count"] == 1
    assert rows[0]["last_message"]["body"] == "ada"
    assert _client(me).get("/forum/conversations/unread-count/").data["count"] == 1


@pytest.mark.django_db
def test_the_last_member_leaving_deletes_the_room_instead_of_orphaning_it():
    me, ada, bob = _users("g-l-me", "g-l-ada", "g-l-bob")
    group_id = _create_group(_client(me), ["g-l-ada", "g-l-bob"]).data["id"]
    url = f"/forum/conversations/{group_id}/participants/"
    assert _client(ada).delete(f"{url}g-l-ada/").status_code == 204
    assert _client(me).delete(f"{url}g-l-bob/").status_code == 204
    # Alone now: the creator may leave, and nothing is left behind.
    assert _client(me).delete(f"{url}g-l-me/").status_code == 204
    assert not Conversation.objects.filter(pk=group_id).exists()
    assert not Message.objects.filter(conversation_id=group_id).exists()


class _FlagAllSpamBackend(SpamBackend):
    def check(self, obj) -> SpamResult:
        return SpamResult(False, "flagged by test")  # is_clean=False


@pytest.mark.django_db
@override_settings(
    WAGTAILFORUM_SPAM_BACKEND="wagtail_forum.tests.api.test_group_conversations._FlagAllSpamBackend"
)
def test_spam_flagged_group_create_is_a_400_with_the_reason_and_creates_nothing():
    me = _users("g-spam-me")[0]
    _users("g-sp1", "g-sp2")

    resp = _create_group(_client(me), ["g-sp1", "g-sp2"], body="buy now")

    assert resp.status_code == 400
    assert "flagged by test" in str(resp.data)
    assert Conversation.objects.count() == 0


@pytest.mark.django_db
def test_removed_member_cannot_send_or_report_and_direct_lookup_ignores_groups():
    me, ada, bob = _users("g-rm-me", "g-rm-ada", "g-rm-bob")
    group_id = _create_group(_client(me), ["g-rm-ada", "g-rm-bob"]).data["id"]
    sent = _client(bob).post(
        f"/forum/conversations/{group_id}/messages/", {"body": "before"}, format="json"
    )
    _client(me).delete(f"/forum/conversations/{group_id}/participants/g-rm-bob/")

    assert (
        _client(bob)
        .post(
            f"/forum/conversations/{group_id}/messages/",
            {"body": "after"},
            format="json",
        )
        .status_code
        == 404
    )
    first_message = (
        Message.objects.filter(conversation_id=group_id).order_by("id").first()
    )
    assert (
        _client(bob)
        .post(
            f"/forum/messages/{first_message.pk}/report/",
            {"reason": "spam"},
            format="json",
        )
        .status_code
        == 404
    )
    # `conversations/with/<username>/` only ever resolves DIRECT threads.
    assert _client(me).get("/forum/conversations/with/g-rm-ada/").status_code == 404
    assert sent.status_code == 201


@pytest.mark.django_db
def test_invite_list_is_bounded_before_per_item_validation():
    me = _users("g-big-me")[0]
    resp = _create_group(_client(me), [f"u{i}" for i in range(51)])
    assert resp.status_code == 400
    assert "Too many members" in str(resp.data)


@pytest.mark.django_db
def test_kind_shape_constraint_rejects_a_group_with_a_pair():
    a, b = _users("g-ck-a", "g-ck-b")
    with pytest.raises(IntegrityError):
        Conversation.objects.create(
            kind=ConversationKind.GROUP, participant_a=a, participant_b=b
        )


@pytest.mark.django_db
def test_kind_shape_constraint_rejects_a_direct_thread_without_a_pair():
    with pytest.raises(IntegrityError):
        Conversation.objects.create(kind=ConversationKind.DIRECT)


@pytest.mark.django_db
def test_messages_read_query_count_is_pinned_for_direct_and_group():
    me, ada, bob = _users("g-pin-me", "g-pin-ada", "g-pin-bob")
    direct = Conversation.between(me, ada)
    Message.objects.create(conversation=direct, sender=ada, body="hi")
    group_id = _create_group(_client(me), ["g-pin-ada", "g-pin-bob"]).data["id"]
    client = _client(me)
    client.get(f"/forum/conversations/{direct.pk}/messages/")  # warm the presence touch
    with CaptureQueriesContext(connection) as direct_ctx:
        assert (
            client.get(f"/forum/conversations/{direct.pk}/messages/").status_code == 200
        )
    with CaptureQueriesContext(connection) as group_ctx:
        assert (
            client.get(f"/forum/conversations/{group_id}/messages/").status_code == 200
        )
    print(
        "DIRECT",
        len(direct_ctx.captured_queries),
        "GROUP",
        len(group_ctx.captured_queries),
    )
    assert len(direct_ctx.captured_queries) == 4
    assert len(group_ctx.captured_queries) == 6
