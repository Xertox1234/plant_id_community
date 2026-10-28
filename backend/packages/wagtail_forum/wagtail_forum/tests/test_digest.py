"""Forum digest (todo 340): opt-in, visibility-filtered, idempotent, and
template-overridable. Emails land in Django's locmem outbox (`mail.outbox`)."""

import copy
import importlib
import inspect
import re
from datetime import timedelta
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
from wagtail.models import Page
from wagtail_forum.digest import build_digest, is_due, render_digest, since_for
from wagtail_forum.models import (
    DigestFrequency,
    ForumIndex,
    ForumProfile,
    Notification,
    NotificationVerb,
    Topic,
    TopicRead,
    UserBlock,
)
from wagtail_forum.tests.factories import hide_forum, make_forum

User = get_user_model()


@pytest.fixture(autouse=True)
def _private_cache():
    """Every test here gets its own empty cache (todo 630). The default cache
    is the shared Redis in dev and sweep runs: a test that adds, reads or
    deletes the real run-lock key there could collide with a parallel slot
    (exiting on 'holds the lock') or free a live worker's digest run, which
    is why test_tasks.py moved off it too (todo 593 #9)."""
    from uuid import uuid4

    with override_settings(
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": f"wagtail-forum-digest-tests-{uuid4().hex}",
            }
        }
    ):
        yield


def test_the_run_lock_tests_never_touch_the_shared_cache():
    """Todo 630: the autouse fixture above swaps the default cache for a
    private, empty one, so the real run-lock key is never on the shared
    Redis while these tests run.

    Todo 642: a bare LocMem check passed without the fixture wherever the
    default cache is already LocMem (CI). This pins the fixture's own private
    LOCATION, that it is the only alias (a lock on another alias would raise
    here), and that the command's module-level `cache` routes to it, so a
    cache object captured at import time would fail too."""
    from django.conf import settings
    from django.core.cache import caches
    from django.core.cache.backends.locmem import LocMemCache
    from wagtail_forum.management.commands import send_forum_digest

    assert list(settings.CACHES) == ["default"]
    location = settings.CACHES["default"]["LOCATION"]
    assert location.startswith("wagtail-forum-digest-tests-")
    assert isinstance(caches["default"], LocMemCache)

    key = "wagtail_forum:digest-run:weekly"
    assert send_forum_digest.cache.add(key, "canary", 60)
    try:
        assert caches["default"].get(key) == "canary"
    finally:
        send_forum_digest.cache.delete(key)


def _normalise_sql(raw):
    """Drop identifier quotes, fold case and collapse whitespace, so a test
    compares the SQL's shape, not Django's exact rendering (todo 605)."""
    return re.sub(r"\s+", " ", raw.replace('"', "")).strip().lower()


def _is_the_claim(raw):
    """True for the digest claim UPDATE on ForumProfile, matched on the
    normalised SQL (todos 630, 642), never on a quoted `UPDATE "<table>"`."""
    sql = _normalise_sql(raw)
    table = re.escape(ForumProfile._meta.db_table.lower())
    return bool(re.match(rf"update {table}\b", sql)) and "last_digest_sent_at" in sql


def _add_call_value(call):
    """The value a `cache.add` call stored, bound by name (todo 642), so the
    test survives a switch between positional and keyword arguments."""
    from django.core.cache.backends.base import BaseCache

    bound = inspect.signature(BaseCache.add).bind(None, *call.args, **call.kwargs)
    return bound.arguments["value"]


def _index():
    root = Page.objects.get(id=1)
    return root.add_child(instance=ForumIndex(title="Forum", slug="forum-digest"))


def _board(index, slug, *, live=True, restricted=False):
    board = make_forum(name=slug.title(), slug=slug)
    if not live:
        hide_forum(board)
    if restricted:
        hide_forum(board)
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
    from wagtail_forum.conf import get_setting

    RUN_LOCK_SECONDS = get_setting("DIGEST_RUN_LOCK_SECONDS")

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
    # 7 -> 6 (todo 665): boards are Forum rows, so the
    # PageViewRestriction query behind the page-era `.public()` is gone.
    assert len(ctx.captured_queries) == 6


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


