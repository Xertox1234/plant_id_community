import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex, Post, Report, Topic
from wagtail_forum.workflow import ensure_default_workflow

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


@pytest.fixture(autouse=True)
def clear_idempotency_cache():
    """Prevent idempotency cache from bleeding between tests (LocMemCache is process-global)."""
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


def _board():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    return index.add_child(instance=ForumBoard(title="General", slug="general"))


def _live_topic():
    board = _board()
    author = User.objects.create_user(username="op")
    topic = Topic.objects.create(board=board, title="T", slug="t", author=author)
    opening = Post.objects.create(topic=topic, author=author, is_opening_post=True)
    opening.save_revision().publish()
    return topic, opening


@pytest.mark.django_db
def test_report_returns_200_and_never_echoes_a_count():
    ensure_default_workflow()
    _, opening = _live_topic()
    user = User.objects.create_user(username="r")
    client = APIClient()
    client.force_authenticate(user)

    resp = client.post(
        f"/forum/posts/{opening.id}/reports/", {"reason": "spam"}, format="json"
    )

    assert resp.status_code == 200
    assert resp.data == {"reported": True}  # no count field (audit L12)
    assert Report.objects.filter(post=opening, reporter=user).count() == 1


@pytest.mark.django_db
def test_can_report_flag_is_false_for_author_true_for_others():
    ensure_default_workflow()
    topic, opening = _live_topic()
    other = User.objects.create_user(username="r")

    as_author = APIClient()
    as_author.force_authenticate(opening.author)
    as_other = APIClient()
    as_other.force_authenticate(other)

    resp_author = as_author.get(f"/forum/topics/{topic.id}/posts/")
    resp_other = as_other.get(f"/forum/topics/{topic.id}/posts/")

    author_post = next(p for p in resp_author.data["results"] if p["id"] == opening.id)
    other_post = next(p for p in resp_other.data["results"] if p["id"] == opening.id)
    assert author_post["can_report"] is False
    assert other_post["can_report"] is True


@pytest.mark.django_db
def test_self_report_is_rejected():
    ensure_default_workflow()
    _, opening = _live_topic()
    client = APIClient()
    client.force_authenticate(opening.author)

    resp = client.post(
        f"/forum/posts/{opening.id}/reports/", {"reason": "spam"}, format="json"
    )

    assert resp.status_code == 400
    assert Report.objects.filter(post=opening).count() == 0


@pytest.mark.django_db
def test_report_rejects_invalid_reason():
    ensure_default_workflow()
    _, opening = _live_topic()
    user = User.objects.create_user(username="r")
    client = APIClient()
    client.force_authenticate(user)

    resp = client.post(
        f"/forum/posts/{opening.id}/reports/", {"reason": "bogus"}, format="json"
    )

    assert resp.status_code == 400


@pytest.mark.django_db
def test_report_on_non_live_topic_post_returns_404():
    # SECURITY: mirrors the reaction/reply non-live guard — a hidden post must
    # not be reportable, and must not reveal its existence.
    ensure_default_workflow()
    board = _board()
    author = User.objects.create_user(username="op")
    draft = Topic.objects.create(
        board=board, title="H", slug="h", author=author, live=False
    )
    hidden_post = Post.objects.create(
        topic=draft, author=author, is_opening_post=True, live=False
    )
    user = User.objects.create_user(username="r")
    client = APIClient()
    client.force_authenticate(user)

    resp = client.post(
        f"/forum/posts/{hidden_post.id}/reports/", {"reason": "spam"}, format="json"
    )

    assert resp.status_code == 404
    assert Report.objects.filter(post=hidden_post).count() == 0


@pytest.mark.django_db
def test_report_on_draft_post_of_live_topic_returns_404():
    # The other half of the `not post.live or not topic.live` guard, isolated
    # from the topic-level case above (mirrors the reaction endpoint's own
    # isolated test — kimi-review flagged that a single conflated test can't
    # tell you which filter clause is actually doing the work).
    ensure_default_workflow()
    topic, _ = _live_topic()
    author = topic.author
    draft_reply = Post.objects.create(
        topic=topic, author=author, is_opening_post=False, live=False
    )
    user = User.objects.create_user(username="r")
    client = APIClient()
    client.force_authenticate(user)

    resp = client.post(
        f"/forum/posts/{draft_reply.id}/reports/", {"reason": "spam"}, format="json"
    )

    assert resp.status_code == 404
    assert Report.objects.filter(post=draft_reply).count() == 0


@pytest.mark.django_db
def test_repeat_report_without_key_is_idempotent_not_an_error():
    # No Idempotency-Key header: dedup falls through to the model-layer unique
    # constraint, not the cache. Must still return 200, not 409/500.
    ensure_default_workflow()
    _, opening = _live_topic()
    user = User.objects.create_user(username="r")
    client = APIClient()
    client.force_authenticate(user)
    url = f"/forum/posts/{opening.id}/reports/"

    first = client.post(url, {"reason": "spam"}, format="json")
    second = client.post(url, {"reason": "abuse"}, format="json")

    assert first.status_code == 200
    assert second.status_code == 200
    assert Report.objects.filter(post=opening, reporter=user).count() == 1


@pytest.mark.django_db
def test_report_retry_with_idempotency_key_does_not_duplicate():
    ensure_default_workflow()
    _, opening = _live_topic()
    user = User.objects.create_user(username="r")
    client = APIClient()
    client.force_authenticate(user)
    url = f"/forum/posts/{opening.id}/reports/"

    r1 = client.post(url, {"reason": "spam"}, format="json", HTTP_IDEMPOTENCY_KEY="k1")
    r2 = client.post(url, {"reason": "spam"}, format="json", HTTP_IDEMPOTENCY_KEY="k1")

    assert r1.status_code == r2.status_code == 200
    assert r2.data == r1.data
    assert Report.objects.filter(post=opening, reporter=user).count() == 1


@pytest.mark.django_db
def test_report_hard_deleted_between_create_and_lock_is_404_not_500(monkeypatch):
    """A hard delete (topic CASCADE) landing between Report.file's own create()
    savepoint and its auto-hide lock re-fetch returns 404, not a 500
    (kimi-review, forum audit todo 254) — mirrors the DELETE endpoint's
    identical race guard (test_post_edit_delete.py). Report.post is
    on_delete=CASCADE, so the just-created report is cascade-deleted along
    with the post in the same statement — verified empirically, not left as
    an orphaned row, which is the harder case: the auto-hide block's lock
    re-fetch must still 404 cleanly with nothing left to find."""
    ensure_default_workflow()
    _, opening = _live_topic()
    real_create = Report.objects.create

    def create_then_delete_post(**kwargs):
        result = real_create(**kwargs)
        Post.objects.filter(id=opening.id).delete()
        return result

    monkeypatch.setattr(Report.objects, "create", create_then_delete_post)
    user = User.objects.create_user(username="r")
    client = APIClient()
    client.force_authenticate(user)

    resp = client.post(
        f"/forum/posts/{opening.id}/reports/", {"reason": "spam"}, format="json"
    )

    assert resp.status_code == 404
    # No orphaned report row survives the cascade — confirms the DB is left
    # consistent, not just that the response happens to be 404.
    assert not Report.objects.filter(post_id=opening.id).exists()
