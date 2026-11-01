"""Unit tests for forum_host.tasks: send_forum_push (Issue 14),
send_forum_push_batch and send_forum_email_batch (todo 268 batched fan-out,
replacing the removed per-recipient send_forum_email).

All tests mock the FCM client and Firebase availability check so they
run without Firebase credentials in CI.
"""

from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from wagtail_forum.models import ForumProfile, Post, Topic
from wagtail_forum.tests.factories import make_forum

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
        "apps.core.firebase_config.is_firebase_available", return_value=True
    ), patch("apps.core.firebase_config.get_fcm_client", return_value=mock_fcm):
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
    # Notification+data hybrid (todo 253 slice 6, AC6): the tray-visible
    # notification block rides alongside the unchanged data payload, built
    # via the client module's Notification factory. This payload has no
    # actor_name, so the body exercises the "Someone" fallback.
    assert call_kwargs["notification"] is mock_fcm.Notification.return_value
    assert mock_fcm.Notification.call_args.kwargs == {
        "title": 'New reply in "Hello"',
        "body": "Someone replied",
    }
    # Stable collapse key on both platforms: a retried send after an
    # accepted-but-timed-out response must REPLACE the tray entry, not stack
    # a duplicate visible notification (slice-6 review, celery checklist).
    # Per-EVENT-TYPE, not per-post — FCM retains at most 4 distinct collapse
    # keys per offline device (review sweep).
    assert mock_fcm.AndroidConfig.call_args.kwargs == {
        "collapse_key": "forum-reply_added"
    }
    assert mock_fcm.APNSConfig.call_args.kwargs == {
        "headers": {"apns-collapse-id": "forum-reply_added"}
    }


@pytest.mark.django_db
def test_send_forum_push_skips_when_no_token():
    user = User.objects.create_user(username="notoken")
    ForumProfile.for_user(user)  # fcm_token="" by default

    mock_fcm = MagicMock()
    with patch(
        "apps.core.firebase_config.is_firebase_available", return_value=True
    ), patch("apps.core.firebase_config.get_fcm_client", return_value=mock_fcm):
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
        "apps.core.firebase_config.is_firebase_available", return_value=False
    ), patch("apps.core.firebase_config.get_fcm_client", return_value=mock_fcm):
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
        "apps.core.firebase_config.is_firebase_available", return_value=True
    ), patch("apps.core.firebase_config.get_fcm_client", return_value=mock_fcm):
        from apps.forum_host.tasks import send_forum_push

        send_forum_push("reply_added", user.pk, {"topic_id": "1"})

    mock_fcm.send.assert_not_called()


@pytest.mark.django_db
def test_send_forum_push_skips_for_nonexistent_user():
    mock_fcm = MagicMock()
    with patch(
        "apps.core.firebase_config.is_firebase_available", return_value=True
    ), patch("apps.core.firebase_config.get_fcm_client", return_value=mock_fcm):
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
        "apps.core.firebase_config.is_firebase_available", return_value=True
    ), patch("apps.core.firebase_config.get_fcm_client", return_value=mock_fcm):
        from apps.forum_host.tasks import send_forum_push

        send_forum_push(
            "moderation_decided", user.pk, {"topic_id": 42, "status": "published"}
        )

    data = mock_fcm.Message.call_args.kwargs["data"]
    for v in data.values():
        assert isinstance(v, str), f"FCM data value {v!r} is not a string"
    # moderation_decided must stay tray-silent (data-only): workflow.py fires
    # it on every routine autopublished post, so a visible block would popup
    # "Your post was published" for users' own ordinary posts (slice-6
    # review, cross-file tracer).
    assert "notification" not in mock_fcm.Message.call_args.kwargs


# ---- _notification_content (todo 253 slice 6, AC6) ---------------------------
#
# Pure-function tests, no DB: the tray title/body derivation must degrade
# gracefully on any missing field — a push may look generic but must never
# fail over cosmetics.


def test_notification_content_reply_uses_topic_title_and_actor():
    from apps.forum_host.tasks import _notification_content

    title, body = _notification_content(
        "reply_added", {"topic_title": "How to repot?", "actor_name": "Alice Chen"}
    )
    assert title == 'New reply in "How to repot?"'
    assert body == "Alice Chen replied"


def test_notification_content_mention():
    from apps.forum_host.tasks import _notification_content

    title, body = _notification_content(
        "mention", {"topic_title": "Propagation tips", "actor_name": "bob"}
    )
    assert title == 'You were mentioned in "Propagation tips"'
    assert body == "bob mentioned you"


@pytest.mark.parametrize(
    "event,data",
    [
        # Fires on EVERY routine autopublish — a visible block would tray-spam
        # users for their own posts (slice-6 review). Both statuses silent.
        ("moderation_decided", {"status": "published"}),
        ("moderation_decided", {"status": "pending"}),
        # Unknown/future events stay data-only until their copy is designed.
        ("some_future_event", {}),
    ],
)
def test_notification_content_is_none_for_tray_silent_events(event, data):
    from apps.forum_host.tasks import _notification_content

    assert _notification_content(event, data) is None


def test_notification_content_degrades_gracefully_on_missing_fields():
    from apps.forum_host.tasks import _notification_content

    title, body = _notification_content("reply_added", {})
    assert title == "New forum reply"
    assert body == "Someone replied"

    title, body = _notification_content("mention", {"actor_name": None})
    assert title == "You were mentioned on the forum"
    assert body == "Someone mentioned you"


