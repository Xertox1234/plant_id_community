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
    u = User.objects.create_user(username=username)
    p = ForumProfile.for_user(u)
    p.trust_level = TrustLevel.MEMBER  # >= autopublish, so create+edit go live
    p.save()
    return u


def _moderator(username):
    u = User.objects.create_user(username=username)
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


def test_pending_edit_response_carries_submitted_body(settings):
    """Audit 2026-07-11 H23 (execution-proven in discovery): an untrusted
    author's flagged edit must NOT echo the stale live body — the client would
    render the user's edit "reverting" with nothing in the response signalling
    it. The response body reflects the SUBMITTED revision; GET keeps serving
    the last-approved live content until moderation clears."""
    settings.WAGTAILFORUM_SPAM_BANNED_WORDS = ["casino"]
    board = _board()
    author = User.objects.create_user(username="newbie")
    ForumProfile.for_user(author)  # trust 0 — below autopublish
    topic, _opening, reply = _topic_with_reply(
        board, author, reply_html="<p>original clean</p>"
    )
    assert reply.live  # clean content auto-approved at create

    client = APIClient()
    client.force_authenticate(author)
    resp = client.patch(
        f"/forum/posts/{reply.id}/",
        {"body": [{"type": "paragraph", "value": "<p>best casino deals</p>"}]},
        format="json",
    )

    assert resp.status_code == 200
    assert resp.data["moderation_status"] == "pending"
    # The response echoes what the client SUBMITTED (the pending revision)...
    assert "casino" in resp.data["body"][0]["value"]

    # ...while reads keep serving the last-approved live body.
    read = client.get(f"/forum/topics/{topic.id}/posts/")
    live_bodies = {p["id"]: p["body"][0]["value"] for p in read.data["results"]}
    assert "original clean" in live_bodies[reply.id]
    assert "casino" not in live_bodies[reply.id]


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
    # finding #7: the message states the real constraint and no longer advertises
    # a topic-delete endpoint that exists in neither URL config.
    assert resp.data["message"] == "Opening posts cannot be deleted via the API."
    assert "delete the topic" not in resp.data["message"].lower()


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


def test_delete_on_closed_topic_conflicts():
    # Per-operand isolation: is_closed=True alone (topic.locked stays False), so an
    # or->and mutation of the DELETE topic guard fails exactly this test (finding #5).
    board = _board()
    author = _member("ada")
    topic, _opening, reply = _topic_with_reply(board, author)
    Topic.objects.filter(id=topic.id).update(is_closed=True)
    client = APIClient()
    client.force_authenticate(author)
    resp = client.delete(f"/forum/posts/{reply.id}/")
    assert resp.status_code == 409
    assert Post.objects.get(id=reply.id).live is True  # not taken down


def test_delete_on_locked_topic_conflicts():
    # Per-operand isolation: topic.locked=True alone (is_closed stays False).
    board = _board()
    author = _member("ada")
    topic, _opening, reply = _topic_with_reply(board, author)
    Topic.objects.filter(id=topic.id).update(locked=True)
    client = APIClient()
    client.force_authenticate(author)
    resp = client.delete(f"/forum/posts/{reply.id}/")
    assert resp.status_code == 409
    assert Post.objects.get(id=reply.id).live is True


def test_edit_locked_post_rejected_for_author():
    # A moderator-locked post blocks the author's edit (finding #6). The topic
    # stays un-closed/un-locked, so this proves the POST lock fires — not the
    # topic guard — and the message distinguishes the two 409s.
    board = _board()
    author = _member("ada")
    _topic, _opening, reply = _topic_with_reply(board, author)
    Post.objects.filter(id=reply.id).update(locked=True)
    client = APIClient()
    client.force_authenticate(author)
    resp = client.patch(
        f"/forum/posts/{reply.id}/",
        {"body": [{"type": "paragraph", "value": "<p>edited</p>"}]},
        format="json",
    )
    assert resp.status_code == 409
    assert resp.data["message"] == "Post is locked."
    assert "a reply" in Post.objects.get(id=reply.id).body[0].value.source  # unchanged


def test_delete_locked_post_rejected_for_author():
    board = _board()
    author = _member("ada")
    _topic, _opening, reply = _topic_with_reply(board, author)
    Post.objects.filter(id=reply.id).update(locked=True)
    client = APIClient()
    client.force_authenticate(author)
    resp = client.delete(f"/forum/posts/{reply.id}/")
    assert resp.status_code == 409
    assert resp.data["message"] == "Post is locked."
    assert Post.objects.get(id=reply.id).live is True  # not taken down


