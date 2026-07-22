"""Tests for the host-side forum AI thread-summary feature (todo 255 slice 3 /
H14): the premium-gated GET endpoint, the Celery generation task, and the
content-hash source builder.

Mirrors test_spam.py (mock the LLM), test_tasks.py (bound-task invocation +
retry pinning), and test_signals.py (real Topic/Post fixtures, enqueue asserts).
"""

from unittest.mock import patch

import pytest
from apps.blog.services.ai_cache_service import AICacheService
from apps.forum_host import constants
from apps.forum_host.summary import build_summary_source
from celery.exceptions import Retry
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from freezegun import freeze_time
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex, Post, Topic

User = get_user_model()

# Lazy imports inside the task bind these names fresh from their source modules
# on each call, so patch at the SOURCE (not as re-exported into tasks.py).
GEN = "apps.blog.wagtail_ai_v3_integration.generate_ai_text"
BUDGET = "apps.blog.services.ai_rate_limiter.AIRateLimiter.check_global_limit"
DELAY = "apps.forum_host.summary.generate_topic_summary.delay"


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def _board(suffix=""):
    root = Page.objects.get(id=1)
    index = root.add_child(
        instance=ForumIndex(title=f"Forum{suffix}", slug=f"forum{suffix}")
    )
    return index.add_child(
        instance=ForumBoard(title=f"General{suffix}", slug=f"general{suffix}")
    )


def _topic_with_posts(n_posts, *, suffix="", body_text="a gardening reply"):
    """Create a live topic with ``n_posts`` live posts (first is the opener)."""
    author = User.objects.create_user(username=f"author{suffix}")
    board = _board(suffix)
    topic = Topic.objects.create(
        board=board, title=f"Tomato blight{suffix}", slug=f"t{suffix}", author=author
    )
    for i in range(n_posts):
        Post.objects.create(
            topic=topic,
            author=author,
            is_opening_post=(i == 0),
            body=[{"type": "paragraph", "value": f"<p>{body_text} {i}</p>"}],
        )
    return topic


def _premium_client():
    user = User.objects.create_user(username="premium", is_premium=True)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _url(topic_id):
    return f"/api/v1/forum/topics/{topic_id}/summary/"


# --------------------------------------------------------------------------- #
# Endpoint — entitlement gating                                               #
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_anonymous_request_is_401():
    topic = _topic_with_posts(3)
    resp = APIClient().get(_url(topic.id))
    # JWT authenticators present + unauthenticated → NotAuthenticated (401).
    assert resp.status_code == 401


@pytest.mark.django_db
def test_authenticated_non_premium_is_403():
    topic = _topic_with_posts(3)
    user = User.objects.create_user(username="basic")  # is_premium defaults False
    client = APIClient()
    client.force_authenticate(user=user)
    resp = client.get(_url(topic.id))
    assert resp.status_code == 403


@pytest.mark.django_db
def test_staff_gets_premium_equivalent_access():
    # has_premium_access() = is_premium OR is_staff OR is_superuser (slice 1).
    topic = _topic_with_posts(3)
    staff = User.objects.create_user(username="staffer", is_staff=True)
    client = APIClient()
    client.force_authenticate(user=staff)
    with patch(DELAY) as mock_delay:
        resp = client.get(_url(topic.id))
    assert resp.status_code == 202
    mock_delay.assert_called_once_with(topic.id)


# --------------------------------------------------------------------------- #
# Endpoint — cache-miss / pending / ready / too-short / 404                    #
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_too_short_topic_returns_200_without_enqueue():
    topic = _topic_with_posts(constants.SUMMARY_MIN_POSTS - 1)
    client = _premium_client()
    with patch(DELAY) as mock_delay:
        resp = client.get(_url(topic.id))
    assert resp.status_code == 200
    assert resp.json()["status"] == "too_short"
    mock_delay.assert_not_called()


