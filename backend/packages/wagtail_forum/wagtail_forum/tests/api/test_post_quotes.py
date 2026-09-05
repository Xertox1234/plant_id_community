"""Structured post quotes (todo 342): validated on write, resolved on read in
one query per page, plain text by the same escape contract as `quote`."""

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from wagtail.models import Page, PageViewRestriction
from wagtail_forum.models import (
    ForumBoard,
    ForumIndex,
    ForumProfile,
    Notification,
    Post,
    Topic,
    TrustLevel,
    UserBlock,
    UserMute,
)

from .test_topic_create import ensure_default_workflow

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


def _board(slug="general", *, restricted=False):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug=f"forum-{slug}"))
    board = index.add_child(instance=ForumBoard(title="General", slug=slug))
    if restricted:
        PageViewRestriction.objects.create(page=board, restriction_type="login")
    return board


def _member(username):
    user = User.objects.create_user(username=username)
    profile = ForumProfile.for_user(user)
    profile.trust_level = TrustLevel.MEMBER
    profile.save(update_fields=["trust_level"])
    return user


def _topic_with_post(
    board, author, title="Quoted topic", body="<p>Original wisdom.</p>"
):
    topic = Topic.objects.create(
        board=board,
        title=title,
        slug=title.lower().replace(" ", "-"),
        author=author,
        live=True,
    )
    post = Post.objects.create(
        topic=topic,
        author=author,
        is_opening_post=True,
        live=True,
        body=[{"type": "paragraph", "value": body}],
    )
    return topic, post


def _reply(client, topic, body):
    return client.post(
        f"/forum/topics/{topic.id}/posts/", {"body": body}, format="json"
    )


def _quote(post_id, text="Original wisdom."):
    return {"type": "post_quote", "value": {"post": post_id, "text": text}}


@pytest.fixture(autouse=True)
def _workflow():
    ensure_default_workflow()


@pytest.mark.django_db
def test_a_valid_quote_is_stored_and_read_as_a_safe_attribution_envelope():
    board = _board()
    original_author = _member("q-original")
    topic, quoted = _topic_with_post(board, original_author)
    quoter = _member("q-quoter")
    client = APIClient()
    client.force_authenticate(quoter)

    resp = _reply(
        client,
        topic,
        [_quote(quoted.id), {"type": "paragraph", "value": "<p>Agreed.</p>"}],
    )

    assert resp.status_code == 201, resp.data
    stored = Post.objects.get(pk=resp.data["id"]).body.raw_data[0]
    assert stored["type"] == "post_quote" and stored["value"] == {
        "post": quoted.id,
        "text": "Original wisdom.",
    }

    blocks = (
        APIClient().get(f"/forum/topics/{topic.id}/posts/").data["results"][1]["body"]
    )
    assert blocks[0]["type"] == "post_quote"
    assert blocks[0]["value"] == {
        "text": "Original wisdom.",
        "post_id": quoted.id,
        "available": True,
        "topic_id": topic.id,
        "author": blocks[0]["value"]["author"],
        "is_blocked": False,
        "is_muted": False,
    }
    assert blocks[0]["value"]["author"]["username"] == "q-original"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "case",
    ["missing", "unpublished", "restricted", "blocked_by_writer", "blocked_the_writer"],
)
def test_an_unquotable_post_is_a_400_with_one_generic_message(case):
    board = _board()
    original_author = _member("q-orig-" + case)
    quoter = _member("q-quoter-" + case)
    topic, target = _topic_with_post(board, original_author)
    reply_topic, _ = _topic_with_post(
        board, original_author, title="Reply here " + case
    )
    if case == "missing":
        pid = 999_999
    elif case == "unpublished":
        Post.objects.filter(pk=target.pk).update(live=False)
        pid = target.pk
    elif case == "restricted":
        restricted = _board("restricted-" + case, restricted=True)
        _, hidden = _topic_with_post(
            restricted, original_author, title="Hidden " + case
        )
        pid = hidden.pk
    elif case == "blocked_by_writer":
        UserBlock.objects.create(blocker=quoter, blocked=original_author)
        pid = target.pk
    else:
        UserBlock.objects.create(blocker=original_author, blocked=quoter)
        pid = target.pk
    client = APIClient()
    client.force_authenticate(quoter)

    resp = _reply(client, reply_topic, [_quote(pid)])

    assert resp.status_code == 400
    assert "not available" in str(resp.data)
    assert Post.objects.filter(topic=reply_topic).count() == 1  # nothing stored


