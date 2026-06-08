import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from wagtail.models import Page, Workflow, WorkflowContentType, WorkflowTask
from wagtail_forum.models import ForumBoard, ForumIndex, Post, Topic
from wagtail_forum.models.moderation import SpamCheckTask

User = get_user_model()


def _draft_post(author, body_text):
    """A post in the born-draft state the moderation flow operates on.

    Posts are born live (DraftStateMixin default), so the moderation entry point
    sets live=False before running the workflow; the workflow's job is to publish
    clean content and leave spam as a draft. This helper mirrors that setup.
    """
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    topic = Topic.objects.create(board=board, title="T", slug="t", author=author)
    post = Post.objects.create(
        topic=topic,
        author=author,
        is_opening_post=True,
        body=[{"type": "paragraph", "value": f"<p>{body_text}</p>"}],
    )
    post.live = False
    post.save(update_fields=["live"])
    post.save_revision()
    return post


def _assign_workflow():
    # A host (e.g. apps.forum_host) may bootstrap the default workflow on
    # post_migrate, which lands in the shared test DB during setup. Clear any
    # pre-existing workflow state so this test owns what it asserts on.
    WorkflowContentType.objects.all().delete()
    Workflow.objects.all().delete()
    workflow = Workflow.objects.create(name="Forum moderation")
    task = SpamCheckTask.objects.create(name="Spam check")
    WorkflowTask.objects.create(workflow=workflow, task=task, sort_order=0)
    WorkflowContentType.objects.create(
        content_type=ContentType.objects.get_for_model(Post), workflow=workflow
    )
    return workflow


@pytest.mark.django_db
def test_clean_post_is_published_by_workflow():
    user = User.objects.create_user(username="ada", password="x")
    post = _draft_post(user, "a totally normal first post")

    # Automated moderation runs as the system (user=None) so the finish-action
    # publish skips Wagtail's editor permission check — forum authors are not
    # Wagtail editors; the spam check is the publication authority.
    _assign_workflow().start(post, None)
    post.refresh_from_db()

    assert post.live is True


@pytest.mark.django_db
def test_spammy_post_is_not_published():
    user = User.objects.create_user(username="eve", password="x")
    spam = "http://a.com http://b.com http://c.com http://d.com http://e.com"
    post = _draft_post(user, spam)

    # Must NOT recurse (update=False) and must NOT publish: the rejected workflow
    # leaves the post a draft for a human to review/publish from the admin.
    _assign_workflow().start(post, None)
    post.refresh_from_db()

    assert post.live is False


@pytest.mark.django_db
def test_spam_in_latest_revision_is_caught_not_db_row():
    # TOCTOU guard: the finish action publishes the LATEST REVISION, so the spam
    # check must inspect that revision, not the saved DB row. A post saved clean
    # whose latest revision was edited to spam must NOT publish.
    user = User.objects.create_user(username="sneak", password="x")
    post = _draft_post(user, "a totally clean saved body")  # DB row stays clean

    spam = "http://a.com http://b.com http://c.com http://d.com http://e.com"
    post.body = [{"type": "paragraph", "value": f"<p>{spam}</p>"}]
    post.save_revision()  # latest revision is now spam; DB row body still clean

    _assign_workflow().start(post, None)
    post.refresh_from_db()

    assert post.live is False