@pytest.mark.django_db
def test_cache_miss_enqueues_once_and_returns_202():
    topic = _topic_with_posts(3)
    client = _premium_client()
    with patch(DELAY) as mock_delay:
        resp = client.get(_url(topic.id))
    assert resp.status_code == 202
    assert resp.json()["status"] == "pending"
    mock_delay.assert_called_once_with(topic.id)


@pytest.mark.django_db
def test_burst_of_polls_enqueues_only_once():
    topic = _topic_with_posts(3)
    client = _premium_client()
    with patch(DELAY) as mock_delay:
        first = client.get(_url(topic.id))
        second = client.get(_url(topic.id))
        third = client.get(_url(topic.id))
    assert (first.status_code, second.status_code, third.status_code) == (202, 202, 202)
    # The pending lock (cache.add) dedupes concurrent enqueues per thread state.
    mock_delay.assert_called_once_with(topic.id)


@pytest.mark.django_db
def test_cache_hit_returns_ready_without_enqueue():
    topic = _topic_with_posts(3)
    content, post_count = build_summary_source(topic)
    AICacheService.set_cached_response(
        constants.SUMMARY_CACHE_FEATURE,
        content,
        {"summary": "A tidy summary.", "post_count": post_count, "generated_at": "x"},
    )
    client = _premium_client()
    with patch(DELAY) as mock_delay:
        resp = client.get(_url(topic.id))
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["summary"] == "A tidy summary."
    mock_delay.assert_not_called()


@pytest.mark.django_db
def test_missing_topic_returns_404():
    client = _premium_client()
    with patch(DELAY) as mock_delay:
        resp = client.get(_url(999999))
    assert resp.status_code == 404
    mock_delay.assert_not_called()


@pytest.mark.django_db
def test_enqueue_failure_releases_lock_and_still_returns_202():
    topic = _topic_with_posts(3)
    client = _premium_client()
    # Broker down: first poll's enqueue raises; the lock must be released so a
    # later poll re-enqueues rather than being wedged for the lock TTL.
    with patch(DELAY, side_effect=RuntimeError("broker down")) as mock_delay:
        first = client.get(_url(topic.id))
        second = client.get(_url(topic.id))
    assert first.status_code == 202
    assert second.status_code == 202
    assert mock_delay.call_count == 2  # lock released after the first failure


# --------------------------------------------------------------------------- #
# Celery task — generate / cache / budget / retry / missing                   #
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_task_generates_and_caches_summary():
    from apps.forum_host.tasks import generate_topic_summary

    topic = _topic_with_posts(3)
    content, post_count = build_summary_source(topic)
    with patch(BUDGET, return_value=True), patch(
        GEN, return_value="This thread is about tomato blight."
    ) as mock_gen:
        generate_topic_summary(topic.id)
    mock_gen.assert_called_once()
    cached = AICacheService.get_cached_response(
        constants.SUMMARY_CACHE_FEATURE, content
    )
    assert cached is not None
    assert cached["summary"] == "This thread is about tomato blight."
    assert cached["post_count"] == post_count
    assert "generated_at" in cached


@pytest.mark.django_db
def test_task_is_noop_when_already_cached():
    from apps.forum_host.tasks import generate_topic_summary

    topic = _topic_with_posts(3)
    content, post_count = build_summary_source(topic)
    AICacheService.set_cached_response(
        constants.SUMMARY_CACHE_FEATURE,
        content,
        {"summary": "already here", "post_count": post_count, "generated_at": "x"},
    )
    with patch(BUDGET, return_value=True), patch(GEN) as mock_gen:
        generate_topic_summary(topic.id)
    mock_gen.assert_not_called()  # racing task short-circuits, no spend


@pytest.mark.django_db
def test_task_skips_when_global_budget_exhausted():
    from apps.forum_host.tasks import generate_topic_summary

    topic = _topic_with_posts(3)
    content, _ = build_summary_source(topic)
    with patch(BUDGET, return_value=False), patch(GEN) as mock_gen:
        generate_topic_summary(topic.id)
    mock_gen.assert_not_called()  # no spend past the cap
    # Degrade-to-noop, not retry: nothing cached, task returned cleanly.
    assert (
        AICacheService.get_cached_response(constants.SUMMARY_CACHE_FEATURE, content)
        is None
    )


