import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from wagtail_forum.models import UserBlock

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


@pytest.mark.django_db
def test_block_creates_row():
    blocker = User.objects.create_user(username="blocker1")
    target = User.objects.create_user(username="target1")

    client = APIClient()
    client.force_authenticate(blocker)
    resp = client.post(f"/forum/users/{target.username}/block/")

    assert resp.status_code == 200
    assert resp.data == {"blocked": True}
    assert UserBlock.objects.filter(blocker=blocker, blocked=target).exists()


@pytest.mark.django_db
def test_block_is_idempotent():
    blocker = User.objects.create_user(username="blocker2")
    target = User.objects.create_user(username="target2")

    client = APIClient()
    client.force_authenticate(blocker)
    client.post(f"/forum/users/{target.username}/block/")
    resp = client.post(f"/forum/users/{target.username}/block/")

    assert resp.status_code == 200
    assert UserBlock.objects.filter(blocker=blocker, blocked=target).count() == 1


@pytest.mark.django_db
def test_unblock_removes_row():
    blocker = User.objects.create_user(username="blocker3")
    target = User.objects.create_user(username="target3")
    UserBlock.block(blocker, target)

    client = APIClient()
    client.force_authenticate(blocker)
    resp = client.delete(f"/forum/users/{target.username}/block/")

    assert resp.status_code == 200
    assert resp.data == {"blocked": False}
    assert not UserBlock.objects.filter(blocker=blocker, blocked=target).exists()


@pytest.mark.django_db
def test_unblock_when_not_blocked_is_noop():
    blocker = User.objects.create_user(username="blocker4")
    target = User.objects.create_user(username="target4")

    client = APIClient()
    client.force_authenticate(blocker)
    resp = client.delete(f"/forum/users/{target.username}/block/")

    assert resp.status_code == 200
    assert resp.data == {"blocked": False}


@pytest.mark.django_db
def test_unblock_survives_a_deactivated_target():
    # Deliberately NOT existence-gated — mirrors TopicSubscriptionView.delete:
    # a caller must always be able to remove their own block row even if the
    # target account was since deactivated (todo 284/M9).
    blocker = User.objects.create_user(username="blocker5")
    target = User.objects.create_user(username="target5")
    UserBlock.block(blocker, target)
    target.is_active = False
    target.save()

    client = APIClient()
    client.force_authenticate(blocker)
    resp = client.delete(f"/forum/users/{target.username}/block/")

    assert resp.status_code == 200
    assert not UserBlock.objects.filter(blocker=blocker, blocked=target).exists()


@pytest.mark.django_db
def test_self_block_is_rejected():
    # Mirrors test_reports.py::test_self_report_is_rejected exactly: a 400
    # and zero rows created.
    user = User.objects.create_user(username="selfblocker")

    client = APIClient()
    client.force_authenticate(user)
    resp = client.post(f"/forum/users/{user.username}/block/")

    assert resp.status_code == 400
    assert UserBlock.objects.filter(blocker=user, blocked=user).count() == 0


@pytest.mark.django_db
def test_block_nonexistent_username_404s():
    blocker = User.objects.create_user(username="blocker6")

    client = APIClient()
    client.force_authenticate(blocker)
    resp = client.post("/forum/users/does-not-exist/block/")

    assert resp.status_code == 404


@pytest.mark.django_db
def test_block_inactive_username_404s():
    blocker = User.objects.create_user(username="blocker7")
    target = User.objects.create_user(username="target7", is_active=False)

    client = APIClient()
    client.force_authenticate(blocker)
    resp = client.post(f"/forum/users/{target.username}/block/")

    assert resp.status_code == 404


@pytest.mark.django_db
def test_block_requires_authentication():
    target = User.objects.create_user(username="target8")

    client = APIClient()
    resp = client.post(f"/forum/users/{target.username}/block/")

    assert resp.status_code == 401


@pytest.mark.django_db
def test_unblock_requires_authentication():
    target = User.objects.create_user(username="target9")

    client = APIClient()
    resp = client.delete(f"/forum/users/{target.username}/block/")

    assert resp.status_code == 401


@pytest.mark.django_db
def test_my_blocks_requires_authentication():
    client = APIClient()
    resp = client.get("/forum/me/blocks/")

    assert resp.status_code == 401


@pytest.mark.django_db
def test_my_blocks_lists_newest_first():
    blocker = User.objects.create_user(username="blocker10")
    first = User.objects.create_user(username="first-blocked")
    second = User.objects.create_user(username="second-blocked")
    UserBlock.block(blocker, first)
    UserBlock.block(blocker, second)

    client = APIClient()
    client.force_authenticate(blocker)
    resp = client.get("/forum/me/blocks/")

    assert resp.status_code == 200
    usernames = [row["username"] for row in resp.data]
    assert usernames == ["second-blocked", "first-blocked"]


@pytest.mark.django_db
def test_my_blocks_only_shows_the_caller_own_blocks():
    blocker = User.objects.create_user(username="blocker11")
    other_blocker = User.objects.create_user(username="blocker12")
    target = User.objects.create_user(username="target11")
    UserBlock.block(other_blocker, target)

    client = APIClient()
    client.force_authenticate(blocker)
    resp = client.get("/forum/me/blocks/")

    assert resp.status_code == 200
    assert resp.data == []


# --- audit 2026-09-04 L12 ------------------------------------------------------


@pytest.mark.django_db
def test_my_blocks_with_avatars_adds_no_per_row_queries():
    """MyBlocksView's select_related("blocked__wagtail_forum_profile__avatar")
    had no query-count pin at all, and no fixture ever set an avatar, so the
    chain's last leg was never exercised (Pattern 30, query-optimization.md).
    Every blocked user gets an avatar here and the endpoint is pinned EXACTLY.
    Mutation-checked: dropping the select_related turns this red."""
    from django.core.cache import cache
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    from wagtail.images import get_image_model
    from wagtail.images.tests.utils import get_test_image_file
    from wagtail_forum.collections import get_forum_image_collection
    from wagtail_forum.models import ForumProfile

    blocker = User.objects.create_user(username="blocker13")
    for i in range(4):
        target = User.objects.create_user(username=f"avatar-target{i}")
        profile = ForumProfile.for_user(target)
        profile.avatar = get_image_model().objects.create(
            title=f"blocked-avatar-{i}",
            file=get_test_image_file(),
            collection=get_forum_image_collection(),
            uploaded_by_user=target,
        )
        profile.save(update_fields=["avatar"])
        UserBlock.block(blocker, target)

    client = APIClient()
    client.force_authenticate(blocker)
    # The presence touch is throttled by cache.add() on a key the test cache
    # (Redis, when reachable) keeps across runs and DB rebuilds — a leftover
    # key for a recycled pk would skip the UPDATE and break the exact pin.
    cache.delete(f"forum:presence:{blocker.pk}")
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get("/forum/me/blocks/")

    assert resp.status_code == 200
    assert len(resp.data) == 4
    assert all(row["avatar"] for row in resp.data)
    # Pinned EXACTLY: the todo 301 presence touch (UPDATE on the caller's own
    # profile) + one SELECT joining blocked -> profile -> avatar.
    assert len(ctx.captured_queries) == 2, [q["sql"][:80] for q in ctx.captured_queries]