@pytest.mark.django_db
@override_settings(WAGTAILFORUM_QUOTES_MAX_PER_POST=2, WAGTAILFORUM_QUOTE_MAX_CHARS=20)
def test_quote_caps_and_shape_are_enforced():
    board = _board()
    author = _member("q-cap-author")
    quoter = _member("q-cap-quoter")
    topic, p1 = _topic_with_post(board, author, title="Cap one")
    _, p2 = _topic_with_post(board, author, title="Cap two")
    _, p3 = _topic_with_post(board, author, title="Cap three")
    client = APIClient()
    client.force_authenticate(quoter)

    too_many = _reply(
        client, topic, [_quote(p1.id, "a"), _quote(p2.id, "b"), _quote(p3.id, "c")]
    )
    assert too_many.status_code == 400 and "at most 2" in str(too_many.data)
    same_twice = _reply(
        client, topic, [_quote(p1.id, "a"), _quote(p1.id, "b"), _quote(p2.id, "c")]
    )
    assert same_twice.status_code == 201  # distinct posts count, not blocks
    too_long = _reply(client, topic, [_quote(p1.id, "x" * 21)])
    assert too_long.status_code == 400 and "at most 20" in str(too_long.data)
    for bad in (
        {"post": "1", "text": "a"},
        {"post": True, "text": "a"},
        {"post": p1.id, "text": "  "},
        "just a string",
    ):
        resp = _reply(client, topic, [{"type": "post_quote", "value": bad}])
        assert resp.status_code == 400, bad


@pytest.mark.django_db
def test_quote_text_is_plain_text_by_contract_never_sanitized_or_rendered():
    """Same escape contract as `quote` (test_topic_create's XSS contract):
    the text is stored and returned VERBATIM; consumers escape at render."""
    board = _board()
    author = _member("q-xss-author")
    quoter = _member("q-xss-quoter")
    topic, quoted = _topic_with_post(board, author)
    client = APIClient()
    client.force_authenticate(quoter)
    hostile = "<script>alert(1)</script>quoted"

    resp = _reply(client, topic, [_quote(quoted.id, hostile)])

    assert resp.status_code == 201
    block = (
        APIClient()
        .get(f"/forum/topics/{topic.id}/posts/")
        .data["results"][1]["body"][0]
    )
    assert block["value"]["text"] == hostile
    assert "html" not in block["value"]


@pytest.mark.django_db
def test_a_quoted_post_that_goes_away_still_renders_its_text_without_attribution():
    board = _board()
    author = _member("q-gone-author")
    quoter = _member("q-gone-quoter")
    # The quoted post lives in ANOTHER topic, so unpublishing it does not
    # change the shape of the list under test.
    _, quoted = _topic_with_post(board, author, title="Source topic")
    topic, _ = _topic_with_post(board, author, title="Discussion topic")
    client = APIClient()
    client.force_authenticate(quoter)
    assert _reply(client, topic, [_quote(quoted.id)]).status_code == 201

    Post.objects.filter(pk=quoted.pk).update(live=False)

    block = (
        APIClient()
        .get(f"/forum/topics/{topic.id}/posts/")
        .data["results"][1]["body"][0]
    )
    assert block["value"] == {
        "text": "Original wisdom.",
        "post_id": quoted.id,
        "available": False,
        "topic_id": None,
        "author": None,
        "is_blocked": False,
        "is_muted": False,
    }