def test_notification_content_caps_runaway_topic_title():
    from apps.forum_host.constants import PUSH_TITLE_TOPIC_MAX_CHARS
    from apps.forum_host.tasks import _notification_content

    long_title = "x" * (PUSH_TITLE_TOPIC_MAX_CHARS * 2)
    title, _body = _notification_content("reply_added", {"topic_title": long_title})
    embedded = title[len('New reply in "') : -1]
    assert len(embedded) == PUSH_TITLE_TOPIC_MAX_CHARS
    assert embedded.endswith("…")


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
        "apps.core.firebase_config.is_firebase_available", return_value=True
    ), patch("apps.core.firebase_config.get_fcm_client", return_value=mock_fcm):
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
        "apps.core.firebase_config.is_firebase_available", return_value=True
    ), patch("apps.core.firebase_config.get_fcm_client", return_value=mock_fcm):
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
        "apps.core.firebase_config.is_firebase_available", return_value=True
    ), patch(
        "apps.core.firebase_config.get_fcm_client", return_value=mock_fcm
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


# ---- send_forum_email_batch tests (todo 268 batched fan-out; behavior H1) ----
#
# The single-recipient send_forum_email was removed (todo 268): the reply
# fan-out now enqueues ONE send_forum_email_batch(event, [pks], data) instead
# of N send_forum_email.delay() calls. These tests call the batch task directly
# with a single-element recipient list, preserving each original test's
# discriminating intent.
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

    board = make_forum(name=f"{slug_prefix}-board", slug=f"{slug_prefix}-board")
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
    from apps.forum_host.tasks import send_forum_email_batch
    from django.core import mail

    topic_author, board, topic, post = _make_reply("emailok")

    send_forum_email_batch("reply_added", [topic_author.pk], {"post_id": str(post.pk)})

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
    from apps.forum_host.tasks import send_forum_email_batch
    from django.core import mail

    topic_author, _, _, post = _make_reply("emailoptout")
    topic_author.forum_notifications = False
    topic_author.save()

    send_forum_email_batch("reply_added", [topic_author.pk], {"post_id": str(post.pk)})

    assert mail.outbox == []


@pytest.mark.django_db
def test_send_forum_email_skips_for_nonexistent_user():
    from apps.forum_host.tasks import send_forum_email_batch
    from django.core import mail

    _, _, _, post = _make_reply("emailnouser")

    send_forum_email_batch("reply_added", [999999], {"post_id": str(post.pk)})

    assert mail.outbox == []


@pytest.mark.django_db
def test_send_forum_email_skips_when_recipient_has_no_email():
    from apps.forum_host.tasks import send_forum_email_batch
    from django.core import mail

    topic_author, _, _, post = _make_reply("emailnoaddr")
    topic_author.email = ""
    topic_author.save()

    # Must not raise, and must not silently claim success (this is the exact
    # case EmailService.send_email() itself gets wrong — recipients() filters
    # the blank address to zero, email.send() returns 0, but the caller logs
    # "sent successfully" anyway since it never checks the return value).
    send_forum_email_batch("reply_added", [topic_author.pk], {"post_id": str(post.pk)})

    assert mail.outbox == []


@pytest.mark.django_db
def test_send_forum_email_skips_when_post_not_found():
    from apps.forum_host.tasks import send_forum_email_batch
    from django.core import mail

    topic_author, _, _, _ = _make_reply("emailnopost")

    send_forum_email_batch("reply_added", [topic_author.pk], {"post_id": "999999"})

    assert mail.outbox == []


@pytest.mark.django_db
def test_send_forum_email_skips_when_post_id_invalid():
    from apps.forum_host.tasks import send_forum_email_batch
    from django.core import mail

    topic_author, _, _, _ = _make_reply("emailbadid")

    # Must not raise on a missing/non-numeric post_id — this is the same
    # payload shape shared with send_forum_push, which never guarantees
    # post_id is present or numeric. Exercises BOTH branches of
    # `except (TypeError, ValueError)`: a missing key defaults to "" ->
    # int("") raises ValueError; a key present with value None -> int(None)
    # raises TypeError (dict.get's default only applies when the key is
    # ABSENT, not when its value is None).
    send_forum_email_batch("reply_added", [topic_author.pk], {})
    send_forum_email_batch(
        "reply_added", [topic_author.pk], {"post_id": "not-a-number"}
    )
    send_forum_email_batch("reply_added", [topic_author.pk], {"post_id": None})

    assert mail.outbox == []


@pytest.mark.django_db
def test_send_forum_email_skips_unimplemented_event():
    from apps.forum_host.tasks import send_forum_email_batch
    from django.core import mail

    topic_author, _, _, post = _make_reply("emailunimpl")

    # mention/moderation/digest emails are later slices of todo 253 — the
    # task must no-op, not crash, until they're wired.
    send_forum_email_batch(
        "mention_added", [topic_author.pk], {"post_id": str(post.pk)}
    )

    assert mail.outbox == []


@pytest.mark.django_db
def test_send_forum_email_deleted_author_renders_bracket_deleted():
    from apps.forum_host.tasks import send_forum_email_batch
    from django.core import mail

    topic_author, _, _, post = _make_reply("emaildeleted")
    # Mirrors the forum API serializer's own null-author convention
    # (wagtail_forum/api/serializers.py: "display_name": "[deleted]").
    post.author = None
    post.save()

    send_forum_email_batch("reply_added", [topic_author.pk], {"post_id": str(post.pk)})

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
    from apps.forum_host.tasks import send_forum_email_batch
    from django.db import OperationalError

    topic_author, _, _, post = _make_reply("emaildberror")

    with patch.object(
        Post.objects, "select_related", side_effect=OperationalError("connection lost")
    ) as mock_select_related:
        result = send_forum_email_batch.apply(
            args=("reply_added", [topic_author.pk], {"post_id": str(post.pk)})
        )

    assert mock_select_related.call_count == 4  # initial attempt + max_retries=3
    assert result.status == "FAILURE"
    assert isinstance(result.result, OperationalError)


# ---- send_forum_push_batch tests (todo 268 batched fan-out) ------------------
#
# The batch variant fans one FCM push out to many recipients from a SINGLE
# enqueue: one bulk ForumProfile fetch, then a server-side send loop. A
# per-recipient TRANSIENT failure is handed off to the retry-capable
# single-recipient send_forum_push task (not a whole-batch retry, which would
# re-send to everyone); a PERMANENT failure is dropped, same as the single task.


@pytest.mark.django_db
def test_send_forum_push_batch_sends_to_each_recipient_from_one_bulk_fetch():
    """One enqueue → one FCM send per recipient, and the DB fetch does NOT
    scale with recipient count (the whole point of batching: a single
    select_related profile fetch instead of N per-recipient lookups). Proven
    by comparing N=1 vs N=5 — sends scale with N, DB queries do not."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    def _run_batch(n, slug):
        recipient_pks = []
        for i in range(n):
            u = User.objects.create_user(username=f"batchsend-{slug}-{i}")
            profile = ForumProfile.for_user(u)
            profile.fcm_token = f"token-{slug}-{i}"
            profile.save()
            recipient_pks.append(u.pk)

        mock_fcm = MagicMock()
        mock_fcm.send.return_value = "ok"

        with patch(
            "apps.core.firebase_config.is_firebase_available", return_value=True
        ), patch("apps.core.firebase_config.get_fcm_client", return_value=mock_fcm):
            from apps.forum_host.tasks import send_forum_push_batch

            with CaptureQueriesContext(connection) as ctx:
                send_forum_push_batch(
                    "reply_added",
                    recipient_pks,
                    {"topic_id": "1", "topic_title": "Hi"},
                )

        sent_tokens = {c.kwargs["token"] for c in mock_fcm.Message.call_args_list}
        return mock_fcm.send.call_count, len(ctx.captured_queries), sent_tokens

    sends_1, queries_1, tokens_1 = _run_batch(1, "one")
    sends_5, queries_5, tokens_5 = _run_batch(5, "five")

    # One FCM send per recipient — sends scale with the recipient list.
    assert sends_1 == 1
    assert sends_5 == 5
    assert tokens_1 == {"token-one-0"}
    assert tokens_5 == {f"token-five-{i}" for i in range(5)}
    # ...but the DB fetch is a single bulk query regardless of N (select_related
    # on the profile's user; no per-recipient lookup).
    assert queries_1 == queries_5


@pytest.mark.django_db
def test_send_forum_push_batch_skips_recipients_without_token():
    """A recipient with no FCM token is silently skipped inside the batch loop
    — only the tokened recipient gets a send."""
    with_token = User.objects.create_user(username="batch-hastoken")
    profile = ForumProfile.for_user(with_token)
    profile.fcm_token = "real-token"
    profile.save()

    no_token = User.objects.create_user(username="batch-notoken")
    ForumProfile.for_user(no_token)  # fcm_token="" by default

    mock_fcm = MagicMock()
    mock_fcm.send.return_value = "ok"

    with patch(
        "apps.core.firebase_config.is_firebase_available", return_value=True
    ), patch("apps.core.firebase_config.get_fcm_client", return_value=mock_fcm):
        from apps.forum_host.tasks import send_forum_push_batch

        send_forum_push_batch(
            "reply_added", [with_token.pk, no_token.pk], {"topic_id": "1"}
        )

    mock_fcm.send.assert_called_once()
    assert mock_fcm.Message.call_args.kwargs["token"] == "real-token"


@pytest.mark.django_db
def test_send_forum_push_batch_skips_forum_notifications_off_recipients():
    """A recipient who has turned forum_notifications off is skipped inside the
    batch loop even though they have a token — only the opted-in user gets a
    send (mirrors the single task's gate, applied per-recipient in the batch)."""
    opted_in = User.objects.create_user(username="batch-optin")
    profile_in = ForumProfile.for_user(opted_in)
    profile_in.fcm_token = "optin-token"
    profile_in.save()

    opted_out = User.objects.create_user(username="batch-optout")
    opted_out.forum_notifications = False
    opted_out.save()
    profile_out = ForumProfile.for_user(opted_out)
    profile_out.fcm_token = "optout-token"
    profile_out.save()

    mock_fcm = MagicMock()
    mock_fcm.send.return_value = "ok"

    with patch(
        "apps.core.firebase_config.is_firebase_available", return_value=True
    ), patch("apps.core.firebase_config.get_fcm_client", return_value=mock_fcm):
        from apps.forum_host.tasks import send_forum_push_batch

        send_forum_push_batch(
            "reply_added", [opted_in.pk, opted_out.pk], {"topic_id": "1"}
        )

    mock_fcm.send.assert_called_once()
    assert mock_fcm.Message.call_args.kwargs["token"] == "optin-token"


@pytest.mark.django_db
def test_send_forum_push_batch_re_enqueues_single_on_transient_error():
    """A per-recipient TRANSIENT FCM failure must be handed off to the
    retry-capable single-recipient send_forum_push task — NOT retried as a
    whole batch (which would re-send to every recipient). The re-enqueue must
    target the failed user's pk and carry the ORIGINAL data dict (send_forum_push
    coerces to str itself)."""
    from firebase_admin import exceptions as fb_exceptions

    user = User.objects.create_user(username="batch-transient")
    profile = ForumProfile.for_user(user)
    profile.fcm_token = "live-token"
    profile.save()

    data = {"topic_id": "1", "topic_title": "Hi"}

    mock_fcm = MagicMock()
    mock_fcm.send.side_effect = fb_exceptions.UnavailableError("FCM backend down")

    with patch(
        "apps.core.firebase_config.is_firebase_available", return_value=True
    ), patch("apps.core.firebase_config.get_fcm_client", return_value=mock_fcm), patch(
        "apps.forum_host.tasks.send_forum_push.delay"
    ) as mock_single:
        from apps.forum_host.tasks import send_forum_push_batch

        send_forum_push_batch("reply_added", [user.pk], data)

    mock_single.assert_called_once_with("reply_added", user.pk, data)


@pytest.mark.django_db
@pytest.mark.parametrize("exc", _permanent_fcm_errors(), ids=lambda e: type(e).__name__)
def test_send_forum_push_batch_does_not_re_enqueue_on_permanent_error(exc):
    """A per-recipient PERMANENT FCM failure (stale token, malformed message)
    can never succeed on retry — the batch drops it and must NOT re-enqueue the
    single-recipient task (uses the same permanent-error classes as the single
    task's permanent-error test)."""
    user = User.objects.create_user(username=f"batch-perm-{type(exc).__name__.lower()}")
    profile = ForumProfile.for_user(user)
    profile.fcm_token = "dead-token"
    profile.save()

    mock_fcm = MagicMock()
    mock_fcm.send.side_effect = exc

    with patch(
        "apps.core.firebase_config.is_firebase_available", return_value=True
    ), patch("apps.core.firebase_config.get_fcm_client", return_value=mock_fcm), patch(
        "apps.forum_host.tasks.send_forum_push.delay"
    ) as mock_single:
        from apps.forum_host.tasks import send_forum_push_batch

        send_forum_push_batch("reply_added", [user.pk], {"topic_id": "1"})

    mock_single.assert_not_called()


# --- todo 593 #1: a credentials error stops the batch only with no success ---


def _batch_recipients(prefix, count):
    users = []
    for i in range(count):
        user = User.objects.create_user(username=f"{prefix}-{i}")
        profile = ForumProfile.for_user(user)
        profile.fcm_token = f"{prefix}-token-{i}"
        profile.save()
        users.append(user)
    return users


def _run_batch(users, send):
    mock_fcm, single, _requeue = _run_batch_with_requeue(users, send)
    return mock_fcm, single


def _run_batch_with_requeue(users, send, requeued=False, ids=None):
    """Also patches the once-only re-enqueue of a credentials stop (todo 606),
    so no test puts a real message on the broker."""
    mock_fcm = MagicMock()
    mock_fcm.send.side_effect = send
    with patch(
        "apps.core.firebase_config.is_firebase_available", return_value=True
    ), patch("apps.core.firebase_config.get_fcm_client", return_value=mock_fcm), patch(
        "apps.forum_host.tasks.send_forum_push.delay"
    ) as single, patch(
        "apps.forum_host.tasks.send_forum_push_batch.apply_async"
    ) as requeue:
        from apps.forum_host.tasks import send_forum_push_batch

        send_forum_push_batch(
            "reply_added",
            ids if ids is not None else [u.pk for u in users],
            {"topic_id": "1"},
            requeued=requeued,
        )
    return mock_fcm, single, requeue


@pytest.mark.django_db
@pytest.mark.parametrize("exc", _permanent_fcm_errors(), ids=lambda e: type(e).__name__)
def test_a_credentials_error_on_every_send_stops_the_batch_at_the_threshold(
    exc, caplog
):
    """Round 3 (owner decision 2026-10-11, a deliberate change from stopping
    on the FIRST credentials error): "Stop only when every send so far in the
    batch failed with a credentials error (none succeeded)". With every send
    failing, the batch stops after FCM_CREDENTIALS_STOP_FAILURES (3) of the 5
    and logs one ERROR naming the 2 not tried. A token-level permanent error
    still moves on to the next recipient."""
    import logging

    from apps.core.fcm import FCM_CREDENTIALS_STOP_FAILURES

    assert FCM_CREDENTIALS_STOP_FAILURES == 3
    users = _batch_recipients(f"stop-{type(exc).__name__.lower()}", 5)

    with caplog.at_level(logging.ERROR, logger="forum_host.tasks"):
        mock_fcm, single = _run_batch(users, exc)

    credentials = type(exc).__name__ in _CREDENTIALS_CLASSES
    assert mock_fcm.send.call_count == (3 if credentials else 5)
    single.assert_not_called()
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    if credentials:
        assert len(errors) == 1, errors
        assert "2 recipient(s) not tried" in errors[0]
    else:
        assert errors == []


@pytest.mark.django_db
def test_a_credentials_error_on_the_first_recipient_does_not_stop_the_batch(caplog):
    """Todo 593 round 3: the error can be the device's (a dev-build token, an
    APNs-only fault), so the batch goes on and every other recipient is
    sent. One ERROR, which does not say the batch stopped."""
    import logging

    from firebase_admin import messaging

    users = _batch_recipients("first-fails", 4)
    calls = []

    def send(message):
        calls.append(message)
        if len(calls) == 1:
            raise messaging.ThirdPartyAuthError("apns auth")
        return "ok"

    with caplog.at_level(logging.ERROR, logger="forum_host.tasks"):
        mock_fcm, single = _run_batch(users, send)

    assert mock_fcm.send.call_count == 4
    single.assert_not_called()
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1, errors
    assert "1 recipient(s)" in errors[0]
    assert "stopped" not in errors[0]


@pytest.mark.django_db
def test_credentials_errors_after_a_success_do_not_stop_the_batch():
    """One send worked, so the server's credentials are fine: the failures
    after it are devices, however many, and every recipient is tried."""
    from firebase_admin import messaging

    users = _batch_recipients("success-first", 5)
    calls = []

    def send(message):
        calls.append(message)
        if len(calls) == 1:
            return "ok"
        raise messaging.SenderIdMismatchError("dev build")

    mock_fcm, _single = _run_batch(users, send)

    assert mock_fcm.send.call_count == 5


@pytest.mark.django_db
def test_a_credentials_stop_re_enqueues_the_untried_recipients_once(caplog):
    """Todo 606 item 1 (owner decision 2026-10-11): the stop can be a few bad
    devices at the head of the batch, so the recipients not tried yet go out
    in one follow-up batch. The users that already failed are not in it, and
    neither are the ones this batch would never have sent to (opted out,
    muted, tokenless): the count in the ERROR names only real losses."""
    import logging

    from apps.forum_host import constants
    from firebase_admin import messaging

    users = _batch_recipients("requeue", 6)
    opted_out, tokenless = users[3], users[4]
    opted_out.forum_notifications = False
    opted_out.save()
    ForumProfile.objects.filter(user=tokenless).update(fcm_token="")
    # Passed in reverse: the batch orders by user id, so the failing head is
    # the three lowest ids whatever order the caller used.
    ids = [u.pk for u in reversed(users)]

    with caplog.at_level(logging.ERROR, logger="forum_host.tasks"):
        mock_fcm, single, requeue = _run_batch_with_requeue(
            users, messaging.ThirdPartyAuthError("apns auth"), ids=ids
        )

    assert mock_fcm.send.call_count == 3
    sent_tokens = [c.kwargs["token"] for c in mock_fcm.Message.call_args_list]
    assert sent_tokens == [f"requeue-token-{i}" for i in range(3)]
    single.assert_not_called()
    requeue.assert_called_once_with(
        args=("reply_added", [users[5].pk], {"topic_id": "1"}),
        kwargs={"requeued": True},
        countdown=constants.FORUM_PUSH_REQUEUE_DELAY,
    )
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1, errors
    assert "1 recipient(s) not tried" in errors[0]
    assert "re-enqueued once" in errors[0]


@pytest.mark.django_db
def test_a_re_enqueued_batch_that_stops_does_not_enqueue_again(caplog):
    """Todo 606 item 1: the follow-up batch is the last one, so a real
    project-wide credentials outage cannot loop."""
    import logging

    from firebase_admin import messaging

    users = _batch_recipients("requeued", 5)

    with caplog.at_level(logging.ERROR, logger="forum_host.tasks"):
        mock_fcm, _single, requeue = _run_batch_with_requeue(
            users, messaging.SenderIdMismatchError("wrong project"), requeued=True
        )

    assert mock_fcm.send.call_count == 3
    requeue.assert_not_called()
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1, errors
    assert "2 recipient(s) not tried" in errors[0]
    assert "already the re-enqueue" in errors[0]


@pytest.mark.django_db
def test_a_credentials_stop_with_nobody_left_does_not_re_enqueue():
    """Todo 606 item 1: nothing untried, nothing to send later."""
    from firebase_admin import messaging

    users = _batch_recipients("nobody-left", 3)

    mock_fcm, _single, requeue = _run_batch_with_requeue(
        users, messaging.ThirdPartyAuthError("apns auth")
    )

    assert mock_fcm.send.call_count == 3
    requeue.assert_not_called()


# --- todo 457 item 3: a dead device token is cleared -------------------------

# SenderIdMismatchError left this set in todo 566 (owner decision
# 2026-10-11): it means the server's credentials are another project's, so
# clearing on it would wipe every healthy token after one bad deploy.
_DEAD_TOKEN_CLASSES = {"UnregisteredError"}
_CREDENTIALS_CLASSES = {"SenderIdMismatchError", "ThirdPartyAuthError"}


@pytest.mark.django_db
@pytest.mark.parametrize("batch", [False, True], ids=["single", "batch"])
@pytest.mark.parametrize("exc", _permanent_fcm_errors(), ids=lambda e: type(e).__name__)
def test_a_dead_token_is_cleared_and_other_permanent_errors_keep_it(exc, batch):
    """Only the token-is-dead class clears it. ThirdPartyAuthError (APNs
    credentials), SenderIdMismatchError (another project's credentials) and
    InvalidArgumentError (a bad message) are permanent too, but the token is
    fine, so clearing on them would wipe healthy devices."""
    name = type(exc).__name__.lower()
    user = User.objects.create_user(username=f"clear-{name}-{batch}")
    profile = ForumProfile.for_user(user)
    profile.fcm_token = "maybe-dead-token"
    profile.save()

    mock_fcm = MagicMock()
    mock_fcm.send.side_effect = exc

    with patch(
        "apps.core.firebase_config.is_firebase_available", return_value=True
    ), patch("apps.core.firebase_config.get_fcm_client", return_value=mock_fcm), patch(
        "apps.forum_host.tasks.send_forum_push.delay"
    ):
        from apps.forum_host.tasks import send_forum_push, send_forum_push_batch

        if batch:
            send_forum_push_batch("reply_added", [user.pk], {"topic_id": "1"})
        else:
            send_forum_push("reply_added", user.pk, {"topic_id": "1"})

    profile.refresh_from_db()
    if type(exc).__name__ in _DEAD_TOKEN_CLASSES:
        assert profile.fcm_token == ""
    else:
        assert profile.fcm_token == "maybe-dead-token"


@pytest.mark.django_db
@pytest.mark.parametrize("batch", [False, True], ids=["single", "batch"])
@pytest.mark.parametrize("exc", _permanent_fcm_errors(), ids=lambda e: type(e).__name__)
def test_a_credentials_error_logs_at_error_level(exc, batch):
    """Todo 566: a project-wide credentials failure must be seen, so it logs
    at ERROR; the token-level ones stay at WARNING."""
    import logging

    name = type(exc).__name__.lower()
    user = User.objects.create_user(username=f"level-{name}-{batch}")
    profile = ForumProfile.for_user(user)
    profile.fcm_token = "a-token"
    profile.save()

    mock_fcm = MagicMock()
    mock_fcm.send.side_effect = exc

    with patch(
        "apps.core.firebase_config.is_firebase_available", return_value=True
    ), patch("apps.core.firebase_config.get_fcm_client", return_value=mock_fcm), patch(
        "apps.forum_host.tasks.send_forum_push.delay"
    ), patch(
        "apps.forum_host.tasks.logger.log"
    ) as log:
        from apps.forum_host.tasks import send_forum_push, send_forum_push_batch

        if batch:
            send_forum_push_batch("reply_added", [user.pk], {"topic_id": "1"})
        else:
            send_forum_push("reply_added", user.pk, {"topic_id": "1"})

    levels = [c.args[0] for c in log.call_args_list if "permanently" in c.args[1]]
    expected = (
        logging.ERROR if type(exc).__name__ in _CREDENTIALS_CLASSES else logging.WARNING
    )
    assert levels == [expected]


@pytest.mark.django_db
def test_a_token_reregistered_during_the_send_is_kept():
    """The clear matches on the token that failed, so a device that
    registered a new token while the send was in flight keeps it."""
    from firebase_admin import messaging

    user = User.objects.create_user(username="rereg")
    profile = ForumProfile.for_user(user)
    profile.fcm_token = "old-token"
    profile.save()

    def send(_message):
        ForumProfile.objects.filter(user=user).update(fcm_token="new-token")
        raise messaging.UnregisteredError("old token gone")

    mock_fcm = MagicMock()
    mock_fcm.send.side_effect = send

    with patch(
        "apps.core.firebase_config.is_firebase_available", return_value=True
    ), patch("apps.core.firebase_config.get_fcm_client", return_value=mock_fcm):
        from apps.forum_host.tasks import send_forum_push

        send_forum_push("reply_added", user.pk, {"topic_id": "1"})

    profile.refresh_from_db()
    assert profile.fcm_token == "new-token"


def test_the_fcm_wrappers_are_gone():
    """Todo 457 item 7: tests patch ``apps.core.fcm`` directly, so the
    one-line forwarding wrappers have no reason to exist."""
    from apps.forum_host import tasks

    assert not hasattr(tasks, "_send_fcm_message")
    assert not hasattr(tasks, "_is_permanent_fcm_error")


# --- audit 2026-09-04 M8 / L3 -------------------------------------------------


def test_side_effect_only_tasks_ignore_results():
    """Every forum task is fire-and-forget (each call site is a bare .delay()
    and nothing reads the AsyncResult), so none may persist a result into the
    configured backend (audit 2026-09-04 L3; domain/celery.md)."""
    from apps.forum_host.tasks import (
        generate_topic_summary,
        send_forum_email_batch,
        send_forum_push,
        send_forum_push_batch,
        sync_blog_page_chunks,
    )

    for task in (
        send_forum_push,
        send_forum_push_batch,
        send_forum_email_batch,
        generate_topic_summary,
        sync_blog_page_chunks,
    ):
        assert task.ignore_result is True, task.name


def test_batch_tasks_declare_a_real_backoff_factor():
    """``retry_backoff`` on an autoretry task is the FACTOR: ``True`` meant
    ~1s/2s/4s (audit 2026-09-04 M8; docs/rules/celery.md), i.e. a near-instant
    retry against a DB that just raised OperationalError."""
    from apps.forum_host import constants
    from apps.forum_host.tasks import send_forum_email_batch, send_forum_push_batch
    from django.db import OperationalError

    for task in (send_forum_push_batch, send_forum_email_batch):
        assert OperationalError in task.autoretry_for, task.name
        assert task.retry_backoff == constants.NOTIFICATION_BATCH_RETRY_DELAY
        assert task.max_retries == constants.NOTIFICATION_BATCH_MAX_RETRIES


@pytest.mark.parametrize("prior_retries, ceiling", [(0, 30), (1, 60), (2, 120)])
def test_push_batch_autoretry_countdown_is_exponential_from_the_retry_delay(
    prior_retries, ceiling
):
    """Pinned the sync_blog_page_chunks way (test_rag_index_tasks.py): fake the
    retry counter, mock retry(), patch full jitter to its maximum, and read the
    countdown the autoretry wrapper computes for the pre-send bulk fetch."""
    from apps.forum_host.tasks import send_forum_push_batch
    from celery.exceptions import Retry
    from django.db import OperationalError

    with patch(
        "apps.core.firebase_config.is_firebase_available", return_value=True
    ), patch(
        "apps.core.firebase_config.get_fcm_client", return_value=MagicMock()
    ), patch.object(
        ForumProfile.objects, "filter", side_effect=OperationalError("db down")
    ), patch(
        "celery.utils.time.random.randrange", side_effect=lambda n: n - 1
    ), patch.object(
        send_forum_push_batch, "retry", side_effect=Retry("retried")
    ) as mock_retry:
        send_forum_push_batch.push_request(retries=prior_retries)
        try:
            with pytest.raises(Retry):
                send_forum_push_batch.run("reply_added", [1], {"topic_id": "1"})
        finally:
            send_forum_push_batch.pop_request()

    assert mock_retry.call_args.kwargs["countdown"] == ceiling


def test_weekly_digest_is_scheduled_on_a_registered_task():
    """The beat entry (todo 340) must name a task Celery can import — a typo
    here is silent in prod (beat logs an error and moves on)."""
    from apps.forum_host import tasks
    from celery.schedules import crontab
    from django.conf import settings

    entry = settings.CELERY_BEAT_SCHEDULE["forum-weekly-digest"]
    assert entry["task"] == tasks.send_forum_weekly_digest.name
    assert isinstance(entry["schedule"], crontab)
    assert entry["schedule"].day_of_week == {1}  # monday
    assert entry["schedule"].hour == {9}
    # The crontab is evaluated in CELERY_TIMEZONE — pinned, not defaulted.
    assert settings.CELERY_TIMEZONE == "UTC" == settings.TIME_ZONE


def test_weekly_digest_task_is_sized_for_a_cohort_and_retries_db_blips():
    """Review finding: the global 90 s soft limit and no-retry default are
    for single-object tasks; a cohort run needs its own budget."""
    from apps.forum_host import tasks
    from django.db import OperationalError

    task = tasks.send_forum_weekly_digest
    assert task.soft_time_limit == tasks.DIGEST_SOFT_TIME_LIMIT >= 20 * 60
    assert task.time_limit == tasks.DIGEST_TIME_LIMIT > task.soft_time_limit
    assert OperationalError in task.autoretry_for
    assert task.max_retries == 3


def test_weekly_digest_task_runs_the_package_command_and_logs_its_summary(caplog):
    from apps.forum_host import tasks

    def fake_command(name, frequency, stdout):
        stdout.write("[EMAIL] digest frequency=weekly recipients=3 due=1 sent=1\n")

    with patch("django.core.management.call_command", side_effect=fake_command) as cmd:
        with caplog.at_level("INFO", logger="forum_host.tasks"):
            tasks.send_forum_weekly_digest.apply()

    assert cmd.call_args.args == ("send_forum_digest",)
    assert cmd.call_args.kwargs["frequency"] == "weekly"
    assert any("recipients=3 due=1 sent=1" in r.getMessage() for r in caplog.records)


def test_weekly_digest_task_re_enqueues_itself_after_a_soft_time_limit():
    from apps.forum_host import tasks
    from celery.exceptions import SoftTimeLimitExceeded

    with patch(
        "django.core.management.call_command", side_effect=SoftTimeLimitExceeded()
    ):
        with patch.object(tasks.send_forum_weekly_digest, "apply_async") as again:
            tasks.send_forum_weekly_digest.apply()

    again.assert_called_once_with(countdown=tasks.DIGEST_CONTINUATION_DELAY)


# The relay loop's own format string: it marks exactly the relayed lines,
# with no word filter that could drop one (todo 573).
RELAY_FORMAT = "%s (task=%s)"


def relayed_lines(info_mock):
    """The command output lines a task relayed through ``logger.info``."""
    return [c.args[1] for c in info_mock.call_args_list if c.args[0] == RELAY_FORMAT]


@pytest.mark.django_db
def test_weekly_digest_relays_the_real_command_output_with_one_prefix():
    """Todo 392: the relay loop adds no prefix because the package command
    already writes `[EMAIL] ...`. Run the REAL command (no call_command mock)
    and read what the task actually logs: exactly one `[EMAIL]` per line.

    The task logger's ``info`` is patched rather than read through caplog,
    which depends on the app logger propagating to the root handler (todo
    573). The run lock is cleared first, and the summary line is required:
    a leaked lock relays only its "holds the lock" line, which would fail.
    """
    from apps.forum_host import tasks
    from django.core.cache import cache
    from django.test import override_settings

    # A private cache: the default one is the shared Redis in dev and sweep
    # runs, where deleting the run lock could free a live worker's digest
    # run (todo 593 #9).
    with override_settings(
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "todo-593-digest-relay",
            }
        }
    ):
        cache.delete("wagtail_forum:digest-run:weekly")
        with patch.object(tasks.logger, "info") as info:
            tasks.send_forum_weekly_digest.apply()

    relayed = relayed_lines(info)
    assert any("recipients=" in line for line in relayed), relayed
    for line in relayed:
        assert line.startswith("[EMAIL] "), line
        assert line.count("[EMAIL]") == 1, line