@pytest.mark.django_db
def test_task_skips_missing_topic_without_spend():
    from apps.forum_host.tasks import generate_topic_summary

    with patch(BUDGET, return_value=True), patch(GEN) as mock_gen:
        generate_topic_summary(999999)  # no such topic
    mock_gen.assert_not_called()


@pytest.mark.django_db
def test_task_skips_too_short_topic_without_spend():
    from apps.forum_host.tasks import generate_topic_summary

    topic = _topic_with_posts(constants.SUMMARY_MIN_POSTS - 1)
    with patch(BUDGET, return_value=True), patch(GEN) as mock_gen:
        generate_topic_summary(topic.id)
    mock_gen.assert_not_called()


@pytest.mark.django_db
def test_task_retries_on_transient_provider_error_with_backoff():
    from apps.forum_host.tasks import generate_topic_summary

    topic = _topic_with_posts(3)
    prior_retries = 1
    with patch(BUDGET, return_value=True), patch(
        GEN, side_effect=RuntimeError("provider down")
    ), patch.object(
        generate_topic_summary, "retry", side_effect=Retry("retried")
    ) as mock_retry:
        generate_topic_summary.push_request(retries=prior_retries)
        try:
            with pytest.raises(Retry):
                generate_topic_summary.run(topic.id)
        finally:
            generate_topic_summary.pop_request()
    mock_retry.assert_called_once()
    # Exponential backoff: default_retry_delay * 2**prior_retries.
    assert mock_retry.call_args.kwargs["countdown"] == constants.SUMMARY_RETRY_DELAY * (
        2**prior_retries
    )


# --------------------------------------------------------------------------- #
# build_summary_source — content-hash invalidation                            #
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_summary_source_changes_when_a_post_is_added():
    topic = _topic_with_posts(3)
    before, count_before = build_summary_source(topic)
    Post.objects.create(
        topic=topic,
        author=topic.author,
        is_opening_post=False,
        body=[{"type": "paragraph", "value": "<p>a brand new reply</p>"}],
    )
    after, count_after = build_summary_source(topic)
    assert count_after == count_before + 1
    # A changed thread yields a different content string → different cache key →
    # the stale summary auto-invalidates.
    assert before != after


@pytest.mark.django_db
def test_task_retries_and_does_not_cache_empty_summary():
    """An empty/whitespace completion is a transient glitch, never cached (else
    it would serve blank for the 30-day TTL) — retried like any failure."""
    from apps.forum_host.tasks import generate_topic_summary

    topic = _topic_with_posts(3)
    content, _ = build_summary_source(topic)
    with patch(BUDGET, return_value=True), patch(GEN, return_value="   "), patch.object(
        generate_topic_summary, "retry", side_effect=Retry("retried")
    ) as mock_retry:
        generate_topic_summary.push_request(retries=0)
        try:
            with pytest.raises(Retry):
                generate_topic_summary.run(topic.id)
        finally:
            generate_topic_summary.pop_request()
    mock_retry.assert_called_once()
    assert (
        AICacheService.get_cached_response(constants.SUMMARY_CACHE_FEATURE, content)
        is None
    )


@override_settings(FORUM_RATELIMITS={"topic_summary": "1/h"})
@pytest.mark.django_db
def test_summary_get_is_throttled_per_user():
    """The throttle actually fires at runtime (not merely documented): the 2nd
    poll within the window is a real 429."""
    topic = _topic_with_posts(3)
    client = _premium_client()
    with freeze_time("2026-07-22 12:00:00"), patch(DELAY):
        first = client.get(_url(topic.id))
        second = client.get(_url(topic.id))
    assert first.status_code == 202
    assert second.status_code == 429
