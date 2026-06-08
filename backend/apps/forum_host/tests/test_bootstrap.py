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
def test_post_resolves_the_default_workflow():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    topic = Topic.objects.create(board=board, title="T", slug="t")
    post = Post.objects.create(topic=topic, is_opening_post=True)

    assert post.get_workflow() is not None
