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
from wagtail_forum.signals import moderation_decided
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


def test_flagged_then_clean_edit_not_wedged():
    """Regression (finding #1): a spam-rejected edit leaves an active
    NEEDS_CHANGES workflow state; a later clean edit on the SAME post must still
    be screened and published, not permanently wedged 'pending'. Before the fix
    the second workflow.start() raised ValidationError (one active state only)."""
    ensure_default_workflow()
    author = _author("wedgee", TrustLevel.NEW)
    post = _live_post(_board(), author, "<p>original clean</p>")
    # First edit is flagged -> rejected -> post keeps its old body, stays pending.
    post.body = _body("<p>spamzzz buy now</p>")
    with override_settings(WAGTAILFORUM_SPAM_BANNED_WORDS=["spamzzz"]):
        first = submit_edit_for_moderation(post, author)
    assert first == "pending"
    # Second, CLEAN edit on the SAME post must not be wedged by the stale state.
    post = Post.objects.get(pk=post.pk)
    post.body = _body("<p>clean followup</p>")
    second = submit_edit_for_moderation(post, author)
    fresh = Post.objects.get(pk=post.pk)
    assert second == "published"
    assert fresh.live and "clean followup" in fresh.body[0].value.source


def test_edit_fires_moderation_decided():
    """The edit path fires moderation_decided like the create path (finding #4)."""
    ensure_default_workflow()
    author = _author("signaler", TrustLevel.MEMBER)
    post = _live_post(_board(), author)
    received = []

    def receiver(sender, obj, status, **kwargs):
        received.append((obj.pk, status))

    moderation_decided.connect(receiver)
    try:
        post.body = _body("<p>edited body</p>")
        submit_edit_for_moderation(post, author)
    finally:
        moderation_decided.disconnect(receiver)
    assert received == [(post.pk, "published")]


def test_edit_does_not_resurrect_unpublished_post():
    """Race guard (finding #13): if a concurrent DELETE unpublishes the post
    between the edit's liveness gate and publish, the edit must NOT republish it.
    The row lock plus a liveness re-read inside submit_edit_for_moderation
    refuses to resurrect a taken-down post. A full two-thread harness is omitted
    as flaky; this asserts the invariant the lock enforces by simulating the
    concurrent take-down having already committed."""
    ensure_default_workflow()
    author = _author("racer", TrustLevel.MEMBER)  # trusted -> would publish
    post = _live_post(_board(), author)
    # Simulate the concurrent delete having committed after the liveness gate.
    Post.objects.filter(pk=post.pk).update(live=False)
    post.refresh_from_db()
    post.body = _body("<p>edit after delete</p>")
    submit_edit_for_moderation(post, author)
    fresh = Post.objects.get(pk=post.pk)
    assert fresh.live is False, "a concurrently-deleted post must not be resurrected"


def test_author_deleted_moderator_edit_publishes():
    """A moderator editing an account-deleted author's post (author=None,
    SET_NULL) publishes immediately — no ForumProfile.for_user(None) crash, and
    the redaction is not left pending behind the un-redacted live body
    (finding #2)."""
    ensure_default_workflow()
    author = _author("gone", TrustLevel.MEMBER)
    post = _live_post(_board(), author)
    Post.objects.filter(pk=post.pk).update(author=None)
    post = Post.objects.get(pk=post.pk)
    post.body = _body("<p>[redacted by mod]</p>")
    status = submit_edit_for_moderation(post, author, acting_as_moderator=True)
    fresh = Post.objects.get(pk=post.pk)
    assert status == "published"
    assert fresh.live and "[redacted by mod]" in fresh.body[0].value.source


def test_author_deleted_untrusted_edit_is_screened_not_crash():
    """author=None without moderator authority is screened as untrusted rather
    than crashing on ForumProfile.for_user(None) (finding #2, fail-safe)."""
    ensure_default_workflow()
    author = _author("gone2", TrustLevel.MEMBER)
    post = _live_post(_board(), author, "<p>original kept</p>")
    Post.objects.filter(pk=post.pk).update(author=None)
    post = Post.objects.get(pk=post.pk)
    post.body = _body("<p>spamzzz</p>")
    with override_settings(WAGTAILFORUM_SPAM_BANNED_WORDS=["spamzzz"]):
        status = submit_edit_for_moderation(post, author, acting_as_moderator=False)
    fresh = Post.objects.get(pk=post.pk)
    assert status == "pending"  # screened as untrusted, not autopublished
    assert "original kept" in fresh.body[0].value.source


def test_edit_of_hard_deleted_post_propagates_does_not_exist(monkeypatch):
    """If the row is hard-deleted (topic CASCADE) between save_revision and the
    lock re-fetch, the edit propagates DoesNotExist (the view maps it to 404)
    rather than swallowing it as a fake 'pending' then crashing on
    refresh_from_db (review PR #435 finding #1). Simulate the take-down landing
    right after save_revision — the actual race window."""
    ensure_default_workflow()
    author = _author("ghost", TrustLevel.MEMBER)
    post = _live_post(_board(), author)
    real_save = Post.save_revision

    def save_then_vanish(self, *args, **kwargs):
        revision = real_save(self, *args, **kwargs)
        Post.objects.filter(pk=self.pk).delete()  # concurrent hard delete lands here
        return revision

    monkeypatch.setattr(Post, "save_revision", save_then_vanish)
    post.body = _body("<p>edit into the void</p>")
    with pytest.raises(Post.DoesNotExist):
        submit_edit_for_moderation(post, author)