def fake_unsubscribe(user):
    """A host callable for DIGEST_UNSUBSCRIBE (todo 416)."""
    return {
        "url": f"https://forum.example/unsubscribe?token=t-{user.pk}",
        "headers": {"List-Unsubscribe": "<https://api.example/one-click>"},
    }


def _send_one_digest():
    index = _index()
    board = _board(index, "general")
    friend = User.objects.create_user(username="du-poster")
    topic = _topic(board, friend, "Fungus gnats", replies=2)
    member = User.objects.create_user(username="du-member", email="du@example.com")
    _opt_in(member)
    _reply_note(member, friend, topic)
    call_command("send_forum_digest", frequency="weekly", stdout=StringIO())
    assert len(mail.outbox) == 1
    return member, mail.outbox[0]


@pytest.mark.django_db
@override_settings(
    SITE_URL="https://forum.example",
    WAGTAILFORUM_DIGEST_UNSUBSCRIBE=(
        "wagtail_forum.tests.test_digest.fake_unsubscribe"
    ),
)
def test_digest_carries_the_hosts_unsubscribe_link_and_header():
    member, message = _send_one_digest()

    url = f"https://forum.example/unsubscribe?token=t-{member.pk}"
    assert (
        message.extra_headers["List-Unsubscribe"] == "<https://api.example/one-click>"
    )
    assert f"Unsubscribe from this digest: {url}" in message.body
    assert f'href="{url}"' in message.alternatives[0][0]


@pytest.mark.django_db
@override_settings(
    SITE_URL="https://forum.example", WAGTAILFORUM_DIGEST_UNSUBSCRIBE=None
)
def test_digest_without_a_host_callable_has_no_unsubscribe_link():
    _, message = _send_one_digest()

    assert "List-Unsubscribe" not in message.extra_headers
    assert "Unsubscribe from this digest" not in message.body
    assert "Unsubscribe from this digest" not in message.alternatives[0][0]


def broken_unsubscribe(user):
    raise RuntimeError("host hook broke")


@pytest.mark.django_db
@override_settings(
    SITE_URL="https://forum.example",
    WAGTAILFORUM_DIGEST_UNSUBSCRIBE="wagtail_forum.tests.test_digest.broken_unsubscribe",
)
def test_a_broken_unsubscribe_hook_still_sends_the_digest():
    # PR #819: the link is an extra; the digest still goes out without it.
    _, message = _send_one_digest()

    assert "List-Unsubscribe" not in message.extra_headers
    assert "https://forum.example/settings" in message.body


class SoftTimeLimitExceeded(Exception):
    """Stands in for billiard's, matched by name like the package does."""


def time_limited_unsubscribe(user):
    raise SoftTimeLimitExceeded()


@pytest.mark.django_db
@override_settings(
    SITE_URL="https://forum.example",
    WAGTAILFORUM_DIGEST_UNSUBSCRIBE=(
        "wagtail_forum.tests.test_digest.time_limited_unsubscribe"
    ),
)
def test_a_soft_time_limit_inside_the_unsubscribe_hook_still_stops_the_run():
    from wagtail_forum.digest import unsubscribe_links

    member = User.objects.create_user(username="du-soft", email="soft@example.com")
    with pytest.raises(SoftTimeLimitExceeded):
        unsubscribe_links(member)


@pytest.mark.django_db
@override_settings(
    SITE_URL="https://forum.example", WAGTAILFORUM_DIGEST_UNSUBSCRIBE=None
)
def test_a_deprecated_mail_argument_is_never_swallowed_as_a_send_failure(monkeypatch):
    """Todo 454: pytest.ini turns RemovedInDjango70Warning into an error, and
    Warning subclasses Exception. A deprecated argument planted in the send
    (``fail_silently=True``, deprecated in Django 6.1) must fail the run, not
    be logged as one member's failed digest."""
    from django.core.mail import EmailMessage
    from django.utils.deprecation import RemovedInDjango70Warning
    from wagtail_forum.digest import Digest, send_digest

    real_send = EmailMessage.send

    def send(self, *args, **kwargs):
        kwargs["fail_silently"] = True
        return real_send(self, *args, **kwargs)

    monkeypatch.setattr(EmailMessage, "send", send)
    member = User.objects.create_user(username="dg-dep", email="dep@example.com")
    with pytest.raises(RemovedInDjango70Warning):
        send_digest(Digest(user=member, since=timezone.now()))