@pytest.mark.django_db
def test_post_list_query_count_is_flat_across_quote_bearing_posts():
    board = _board()
    author = _member("q-flat-author")
    quoter = _member("q-flat-quoter")
    one, _ = _topic_with_post(board, author, title="Flat one")
    many, _ = _topic_with_post(board, author, title="Flat many")
    quoted = [
        _topic_with_post(board, author, title=f"Flat source {i}")[1] for i in range(3)
    ]
    # The quoted author has an avatar so the attribution traverses the
    # `author__wagtail_forum_profile__avatar` leg of the map's select_related
    # (a pin over a chain must feed data down EVERY leg — cross-cutting review).
    from wagtail.images import get_image_model
    from wagtail.images.tests.utils import get_test_image_file

    profile = ForumProfile.for_user(author)
    profile.avatar = get_image_model().objects.create(
        title="leaf", file=get_test_image_file()
    )
    profile.save(update_fields=["avatar"])
    Post.objects.create(
        topic=one, author=quoter, live=True, body=[_quote(quoted[0].id)]
    )
    for i in range(3):
        Post.objects.create(
            topic=many,
            author=quoter,
            live=True,
            body=[_quote(quoted[i].id), _quote(quoted[(i + 1) % 3].id)],
        )

    anon = APIClient()
    with CaptureQueriesContext(connection) as ctx_one:
        r1 = anon.get(f"/forum/topics/{one.id}/posts/")
    with CaptureQueriesContext(connection) as ctx_many:
        r2 = anon.get(f"/forum/topics/{many.id}/posts/")

    assert r1.status_code == r2.status_code == 200
    assert (
        sum(b["type"] == "post_quote" for p in r2.data["results"] for b in p["body"])
        == 6
    )
    assert all(
        b["value"]["available"]
        for p in r2.data["results"]
        for b in p["body"]
        if b["type"] == "post_quote"
    )
    assert len(ctx_many.captured_queries) == len(ctx_one.captured_queries)


@pytest.mark.django_db
def test_notification_payload_carries_quoted_post_id():
    board = _board()
    author = _member("q-note-author")
    quoter = _member("q-note-quoter")
    topic, quoted = _topic_with_post(board, author)
    reply = Post.objects.create(
        topic=topic, author=quoter, live=True, body=[_quote(quoted.id)]
    )
    Notification.objects.create(
        recipient=author,
        actor=quoter,
        verb="quote",
        topic=topic,
        post=reply,
        quoted_post=quoted,
    )
    client = APIClient()
    client.force_authenticate(author)

    rows = client.get("/forum/notifications/").data["results"]

    assert rows[0]["verb"] == "quote"
    assert rows[0]["post_id"] == reply.id
    assert rows[0]["quoted_post_id"] == quoted.id

    Notification.objects.create(
        recipient=author, actor=quoter, verb="reply", topic=topic, post=reply
    )
    rows = client.get("/forum/notifications/").data["results"]
    by_verb = {row["verb"]: row for row in rows}
    assert by_verb["reply"]["quoted_post_id"] is None


@pytest.mark.django_db
def test_editing_keeps_a_stored_quote_whose_target_went_away_but_rejects_a_new_one():
    """An edit resends the whole body (like images, audit L21): a quote the
    post ALREADY carries must not lock the author out once its target is
    unpublished — but a NEWLY added unavailable quote is still a 400, and
    removing the quote stores a body without it."""
    board = _board()
    author = _member("q-edit-original")
    topic, _ = _topic_with_post(board, author, title="Edit thread")
    _, quoted = _topic_with_post(board, author, title="Edit source")
    _, other_quoted = _topic_with_post(board, author, title="Other source")
    quoter = _member("q-editor")
    client = APIClient()
    client.force_authenticate(quoter)
    created = _reply(
        client, topic, [_quote(quoted.id), {"type": "paragraph", "value": "<p>A</p>"}]
    )
    assert created.status_code == 201, created.data
    reply_id = created.data["id"]

    Post.objects.filter(pk=quoted.pk).update(live=False)
    Post.objects.filter(pk=other_quoted.pk).update(live=False)

    kept = client.patch(
        f"/forum/posts/{reply_id}/",
        {"body": [_quote(quoted.id), {"type": "paragraph", "value": "<p>B</p>"}]},
        format="json",
    )
    assert kept.status_code == 200, kept.data
    raw = Post.objects.get(pk=reply_id).body.raw_data
    assert raw[0]["value"] == {"post": quoted.id, "text": "Original wisdom."}
    assert "<p>B</p>" in raw[1]["value"]
    envelope = client.get(f"/forum/topics/{topic.id}/posts/").data["results"][1]
    assert envelope["body"][0]["value"]["available"] is False

    added = client.patch(
        f"/forum/posts/{reply_id}/",
        {"body": [_quote(quoted.id), _quote(other_quoted.id)]},
        format="json",
    )
    assert added.status_code == 400
    assert "not available" in str(added.data)

    removed = client.patch(
        f"/forum/posts/{reply_id}/",
        {"body": [{"type": "paragraph", "value": "<p>C</p>"}]},
        format="json",
    )
    assert removed.status_code == 200, removed.data
    assert [b["type"] for b in Post.objects.get(pk=reply_id).body.raw_data] == [
        "paragraph"
    ]


