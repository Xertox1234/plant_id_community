import pytest
from django.contrib.auth.models import Group
from wagtail.models import GroupCollectionPermission, Page, Workflow
from wagtail_forum.collections import get_forum_image_collection
from wagtail_forum.models import ForumBoard, ForumIndex, Post, Topic
from wagtail_forum.workflow import DEFAULT_WORKFLOW_NAME


@pytest.mark.django_db
def test_bootstrap_created_workflow_and_group():
    # post_migrate ran during test-DB setup; both should exist.
    assert Workflow.objects.filter(name=DEFAULT_WORKFLOW_NAME).exists()
    group = Group.objects.filter(name="Forum Moderators").first()
    assert group is not None
    # Assert perms were actually attached — not just that the group exists. If
    # forum_host ran before wagtail_forum's create_permissions, this would be 0.
    assert group.permissions.count() > 0


@pytest.mark.django_db
def test_bootstrap_preserves_admin_added_permissions():
    """Re-running bootstrap (every deploy's migrate) must not strip permissions
    an admin granted to the group (2026-06-10 audit M3)."""
    from apps.forum_host.bootstrap import ensure_forum_bootstrap
    from django.contrib.auth.models import Permission

    group = Group.objects.get(name="Forum Moderators")
    extra = Permission.objects.exclude(pk__in=group.permissions.all()).first()
    group.permissions.add(extra)

    ensure_forum_bootstrap(sender=type("S", (), {"label": "forum_host"}))

    assert group.permissions.filter(pk=extra.pk).exists()


@pytest.mark.django_db
def test_moderator_group_grants_wagtail_admin_access():
    """A user whose only group is Forum Moderators must be able to log into
    /cms/ — the group needs wagtailadmin.access_admin (2026-06-10 audit M3)."""
    group = Group.objects.get(name="Forum Moderators")
    assert group.permissions.filter(
        codename="access_admin", content_type__app_label="wagtailadmin"
    ).exists()


@pytest.mark.django_db
def test_moderator_group_can_view_and_change_reports():
    """The moderation queue (todo 345) and the Report snippet inspect/edit
    views are gated on Report permissions; a moderator who can act on posts
    but not on the reports that flagged them would see a queue whose every
    link bounces to the admin home (review finding, PR for todo 345)."""
    group = Group.objects.get(name="Forum Moderators")
    codenames = set(
        group.permissions.filter(content_type__app_label="wagtail_forum").values_list(
            "codename", flat=True
        )
    )
    assert {"view_report", "change_report"} <= codenames


@pytest.mark.django_db
def test_post_resolves_the_default_workflow():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    topic = Topic.objects.create(board=board, title="T", slug="t")
    post = Post.objects.create(topic=topic, is_opening_post=True)

    assert post.get_workflow() is not None


@pytest.mark.django_db
def test_forum_members_group_can_add_and_choose_forum_images():
    """New members must be able to upload to the forum's own image
    collection AND browse their own past uploads there (audit: image
    permissions were previously never wired to non-moderator users at all)."""
    group = Group.objects.filter(name="Forum Members").first()
    assert group is not None

    collection = get_forum_image_collection()
    codenames = set(
        GroupCollectionPermission.objects.filter(
            group=group, collection=collection
        ).values_list("permission__codename", flat=True)
    )
    assert {"add_image", "choose_image"} <= codenames


@pytest.mark.django_db
def test_forum_moderators_group_can_change_forum_images():
    """Moderators get change_image on the forum collection —
    CollectionOwnershipPermissionPolicy treats "delete" as equivalent to
    "change", so this alone covers removing ANY forum image, not just ones
    a moderator personally uploaded."""
    group = Group.objects.get(name="Forum Moderators")
    collection = get_forum_image_collection()
    assert GroupCollectionPermission.objects.filter(
        group=group, collection=collection, permission__codename="change_image"
    ).exists()


@pytest.mark.django_db
def test_image_permission_bootstrap_is_idempotent():
    """Re-running bootstrap (every deploy's migrate) must not raise or
    duplicate GroupCollectionPermission rows (unique_together enforces this;
    this test is the regression guard if that constraint is ever loosened)."""
    from apps.forum_host.bootstrap import ensure_forum_bootstrap

    ensure_forum_bootstrap(sender=type("S", (), {"label": "forum_host"}))
    ensure_forum_bootstrap(sender=type("S", (), {"label": "forum_host"}))

    group = Group.objects.get(name="Forum Members")
    collection = get_forum_image_collection()
    assert (
        GroupCollectionPermission.objects.filter(
            group=group, collection=collection, permission__codename="add_image"
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_image_permissions_skip_an_empty_collection_tree():
    """`post_migrate` fires from `flush`, not only from `migrate`.

    Django's `flush` — what `TransactionTestCase._fixture_teardown` runs —
    TRUNCATES every table and then re-emits `post_migrate`. Wagtail's root
    Collection comes from a data migration, which does not re-run, so the
    receiver can legitimately see an empty collection tree and
    `Collection.get_first_root_node()` returns None.

    Raising there fails the teardown of every TransactionTestCase in the
    suite: it cost 12 blog-analytics tests and a forum migration test, none of
    which touch forum images.

    The tree is emptied directly rather than by relying on a
    `transaction=True` teardown — a test that only asserted "teardown did not
    explode" passed with the guard REMOVED, so it discriminated nothing.
    """
    from apps.forum_host.bootstrap import _ensure_forum_image_permissions
    from wagtail.models import Collection

    Collection.objects.all().delete()
    assert Collection.get_first_root_node() is None

    _ensure_forum_image_permissions()  # must not raise
