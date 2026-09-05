"""Forum digest (todo 340): opt-in, visibility-filtered, idempotent, and
template-overridable. Emails land in Django's locmem outbox (`mail.outbox`)."""

import copy
import importlib
from datetime import timedelta
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
from wagtail.models import Page, PageViewRestriction
from wagtail_forum.digest import build_digest, is_due, render_digest, since_for
from wagtail_forum.models import (
    DigestFrequency,
    ForumBoard,
    ForumIndex,
    ForumProfile,
    Notification,
    NotificationVerb,
    Topic,
    TopicRead,
    UserBlock,
)

User = get_user_model()


def _index():
    root = Page.objects.get(id=1)
    return root.add_child(instance=ForumIndex(title="Forum", slug="forum-digest"))


def _board(index, slug, *, live=True, restricted=False):
    board = index.add_child(instance=ForumBoard(title=slug.title(), slug=slug))
    if not live:
        board.unpublish()
    if restricted:
        PageViewRestriction.objects.create(page=board, restriction_type="login")
    return board


def _topic(board, author, title, *, replies=1, minutes_ago=60):
    at = timezone.now() - timedelta(minutes=minutes_ago)
    topic = Topic.objects.create(
        board=board,
        title=title,
        slug=title.lower().replace(" ", "-"),
        author=author,
        live=True,
    )
    Topic.objects.filter(pk=topic.pk).update(reply_count=replies, last_post_at=at)
    topic.refresh_from_db()
    return topic


def _reply_note(recipient, actor, topic, *, minutes_ago=30):
    note = Notification.objects.create(
        recipient=recipient, actor=actor, verb=NotificationVerb.REPLY, topic=topic
    )
    Notification.objects.filter(pk=note.pk).update(
        created_at=timezone.now() - timedelta(minutes=minutes_ago)
    )
    return note


def _opt_in(user):
    profile = ForumProfile.for_user(user)
    profile.digest_frequency = DigestFrequency.WEEKLY
    profile.save(update_fields=["digest_frequency"])
    return profile


@pytest.mark.django_db
def test_digest_is_off_by_default_and_the_host_default_applies_to_new_profiles():
    plain = ForumProfile.for_user(User.objects.create_user(username="dg-default"))
    assert plain.digest_frequency == DigestFrequency.OFF
    with override_settings(WAGTAILFORUM_DIGEST_DEFAULT_FREQUENCY="weekly"):
        fresh = ForumProfile.for_user(
            User.objects.create_user(username="dg-host-default")
        )
        plain.refresh_from_db()
    assert fresh.digest_frequency == DigestFrequency.WEEKLY
    assert plain.digest_frequency == DigestFrequency.OFF  # existing choice untouched


