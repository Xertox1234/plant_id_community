"""Host push/email fan-out honours the member's per-event preferences (todo 343)."""

from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from wagtail_forum.models import ForumProfile

from .test_tasks import _make_reply

User = get_user_model()


def _pushable(username, overrides):
    user = User.objects.create_user(username=username)
    profile = ForumProfile.for_user(user)
    profile.fcm_token = f"token-{username}"
    profile.notification_preferences = overrides
    profile.save(update_fields=["fcm_token", "notification_preferences"])
    return user


def _fcm():
    mock_fcm = MagicMock()
    return (
        mock_fcm,
        patch("apps.garden.firebase_config.is_firebase_available", return_value=True),
        patch("apps.garden.firebase_config.get_fcm_client", return_value=mock_fcm),
    )


@pytest.mark.django_db
def test_single_push_skips_an_event_the_member_turned_off_but_not_others():
    user = _pushable("single", {"solution": {"push": False}})
    mock_fcm, available, client = _fcm()
    with available, client:
        from apps.forum_host.tasks import send_forum_push

        send_forum_push("answer_accepted", user.pk, {"topic_id": "1"})
        assert mock_fcm.send.call_count == 0
        # The moderation push is a client sync signal, never a preference.
        send_forum_push("moderation_decided", user.pk, {"topic_id": "1"})
        assert mock_fcm.send.call_count == 1


@pytest.mark.django_db
def test_batch_push_skips_only_the_opted_out_recipient():
    opted_out = _pushable("batch-out", {"reply": {"push": False}})
    kept = _pushable("batch-in", {"reply": {"email": False}})  # email off, push stays
    mock_fcm, available, client = _fcm()
    with available, client, patch("apps.forum_host.tasks._send_fcm_message") as send:
        from apps.forum_host.tasks import send_forum_push_batch

        send_forum_push_batch("reply_added", [opted_out.pk, kept.pk], {"topic_id": "1"})

    assert [call.args[1] for call in send.call_args_list] == ["token-batch-in"]


@pytest.mark.django_db
def test_mention_and_quote_batches_use_their_own_cells():
    user = _pushable("verbs", {"mention": {"push": False}})
    mock_fcm, available, client = _fcm()
    with available, client:
        from apps.forum_host.tasks import send_forum_push_batch

        send_forum_push_batch("mention", [user.pk], {"topic_id": "1"})
        assert mock_fcm.send.call_count == 0
        send_forum_push_batch("quote", [user.pk], {"topic_id": "1"})
        assert mock_fcm.send.call_count == 1


@pytest.mark.django_db
def test_email_batch_skips_a_member_who_turned_reply_email_off():
    from apps.forum_host.tasks import send_forum_email_batch
    from django.core import mail

    topic_author, _, _, post = _make_reply("emailpref")
    topic_author.email = "author@example.com"
    topic_author.save(update_fields=["email"])
    profile = ForumProfile.for_user(topic_author)
    profile.notification_preferences = {"reply": {"email": False, "push": True}}
    profile.save(update_fields=["notification_preferences"])

    send_forum_email_batch("reply_added", [topic_author.pk], {"post_id": str(post.pk)})
    assert mail.outbox == []

    profile.notification_preferences = {
        "reply": {"push": False}
    }  # email back to default
    profile.save(update_fields=["notification_preferences"])
    send_forum_email_batch("reply_added", [topic_author.pk], {"post_id": str(post.pk)})
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_a_member_without_a_profile_row_gets_the_defaults_for_email():
    from apps.forum_host.tasks import send_forum_email_batch
    from django.core import mail

    topic_author, _, _, post = _make_reply("noprofile")
    topic_author.email = "fresh@example.com"
    topic_author.save(update_fields=["email"])
    ForumProfile.objects.filter(user=topic_author).delete()

    send_forum_email_batch("reply_added", [topic_author.pk], {"post_id": str(post.pk)})

    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_master_switch_off_wins_over_an_explicit_push_on_override():
    user = _pushable("master", {"reply": {"push": True}})
    user.forum_notifications = False
    user.save(update_fields=["forum_notifications"])
    mock_fcm, available, client = _fcm()
    with available, client, patch("apps.forum_host.tasks._send_fcm_message") as send:
        from apps.forum_host.tasks import send_forum_push, send_forum_push_batch

        send_forum_push("reply_added", user.pk, {"topic_id": "1"})
        send_forum_push_batch("reply_added", [user.pk], {"topic_id": "1"})

    assert send.call_count == 0


@pytest.mark.django_db
def test_batch_push_with_every_recipient_opted_out_sends_nothing_and_does_not_raise():
    first = _pushable("all-out-1", {"reply": {"push": False}})
    second = _pushable("all-out-2", {"reply": {"push": False}})
    mock_fcm, available, client = _fcm()
    with available, client, patch("apps.forum_host.tasks._send_fcm_message") as send:
        from apps.forum_host.tasks import send_forum_push_batch

        send_forum_push_batch("reply_added", [first.pk, second.pk], {"topic_id": "1"})

    assert send.call_count == 0