def test_the_digest_run_lock_outlives_the_task_but_not_by_much():
    """Todo 548: the command's run lock TTL (package setting
    WAGTAILFORUM_DIGEST_RUN_LOCK_SECONDS) is the task's hard time limit plus
    a few minutes. Shorter, a live run could lose its lock; much longer, a
    hard-killed run blocks the continuation and the next fire for hours."""
    from apps.forum_host import tasks
    from wagtail_forum.conf import get_setting

    ttl = get_setting("DIGEST_RUN_LOCK_SECONDS")
    assert tasks.DIGEST_TIME_LIMIT < ttl <= tasks.DIGEST_TIME_LIMIT + 5 * 60


@pytest.mark.django_db
def test_a_re_enqueue_the_broker_refuses_still_logs_the_credentials_error(caplog):
    """Todo 631 #1/#3: the re-enqueue ran unguarded before the single ERROR,
    so a broker outage (kombu's OperationalError, outside autoretry_for)
    failed the task and the ERROR naming the stop was never logged. Now the
    task returns, and the one ERROR says the untried recipients were dropped."""
    import logging

    from firebase_admin import messaging
    from kombu.exceptions import OperationalError as BrokerError

    users = _batch_recipients("broker-down", 5)
    mock_fcm = MagicMock()
    mock_fcm.send.side_effect = messaging.ThirdPartyAuthError("apns auth")

    with caplog.at_level(logging.ERROR, logger="forum_host.tasks"), patch(
        "apps.core.firebase_config.is_firebase_available", return_value=True
    ), patch("apps.core.firebase_config.get_fcm_client", return_value=mock_fcm), patch(
        "apps.forum_host.tasks.send_forum_push.delay"
    ), patch(
        "apps.forum_host.tasks.send_forum_push_batch.apply_async",
        side_effect=BrokerError("broker down"),
    ) as requeue:
        from apps.forum_host.tasks import send_forum_push_batch

        send_forum_push_batch("reply_added", [u.pk for u in users], {"topic_id": "1"})

    requeue.assert_called_once()
    assert mock_fcm.send.call_count == 3
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1, errors
    assert "2 recipient(s) not tried" in errors[0]
    assert "re-enqueue failed (OperationalError)" in errors[0]
    # Todo 643 #2: the type only, never the broker's message, which can carry
    # its host or URL into the logs and Sentry.
    assert "broker down" not in errors[0]
    assert "2 recipient(s) dropped" in errors[0]
    assert "re-enqueued once" not in errors[0]