@pytest.mark.django_db
def test_digest_content_respects_visibility_and_blocks():
    """Hidden/restricted boards and blocked authors never reach a digest —
    the same rules as every API read."""
    index = _index()
    public = _board(index, "public")
    hidden = _board(index, "hidden", live=False)
    restricted = _board(index, "restricted", restricted=True)
    me = User.objects.create_user(username="dg-me", email="me@example.com")
    friend = User.objects.create_user(username="dg-friend")
    blocked = User.objects.create_user(username="dg-blocked")
    UserBlock.objects.create(blocker=me, blocked=blocked)
    since = timezone.now() - timedelta(days=7)

    # Watched section: reply notifications, one per source.
    watched_ok = _topic(public, friend, "Watched ok")
    _reply_note(me, friend, watched_ok)
    _reply_note(me, friend, watched_ok, minutes_ago=20)
    watched_hidden = _topic(hidden, friend, "Watched hidden")
    _reply_note(me, friend, watched_hidden)
    watched_restricted = _topic(restricted, friend, "Watched restricted")
    _reply_note(me, friend, watched_restricted)
    # These two fall out of the WATCHED section (blocked replier / stale
    # notification) and are stale enough not to trend either.
    watched_blocked_replier = _topic(
        public, friend, "Watched blocked replier", minutes_ago=60 * 24 * 10
    )
    _reply_note(me, blocked, watched_blocked_replier)
    old = _topic(public, friend, "Watched old", minutes_ago=60 * 24 * 10)
    _reply_note(me, friend, old, minutes_ago=60 * 24 * 10)  # before `since`

    # Trending section.
    trending_ok = _topic(public, friend, "Trending ok", replies=9)
    _topic(hidden, friend, "Trending hidden", replies=50)
    _topic(restricted, friend, "Trending restricted", replies=50)
    _topic(public, blocked, "Trending blocked author", replies=50)
    _topic(public, me, "My own topic", replies=50)
    seen = _topic(public, friend, "Trending seen", replies=40)
    TopicRead.objects.create(user=me, topic=seen, last_read_at=timezone.now())
    _topic(public, friend, "Trending stale", replies=99, minutes_ago=60 * 24 * 10)
    # An already-read reply notification is not "new" — it must not surface.
    read_topic = _topic(public, friend, "Watched read", minutes_ago=60 * 24 * 10)
    read_note = _reply_note(me, friend, read_topic)
    Notification.objects.filter(pk=read_note.pk).update(read_at=timezone.now())

    digest = build_digest(me, since)

    assert [(t.title, t.new_replies) for t in digest.watched] == [("Watched ok", 2)]
    assert [t.title for t in digest.trending] == ["Trending ok"]
    assert digest.trending[0].reply_count == 9
    assert digest.trending[0].url.endswith(trending_ok.get_absolute_url())
    assert not digest.empty


@pytest.mark.django_db
def test_nothing_new_means_no_email_and_no_marker_write():
    me = User.objects.create_user(username="dg-quiet", email="quiet@example.com")
    profile = _opt_in(me)
    out = StringIO()

    call_command("send_forum_digest", frequency="weekly", stdout=out)

    assert mail.outbox == []
    profile.refresh_from_db()
    assert profile.last_digest_sent_at is None
    assert "recipients=1 due=1 empty=1 sent=0" in out.getvalue()


@pytest.mark.django_db
@override_settings(
    SITE_URL="https://forum.example", DEFAULT_FROM_EMAIL="Forum <noreply@example>"
)
def test_command_sends_to_opted_in_members_only_and_is_idempotent():
    index = _index()
    board = _board(index, "general")
    friend = User.objects.create_user(username="dg-poster")
    topic = _topic(board, friend, "Repotting monstera", replies=3)
    opted = User.objects.create_user(username="dg-opted", email="opted@example.com")
    _opt_in(opted)
    User.objects.create_user(username="dg-off", email="off@example.com")  # default off
    no_email = User.objects.create_user(username="dg-noemail", email="")
    _opt_in(no_email)
    inactive = User.objects.create_user(
        username="dg-inactive", email="inactive@example.com", is_active=False
    )
    _opt_in(inactive)
    _reply_note(inactive, friend, topic)
    _reply_note(opted, friend, topic)
    out = StringIO()

    call_command("send_forum_digest", frequency="weekly", stdout=out)

    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ["opted@example.com"]
    assert message.from_email == "Forum <noreply@example>"
    assert message.subject == "Your weekly forum digest"
    assert "Repotting monstera" in message.body
    assert f"https://forum.example{topic.get_absolute_url()}" in message.body
    assert "https://forum.example/settings" in message.body
    html = message.alternatives[0][0]
    assert (
        "Repotting monstera" in html and 'href="https://forum.example/settings"' in html
    )
    assert "recipients=1 due=1 empty=0 sent=1 failed=0" in out.getvalue()
    profile = ForumProfile.for_user(opted)
    assert profile.last_digest_sent_at is not None

    # A second run inside the window: not due, nothing sent, marker kept.
    mail.outbox.clear()
    out = StringIO()
    call_command("send_forum_digest", frequency="weekly", stdout=out)
    assert mail.outbox == []
    assert "due=0" in out.getvalue()