@pytest.mark.django_db
@override_settings(
    SITE_URL="https://forum.example", WAGTAILFORUM_DIGEST_UNSUBSCRIBE=None
)
def test_a_deprecation_raised_by_the_send_gives_the_members_claim_back(monkeypatch):
    """Todo 537: the command claims the member before sending. A re-raised
    Warning stops the run, and the member must stay due for the next one."""
    from django.core.mail import EmailMessage
    from django.utils.deprecation import RemovedInDjango70Warning

    real_send = EmailMessage.send

    def send(self, *args, **kwargs):
        kwargs["fail_silently"] = True
        return real_send(self, *args, **kwargs)

    index = _index()
    board = _board(index, "general")
    friend = User.objects.create_user(username="dg-claim-poster")
    topic = _topic(board, friend, "Claim me")
    member = User.objects.create_user(username="dg-claim", email="claim@example.com")
    profile = _opt_in(member)
    _reply_note(member, friend, topic)
    monkeypatch.setattr(EmailMessage, "send", send)

    with pytest.raises(RemovedInDjango70Warning):
        call_command("send_forum_digest", frequency="weekly", stdout=StringIO())

    profile.refresh_from_db()
    assert profile.last_digest_sent_at is None


@pytest.mark.django_db
@override_settings(
    SITE_URL="https://forum.example", WAGTAILFORUM_DIGEST_UNSUBSCRIBE=None
)
def test_a_soft_time_limit_in_the_send_gives_the_members_claim_back(monkeypatch):
    """Todo 541 (owner decision 2026-10-10): delivery is at-least-once, as in
    send_blog_newsletter. A soft time limit raised by the send itself stops
    the run, and the member's claim is given back, so the member is due again
    (a duplicate digest is possible if the mail had already gone out)."""
    from wagtail_forum.management.commands import send_forum_digest

    def time_limited_send(digest):
        raise SoftTimeLimitExceeded()

    index = _index()
    board = _board(index, "general")
    friend = User.objects.create_user(username="dg-soft-poster")
    topic = _topic(board, friend, "Soft limit")
    member = User.objects.create_user(username="dg-soft", email="soft-send@example.com")
    profile = _opt_in(member)
    _reply_note(member, friend, topic)
    monkeypatch.setattr(send_forum_digest, "send_digest", time_limited_send)

    with pytest.raises(SoftTimeLimitExceeded):
        call_command("send_forum_digest", frequency="weekly", stdout=StringIO())

    profile.refresh_from_db()
    assert profile.last_digest_sent_at is None


def _member_with_a_reply(prefix):
    index = _index()
    board = _board(index, "general")
    friend = User.objects.create_user(username=f"{prefix}-poster")
    topic = _topic(board, friend, f"{prefix} topic")
    member = User.objects.create_user(username=prefix, email=f"{prefix}@example.com")
    profile = _opt_in(member)
    _reply_note(member, friend, topic)
    return profile


@pytest.mark.django_db
@override_settings(
    SITE_URL="https://forum.example", WAGTAILFORUM_DIGEST_UNSUBSCRIBE=None
)
def test_a_cache_outage_sends_the_digest_without_the_lock(caplog, monkeypatch):
    """Todo 548: with IGNORE_EXCEPTIONS a Redis outage makes cache.add answer
    None; only False means another run holds the lock."""
    from unittest.mock import MagicMock

    from wagtail_forum.management.commands import send_forum_digest

    profile = _member_with_a_reply("dg-cache-down")
    down = MagicMock()
    down.add.return_value = None
    monkeypatch.setattr(send_forum_digest, "cache", down)

    out = StringIO()
    with caplog.at_level("WARNING", logger="wagtail_forum"):
        call_command("send_forum_digest", frequency="weekly", stdout=out)

    assert [m.to for m in mail.outbox] == [["dg-cache-down@example.com"]]
    assert "sent=1" in out.getvalue()
    assert any(
        r.levelname == "WARNING" and "lock is unavailable" in r.getMessage()
        for r in caplog.records
    )
    profile.refresh_from_db()
    assert profile.last_digest_sent_at is not None


