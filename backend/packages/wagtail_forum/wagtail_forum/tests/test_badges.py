"""Badge engine (todo 348): metrics, idempotent awards, any-rule semantics,
inactive badges, the signal-site triggers, and the two commands."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.utils import timezone
from wagtail.models import Page
from wagtail_forum.badges import award_badges_for_user, user_metrics
from wagtail_forum.models import (
    Badge,
    BadgeMetric,
    BadgeRule,
    ForumActivityDate,
    ForumBoard,
    ForumIndex,
    ForumProfile,
    Post,
    Topic,
    UserBadge,
)

User = get_user_model()


def _board(slug="general"):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug=f"forum-{slug}"))
    return index.add_child(instance=ForumBoard(title="General", slug=slug))


def _badge(slug, *rules, active=True, order=0):
    badge = Badge.objects.create(
        slug=slug, name=slug.title(), order=order, is_active=active
    )
    for metric, threshold in rules:
        BadgeRule.objects.create(badge=badge, metric=metric, threshold=threshold)
    return badge


@pytest.mark.django_db
def test_user_metrics_are_zero_for_a_member_who_never_wrote():
    user = User.objects.create_user(username="quiet")

    assert user_metrics(user.pk) == {
        BadgeMetric.POSTS: 0,
        BadgeMetric.SOLUTIONS_ACCEPTED: 0,
        BadgeMetric.IDENTIFICATIONS_SHARED: 0,
        BadgeMetric.STREAK_DAYS: 0,
    }


@pytest.mark.django_db
def test_user_metrics_read_the_counters_me_stats_shows():
    board = _board()
    author = User.objects.create_user(username="metrics")
    profile = ForumProfile.for_user(author)
    profile.post_count = 7
    profile.save(update_fields=["post_count"])
    topic = Topic.objects.create(
        board=board, title="T", slug="t", author=author, live=True
    )
    answer = Post.objects.create(topic=topic, author=author, live=True)
    Topic.objects.filter(pk=topic.pk).update(solved_post=answer)
    ForumActivityDate.record(author.pk)
    ForumActivityDate.record(author.pk, timezone.now() - timedelta(days=1))

    metrics = user_metrics(author.pk)

    assert metrics[BadgeMetric.POSTS] == 7
    assert metrics[BadgeMetric.SOLUTIONS_ACCEPTED] == 1
    assert metrics[BadgeMetric.STREAK_DAYS] == 2


@pytest.mark.django_db
def test_award_is_idempotent_and_returns_only_new_awards():
    user = User.objects.create_user(username="idem")
    ForumActivityDate.record(user.pk)
    badge = _badge("day-one", (BadgeMetric.STREAK_DAYS, 1))

    first = award_badges_for_user(user.pk)
    second = award_badges_for_user(user.pk)

    assert first == [badge]
    assert second == []
    assert UserBadge.objects.filter(user=user, badge=badge).count() == 1
    with pytest.raises(IntegrityError), transaction.atomic():  # DB backstop
        UserBadge.objects.create(user=user, badge=badge)


@pytest.mark.django_db
def test_any_rule_earns_the_badge_and_none_met_awards_nothing():
    user = User.objects.create_user(username="anyrule")
    ForumActivityDate.record(user.pk)
    either = _badge("either", (BadgeMetric.POSTS, 50), (BadgeMetric.STREAK_DAYS, 1))
    _badge("neither", (BadgeMetric.POSTS, 50), (BadgeMetric.SOLUTIONS_ACCEPTED, 1))
    _badge("no-rules")  # can never be earned

    awarded = award_badges_for_user(user.pk)

    assert awarded == [either]


@pytest.mark.django_db
def test_inactive_badges_are_neither_awarded_nor_needed_for_nothing_to_award():
    user = User.objects.create_user(username="inactive")
    ForumActivityDate.record(user.pk)
    _badge("off", (BadgeMetric.STREAK_DAYS, 1), active=False)

    assert award_badges_for_user(user.pk) == []
    assert not UserBadge.objects.exists()


@pytest.mark.django_db
def test_a_post_first_publish_awards_after_commit(django_capture_on_commit_callbacks):
    """The signal-site trigger: publishing a first post records today's
    activity and, once the write commits, evaluates the author."""
    board = _board()
    author = User.objects.create_user(username="publisher")
    badge = _badge("first-post", (BadgeMetric.POSTS, 1))
    topic = Topic.objects.create(
        board=board, title="T", slug="t", author=author, live=True
    )
    post = Post(topic=topic, author=author, is_opening_post=True)
    post.save()

    with django_capture_on_commit_callbacks(execute=True):
        post.save_revision().publish()

    assert list(
        UserBadge.objects.filter(user=author).values_list("badge", flat=True)
    ) == [badge.pk]


@pytest.mark.django_db
def test_badge_awarded_signal_fires_once_per_new_award():
    from wagtail_forum.signals import badge_awarded

    user = User.objects.create_user(username="signalled")
    ForumActivityDate.record(user.pk)
    badge = _badge("day-one", (BadgeMetric.STREAK_DAYS, 1))
    seen = []

    def receiver(sender, **kw):
        seen.append(kw["badge"])

    badge_awarded.connect(receiver, weak=False)
    try:
        award_badges_for_user(user.pk)
        award_badges_for_user(user.pk)
    finally:
        badge_awarded.disconnect(receiver)

    assert seen == [badge]


@pytest.mark.django_db
def test_seed_default_badges_is_idempotent_and_never_edits_existing():
    from wagtail_forum.conf import get_setting

    call_command("seed_default_badges")
    assert Badge.objects.count() == 5
    botanist = Badge.objects.get(slug="botanist")
    assert botanist.name == get_setting("BADGE_BOTANIST_NAME")
    assert botanist.rules.get().threshold == get_setting("BADGE_BOTANIST_THRESHOLD")

    # A CMS edit survives a re-seed; nothing is duplicated.
    botanist.name = "Master Botanist"
    botanist.save(update_fields=["name"])
    call_command("seed_default_badges")

    assert Badge.objects.count() == 5
    assert Badge.objects.get(slug="botanist").name == "Master Botanist"


@pytest.mark.django_db
def test_seed_default_badges_skips_a_name_collision_instead_of_failing_the_deploy():
    """`name` is unique and CMS-editable (review): a host badge that already
    took a default's NAME under another slug must make the seed skip that
    default — never raise inside preDeployCommand."""
    Badge.objects.create(slug="custom-first", name="First post")

    call_command("seed_default_badges")

    assert Badge.objects.count() == 5  # 1 existing + 4 seeded
    assert not Badge.objects.filter(slug="first-post").exists()


@pytest.mark.django_db
def test_award_badges_command_backfills_every_member_with_a_profile():
    users = [User.objects.create_user(username=f"backfill{i}") for i in range(3)]
    for user in users[:2]:
        ForumProfile.for_user(user)
        ForumActivityDate.record(user.pk)
    # users[2] has no profile: never wrote, never evaluated (every metric 0).
    badge = _badge("day-one", (BadgeMetric.STREAK_DAYS, 1))

    call_command("award_badges", "--all")

    assert set(
        UserBadge.objects.filter(badge=badge).values_list("user", flat=True)
    ) == {
        users[0].pk,
        users[1].pk,
    }

    # --username evaluates ONLY that member: a badge seeded after the bulk
    # run lands for users[0] alone (review: the previous assertion was
    # already true before this call).
    later = _badge("day-one-again", (BadgeMetric.STREAK_DAYS, 1))
    call_command("award_badges", "--username", users[0].username)
    assert list(
        UserBadge.objects.filter(badge=later).values_list("user", flat=True)
    ) == [users[0].pk]


@pytest.mark.django_db
def test_deleting_a_badge_with_awards_is_refused_retire_it_instead():
    """PROTECT (review): a plain FK is not in Wagtail's ReferenceIndex, so a
    CASCADE would erase award history with no admin warning."""
    from django.db.models import ProtectedError

    user = User.objects.create_user(username="protected")
    ForumActivityDate.record(user.pk)
    badge = _badge("day-one", (BadgeMetric.STREAK_DAYS, 1))
    award_badges_for_user(user.pk)

    with pytest.raises(ProtectedError):
        badge.delete()
    badge.is_active = False
    badge.save(update_fields=["is_active"])
    assert UserBadge.objects.filter(user=user, badge=badge).exists()  # kept, hidden
    _badge("unawarded", (BadgeMetric.POSTS, 99)).delete()  # no awards: fine


@pytest.mark.django_db
def test_user_metrics_match_the_me_stats_counters_for_the_same_member():
    """The engine's docstring claims these are the same four counters
    `GET me/stats/` shows; they are computed twice (badges.py, views.py), so
    pin them against each other so one cannot drift (review)."""
    from rest_framework.test import APIClient

    board = _board()
    author = User.objects.create_user(username="drift")
    ForumProfile.for_user(author)
    topic = Topic.objects.create(
        board=board, title="T", slug="t", author=author, live=True
    )
    answer = Post.objects.create(topic=topic, author=author, live=True)
    Topic.objects.filter(pk=topic.pk).update(solved_post=answer)
    ForumActivityDate.record(author.pk)

    client = APIClient()
    client.force_authenticate(author)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("django.conf.settings.ROOT_URLCONF", "wagtail_forum.tests.api.urls")
        stats = client.get("/forum/me/stats/").data
    metrics = user_metrics(author.pk)

    assert metrics[BadgeMetric.POSTS] == stats["posts"]
    assert metrics[BadgeMetric.SOLUTIONS_ACCEPTED] == stats["solutions_accepted"] == 1
    assert (
        metrics[BadgeMetric.IDENTIFICATIONS_SHARED] == stats["identifications_shared"]
    )
    assert metrics[BadgeMetric.STREAK_DAYS] == stats["streak_days"] == 1