@pytest.mark.django_db
def test_dry_run_reports_counts_but_sends_and_writes_nothing():
    index = _index()
    board = _board(index, "general")
    friend = User.objects.create_user(username="dg-poster2")
    topic = _topic(board, friend, "Dry run topic")
    opted = User.objects.create_user(username="dg-dry", email="dry@example.com")
    profile = _opt_in(opted)
    _reply_note(opted, friend, topic)
    out = StringIO()

    call_command("send_forum_digest", frequency="weekly", dry_run=True, stdout=out)

    assert mail.outbox == []
    profile.refresh_from_db()
    assert profile.last_digest_sent_at is None
    text = out.getvalue()
    assert f"dry-run: user={opted.pk} watched=1 trending=0" in text
    assert "would send=1" in text and "nothing sent, nothing written" in text


def test_due_and_since_windows():
    now = timezone.now()
    never = ForumProfile(last_digest_sent_at=None)
    assert is_due(never, now, 7)
    assert since_for(never, now, 7) == now - timedelta(days=7)
    recent = ForumProfile(last_digest_sent_at=now - timedelta(days=2))
    assert not is_due(recent, now, 7)
    jittered = ForumProfile(last_digest_sent_at=now - timedelta(days=6, hours=2))
    assert is_due(jittered, now, 7)  # a weekly job firing a few hours early
    assert since_for(jittered, now, 7) == jittered.last_digest_sent_at
    ancient = ForumProfile(last_digest_sent_at=now - timedelta(days=40))
    assert since_for(ancient, now, 7) == now - timedelta(days=7)  # capped at one window


@pytest.mark.django_db
def test_host_can_override_the_templates(tmp_path, settings):
    """Normal Django template resolution: a host template dir that shadows
    `wagtail_forum/email/digest.txt` wins over the package copy."""
    override_dir = tmp_path / "templates" / "wagtail_forum" / "email"
    override_dir.mkdir(parents=True)
    (override_dir / "digest.txt").write_text("HOST OVERRIDE for {{ display_name }}")
    templates = copy.deepcopy(settings.TEMPLATES)
    templates[0]["DIRS"] = [str(tmp_path / "templates"), *templates[0].get("DIRS", [])]
    me = User.objects.create_user(username="dg-override", email="o@example.com")
    profile = ForumProfile.for_user(me)
    profile.display_name = "Override Person"
    profile.save(update_fields=["display_name"])
    digest = build_digest(me, timezone.now() - timedelta(days=7))

    with override_settings(TEMPLATES=templates):
        subject, text, html = render_digest(digest)

    assert text == "HOST OVERRIDE for Override Person"
    assert "Override Person" in html  # the package html is still used


@pytest.mark.django_db
@pytest.mark.urls("wagtail_forum.tests.api.urls")
def test_me_endpoint_exposes_and_updates_the_digest_preference():
    from rest_framework.test import APIClient

    me = User.objects.create_user(username="dg-api")
    client = APIClient()
    client.force_authenticate(me)
    assert client.get("/forum/me/profile/").data["digest_frequency"] == "off"
    resp = client.patch(
        "/forum/me/profile/", {"digest_frequency": "weekly"}, format="json"
    )
    assert resp.status_code == 200, resp.data
    assert resp.data["digest_frequency"] == "weekly"
    assert (
        client.patch(
            "/forum/me/profile/", {"digest_frequency": "daily"}, format="json"
        ).status_code
        == 400
    )
    assert ForumProfile.for_user(me).digest_frequency == DigestFrequency.WEEKLY


def test_package_never_imports_celery():
    """The management command is the package boundary; scheduling is host wiring."""
    import wagtail_forum.digest as digest_module

    command = importlib.import_module(
        "wagtail_forum.management.commands.send_forum_digest"
    )
    for path in (digest_module.__file__, command.__file__):
        source = open(path).read()
        assert "import celery" not in source and "from celery" not in source, path