@pytest.mark.django_db
def test_an_opening_post_can_quote_through_the_topic_create_api():
    board = _board()
    author = _member("q-open-original")
    _, quoted = _topic_with_post(board, author)
    opener = _member("q-opener")
    client = APIClient()
    client.force_authenticate(opener)

    resp = client.post(
        f"/forum/boards/{board.slug}/topics/",
        {
            "title": "Quoting opener",
            "slug": "quoting-opener",
            "body": [_quote(quoted.id), {"type": "paragraph", "value": "<p>Hi</p>"}],
        },
        format="json",
    )

    assert resp.status_code == 201, resp.data
    new_topic = Topic.objects.get(slug="quoting-opener")
    first = APIClient().get(f"/forum/topics/{new_topic.id}/posts/").data["results"][0]
    assert first["body"][0]["type"] == "post_quote"
    assert first["body"][0]["value"]["available"] is True
    assert first["body"][0]["value"]["author"]["username"] == "q-open-original"

    rejected = client.post(
        f"/forum/boards/{board.slug}/topics/",
        {
            "title": "Bad opener",
            "slug": "bad-opener",
            "body": [_quote(quoted.id + 999)],
        },
        format="json",
    )
    assert rejected.status_code == 400
    assert "not available" in str(rejected.data)


@pytest.mark.django_db
def test_quote_attribution_carries_the_viewers_block_and_mute_signals():
    """COLLAPSE, not HIDE: a quote is one more surface rendering an author,
    so the envelope carries is_blocked / is_muted for the viewer exactly like
    PostSerializer does for the post itself; anonymous viewers get False."""
    board = _board()
    author = _member("q-flag-author")
    quoter = _member("q-flag-quoter")
    topic, quoted = _topic_with_post(board, author)
    Post.objects.create(topic=topic, author=quoter, live=True, body=[_quote(quoted.id)])
    viewer = _member("q-flag-viewer")
    UserBlock.objects.create(blocker=viewer, blocked=author)
    muter = _member("q-flag-muter")
    UserMute.objects.create(muter=muter, muted=author)

    def envelope(client):
        return client.get(f"/forum/topics/{topic.id}/posts/").data["results"][1][
            "body"
        ][0]["value"]

    anon = envelope(APIClient())
    assert (anon["is_blocked"], anon["is_muted"]) == (False, False)
    assert anon["available"] is True

    blocking = APIClient()
    blocking.force_authenticate(viewer)
    assert envelope(blocking)["is_blocked"] is True
    assert envelope(blocking)["is_muted"] is False

    muting = APIClient()
    muting.force_authenticate(muter)
    assert envelope(muting)["is_muted"] is True
    assert envelope(muting)["is_blocked"] is False


@pytest.mark.django_db
def test_plain_text_excerpt_includes_a_quotes_text():
    from wagtail_forum.api.views import plain_text_excerpt

    board = _board()
    author = _member("q-excerpt")
    topic, quoted = _topic_with_post(board, author)
    post = Post.objects.create(
        topic=topic, author=author, live=True, body=[_quote(quoted.id, "Quoted words")]
    )
    assert plain_text_excerpt(post.body, 200) == "Quoted words"
