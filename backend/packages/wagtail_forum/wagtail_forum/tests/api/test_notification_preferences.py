"""Per-channel notification preferences (todo 343): resolved on read, partial
on write, defaults from the host, junk-tolerant storage."""

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIClient
from wagtail_forum.models import ForumProfile
from wagtail_forum.preferences import (
    NOTIFICATION_VERBS,
    merge_preferences,
    resolve_preferences,
    wants_channel,
)

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")

PRE_343_BEHAVIOUR = {
    "reply": {"push": True, "email": True},
    "mention": {"push": True},
    "quote": {"push": True},
    "solution": {"push": True},
}


def _client(username="prefs"):
    user = User.objects.create_user(username=username)
    client = APIClient()
    client.force_authenticate(user)
    return user, client


@pytest.mark.django_db
def test_defaults_are_the_pre_343_behaviour_and_fully_resolved_on_read():
    user, client = _client()

    data = client.get("/forum/me/profile/").data

    assert data["notification_preferences"] == PRE_343_BEHAVIOUR
    assert ForumProfile.for_user(user).notification_preferences == {}
    assert set(data["notification_preferences"]) == set(NOTIFICATION_VERBS)
    # Only wired cells exist: email for replies, push everywhere.
    assert {v: tuple(row) for v, row in data["notification_preferences"].items()} == {
        "reply": ("push", "email"),
        "mention": ("push",),
        "quote": ("push",),
        "solution": ("push",),
    }


@pytest.mark.django_db
def test_partial_patch_merges_and_stores_only_the_overrides():
    user, client = _client("merge")

    first = client.patch(
        "/forum/me/profile/",
        {"notification_preferences": {"mention": {"push": False}}},
        format="json",
    )
    assert first.status_code == 200, first.data
    assert first.data["notification_preferences"]["mention"] == {"push": False}
    assert first.data["notification_preferences"]["reply"] == PRE_343_BEHAVIOUR["reply"]
    assert ForumProfile.for_user(user).notification_preferences == {
        "mention": {"push": False}
    }

    second = client.patch(
        "/forum/me/profile/",
        {"notification_preferences": {"reply": {"email": False}}},
        format="json",
    )
    assert second.status_code == 200, second.data
    prefs = second.data["notification_preferences"]
    assert prefs["mention"]["push"] is False  # the earlier cell survived
    assert prefs["reply"] == {"push": True, "email": False}
    assert ForumProfile.for_user(user).notification_preferences == {
        "mention": {"push": False},
        "reply": {"email": False},
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "payload, fragment",
    [
        ({"digest": {"push": False}}, "Unknown notification event"),
        ({"moderation": {"push": False}}, "Unknown notification event"),
        ({"reply": {"sms": False}}, "Unknown notification channel"),
        ({"mention": {"email": True}}, "Email is not available for mention"),
        ({"reply": {"push": "no"}}, "true or false"),
        ({"reply": True}, "must be an object"),
        (["reply"], "must be an object"),
    ],
)
def test_unknown_verb_channel_or_non_boolean_is_a_400(payload, fragment):
    user, client = _client("bad")

    resp = client.patch(
        "/forum/me/profile/", {"notification_preferences": payload}, format="json"
    )

    assert resp.status_code == 400
    assert fragment in str(resp.data)
    assert ForumProfile.for_user(user).notification_preferences == {}


