"""Unit tests for forum_host.tasks.send_forum_push (Issue 14) and
send_forum_email (todo 253 slice 2, H1).

All tests mock the FCM client and Firebase availability check so they
run without Firebase credentials in CI.
"""

from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex, ForumProfile, Post, Topic

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


# ---- send_forum_email tests (todo 253 slice 2, H1) ---------------------------
#
# Unlike push, these assert on RENDERED EMAIL CONTENT (mail.outbox[0].subject /
# .body), not just "an email was sent" — this is the one thing that catches
# both latent bugs the wiring surfaced: the missing forum_reply.txt template
# (silent no-op, TemplateDoesNotExist swallowed to False) and the
# author_name/post_excerpt context-key mismatch (Django renders an undefined
# var as '', shipping a blank-author blank-excerpt email that a bare
# len(mail.outbox) == 1 assertion would not catch).


def _make_reply(slug_prefix, author=None):
    """Real (saved) board/topic/reply fixture, mirroring test_signals.py's
    inline-boilerplate convention. Returns (topic_author, topic, post)."""
    # Real emails matter here, not just usernames: EmailMessage.recipients()
    # filters out a blank address, so a blank-email fixture user would make
    # send_email() silently no-op (0 recipients) while still logging success.
    topic_author = User.objects.create_user(
        username=f"{slug_prefix}-topicowner",
        email=f"{slug_prefix}-topicowner@example.com",
    )
    replier = author or User.objects.create_user(
        username=f"{slug_prefix}-replier", email=f"{slug_prefix}-replier@example.com"
    )

    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title=slug_prefix, slug=slug_prefix))
    board = index.add_child(
        instance=ForumBoard(title=f"{slug_prefix}-board", slug=f"{slug_prefix}-board")
    )
    topic = Topic.objects.create(
        board=board,
        title="How to care for succulents?",
        slug="succulents",
        author=topic_author,
    )
    post = Post.objects.create(
        topic=topic,
        author=replier,
        body=[
            {
                "type": "paragraph",
                # Literal apostrophe + ampersand deliberately included: they're
                # what caught the forum_reply.txt autoescape bug (Django
                # escapes template vars in .txt renders exactly like .html;
                # without {% autoescape off %} this shipped as "I&#x27;ve
                # grown ... & thanks").
                "value": "<p>Great question! I've grown succulents for years & thanks!</p>",
            }
        ],
    )
    return topic_author, board, topic, post


@pytest.mark.django_db
def test_send_forum_email_sends_reply_notification():
    from apps.forum_host.tasks import send_forum_email
    from django.core import mail

    topic_author, board, topic, post = _make_reply("emailok")

    send_forum_email("reply_added", topic_author.pk, {"post_id": str(post.pk)})

    assert len(mail.outbox) == 1
    sent = mail.outbox[0]
    assert sent.to == [topic_author.email]
    expected_url_path = f"/forum/{board.id}-{board.slug}/{topic.id}-{topic.slug}"
    # The actual replier's display name and post excerpt must appear in BOTH
    # alternatives — proves the author_name/post_excerpt context-key fix (the
    # .txt body) AND the forum_preferences_url->preferences_url template fix
    # (only reachable via the .html alternative), not just that SOME email
    # with the right subject line went out.
    assert post.author.display_name in sent.body
    assert "Great question" in sent.body
    # The .txt alternative must NOT HTML-entity-escape the apostrophe/ampersand
    # — Django's autoescaping applies to .txt renders exactly like .html, so
    # without {% autoescape off %} this shipped as "I&#x27;ve ... &amp;
    # thanks!" in a PLAIN TEXT email. This is the one assertion the original
    # fixture (no apostrophe/ampersand) couldn't catch.
    assert "I've grown succulents for years & thanks!" in sent.body
    assert "&#x27;" not in sent.body and "&amp;" not in sent.body
    # The topic URL must resolve using the SAME board_id/slug the frontend's
    # threadPath() routes on (matches web/src/utils/forumUrls.ts).
    assert expected_url_path in sent.body

    html_body = sent.alternatives[0][0]
    assert sent.alternatives[0][1] == "text/html"
    assert post.author.display_name in html_body
    assert "Great question" in html_body
    assert expected_url_path in html_body


@pytest.mark.django_db
def test_send_forum_email_skips_when_forum_notifications_off():
    from apps.forum_host.tasks import send_forum_email
    from django.core import mail

    topic_author, _, _, post = _make_reply("emailoptout")
    topic_author.forum_notifications = False
    topic_author.save()

    send_forum_email("reply_added", topic_author.pk, {"post_id": str(post.pk)})

    assert mail.outbox == []


