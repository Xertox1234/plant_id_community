"""Write permissions per forum (todo 677): post, reply, poll and attach.

For each flag a member whose role lacks it gets 403 with the flag's stable
error code, and a member whose role has it succeeds. Guests and hidden forums
are out of scope here (401 / 404 as before). Owner decision 2026-11-01: the
image upload's ``forum_id`` is optional — checked when sent, accepted when
absent — and an image block in a body is always checked against the forum it
is posted to.
"""

import io

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image as PILImage
from rest_framework.test import APIClient
from wagtail.images import get_image_model
from wagtail_forum.collections import get_forum_image_collection
from wagtail_forum.models import (
    ForumGrant,
    ForumProfile,
    ForumRole,
    Post,
    Topic,
    TrustLevel,
)
from wagtail_forum.services.forum_permissions import forum_capabilities, set_grant
from wagtail_forum.tests.factories import make_forum
from wagtail_forum.workflow import ensure_default_workflow

User = get_user_model()
pytestmark = [pytest.mark.django_db, pytest.mark.urls("wagtail_forum.tests.api.urls")]

BODY = [{"type": "paragraph", "value": "<p>Hello there.</p>"}]


@pytest.fixture(autouse=True)
def _clean_cache():
    cache.clear()
    yield
    cache.clear()


def _jpeg():
    buf = io.BytesIO()
    PILImage.new("RGB", (10, 10), color="green").save(buf, format="JPEG")
    return buf.getvalue()


def _member(username):
    user = User.objects.create_user(username=username)
    profile = ForumProfile.for_user(user)
    profile.trust_level = TrustLevel.MEMBER
    profile.save()
    client = APIClient()
    client.force_authenticate(user)
    return user, client


def _forum(slug, role):
    """A forum whose members get ``role``."""
    forum = make_forum(name=slug.title(), slug=slug)
    set_grant(forum, ForumGrant.MEMBERS, role)
    return forum


def _live_topic(forum, author):
    topic = Topic.objects.create(
        board=forum, title="Existing", slug="existing", author=author, live=True
    )
    Post.objects.create(
        topic=topic, author=author, is_opening_post=True, live=True, body=BODY
    )
    return topic


def _image(user):
    return get_image_model().objects.create(
        title="leaf.jpg",
        file=SimpleUploadedFile("leaf.jpg", _jpeg(), content_type="image/jpeg"),
        collection=get_forum_image_collection(),
        uploaded_by_user=user,
    )


def _create_topic(client, forum, *, body=None, poll=None, slug="new-topic"):
    payload = {"title": "A new topic", "slug": slug, "body": body or BODY}
    if poll is not None:
        payload["poll"] = poll
    return client.post(f"/forum/boards/{forum.slug}/topics/", payload, format="json")


def _reply(client, topic, body=None):
    return client.post(
        f"/forum/topics/{topic.pk}/posts/", {"body": body or BODY}, format="json"
    )


def _upload(client, forum_id=None):
    data = {"image": SimpleUploadedFile("leaf.jpg", _jpeg(), content_type="image/jpeg")}
    if forum_id is not None:
        data["forum_id"] = str(forum_id)
    return client.post("/forum/images/", data, format="multipart")


def _assert_denied(resp, code):
    assert resp.status_code == 403, resp.content
    assert resp.json()["code"] == code


# ---------------------------------------------------------------- f_post


def test_post_denied_without_the_post_flag_and_allowed_with_it():
    ensure_default_workflow()
    _, client = _member("poster")
    read_only = _forum("read-only", ForumRole.READ_ONLY)
    standard = _forum("standard", ForumRole.STANDARD)

    _assert_denied(_create_topic(client, read_only), "forum_post_denied")
    assert not Topic.objects.filter(board=read_only).exists()

    resp = _create_topic(client, standard)
    assert resp.status_code == 201, resp.content
    assert Topic.objects.filter(board=standard, slug="new-topic").exists()


# ---------------------------------------------------------------- f_reply