@pytest.mark.django_db
def test_a_host_default_change_reaches_every_untouched_cell():
    user, client = _client("hostdefault")
    client.patch(
        "/forum/me/profile/",
        {"notification_preferences": {"quote": {"push": False}}},
        format="json",
    )
    with override_settings(
        WAGTAILFORUM_NOTIFICATION_DEFAULTS={
            "reply": {"push": False, "email": False},
            "quote": {"push": True, "email": True},
        }
    ):
        prefs = client.get("/forum/me/profile/").data["notification_preferences"]
        assert prefs["reply"] == {"push": False, "email": False}
        # The member's own cell wins; the host's unwired quote email cell is
        # not a cell at all.
        assert prefs["quote"] == {"push": False}
        # A cell the host left out falls back to the PACKAGE default for that
        # cell — never a literal (django review).
        assert prefs["mention"] == {"push": True}
    with override_settings(
        WAGTAILFORUM_NOTIFICATION_DEFAULTS={"reply": {"push": False}}
    ):
        prefs = client.get("/forum/me/profile/").data["notification_preferences"]
        assert prefs["reply"] == {"push": False, "email": True}
    # The fallback is the PACKAGE default for that cell, not a literal: with
    # the package's own mention.push flipped, a host that omits mention gets
    # the flipped value (mutation: `row.get(channel, True)` fails this).
    from unittest.mock import patch

    from wagtail_forum import preferences

    with (
        patch.dict(
            preferences.DEFAULTS["NOTIFICATION_DEFAULTS"], {"mention": {"push": False}}
        ),
        override_settings(WAGTAILFORUM_NOTIFICATION_DEFAULTS={"reply": {"push": True}}),
    ):
        prefs = client.get("/forum/me/profile/").data["notification_preferences"]
        assert prefs["mention"] == {"push": False}


def test_resolve_ignores_junk_in_stored_data_and_wants_channel_gates_only_known_events():
    junk = {
        "reply": {"push": "no", "email": False, "sms": True},
        "bogus": {"push": False},
        "mention": 3,
        "quote": {"email": False},  # an unwired cell in stored data is ignored
    }
    resolved = resolve_preferences(junk)
    assert resolved["reply"] == {"push": True, "email": False}
    assert (
        "bogus" not in resolved and resolved["mention"] == PRE_343_BEHAVIOUR["mention"]
    )
    assert resolved["quote"] == {"push": True}
    assert resolve_preferences(None) == PRE_343_BEHAVIOUR
    # A junk-valued stored verb is replaced by a merge, never dereferenced.
    assert merge_preferences({"reply": "oops"}, {"reply": {"push": False}}) == {
        "reply": {"push": False}
    }

    overrides = {"reply": {"push": False}, "solution": {"push": False}}
    assert wants_channel(overrides, "reply_added", "push") is False
    assert wants_channel(overrides, "reply_added", "email") is True
    assert wants_channel(overrides, "answer_accepted", "push") is False
    assert wants_channel(overrides, "mention", "push") is True
    # Unmapped events (moderation_decided is a sync signal, not a preference)
    # and cells outside the matrix are never gated.
    assert wants_channel({"reply": {"push": False}}, "future_event", "push") is True
    assert (
        wants_channel({"reply": {"push": False}}, "moderation_decided", "push") is True
    )
    assert wants_channel({"reply": {"push": False}}, "reply_added", "sms") is True
    assert wants_channel({"mention": {"push": False}}, "mention", "email") is True


@pytest.mark.django_db
def test_empty_patch_is_a_no_op_and_stored_junk_survives_an_unrelated_patch():
    user, client = _client("junk")
    empty = client.patch(
        "/forum/me/profile/", {"notification_preferences": {}}, format="json"
    )
    assert empty.status_code == 200, empty.data
    assert empty.data["notification_preferences"] == PRE_343_BEHAVIOUR
    assert ForumProfile.for_user(user).notification_preferences == {}

    # A row written by an older release carries junk: reads stay resolved and
    # an unrelated PATCH neither fails nor "repairs" it.
    profile = ForumProfile.for_user(user)
    profile.notification_preferences = {"bogus": {"push": False}, "reply": "no"}
    profile.save(update_fields=["notification_preferences"])
    resp = client.patch(
        "/forum/me/profile/",
        {"notification_preferences": {"mention": {"push": False}}},
        format="json",
    )
    assert resp.status_code == 200, resp.data
    assert resp.data["notification_preferences"]["mention"]["push"] is False
    assert resp.data["notification_preferences"]["reply"] == PRE_343_BEHAVIOUR["reply"]
    stored = ForumProfile.for_user(user).notification_preferences
    assert stored["bogus"] == {"push": False} and stored["mention"] == {"push": False}
    assert stored["reply"] == "no"  # junk left alone, harmless


def test_preference_verbs_track_notification_verbs():
    from wagtail_forum.models import NotificationVerb

    assert set(NotificationVerb.values) == set(NOTIFICATION_VERBS)
