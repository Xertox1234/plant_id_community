"""Unit tests for forum_host.tasks.send_forum_push (Issue 14).

All tests mock the FCM client and Firebase availability check so they
run without Firebase credentials in CI.
"""

from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from wagtail_forum.models import ForumProfile

User = get_user_model()


@pytest.mark.django_db
def test_send_forum_push_sends_when_token_present():
    user = User.objects.create_user(username="pushme", password="x")
    profile = ForumProfile.for_user(user)
    profile.fcm_token = "device-token-abc"
    profile.save()

    mock_fcm = MagicMock()
    mock_fcm.send.return_value = "projects/x/messages/1"

    with patch(
        "apps.garden.firebase_config.is_firebase_available", return_value=True
    ), patch("apps.garden.firebase_config.get_fcm_client", return_value=mock_fcm):
        from apps.forum_host.tasks import send_forum_push

        send_forum_push(
            "reply_added",
            user.pk,
            {"topic_id": "7", "topic_title": "Hello", "post_id": "3"},
        )

    mock_fcm.Message.assert_called_once()
    mock_fcm.send.assert_called_once()
    # The FCM Message must include the event key
    call_kwargs = mock_fcm.Message.call_args.kwargs
    assert call_kwargs["data"]["event"] == "reply_added"
    assert call_kwargs["token"] == "device-token-abc"


@pytest.mark.django_db
def test_send_forum_push_skips_when_no_token():
    user = User.objects.create_user(username="notoken", password="x")
    ForumProfile.for_user(user)  # fcm_token="" by default

    mock_fcm = MagicMock()
    with patch(
        "apps.garden.firebase_config.is_firebase_available", return_value=True
    ), patch("apps.garden.firebase_config.get_fcm_client", return_value=mock_fcm):
        from apps.forum_host.tasks import send_forum_push

        send_forum_push("reply_added", user.pk, {"topic_id": "1"})

    mock_fcm.send.assert_not_called()


@pytest.mark.django_db
def test_send_forum_push_skips_when_firebase_unavailable():
    user = User.objects.create_user(username="nofb", password="x")
    profile = ForumProfile.for_user(user)
    profile.fcm_token = "some-token"
    profile.save()

    mock_fcm = MagicMock()
    with patch(
        "apps.garden.firebase_config.is_firebase_available", return_value=False
    ), patch("apps.garden.firebase_config.get_fcm_client", return_value=mock_fcm):
        from apps.forum_host.tasks import send_forum_push

        send_forum_push("reply_added", user.pk, {"topic_id": "1"})

    mock_fcm.send.assert_not_called()


@pytest.mark.django_db
def test_send_forum_push_skips_when_forum_notifications_off():
    user = User.objects.create_user(username="optout", password="x")
    user.forum_notifications = False
    user.save()
    profile = ForumProfile.for_user(user)
    profile.fcm_token = "some-token"
    profile.save()

    mock_fcm = MagicMock()
    with patch(
        "apps.garden.firebase_config.is_firebase_available", return_value=True
    ), patch("apps.garden.firebase_config.get_fcm_client", return_value=mock_fcm):
        from apps.forum_host.tasks import send_forum_push

        send_forum_push("reply_added", user.pk, {"topic_id": "1"})

    mock_fcm.send.assert_not_called()


@pytest.mark.django_db
def test_send_forum_push_skips_for_nonexistent_user():
    mock_fcm = MagicMock()
    with patch(
        "apps.garden.firebase_config.is_firebase_available", return_value=True
    ), patch("apps.garden.firebase_config.get_fcm_client", return_value=mock_fcm):
        from apps.forum_host.tasks import send_forum_push

        send_forum_push("reply_added", 999999, {"topic_id": "1"})

    mock_fcm.send.assert_not_called()


@pytest.mark.django_db
def test_send_forum_push_all_data_values_coerced_to_str():
    user = User.objects.create_user(username="strcheck", password="x")
    profile = ForumProfile.for_user(user)
    profile.fcm_token = "tok"
    profile.save()

    mock_fcm = MagicMock()
    mock_fcm.send.return_value = "ok"

    with patch(
        "apps.garden.firebase_config.is_firebase_available", return_value=True
    ), patch("apps.garden.firebase_config.get_fcm_client", return_value=mock_fcm):
        from apps.forum_host.tasks import send_forum_push

        send_forum_push(
            "moderation_decided", user.pk, {"topic_id": 42, "status": "published"}
        )

    data = mock_fcm.Message.call_args.kwargs["data"]
    for v in data.values():
        assert isinstance(v, str), f"FCM data value {v!r} is not a string"