@pytest.mark.django_db
@override_settings(
    SITE_URL="https://forum.example", WAGTAILFORUM_DIGEST_UNSUBSCRIBE=None
)
def test_a_held_lock_answering_false_still_exits(monkeypatch):
    from unittest.mock import MagicMock

    from wagtail_forum.management.commands import send_forum_digest

    profile = _member_with_a_reply("dg-cache-held")
    held = MagicMock()
    held.add.return_value = False
    monkeypatch.setattr(send_forum_digest, "cache", held)

    out = StringIO()
    call_command("send_forum_digest", frequency="weekly", stdout=out)

    assert mail.outbox == []
    assert "another run holds the lock" in out.getvalue()
    held.delete.assert_not_called()  # never release a lock we do not hold
    profile.refresh_from_db()
    assert profile.last_digest_sent_at is None


@pytest.mark.django_db
@override_settings(WAGTAILFORUM_DIGEST_RUN_LOCK_SECONDS=123)
def test_the_run_lock_ttl_comes_from_the_package_setting(monkeypatch):
    """Todo 548: the TTL is DIGEST_RUN_LOCK_SECONDS (default 35 minutes, the
    host task's 30-minute hard limit + 5), not a fixed 2 hours."""
    from unittest.mock import MagicMock

    from wagtail_forum.conf import DEFAULTS
    from wagtail_forum.management.commands import send_forum_digest

    assert DEFAULTS["DIGEST_RUN_LOCK_SECONDS"] == 35 * 60
    lock = MagicMock()
    lock.add.return_value = True
    # The key still holds this run's token at release (todo 605).
    lock.get.side_effect = lambda key: lock.add.call_args.args[1]
    monkeypatch.setattr(send_forum_digest, "cache", lock)

    call_command("send_forum_digest", frequency="weekly", stdout=StringIO())

    key, _value, ttl = lock.add.call_args.args
    assert key == "wagtail_forum:digest-run:weekly" and ttl == 123
    lock.delete.assert_called_once_with(key)


def _one_topic_digest_patches(monkeypatch, send):
    """Stub the digest build and the send so a test needs no pages."""
    from django.core.cache import cache
    from wagtail_forum.digest import Digest, DigestTopic
    from wagtail_forum.management.commands import send_forum_digest

    cache.delete("wagtail_forum:digest-run:weekly")
    topic = DigestTopic(
        id=1,
        title="Fresh",
        url="https://forum.example/t/1",
        board_title="General",
        reply_count=1,
        last_post_at=timezone.now(),
    )

    def build(user, since, profile=None):
        return Digest(user=user, since=since, watched=[topic])

    monkeypatch.setattr(send_forum_digest, "build_digest", build)
    monkeypatch.setattr(send_forum_digest, "send_digest", send)


@pytest.mark.django_db
@override_settings(
    SITE_URL="https://forum.example", WAGTAILFORUM_DIGEST_UNSUBSCRIBE=None
)
def test_the_claim_and_the_send_share_one_transaction(monkeypatch):
    """Todo 548: send_digest() runs inside an atomic block the command opened
    (deeper than the test's own), and the claim UPDATE is already applied in
    that block. A hard kill mid-send therefore rolls the claim back with the
    rest of the uncommitted transaction. Not django_db(transaction=True): its
    flush wipes Wagtail's seeded rows (docs/rules/testing.md)."""
    from django.db import connection

    member = User.objects.create_user(username="dg-txn", email="txn@example.com")
    profile = _opt_in(member)
    outer_depth = len(connection.atomic_blocks)
    seen = {}

    def send(digest):
        seen["in_atomic"] = connection.in_atomic_block
        seen["depth"] = len(connection.atomic_blocks)
        seen["claim"] = ForumProfile.objects.get(pk=profile.pk).last_digest_sent_at
        return True

    _one_topic_digest_patches(monkeypatch, send)
    call_command("send_forum_digest", frequency="weekly", stdout=StringIO())

    assert seen["in_atomic"] is True
    assert seen["depth"] > outer_depth  # the command's own atomic block
    assert seen["claim"] is not None  # claimed before the send, same txn
    profile.refresh_from_db()
    assert profile.last_digest_sent_at == seen["claim"]  # kept after a send


