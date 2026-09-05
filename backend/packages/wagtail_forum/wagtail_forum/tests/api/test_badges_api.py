"""Badges on the API (todo 348): `me/stats/` (with its lazy catch-up) and the
public profile carry earned badges in display order, flat in query count,
and the CMS snippet listing is reachable."""

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from wagtail_forum.models import (
    Badge,
    BadgeMetric,
    BadgeRule,
    ForumActivityDate,
    ForumProfile,
    UserBadge,
)

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


def _badge(slug, metric, threshold, order=0):
    badge = Badge.objects.create(slug=slug, name=slug.title(), order=order)
    BadgeRule.objects.create(badge=badge, metric=metric, threshold=threshold)
    return badge


@pytest.mark.django_db
def test_me_stats_lists_earned_badges_in_display_order_and_catches_up_lazily():
    """A member who already qualified before the badge existed is awarded on
    their first look at me/stats/ — the pre-engine Botanist holders' path."""
    user = User.objects.create_user(username="earner")
    ForumProfile.for_user(user)
    ForumActivityDate.record(user.pk)
    later = _badge("later", BadgeMetric.STREAK_DAYS, 1, order=20)
    first = _badge("first", BadgeMetric.STREAK_DAYS, 1, order=10)
    _badge("unearned", BadgeMetric.POSTS, 100, order=5)
    # Awarded DIRECTLY, in reverse display order, so the read path's
    # ORDER BY is what the assertion below pins — not the engine's own
    # iteration order (review); `earlier` is left for the lazy award.
    UserBadge.objects.create(user=user, badge=later)
    UserBadge.objects.create(user=user, badge=first)
    earlier = _badge("earlier", BadgeMetric.STREAK_DAYS, 1, order=1)

    client = APIClient()
    client.force_authenticate(user)
    resp = client.get("/forum/me/stats/")

    assert resp.status_code == 200
    assert [b["slug"] for b in resp.data["badges"]] == [
        earlier.slug,
        first.slug,
        later.slug,
    ]
    assert set(resp.data["badges"][0]) == {"slug", "name", "description", "awarded_at"}
    assert UserBadge.objects.filter(user=user).count() == 3
    # The single-badge progress fields are unchanged by the engine (AC2).
    assert {"badge_name", "badge_progress", "badge_target"} <= set(resp.data)


@pytest.mark.django_db
def test_me_stats_query_count_is_flat_in_the_number_of_badges_held():
    user = User.objects.create_user(username="flat")
    ForumProfile.for_user(user)
    ForumActivityDate.record(user.pk)
    _badge("one", BadgeMetric.STREAK_DAYS, 1)
    client = APIClient()
    client.force_authenticate(user)
    client.get("/forum/me/stats/")  # awards `one`, warms the presence touch
    cache.delete(f"forum:presence:{user.pk}")
    with CaptureQueriesContext(connection) as one:
        client.get("/forum/me/stats/")

    for i in range(5):
        _badge(f"more-{i}", BadgeMetric.STREAK_DAYS, 1)
    client.get("/forum/me/stats/")  # awards the five
    cache.delete(f"forum:presence:{user.pk}")
    with CaptureQueriesContext(connection) as six:
        resp = client.get("/forum/me/stats/")

    assert len(resp.data["badges"]) == 6
    assert len(six.captured_queries) == len(one.captured_queries)


@pytest.mark.django_db
def test_public_profile_shows_badges_even_to_a_viewer_who_blocked_the_member():
    from wagtail_forum.models import UserBlock

    member = User.objects.create_user(username="badged")
    viewer = User.objects.create_user(username="viewer")
    badge = _badge("day-one", BadgeMetric.STREAK_DAYS, 1)
    UserBadge.objects.create(user=member, badge=badge)
    hidden = Badge.objects.create(slug="retired", name="Retired", is_active=False)
    UserBadge.objects.create(user=member, badge=hidden)
    UserBlock.block(viewer, member)

    client = APIClient()
    client.force_authenticate(viewer)
    resp = client.get(f"/forum/users/{member.username}/")

    assert resp.status_code == 200
    assert resp.data["is_blocked"] is True
    # Identity, not content: the badge list is not collapsed by the block,
    # and an inactive badge is held but not shown.
    assert [b["slug"] for b in resp.data["badges"]] == ["day-one"]
    anon = APIClient().get(f"/forum/users/{member.username}/")
    assert [b["slug"] for b in anon.data["badges"]] == ["day-one"]


@pytest.mark.django_db
def test_me_stats_botanist_progress_reads_the_seeded_rule_not_the_setting():
    """Single source of truth (review): once seeded, retuning the Botanist
    rule in the CMS moves the progress bar; the setting is only the seed and
    the fallback for an unseeded host."""
    from django.core.management import call_command
    from wagtail_forum.conf import get_setting

    user = User.objects.create_user(username="botanist-bar")
    ForumProfile.for_user(user)
    client = APIClient()
    client.force_authenticate(user)

    unseeded = client.get("/forum/me/stats/")
    assert unseeded.data["badge_target"] == get_setting("BADGE_BOTANIST_THRESHOLD")
    assert unseeded.data["badge_name"] == get_setting("BADGE_BOTANIST_NAME")

    call_command("seed_default_badges")
    botanist = Badge.objects.get(slug="botanist")
    rule = botanist.rules.get()
    rule.threshold = 3
    rule.save(update_fields=["threshold"])
    botanist.name = "Master Botanist"
    botanist.save(update_fields=["name"])

    seeded = client.get("/forum/me/stats/")
    assert seeded.data["badge_target"] == 3
    assert seeded.data["badge_name"] == "Master Botanist"