def test_reply_denied_without_the_reply_flag_and_allowed_with_it():
    ensure_default_workflow()
    author = User.objects.create_user(username="op")
    _, client = _member("replier")
    read_only = _forum("read-only", ForumRole.READ_ONLY)
    standard = _forum("standard", ForumRole.STANDARD)
    closed_topic = _live_topic(read_only, author)
    open_topic = _live_topic(standard, author)

    _assert_denied(_reply(client, closed_topic), "forum_reply_denied")
    assert closed_topic.posts.count() == 1

    resp = _reply(client, open_topic)
    assert resp.status_code == 201, resp.content
    assert open_topic.posts.count() == 2


# ---------------------------------------------------------------- f_poll


def test_poll_denied_without_the_poll_flag_and_allowed_with_it():
    ensure_default_workflow()
    _, client = _member("pollster")
    # Standard has post but not poll; Standard + polls has both.
    standard = _forum("standard", ForumRole.STANDARD)
    with_polls = _forum("with-polls", ForumRole.STANDARD_POLLS)
    poll = {"question": "Best soil?", "options": ["Peat", "Coir"]}

    _assert_denied(_create_topic(client, standard, poll=poll), "forum_poll_denied")
    assert not Topic.objects.filter(board=standard).exists()
    # The same member may still start a topic there without a poll.
    assert _create_topic(client, standard, slug="no-poll").status_code == 201

    resp = _create_topic(client, with_polls, poll=poll)
    assert resp.status_code == 201, resp.content
    assert Topic.objects.get(board=with_polls).poll.question == "Best soil?"


# ---------------------------------------------------------------- f_attach


def test_attach_denied_for_an_image_block_without_the_attach_flag():
    ensure_default_workflow()
    author = User.objects.create_user(username="op")
    user, client = _member("attacher")
    # Limited has post and reply but not attach; Standard has attach.
    limited = _forum("limited", ForumRole.LIMITED)
    standard = _forum("standard", ForumRole.STANDARD)
    image = _image(user)
    with_image = [*BODY, {"type": "image", "value": image.pk}]

    _assert_denied(
        _create_topic(client, limited, body=with_image), "forum_attach_denied"
    )
    _assert_denied(
        _reply(client, _live_topic(limited, author), body=with_image),
        "forum_attach_denied",
    )
    # Text-only posts still work there.
    assert _create_topic(client, limited, slug="text-only").status_code == 201

    resp = _create_topic(client, standard, body=with_image)
    assert resp.status_code == 201, resp.content
    resp = _reply(client, _live_topic(standard, author), body=with_image)
    assert resp.status_code == 201, resp.content


def test_attach_denied_for_an_identification_photo_without_the_attach_flag():
    """The identification photo shows on the thread card and the Recent
    thumbnail, so it is checked like an image block; without a photo the
    identification needs no `attach`."""
    ensure_default_workflow()
    user, client = _member("identifier")
    limited = _forum("limited-id", ForumRole.LIMITED)
    standard = _forum("standard-id", ForumRole.STANDARD)
    candidates = [{"name": "Monstera deliciosa", "confidence": 0.9}]

    def create(forum, slug, **identification):
        payload = {
            "title": "What is this?",
            "slug": slug,
            "body": BODY,
            "identification": {"candidates": candidates, **identification},
        }
        return client.post(
            f"/forum/boards/{forum.slug}/topics/", payload, format="json"
        )

    _assert_denied(
        create(limited, "with-photo", image_id=_image(user).pk),
        "forum_attach_denied",
    )
    assert create(limited, "no-photo").status_code == 201
    resp = create(standard, "with-photo", image_id=_image(user).pk)
    assert resp.status_code == 201, resp.content


