"""PostWriteView: edit (PATCH) + soft-delete (DELETE). Spec 2 Q1/Q2/Q3."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.api.views import PostWriteView
from wagtail_forum.blocks import ForumBodyBlock
from wagtail_forum.models import (
    ForumBoard,
    ForumIndex,
    ForumProfile,
    Post,
    Topic,
    TrustLevel,
)
from wagtail_forum.workflow import ensure_default_workflow, submit_for_moderation

User = get_user_model()
pytestmark = [pytest.mark.django_db, pytest.mark.urls("wagtail_forum.tests.api.urls")]


def _board():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    return index.add_child(instance=ForumBoard(title="General", slug="general"))


def _member(username):
    u = User.objects.create_user(username=username, password="x")
    p = ForumProfile.for_user(u)
    p.trust_level = TrustLevel.MEMBER  # >= autopublish, so create+edit go live
    p.save()
    return u


def _moderator(username):
    u = User.objects.create_user(username=username, password="x")
    ForumProfile.for_user(u)
    perm = Permission.objects.get(
        content_type__app_label="wagtail_forum", codename="change_post"
    )
    u.user_permissions.add(perm)
    return User.objects.get(pk=u.pk)  # re-fetch to clear the permission cache


def _body(html):
    return ForumBodyBlock().to_python([{"type": "paragraph", "value": html}])


def _topic_with_reply(board, author, reply_html="<p>a reply</p>"):
    ensure_default_workflow()
    topic = Topic(board=board, title="t", slug="t", author=author, live=False)
    topic.save()
    opening = Post(
        topic=topic,
        author=author,
        is_opening_post=True,
        body=_body("<p>op</p>"),
        live=False,
    )
    opening.save()
    submit_for_moderation(opening, author)
    reply = Post(topic=topic, author=author, body=_body(reply_html), live=False)
    reply.save()
    submit_for_moderation(reply, author)
    topic.refresh_from_db()
    return topic, opening, reply


def test_author_edit_publishes_new_body():
    board = _board()
    author = _member("ada")
    _topic, _opening, reply = _topic_with_reply(board, author)
    client = APIClient()
    client.force_authenticate(author)
    resp = client.patch(
        f"/forum/posts/{reply.id}/",
        {"body": [{"type": "paragraph", "value": "<p>edited</p>"}]},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.data["moderation_status"] == "published"
    assert any("edited" in b["value"] for b in resp.data["body"])
    assert resp.data["edited_at"] is not None


def test_non_author_cannot_edit():
    board = _board()
    author = _member("ada")
    intruder = _member("eve")
    _topic, _opening, reply = _topic_with_reply(board, author)
    client = APIClient()
    client.force_authenticate(intruder)
    resp = client.patch(
        f"/forum/posts/{reply.id}/",
        {"body": [{"type": "paragraph", "value": "<p>hax</p>"}]},
        format="json",
    )
    assert resp.status_code == 403


def test_moderator_can_edit_and_delete_others_post():
    board = _board()
    author = _member("ada")
    _topic, _opening, reply = _topic_with_reply(board, author)
    mod = _moderator("mod")
    client = APIClient()
    client.force_authenticate(mod)
    edit = client.patch(
        f"/forum/posts/{reply.id}/",
        {"body": [{"type": "paragraph", "value": "<p>mod edit</p>"}]},
        format="json",
    )
    assert edit.status_code == 200
    delete = client.delete(f"/forum/posts/{reply.id}/")
    assert delete.status_code == 204
    assert Post.objects.get(id=reply.id).live is False


def test_edit_on_closed_topic_conflicts():
    board = _board()
    author = _member("ada")
    topic, _opening, reply = _topic_with_reply(board, author)
    Topic.objects.filter(id=topic.id).update(is_closed=True)
    client = APIClient()
    client.force_authenticate(author)
    resp = client.patch(
        f"/forum/posts/{reply.id}/",
        {"body": [{"type": "paragraph", "value": "<p>edited</p>"}]},
        format="json",
    )
    assert resp.status_code == 409


def test_edit_malformed_body_is_400_not_500():
    board = _board()
    author = _member("ada")
    _topic, _opening, reply = _topic_with_reply(board, author)
    client = APIClient()
    client.force_authenticate(author)
    resp = client.patch(
        f"/forum/posts/{reply.id}/", {"body": "not-a-list"}, format="json"
    )
    assert resp.status_code == 400


def test_author_delete_soft_deletes_and_recounts():
    board = _board()
    author = _member("ada")
    topic, _opening, reply = _topic_with_reply(board, author)
    assert topic.reply_count == 1
    client = APIClient()
    client.force_authenticate(author)
    resp = client.delete(f"/forum/posts/{reply.id}/")
    assert resp.status_code == 204
    assert Post.objects.get(id=reply.id).live is False
    topic.refresh_from_db()
    assert topic.reply_count == 0  # signal-maintained recount, not manual


def test_delete_opening_post_conflicts():
    board = _board()
    author = _member("ada")
    _topic, opening, _reply = _topic_with_reply(board, author)
    client = APIClient()
    client.force_authenticate(author)
    resp = client.delete(f"/forum/posts/{opening.id}/")
    assert resp.status_code == 409
    assert Post.objects.get(id=opening.id).live is True


def test_edit_hidden_post_is_404():
    board = _board()
    author = _member("ada")
    _topic, _opening, reply = _topic_with_reply(board, author)
    Post.objects.filter(id=reply.id).update(live=False)  # now hidden
    client = APIClient()
    client.force_authenticate(author)
    resp = client.patch(
        f"/forum/posts/{reply.id}/",
        {"body": [{"type": "paragraph", "value": "<p>x</p>"}]},
        format="json",
    )
    assert resp.status_code == 404


def test_delete_on_hidden_board_is_404():
    # The board-visibility guard in _get_editable is a security check (no writes
    # on a restricted/non-live board) — exercise that branch specifically.
    board = _board()
    author = _member("ada")
    _topic, _opening, reply = _topic_with_reply(board, author)
    ForumBoard.objects.filter(id=board.id).update(live=False)  # board now hidden
    client = APIClient()
    client.force_authenticate(author)
    resp = client.delete(f"/forum/posts/{reply.id}/")
    assert resp.status_code == 404
    assert Post.objects.get(id=reply.id).live is True  # not deleted


def test_moderator_edit_author_deleted_post_persists():
    """A moderator redaction of an account-deleted author's post (author=None,
    SET_NULL) persists — never a crash or a silent 200 that drops the edit
    (finding #2)."""
    board = _board()
    author = _member("ada")
    _topic, _opening, reply = _topic_with_reply(board, author)
    Post.objects.filter(id=reply.id).update(author=None)  # author account deleted
    mod = _moderator("mod")
    client = APIClient()
    client.force_authenticate(mod)
    resp = client.patch(
        f"/forum/posts/{reply.id}/",
        {"body": [{"type": "paragraph", "value": "<p>[redacted]</p>"}]},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.data["moderation_status"] == "published"
    fresh = Post.objects.get(id=reply.id)
    assert fresh.live and "[redacted]" in fresh.body[0].value.source


def test_edit_save_revision_failure_is_not_fake_pending(monkeypatch):
    """A failure BEFORE the revision is saved must surface as an error, not a
    fake 200 'pending' (finding #3) — nothing was persisted, so the old body
    keeps serving and the client is not told a phantom edit is queued."""
    board = _board()
    author = _member("ada")
    _topic, _opening, reply = _topic_with_reply(board, author)
    original = reply.body[0].value.source

    def boom(self, *args, **kwargs):
        raise RuntimeError("save_revision blew up")

    monkeypatch.setattr(Post, "save_revision", boom)
    client = APIClient()
    client.raise_request_exception = False  # capture the 500 instead of re-raising
    client.force_authenticate(author)
    resp = client.patch(
        f"/forum/posts/{reply.id}/",
        {"body": [{"type": "paragraph", "value": "<p>edited</p>"}]},
        format="json",
    )
    assert resp.status_code != 200
    fresh = Post.objects.get(id=reply.id)
    assert original in fresh.body[0].value.source  # nothing persisted


def test_delete_hard_deleted_post_is_404_not_500(monkeypatch):
    """A hard delete (topic CASCADE) landing between _get_editable and the lock
    re-fetch returns 404, not a 500 (review PR #435 finding #1). Monkeypatch
    _get_editable to return the pre-lock instance, then delete the row, so the
    lock re-fetch is what hits the gap."""
    board = _board()
    author = _member("ada")
    _topic, _opening, reply = _topic_with_reply(board, author)
    monkeypatch.setattr(
        PostWriteView, "_get_editable", lambda self, request, post_id: reply
    )
    Post.objects.filter(id=reply.id).delete()  # row gone after the initial fetch
    client = APIClient()
    client.force_authenticate(author)
    resp = client.delete(f"/forum/posts/{reply.id}/")
    assert resp.status_code == 404