@pytest.mark.django_db
@override_settings(
    SITE_URL="https://forum.example", WAGTAILFORUM_DIGEST_UNSUBSCRIBE=None
)
@pytest.mark.parametrize("outcome", ["returns_false", "raises"])
def test_a_failed_send_rolls_the_claim_back_with_its_transaction(monkeypatch, outcome):
    """Todo 548: the claim was applied inside the send's transaction, and a
    send that fails (returns False, or raises) leaves the marker unchanged."""
    from django.db import connection

    member = User.objects.create_user(
        username=f"dg-txn-{outcome}", email=f"txn-{outcome}@example.com"
    )
    profile = _opt_in(member)
    outer_depth = len(connection.atomic_blocks)
    seen = {}

    def send(digest):
        seen["depth"] = len(connection.atomic_blocks)
        seen["claim"] = ForumProfile.objects.get(pk=profile.pk).last_digest_sent_at
        if outcome == "raises":
            raise ConnectionError("smtp down")
        return False

    _one_topic_digest_patches(monkeypatch, send)
    out = StringIO()
    if outcome == "raises":  # a stubbed send_digest's error is not caught
        with pytest.raises(ConnectionError):
            call_command("send_forum_digest", frequency="weekly", stdout=out)
    else:
        call_command("send_forum_digest", frequency="weekly", stdout=out)
        assert "failed=1" in out.getvalue()

    assert seen["depth"] > outer_depth
    assert seen["claim"] is not None  # the claim was applied, then undone
    profile.refresh_from_db()
    assert profile.last_digest_sent_at is None


@pytest.mark.django_db
@override_settings(
    SITE_URL="https://forum.example", WAGTAILFORUM_DIGEST_UNSUBSCRIBE=None
)
def test_a_run_without_the_lock_never_releases_anothers_lock(monkeypatch):
    """Todo 585: after a cache outage (add answered None) the run holds no
    lock, so its `finally` must not delete one another fire took meanwhile."""
    from unittest.mock import MagicMock

    from wagtail_forum.management.commands import send_forum_digest

    _member_with_a_reply("dg-no-release")
    down = MagicMock()
    down.add.return_value = None
    monkeypatch.setattr(send_forum_digest, "cache", down)

    call_command("send_forum_digest", frequency="weekly", stdout=StringIO())

    assert len(mail.outbox) == 1
    down.delete.assert_not_called()


@pytest.mark.django_db
@override_settings(
    SITE_URL="https://forum.example", WAGTAILFORUM_DIGEST_UNSUBSCRIBE=None
)
@pytest.mark.parametrize("change", ["opted_out", "deactivated"])
def test_the_claim_skips_a_member_who_left_after_the_chunk_was_read(
    monkeypatch, change
):
    """Todo 585: the recipient iterator reads 200 rows at a time; a member
    who opts out or is deactivated after that read is not claimed or mailed."""
    from wagtail_forum.management.commands import send_forum_digest

    member = User.objects.create_user(
        username=f"dg-left-{change}", email=f"left-{change}@example.com"
    )
    profile = _opt_in(member)
    sends = []

    def send(digest):
        sends.append(digest.user.pk)
        return True

    _one_topic_digest_patches(monkeypatch, send)
    stub_build = send_forum_digest.build_digest

    def build_then_leave(user, since, profile=None):
        # Lands between the iterator's read and the claim.
        if change == "opted_out":
            ForumProfile.objects.filter(user=user).update(
                digest_frequency=DigestFrequency.OFF
            )
        else:
            User.objects.filter(pk=user.pk).update(is_active=False)
        return stub_build(user, since, profile)

    monkeypatch.setattr(send_forum_digest, "build_digest", build_then_leave)
    out = StringIO()
    call_command("send_forum_digest", frequency="weekly", stdout=out)

    assert sends == []
    assert "sent=0 failed=0" in out.getvalue()
    profile.refresh_from_db()
    assert profile.last_digest_sent_at is None


