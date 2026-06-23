"""submit_edit_for_moderation: re-screen an edit without unpublishing live
content (Spec 2 Q2). Mirrors the PR-2a spike, now against the real helper."""

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from wagtail.models import Page
from wagtail_forum.blocks import ForumBodyBlock
from wagtail_forum.models import (
    ForumBoard,
    ForumIndex,
    ForumProfile,
    Post,
    Topic,
    TrustLevel,
)
from wagtail_forum.workflow import (
    ensure_default_workflow,
    submit_edit_for_moderation,
    submit_for_moderation,
)

User = get_user_model()
pytestmark = pytest.mark.django_db


def _board():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    return index.add_child(instance=ForumBoard(title="General", slug="general"))


def _author(username, trust):
    u = User.objects.create_user(username=username, password="x")
    p = ForumProfile.for_user(u)
    p.trust_level = trust
    p.save()
    return u


def _body(html):
    return ForumBodyBlock().to_python([{"type": "paragraph", "value": html}])


def _live_post(board, author, html="<p>original</p>", slug="t"):
    topic = Topic(board=board, title="t", slug=slug, author=author, live=False)
    topic.save()
    post = Post(
        topic=topic, author=author, is_opening_post=True, body=_body(html), live=False
    )
    post.save()
    submit_for_moderation(post, author)
    post.refresh_from_db()
    return post


def test_trusted_edit_publishes_immediately():
    ensure_default_workflow()
    author = _author("trusted", TrustLevel.MEMBER)
    post = _live_post(_board(), author)
    post.body = _body("<p>edited by trusted</p>")
    status = submit_edit_for_moderation(post, author)
    fresh = Post.objects.get(pk=post.pk)
    assert status == "published"
    assert fresh.live and "edited by trusted" in fresh.body[0].value.source
    assert fresh.edited is True


def test_untrusted_flagged_edit_keeps_old_body_live():
    ensure_default_workflow()
    author = _author("newbie", TrustLevel.NEW)
    post = _live_post(_board(), author, "<p>original clean</p>")
    post.body = _body("<p>spamzzz buy now</p>")
    with override_settings(WAGTAILFORUM_SPAM_BANNED_WORDS=["spamzzz"]):
        status = submit_edit_for_moderation(post, author)
    fresh = Post.objects.get(pk=post.pk)
    assert status == "pending"
    assert fresh.live, "post stays live during a pending edit"
    assert "original clean" in fresh.body[0].value.source, "OLD body keeps serving"
    assert "spamzzz" not in fresh.body[0].value.source
    assert fresh.edited is False
    assert fresh.has_unpublished_changes is True


def test_untrusted_clean_edit_auto_publishes():
    ensure_default_workflow()
    author = _author("newbie2", TrustLevel.NEW)
    post = _live_post(_board(), author, "<p>original2</p>")
    post.body = _body("<p>clean edit here</p>")
    status = submit_edit_for_moderation(post, author)
    fresh = Post.objects.get(pk=post.pk)
    assert status == "published"
    assert fresh.live and "clean edit here" in fresh.body[0].value.source
    assert fresh.edited is True