@pytest.mark.django_db
def test_an_overlapping_run_exits_on_the_lock_but_a_dry_run_ignores_it():
    """Review finding: overlap safety must be a lock, not a claim. A second
    fire while the first holds the lock sends nothing; the lock is released
    afterwards; dry-run never takes or honours it."""
    from django.core.cache import cache
    from wagtail_forum.management.commands.send_forum_digest import RUN_LOCK_SECONDS

    index = _index()
    board = _board(index, "general")
    friend = User.objects.create_user(username="dg-lock-poster")
    topic = _topic(board, friend, "Locked topic")
    opted = User.objects.create_user(username="dg-lock", email="lock@example.com")
    _opt_in(opted)
    _reply_note(opted, friend, topic)
    cache.delete("wagtail_forum:digest-run:weekly")
    assert cache.add("wagtail_forum:digest-run:weekly", "other", RUN_LOCK_SECONDS)

    out = StringIO()
    call_command("send_forum_digest", frequency="weekly", stdout=out)
    assert mail.outbox == []
    assert "another run holds the lock" in out.getvalue()

    out = StringIO()
    call_command("send_forum_digest", frequency="weekly", dry_run=True, stdout=out)
    assert "would send=1" in out.getvalue()

    cache.delete("wagtail_forum:digest-run:weekly")
    call_command("send_forum_digest", frequency="weekly", stdout=StringIO())
    assert len(mail.outbox) == 1
    assert cache.get("wagtail_forum:digest-run:weekly") is None  # released


@pytest.mark.django_db
def test_one_members_failure_does_not_end_the_run(monkeypatch):
    import wagtail_forum.management.commands.send_forum_digest as cmd
    from django.core.cache import cache

    index = _index()
    board = _board(index, "general")
    friend = User.objects.create_user(username="dg-fail-poster")
    topic = _topic(board, friend, "Fail topic")
    first = User.objects.create_user(username="dg-fail-a", email="a@example.com")
    second = User.objects.create_user(username="dg-fail-b", email="b@example.com")
    _opt_in(first)
    _opt_in(second)
    _reply_note(first, friend, topic)
    _reply_note(second, friend, topic)
    cache.delete("wagtail_forum:digest-run:weekly")
    real = cmd.build_digest

    def flaky(user, since, now=None):
        if user.pk == first.pk:
            raise RuntimeError("boom")
        return real(user, since, now)

    monkeypatch.setattr(cmd, "build_digest", flaky)
    out = StringIO()
    call_command("send_forum_digest", frequency="weekly", stdout=out)

    assert [m.to for m in mail.outbox] == [["b@example.com"]]
    assert "sent=1 failed=1" in out.getvalue()
    assert ForumProfile.for_user(first).last_digest_sent_at is None  # due next time


@pytest.mark.django_db
@override_settings(
    WAGTAILFORUM_DIGEST_MAX_WATCHED_TOPICS=2, WAGTAILFORUM_DIGEST_MAX_TRENDING_TOPICS=2
)
def test_caps_apply_and_an_overflowing_watched_topic_never_resurfaces_as_trending():
    index = _index()
    board = _board(index, "general")
    me = User.objects.create_user(username="dg-caps")
    friend = User.objects.create_user(username="dg-caps-poster")
    for i in range(4):  # 4 followed topics with unread replies, cap 2
        t = _topic(board, friend, f"Watched {i}", replies=50 - i, minutes_ago=10 + i)
        _reply_note(me, friend, t, minutes_ago=5 + i)
    for i in range(3):  # 3 trending candidates, cap 2
        _topic(board, friend, f"Trending {i}", replies=10 - i)

    digest = build_digest(me, timezone.now() - timedelta(days=7))

    assert [t.title for t in digest.watched] == ["Watched 0", "Watched 1"]
    # The two overflow watched topics are the most active of all — they must
    # NOT show up under "not seen", because the member follows them.
    assert [t.title for t in digest.trending] == ["Trending 0", "Trending 1"]