@pytest.mark.django_db
@override_settings(
    SITE_URL="https://forum.example", WAGTAILFORUM_DIGEST_UNSUBSCRIBE=None
)
@pytest.mark.parametrize("falsy", [None, 0])
def test_a_falsy_non_bool_send_result_counts_as_a_failure(monkeypatch, falsy):
    """Todo 585: the loop no longer relies on send_digest returning a strict
    bool; None or 0 is a failed send, rolled back and counted."""
    member = User.objects.create_user(
        username=f"dg-falsy-{falsy}", email=f"falsy-{falsy}@example.com"
    )
    profile = _opt_in(member)
    _one_topic_digest_patches(monkeypatch, lambda digest: falsy)

    out = StringIO()
    call_command("send_forum_digest", frequency="weekly", stdout=out)

    assert "sent=0 failed=1" in out.getvalue()
    profile.refresh_from_db()
    assert profile.last_digest_sent_at is None


@pytest.mark.django_db
@override_settings(
    SITE_URL="https://forum.example", WAGTAILFORUM_DIGEST_UNSUBSCRIBE=None
)
def test_the_claim_update_stays_on_one_table_with_the_marker_outside(monkeypatch):
    """Todo 585 review: a join in the claim (`user__is_active`) makes Django
    rewrite the UPDATE as `id IN (SELECT ... JOIN ...)`, and PostgreSQL's
    recheck after a racing claim then tests only that stale subquery, so two
    runs both claim. The UPDATE must have no JOIN and keep the marker check
    in its outer WHERE, on the row it locks."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    member = User.objects.create_user(username="dg-one-table", email="one@example.com")
    profile = _opt_in(member)
    _one_topic_digest_patches(monkeypatch, lambda digest: True)

    with CaptureQueriesContext(connection) as ctx:
        call_command("send_forum_digest", frequency="weekly", stdout=StringIO())

    # Compare on the shape, not Django's exact rendering (todo 605). The claim
    # is picked from the normalised SQL too, so a change in quoting or case
    # cannot make it match nothing (todo 630).
    claims = [
        _normalise_sql(q["sql"])
        for q in ctx.captured_queries
        if _is_the_claim(q["sql"])
    ]
    assert len(claims) == 1, claims
    sql = claims[0]
    assert " join " not in sql
    table = re.escape(ForumProfile._meta.db_table.lower())
    where = sql.split(" where ", 1)[1]
    # The outer WHERE (before any subquery) carries the pk and the marker.
    outer = where.split("(select", 1)[0]
    assert re.search(rf"\b{table}\.id = ", outer), outer
    assert re.search(rf"\b{table}\.last_digest_sent_at is null", outer), outer
    assert re.search(rf"\b{table}\.digest_frequency = ", outer), outer
    profile.refresh_from_db()
    assert profile.last_digest_sent_at is not None


def _patches_with_a_mid_run_change(monkeypatch, change):
    """Like _one_topic_digest_patches, but `change(user)` runs after the
    chunk was read (inside the build), and every send is recorded."""
    from wagtail_forum.management.commands import send_forum_digest

    sent = []

    def send(digest):
        sent.append(digest.user.email)
        return True

    _one_topic_digest_patches(monkeypatch, send)
    build = send_forum_digest.build_digest

    def build_then_change(user, since, profile=None):
        change(user)
        return build(user, since, profile)

    monkeypatch.setattr(send_forum_digest, "build_digest", build_then_change)
    return sent


@pytest.mark.django_db
@override_settings(
    SITE_URL="https://forum.example", WAGTAILFORUM_DIGEST_UNSUBSCRIBE=None
)
def test_a_member_who_clears_their_email_mid_run_is_not_claimed_or_mailed(
    monkeypatch,
):
    """Todo 605: the claim rechecks digest_recipients' third condition,
    `user.email != ""`, not only the opt-in and is_active."""
    member = User.objects.create_user(username="dg-cleared", email="gone@example.com")
    profile = _opt_in(member)
    sent = _patches_with_a_mid_run_change(
        monkeypatch, lambda user: User.objects.filter(pk=user.pk).update(email="")
    )

    out = StringIO()
    call_command("send_forum_digest", frequency="weekly", stdout=out)

    assert sent == []
    assert "sent=0 failed=0" in out.getvalue()
    profile.refresh_from_db()
    assert profile.last_digest_sent_at is None


@pytest.mark.django_db
@override_settings(
    SITE_URL="https://forum.example", WAGTAILFORUM_DIGEST_UNSUBSCRIBE=None
)
def test_a_member_who_changes_their_email_mid_run_is_mailed_at_the_new_one(
    monkeypatch,
):
    """Todo 605: the digest goes to the address on the row at claim time,
    never the stale one read with the 200-row chunk."""
    member = User.objects.create_user(username="dg-moved", email="old@example.com")
    profile = _opt_in(member)
    sent = _patches_with_a_mid_run_change(
        monkeypatch,
        lambda user: User.objects.filter(pk=user.pk).update(email="new@example.com"),
    )

    out = StringIO()
    call_command("send_forum_digest", frequency="weekly", stdout=out)

    assert sent == ["new@example.com"]
    assert "sent=1 failed=0" in out.getvalue()
    profile.refresh_from_db()
    assert profile.last_digest_sent_at is not None


@pytest.mark.django_db
@override_settings(
    SITE_URL="https://forum.example", WAGTAILFORUM_DIGEST_UNSUBSCRIBE=None
)
def test_a_run_that_outlives_its_lock_leaves_a_later_fires_lock_alone(monkeypatch):
    """Todo 605: when this run's key expired and another fire took it, the
    finally must not delete that fire's lock."""
    from django.core.cache import cache

    key = "wagtail_forum:digest-run:weekly"
    member = User.objects.create_user(username="dg-outlived", email="o@example.com")
    _opt_in(member)

    def expire_and_retake(user):
        cache.delete(key)  # our TTL ran out mid-run
        assert cache.add(key, "a-later-fire", 60)

    _patches_with_a_mid_run_change(monkeypatch, expire_and_retake)
    try:
        call_command("send_forum_digest", frequency="weekly", stdout=StringIO())
        assert cache.get(key) == "a-later-fire"
    finally:
        cache.delete(key)