@pytest.mark.django_db
def test_send_forum_email_skips_for_nonexistent_user():
    from apps.forum_host.tasks import send_forum_email
    from django.core import mail

    _, _, _, post = _make_reply("emailnouser")

    send_forum_email("reply_added", 999999, {"post_id": str(post.pk)})

    assert mail.outbox == []


@pytest.mark.django_db
def test_send_forum_email_skips_when_recipient_has_no_email():
    from apps.forum_host.tasks import send_forum_email
    from django.core import mail

    topic_author, _, _, post = _make_reply("emailnoaddr")
    topic_author.email = ""
    topic_author.save()

    # Must not raise, and must not silently claim success (this is the exact
    # case EmailService.send_email() itself gets wrong — recipients() filters
    # the blank address to zero, email.send() returns 0, but the caller logs
    # "sent successfully" anyway since it never checks the return value).
    send_forum_email("reply_added", topic_author.pk, {"post_id": str(post.pk)})

    assert mail.outbox == []


@pytest.mark.django_db
def test_send_forum_email_skips_when_post_not_found():
    from apps.forum_host.tasks import send_forum_email
    from django.core import mail

    topic_author, _, _, _ = _make_reply("emailnopost")

    send_forum_email("reply_added", topic_author.pk, {"post_id": "999999"})

    assert mail.outbox == []


@pytest.mark.django_db
def test_send_forum_email_skips_when_post_id_invalid():
    from apps.forum_host.tasks import send_forum_email
    from django.core import mail

    topic_author, _, _, _ = _make_reply("emailbadid")

    # Must not raise on a missing/non-numeric post_id — this is the same
    # payload shape shared with send_forum_push, which never guarantees
    # post_id is present or numeric. Exercises BOTH branches of
    # `except (TypeError, ValueError)`: a missing key defaults to "" ->
    # int("") raises ValueError; a key present with value None -> int(None)
    # raises TypeError (dict.get's default only applies when the key is
    # ABSENT, not when its value is None).
    send_forum_email("reply_added", topic_author.pk, {})
    send_forum_email("reply_added", topic_author.pk, {"post_id": "not-a-number"})
    send_forum_email("reply_added", topic_author.pk, {"post_id": None})

    assert mail.outbox == []


@pytest.mark.django_db
def test_send_forum_email_skips_unimplemented_event():
    from apps.forum_host.tasks import send_forum_email
    from django.core import mail

    topic_author, _, _, post = _make_reply("emailunimpl")

    # mention/moderation/digest emails are later slices of todo 253 — the
    # task must no-op, not crash, until they're wired.
    send_forum_email("mention_added", topic_author.pk, {"post_id": str(post.pk)})

    assert mail.outbox == []


@pytest.mark.django_db
def test_send_forum_email_deleted_author_renders_bracket_deleted():
    from apps.forum_host.tasks import send_forum_email
    from django.core import mail

    topic_author, _, _, post = _make_reply("emaildeleted")
    # Mirrors the forum API serializer's own null-author convention
    # (wagtail_forum/api/serializers.py: "display_name": "[deleted]").
    post.author = None
    post.save()

    send_forum_email("reply_added", topic_author.pk, {"post_id": str(post.pk)})

    assert len(mail.outbox) == 1
    assert "[deleted]" in mail.outbox[0].body


@pytest.mark.django_db
def test_send_forum_email_retries_on_transient_db_error():
    """A transient OperationalError during the Post fetch must autoretry, not
    silently drop the email (docs/rules/celery.md: every network-touching task
    declares retry config). Mirrors
    test_send_forum_push_retries_transient_errors_until_exhausted's .apply()
    pattern — proves autoretry_for=(OperationalError,) actually fires and
    isn't dead config, the exact gap flagged when the original broad
    try/except/self.retry() wrapper (which only ever wrapped the swallow-all
    send call) was removed as untested dead code."""
    from apps.forum_host.tasks import send_forum_email
    from django.db import OperationalError

    topic_author, _, _, post = _make_reply("emaildberror")

    with patch.object(
        Post.objects, "select_related", side_effect=OperationalError("connection lost")
    ) as mock_select_related:
        result = send_forum_email.apply(
            args=("reply_added", topic_author.pk, {"post_id": str(post.pk)})
        )

    assert mock_select_related.call_count == 4  # initial attempt + max_retries=3
    assert result.status == "FAILURE"
    assert isinstance(result.result, OperationalError)