@pytest.mark.django_db
@override_settings(SITE_URL="https://forum.example")
def test_html_part_escapes_a_hostile_topic_title():
    index = _index()
    board = _board(index, "general")
    friend = User.objects.create_user(username="dg-xss-poster")
    topic = _topic(board, friend, "<script>alert(1)</script> care", replies=2)
    me = User.objects.create_user(username="dg-xss", email="x@example.com")
    _opt_in(me)
    _reply_note(me, friend, topic)

    call_command("send_forum_digest", frequency="weekly", stdout=StringIO())

    html = mail.outbox[0].alternatives[0][0]
    assert (
        "<script>" not in html and "&lt;script&gt;alert(1)&lt;/script&gt; care" in html
    )


@pytest.mark.django_db
@override_settings(SITE_URL="https://forum.example")
def test_a_failed_send_is_logged_counted_and_leaves_the_member_due(caplog, monkeypatch):
    from django.core.mail import EmailMultiAlternatives

    index = _index()
    board = _board(index, "general")
    friend = User.objects.create_user(username="dg-smtp-poster")
    topic = _topic(board, friend, "SMTP down")
    me = User.objects.create_user(username="dg-smtp", email="s@example.com")
    profile = _opt_in(me)
    _reply_note(me, friend, topic)

    def boom(self, fail_silently=False):
        raise ConnectionError("smtp down")

    monkeypatch.setattr(EmailMultiAlternatives, "send", boom)
    out = StringIO()
    with caplog.at_level("ERROR", logger="wagtail_forum"):
        call_command("send_forum_digest", frequency="weekly", stdout=out)

    assert mail.outbox == []
    assert "sent=0 failed=1" in out.getvalue()
    assert any("[EMAIL] forum digest failed" in r.getMessage() for r in caplog.records)
    profile.refresh_from_db()
    assert profile.last_digest_sent_at is None  # the claim was reverted


def test_a_soft_time_limit_is_never_swallowed_as_a_send_failure():
    """billiard's SoftTimeLimitExceeded subclasses Exception; the package
    cannot import it, so it is matched by name and re-raised."""
    from unittest.mock import patch

    from wagtail_forum.digest import Digest, send_digest

    class SoftTimeLimitExceeded(Exception):
        pass

    digest = Digest(
        user=User(username="u", email="u@example.com"), since=timezone.now()
    )
    with patch(
        "wagtail_forum.digest.render_digest", side_effect=SoftTimeLimitExceeded()
    ):
        with pytest.raises(SoftTimeLimitExceeded):
            send_digest(digest)


@override_settings(SITE_URL="", WAGTAILFORUM_EMAIL_SITE_URL=None)
def test_missing_site_origin_is_a_loud_configuration_error():
    from django.core.exceptions import ImproperlyConfigured
    from wagtail_forum.digest import site_url

    with pytest.raises(ImproperlyConfigured):
        site_url()


@pytest.mark.django_db
def test_build_digest_query_count_is_pinned():
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    index = _index()
    board = _board(index, "general")
    friend = User.objects.create_user(username="dg-q-poster")
    me = User.objects.create_user(username="dg-q")
    profile = ForumProfile.for_user(me)
    for i in range(3):
        t = _topic(board, friend, f"Q watched {i}")
        _reply_note(me, friend, t)
    for i in range(3):
        _topic(board, friend, f"Q trending {i}", replies=5)
    since = timezone.now() - timedelta(days=7)

    with CaptureQueriesContext(connection) as ctx:
        digest = build_digest(me, since, profile)

    assert len(digest.watched) == 3 and len(digest.trending) == 3
    # Flat in the number of topics: blocked ids (blocker/blocked), followed
    # ids, grouped watched, watched topics, trending.
    assert len(ctx.captured_queries) == 7


@pytest.mark.django_db
def test_recount_created_profiles_get_the_host_digest_default():
    """The second profile-creation path (signals._refresh_profile) seeds the
    same default as for_user — todo 285's seven-call-site lesson."""
    from wagtail_forum.signals import _refresh_profile

    user = User.objects.create_user(username="dg-recount")
    with override_settings(WAGTAILFORUM_DIGEST_DEFAULT_FREQUENCY="weekly"):
        _refresh_profile(user.pk)
    assert (
        ForumProfile.objects.get(user=user).digest_frequency == DigestFrequency.WEEKLY
    )