@pytest.mark.django_db
@override_settings(
    SITE_URL="https://forum.example", WAGTAILFORUM_DIGEST_UNSUBSCRIBE=None
)
def test_a_run_releases_its_own_lock_by_token(monkeypatch):
    """Todo 605: the token check still releases the lock this run holds.
    Todo 630: it pins the comparison too. The release reads the key and
    finds the very token this run stored, each run stores a token of its
    own (so a later fire's lock never matches), and only then deletes."""
    from unittest.mock import MagicMock

    from django.core.cache import cache
    from wagtail_forum.management.commands import send_forum_digest

    key = "wagtail_forum:digest-run:weekly"
    member = User.objects.create_user(username="dg-own-lock", email="l@example.com")
    profile = _opt_in(member)
    held = []
    _patches_with_a_mid_run_change(
        monkeypatch, lambda user: held.append(cache.get(key))
    )
    spy = MagicMock(wraps=cache)
    monkeypatch.setattr(send_forum_digest, "cache", spy)

    tokens = []
    for _ in range(2):
        ForumProfile.objects.filter(pk=profile.pk).update(last_digest_sent_at=None)
        spy.reset_mock()
        call_command("send_forum_digest", frequency="weekly", stdout=StringIO())
        token = _add_call_value(spy.add.call_args)
        tokens.append(token)
        assert held[-1] == token  # the key held this run's token
        spy.get.assert_called_once_with(key)  # the release compared it
        spy.delete.assert_called_once_with(key)
        assert cache.get(key) is None  # released after

    assert len(held) == 2 and tokens[0] != tokens[1]


@pytest.mark.django_db
@override_settings(
    SITE_URL="https://forum.example", WAGTAILFORUM_DIGEST_UNSUBSCRIBE=None
)
def test_a_lock_read_that_answers_none_still_releases_the_lock(monkeypatch):
    """Todo 630 (owner decision 2026-10-12): under IGNORE_EXCEPTIONS a Redis
    blip makes the release's get answer None. Keeping the lock would block
    the soft-time-limit continuation for the full TTL, so a None read falls
    back to a plain delete."""
    from unittest.mock import MagicMock

    from wagtail_forum.management.commands import send_forum_digest

    _member_with_a_reply("dg-blip-release")
    blip = MagicMock()
    blip.add.return_value = True
    blip.get.return_value = None
    monkeypatch.setattr(send_forum_digest, "cache", blip)

    call_command("send_forum_digest", frequency="weekly", stdout=StringIO())

    assert len(mail.outbox) == 1
    blip.delete.assert_called_once_with("wagtail_forum:digest-run:weekly")


