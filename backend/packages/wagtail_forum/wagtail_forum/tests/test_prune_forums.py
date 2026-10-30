"""``manage.py prune_forums`` (todo 679): per-forum pruning by days since the
last post (owner decision 2026-10-30: no days-since-viewed rule)."""

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone
from wagtail_forum.models import Poll, Topic
from wagtail_forum.tests.factories import make_forum

pytestmark = pytest.mark.django_db


def _topic(board, slug, *, days_ago, **fields):
    return Topic.objects.create(
        board=board,
        title=slug,
        slug=slug,
        live=True,
        last_post_at=timezone.now() - timedelta(days=days_ago),
        **fields,
    )


def _live(*topics):
    return {t.slug for t in topics if Topic.objects.get(pk=t.pk).live}


def _prune(*args):
    out = StringIO()
    call_command("prune_forums", *args, stdout=out)
    return out.getvalue()


@pytest.fixture
def forum():
    return make_forum(
        name="Swap", slug="swap", prune_enabled=True, prune_days_since_last_post=30
    )


def test_only_topics_past_the_threshold_are_pruned_and_pinned_and_polls_spared(forum):
    old = _topic(forum, "old", days_ago=31)
    fresh = _topic(forum, "fresh", days_ago=29)
    pinned = _topic(forum, "pinned", days_ago=90, is_pinned=True)
    polled = _topic(forum, "polled", days_ago=90)
    Poll.objects.create(topic=polled, question="Which?")

    output = _prune()

    assert _live(old, fresh, pinned, polled) == {"fresh", "pinned", "polled"}
    # A take-down, not a delete: the topic is still there to restore.
    assert Topic.objects.filter(pk=old.pk).exists()
    assert "[PRUNE] forum swap: 1 topic(s) unpublished" in output


def test_pinned_and_poll_topics_are_pruned_when_the_forum_says_so(forum):
    forum.prune_pinned = True
    forum.prune_polls = True
    forum.save()
    pinned = _topic(forum, "pinned", days_ago=90, is_pinned=True)
    polled = _topic(forum, "polled", days_ago=90)
    Poll.objects.create(topic=polled, question="Which?")

    _prune()

    assert _live(pinned, polled) == set()


def test_dry_run_changes_nothing(forum):
    old = _topic(forum, "old", days_ago=31)

    output = _prune("--dry-run")

    assert _live(old) == {"old"}
    assert "1 topic(s) would be unpublished" in output


def test_forums_with_pruning_disabled_are_untouched():
    off = make_forum(name="Off", slug="off", prune_days_since_last_post=1)
    no_days = make_forum(name="NoDays", slug="no-days", prune_enabled=True)
    a = _topic(off, "a", days_ago=400)
    b = _topic(no_days, "b", days_ago=400)

    _prune()

    assert _live(a, b) == {"a", "b"}
