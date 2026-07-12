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
    user = User.objects.create_user(username="pushme")
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
    user = User.objects.create_user(username="notoken")
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
    user = User.objects.create_user(username="nofb")
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
    user = User.objects.create_user(username="optout")
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
    user = User.objects.create_user(username="strcheck")
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


def _permanent_fcm_errors():
    from firebase_admin import exceptions as fb_exceptions
    from firebase_admin import messaging

    return [
        messaging.UnregisteredError("token gone"),
        messaging.SenderIdMismatchError("wrong sender"),
        messaging.ThirdPartyAuthError("apns auth"),
        fb_exceptions.InvalidArgumentError("bad message"),
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("exc", _permanent_fcm_errors(), ids=lambda e: type(e).__name__)
def test_send_forum_push_does_not_retry_permanent_fcm_errors(exc):
    # Audit 2026-07-11 M33: permanent failures (stale token, malformed message)
    # can never succeed on retry — the task must log and return, not retry.
    user = User.objects.create_user(username=f"perm-{type(exc).__name__.lower()}")
    profile = ForumProfile.for_user(user)
    profile.fcm_token = "dead-token"
    profile.save()

    mock_fcm = MagicMock()
    mock_fcm.send.side_effect = exc

    with patch(
        "apps.garden.firebase_config.is_firebase_available", return_value=True
    ), patch("apps.garden.firebase_config.get_fcm_client", return_value=mock_fcm):
        from apps.forum_host.tasks import send_forum_push

        # Must complete without raising (no Retry, no exception).
        send_forum_push("reply_added", user.pk, {"topic_id": "1"})

    mock_fcm.send.assert_called_once()  # exactly one attempt — no retries


@pytest.mark.django_db
def test_send_forum_push_retries_transient_errors_until_exhausted():
    # The retry branch (the reason bind=True/max_retries exist) — previously
    # untested (audit M33). apply() runs eagerly WITH a task context, so
    # celery re-executes retries synchronously: initial + 3 retries = 4 sends,
    # then the final state is FAILURE carrying the transient error.
    from firebase_admin import exceptions as fb_exceptions

    user = User.objects.create_user(username="transient")
    profile = ForumProfile.for_user(user)
    profile.fcm_token = "live-token"
    profile.save()

    mock_fcm = MagicMock()
    mock_fcm.send.side_effect = fb_exceptions.UnavailableError("FCM backend down")

    with patch(
        "apps.garden.firebase_config.is_firebase_available", return_value=True
    ), patch("apps.garden.firebase_config.get_fcm_client", return_value=mock_fcm):
        from apps.forum_host.tasks import send_forum_push

        result = send_forum_push.apply(args=("reply_added", user.pk, {"topic_id": "1"}))

    assert mock_fcm.send.call_count == 4  # initial attempt + max_retries=3
    assert result.status == "FAILURE"
    assert isinstance(result.result, fb_exceptions.UnavailableError)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "prior_retries,expected_countdown", [(0, 30), (1, 60), (2, 120)]
)
def test_send_forum_push_backoff_countdown_values(prior_retries, expected_countdown):
    # Phase 6 review: apply() re-executes retries eagerly WITHOUT honoring
    # countdown, so the exhaustion test above proves the attempt count but is
    # structurally blind to the backoff values. push_request() fakes the retry
    # counter and retry() is mocked, so the countdown each attempt would
    # schedule is observable directly.
    from apps.forum_host.tasks import send_forum_push
    from celery.exceptions import Retry
    from firebase_admin import exceptions as fb_exceptions

    user = User.objects.create_user(username=f"backoff{prior_retries}")
    profile = ForumProfile.for_user(user)
    profile.fcm_token = "live-token"
    profile.save()

    mock_fcm = MagicMock()
    mock_fcm.send.side_effect = fb_exceptions.UnavailableError("FCM backend down")

    with patch(
        "apps.garden.firebase_config.is_firebase_available", return_value=True
    ), patch(
        "apps.garden.firebase_config.get_fcm_client", return_value=mock_fcm
    ), patch.object(
        send_forum_push, "retry", side_effect=Retry("retried")
    ) as mock_retry:
        send_forum_push.push_request(retries=prior_retries)
        try:
            with pytest.raises(Retry):
                send_forum_push.run("reply_added", user.pk, {"topic_id": "1"})
        finally:
            send_forum_push.pop_request()

    assert mock_retry.call_args.kwargs["countdown"] == expected_countdown