def test_moderator_bypasses_post_lock():
    # Wagtail semantics: privileged users (change_post) edit locked objects, so a
    # moderator's edit of a locked post publishes (finding #6, the decided bypass).
    board = _board()
    author = _member("ada")
    _topic, _opening, reply = _topic_with_reply(board, author)
    Post.objects.filter(id=reply.id).update(locked=True)
    mod = _moderator("mod")
    client = APIClient()
    client.force_authenticate(mod)
    resp = client.patch(
        f"/forum/posts/{reply.id}/",
        {"body": [{"type": "paragraph", "value": "<p>mod edit</p>"}]},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.data["moderation_status"] == "published"


def test_affordance_flags_match_write_outcomes():
    # Parity acid test (todo 252): the can_edit/can_delete flags the LIST serves
    # must match what the WRITE endpoints actually do — the shared predicate is
    # only worth anything if the button and the write path agree. Drives both
    # from the SAME posts, so a future divergence in either fails here.
    board = _board()
    author = _member("ada")
    topic, opening, reply = _topic_with_reply(board, author)
    client = APIClient()
    client.force_authenticate(author)

    listed = {
        p["is_opening_post"]: p
        for p in client.get(f"/forum/topics/{topic.id}/posts/").data["results"]
    }
    # Opening post: flags say editable but NOT deletable — the endpoints agree.
    assert listed[True]["can_edit"] is True
    assert listed[True]["can_delete"] is False
    assert client.delete(f"/forum/posts/{opening.id}/").status_code == 409
    # Reply: flags say editable AND deletable — the endpoints agree.
    assert listed[False]["can_edit"] is True
    assert listed[False]["can_delete"] is True
    assert (
        client.patch(
            f"/forum/posts/{reply.id}/",
            {"body": [{"type": "paragraph", "value": "<p>x</p>"}]},
            format="json",
        ).status_code
        == 200
    )
    assert client.delete(f"/forum/posts/{reply.id}/").status_code == 204


def test_affordance_flags_match_write_outcomes_in_closed_topic():
    # Parity in a frozen topic: can_edit=false ⇔ PATCH 409 (finding #8 goal).
    board = _board()
    author = _member("ada")
    topic, _opening, reply = _topic_with_reply(board, author)
    Topic.objects.filter(id=topic.id).update(is_closed=True)
    client = APIClient()
    client.force_authenticate(author)

    listed = {
        p["is_opening_post"]: p
        for p in client.get(f"/forum/topics/{topic.id}/posts/").data["results"]
    }
    assert listed[False]["can_edit"] is False
    assert (
        client.patch(
            f"/forum/posts/{reply.id}/",
            {"body": [{"type": "paragraph", "value": "<p>x</p>"}]},
            format="json",
        ).status_code
        == 409
    )


def test_unauthenticated_patch_is_401():
    # PostWriteView.permission_classes = [IsAuthenticated] must gate PATCH — every
    # other edit test force_authenticates first, so a weakened permission gate
    # would pass the suite silently (the silent-auth-hole class, finding #9). 401
    # via the JWT authenticate header, mirroring test_unauthenticated_writes_are_
    # rejected.
    board = _board()
    author = _member("ada")
    _topic, _opening, reply = _topic_with_reply(board, author)
    client = APIClient()  # no credentials
    resp = client.patch(
        f"/forum/posts/{reply.id}/",
        {"body": [{"type": "paragraph", "value": "<p>x</p>"}]},
        format="json",
    )
    assert resp.status_code == 401
    assert "a reply" in Post.objects.get(id=reply.id).body[0].value.source  # unchanged


def test_unauthenticated_delete_is_401():
    # DELETE half of finding #9 — same silent-auth-hole class.
    board = _board()
    author = _member("ada")
    _topic, _opening, reply = _topic_with_reply(board, author)
    client = APIClient()  # no credentials
    resp = client.delete(f"/forum/posts/{reply.id}/")
    assert resp.status_code == 401
    assert Post.objects.get(id=reply.id).live is True  # not taken down


def test_edit_on_locked_topic_conflicts():
    # PATCH guard operand parity with test_edit_on_closed_topic_conflicts: the
    # guard is `topic.is_closed or topic.locked`, but only is_closed was exercised
    # on the edit path (finding #10). Isolate the locked operand (is_closed stays
    # False) so removing `or topic.locked` fails exactly this test.
    board = _board()
    author = _member("ada")
    topic, _opening, reply = _topic_with_reply(board, author)
    Topic.objects.filter(id=topic.id).update(locked=True)
    client = APIClient()
    client.force_authenticate(author)
    resp = client.patch(
        f"/forum/posts/{reply.id}/",
        {"body": [{"type": "paragraph", "value": "<p>edited</p>"}]},
        format="json",
    )
    assert resp.status_code == 409


def test_delete_query_count_is_pinned():
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    board = _board()
    author = _member("ada")
    _topic, _opening, reply = _topic_with_reply(board, author)
    client = APIClient()
    client.force_authenticate(author)
    with CaptureQueriesContext(connection) as ctx:
        resp = client.delete(f"/forum/posts/{reply.id}/")
    assert resp.status_code == 204
    # Pinned EXACTLY (docs/rules/testing.md): the single-query _get_visible_post
    # (todo 255) folds the visibility guard into the fetch, so re-introducing the
    # separate _visible_boards().exists() check would bump this and fail here.
    # The bulk is Wagtail's unpublish + counter-signal recount cascade (255 does
    # not change that); the fold is the delta this pin protects.
    # 32 -> 33 (audit 2026-07-11 M15): attributed unpublish (user=request.user)
    # adds ONE `SELECT 1 FROM auth_user` existence check before the log-entry
    # INSERT — Wagtail's log writer guards against deleted users.
    assert len(ctx.captured_queries) == 33, len(ctx.captured_queries)


def test_edit_query_count_is_pinned():
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    board = _board()
    author = _member("ada")
    _topic, _opening, reply = _topic_with_reply(board, author)
    client = APIClient()
    client.force_authenticate(author)
    with CaptureQueriesContext(connection) as ctx:
        resp = client.patch(
            f"/forum/posts/{reply.id}/",
            {"body": [{"type": "paragraph", "value": "<p>edited</p>"}]},
            format="json",
        )
    assert resp.status_code == 200
    # Pinned EXACTLY (docs/rules/testing.md): _get_visible_post is one query (was
    # fetch + a separate visibility .exists()); todo 255. The bulk is Wagtail's
    # revision save/publish + workflow finish + counter recount, unchanged by 255.
    # 68 -> 69 (audit 2026-07-11 M15): attributed publish (user=<editor>) adds
    # ONE `SELECT 1 FROM auth_user` existence check before the log-entry INSERT.
    assert len(ctx.captured_queries) == 69, len(ctx.captured_queries)