@pytest.mark.django_db
def test_a_single_hand_off_the_broker_refuses_does_not_abort_the_batch(caplog):
    """Todo 643 #1: the transient path's ``send_forum_push.delay`` ran
    unguarded, so a broker outage raised kombu's OperationalError mid-batch:
    the rest of the batch was never tried and the credentials ERROR never
    logged. Now the failed hand-off is logged (its type only, #2) and the
    batch goes on. Recipient 0 fails transiently, 1-3 on credentials."""
    import logging

    from firebase_admin import exceptions as fb_exceptions
    from firebase_admin import messaging
    from kombu.exceptions import OperationalError as BrokerError

    users = _batch_recipients("handoff-down", 5)
    mock_fcm = MagicMock()
    mock_fcm.send.side_effect = [
        fb_exceptions.UnavailableError("FCM backend down"),
        messaging.ThirdPartyAuthError("apns auth"),
        messaging.ThirdPartyAuthError("apns auth"),
        messaging.ThirdPartyAuthError("apns auth"),
    ]

    with caplog.at_level(logging.ERROR, logger="forum_host.tasks"), patch(
        "apps.core.firebase_config.is_firebase_available", return_value=True
    ), patch("apps.core.firebase_config.get_fcm_client", return_value=mock_fcm), patch(
        "apps.forum_host.tasks.send_forum_push.delay",
        side_effect=BrokerError("redis://secret-host:6379 refused"),
    ) as single, patch(
        "apps.forum_host.tasks.send_forum_push_batch.apply_async"
    ) as requeue:
        from apps.forum_host.tasks import send_forum_push_batch

        send_forum_push_batch("reply_added", [u.pk for u in users], {"topic_id": "1"})

    single.assert_called_once_with("reply_added", users[0].pk, {"topic_id": "1"})
    assert mock_fcm.send.call_count == 4
    requeue.assert_called_once()
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 2, errors
    assert f"re-enqueue single failed (user={users[0].pk}): OperationalError" in (
        errors[0]
    )
    assert "1 device(s) dropped" in errors[0]
    assert "credentials error for 3 recipient(s)" in errors[1]
    assert "1 recipient(s) not tried" in errors[1]
    assert all("secret-host" not in e for e in errors), errors
