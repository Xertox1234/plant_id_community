import pytest
from django.contrib.auth.models import Group
from wagtail.models import Page, Workflow
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
def test_post_resolves_the_default_workflow():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    topic = Topic.objects.create(board=board, title="T", slug="t")
    post = Post.objects.create(topic=topic, is_opening_post=True)

    assert post.get_workflow() is not None
