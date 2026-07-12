import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
def test_topic_snippet_list_is_reachable_in_admin(client):
    admin = User.objects.create_superuser(username="root", email="r@x.io")
    client.force_login(admin)

    resp = client.get("/cms/snippets/wagtail_forum/topic/")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_post_snippet_list_is_reachable_in_admin(client):
    admin = User.objects.create_superuser(username="root", email="r@x.io")
    client.force_login(admin)

    resp = client.get("/cms/snippets/wagtail_forum/post/")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_profile_snippet_list_is_reachable_in_admin(client):
    # ForumProfileViewSet is registered but its __str__ touches user.get_username();
    # guard the profile list against a silent 500 on a field/relation regression.
    admin = User.objects.create_superuser(username="root", email="r@x.io")
    client.force_login(admin)

    resp = client.get("/cms/snippets/wagtail_forum/forumprofile/")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_report_snippet_list_is_reachable_in_admin(client):
    admin = User.objects.create_superuser(username="root", email="r@x.io")
    client.force_login(admin)

    resp = client.get("/cms/snippets/wagtail_forum/report/")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_moderation_summary_item_counts_spam_rejected_post(client):
    # The homepage panel's signal is NEEDS_CHANGES content (spam the workflow
    # rejected, left as a draft) — drive a real post through submit_for_moderation
    # rather than hand-constructing a WorkflowState, so this proves the whole
    # chain: reject -> active WorkflowState -> _pending_moderation_count ->
    # homepage summary item (audit H16).
    from wagtail.models import Page
    from wagtail_forum.models import ForumBoard, ForumIndex, ForumProfile, Post, Topic
    from wagtail_forum.wagtail_hooks import _pending_moderation_count
    from wagtail_forum.workflow import ensure_default_workflow, submit_for_moderation

    ensure_default_workflow()
    author = User.objects.create_user(username="spammer")
    ForumProfile.for_user(author)  # trust NEW -- screened, not autopublished

    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    topic = Topic.objects.create(board=board, title="T", slug="t", author=author)
    spam = "http://a.com http://b.com http://c.com http://d.com http://e.com"
    post = Post(
        topic=topic,
        author=author,
        is_opening_post=True,
        body=[{"type": "paragraph", "value": f"<p>{spam}</p>"}],
    )
    post.save()
    status = submit_for_moderation(post, author)
    assert status == "pending"  # sanity: this really did get rejected, not published

    assert _pending_moderation_count() == 1

    admin = User.objects.create_superuser(username="root", email="r@x.io")
    client.force_login(admin)
    resp = client.get("/cms/")

    assert resp.status_code == 200
    assert b"1 Forum post awaiting moderation" in resp.content