def test_attach_denied_for_an_edit_that_adds_an_image_but_not_one_that_keeps_it():
    ensure_default_workflow()
    user, client = _member("editor")
    limited = _forum("limited", ForumRole.LIMITED)
    image = _image(user)
    topic = Topic.objects.create(
        board=limited, title="Mine", slug="mine", author=user, live=True
    )
    kept = Post.objects.create(
        topic=topic,
        author=user,
        is_opening_post=True,
        live=True,
        body=[*BODY, {"type": "image", "value": {"image": image.pk, "alt_text": ""}}],
    )
    plain = Post.objects.create(topic=topic, author=user, live=True, body=BODY)
    with_image = [*BODY, {"type": "image", "value": image.pk}]

    _assert_denied(
        client.patch(f"/forum/posts/{plain.pk}/", {"body": with_image}, format="json"),
        "forum_attach_denied",
    )
    # A post that already shows the image may keep it through an edit.
    resp = client.patch(
        f"/forum/posts/{kept.pk}/",
        {"body": [{"type": "paragraph", "value": "<p>Edited.</p>"}, with_image[1]]},
        format="json",
    )
    assert resp.status_code == 200, resp.content


def test_attach_checked_on_upload_when_a_forum_id_is_sent():
    _, client = _member("uploader")
    limited = _forum("limited", ForumRole.LIMITED)
    standard = _forum("standard", ForumRole.STANDARD)
    hidden = _forum("hidden", ForumRole.NO_ACCESS)

    _assert_denied(_upload(client, limited.pk), "forum_attach_denied")
    assert _upload(client, standard.pk).status_code == 201
    # A forum the caller cannot see is 404, never 403 (no existence leak).
    assert _upload(client, hidden.pk).status_code == 404
    # Not a number: 400.
    resp = client.post(
        "/forum/images/",
        {
            "image": SimpleUploadedFile("a.jpg", _jpeg(), content_type="image/jpeg"),
            "forum_id": "abc",
        },
        format="multipart",
    )
    assert resp.status_code == 400


def test_upload_to_a_closed_forum_checks_attach_only():
    """An edit in a closed forum may still add an image, so the upload's
    forum_id check is `attach` alone, not the closed rule."""
    user, client = _member("closed-uploader")
    forum = _forum("closed-up", ForumRole.STANDARD)
    forum.is_closed = True
    forum.save(update_fields=["is_closed"])

    assert _upload(client, forum.pk).status_code == 201


def test_upload_without_a_forum_id_is_still_accepted():
    """Owner decision 2026-11-01: the Identify upload and shipped app builds
    send no forum id, and keep working."""
    _, client = _member("identify")
    _forum("limited", ForumRole.LIMITED)
    assert _upload(client).status_code == 201


# ---------------------------------------------------------------- capabilities


def test_capabilities_follow_the_role():
    user, _ = _member("caps")
    assert forum_capabilities(user, _forum("full", ForumRole.FULL)) == {
        "can_post": True,
        "can_reply": True,
        "can_poll": True,
        "can_attach": True,
    }
    assert forum_capabilities(user, _forum("limited", ForumRole.LIMITED)) == {
        "can_post": True,
        "can_reply": True,
        "can_poll": False,
        "can_attach": False,
    }
    assert forum_capabilities(None, _forum("guest-view", ForumRole.FULL)) == {
        "can_post": False,
        "can_reply": False,
        "can_poll": False,
        "can_attach": False,
    }


def test_category_rows_carry_the_viewers_capabilities():
    _, client = _member("rows")
    _forum("read-only", ForumRole.READ_ONLY)
    _forum("full", ForumRole.FULL)
    rows = {
        forum["slug"]: forum
        for category in client.get("/forum/categories/").json()["results"]
        for forum in category["forums"]
    }
    assert {k: rows["read-only"][k] for k in ("can_post", "can_reply")} == {
        "can_post": False,
        "can_reply": False,
    }
    assert all(
        rows["full"][k] for k in ("can_post", "can_reply", "can_poll", "can_attach")
    )
    # A guest can write nothing.
    guest = {
        forum["slug"]: forum
        for category in APIClient().get("/forum/categories/").json()["results"]
        for forum in category["forums"]
    }
    assert not any(
        guest["full"][k] for k in ("can_post", "can_reply", "can_poll", "can_attach")
    )