@pytest.mark.django_db
@override_settings(
    SITE_URL="https://forum.example", WAGTAILFORUM_DIGEST_UNSUBSCRIBE=None
)
@pytest.mark.parametrize("change", ["cleared_email", "deactivated"])
def test_an_account_change_between_the_claim_and_the_read_gives_the_claim_back(
    monkeypatch, change
):
    """Todo 630: the claim succeeded, then the email was cleared or the
    account deactivated before the address was re-read. The command rolls
    the claim back and mails no one. The change lands right after the claim
    UPDATE runs, inside the command's transaction, so the claim's own
    filters cannot stop it first."""
    from django.db import connection

    member = User.objects.create_user(
        username=f"dg-after-claim-{change}", email=f"after-{change}@example.com"
    )
    profile = _opt_in(member)
    sent = []

    def send(digest):
        sent.append(digest.user.email)
        return True

    _one_topic_digest_patches(monkeypatch, send)
    claims = []

    def change_after_the_claim(execute, sql, params, many, context):
        result = execute(sql, params, many, context)
        if _is_the_claim(sql):
            claims.append(sql)
            if change == "cleared_email":
                User.objects.filter(pk=member.pk).update(email="")
            else:
                User.objects.filter(pk=member.pk).update(is_active=False)
        return result

    out = StringIO()
    with connection.execute_wrapper(change_after_the_claim):
        call_command("send_forum_digest", frequency="weekly", stdout=out)

    assert len(claims) == 1  # the claim ran, so this is the post-claim branch
    assert sent == []
    assert "sent=0 failed=0" in out.getvalue()
    profile.refresh_from_db()
    assert profile.last_digest_sent_at is None  # the claim was given back


def only_accounts_named_ok():
    """A host DIGEST_RECIPIENT_FILTER for the tests below (todo 620)."""
    from django.db.models import Q

    return Q(username__startswith="dg-ok")


_FILTER = "wagtail_forum.tests.test_digest.only_accounts_named_ok"


@pytest.mark.django_db
@override_settings(WAGTAILFORUM_DIGEST_RECIPIENT_FILTER=_FILTER)
def test_digest_recipients_apply_the_host_recipient_filter():
    """Todo 620: the host's account-wide policy (a master email switch) holds
    back an opted-in member the package alone would mail."""
    from wagtail_forum.digest import digest_recipients

    kept = _opt_in(User.objects.create_user(username="dg-ok-1", email="a@x.test"))
    _opt_in(User.objects.create_user(username="dg-held", email="b@x.test"))

    assert list(digest_recipients(DigestFrequency.WEEKLY)) == [kept]


@pytest.mark.django_db
@override_settings(WAGTAILFORUM_DIGEST_RECIPIENT_FILTER=None)
def test_digest_recipients_without_a_host_filter_keep_every_opted_in_account():
    from wagtail_forum.digest import digest_recipients

    a = _opt_in(User.objects.create_user(username="dg-ok-2", email="a@x.test"))
    b = _opt_in(User.objects.create_user(username="dg-free", email="b@x.test"))

    assert list(digest_recipients(DigestFrequency.WEEKLY)) == [a, b]


@pytest.mark.django_db
@override_settings(
    SITE_URL="https://forum.example",
    WAGTAILFORUM_DIGEST_UNSUBSCRIBE=None,
    WAGTAILFORUM_DIGEST_RECIPIENT_FILTER=_FILTER,
)
def test_a_member_the_host_filter_drops_mid_run_is_not_claimed_or_mailed(
    monkeypatch,
):
    """Todo 620: the claim rechecks the host filter too, so a member who
    switches email off after the chunk was read is not mailed."""
    member = User.objects.create_user(username="dg-ok-late", email="late@x.test")
    profile = _opt_in(member)
    sent = _patches_with_a_mid_run_change(
        monkeypatch,
        lambda user: User.objects.filter(pk=user.pk).update(username="dg-now-off"),
    )

    out = StringIO()
    call_command("send_forum_digest", frequency="weekly", stdout=out)

    assert sent == []
    assert "sent=0 failed=0" in out.getvalue()
    profile.refresh_from_db()
    assert profile.last_digest_sent_at is None
