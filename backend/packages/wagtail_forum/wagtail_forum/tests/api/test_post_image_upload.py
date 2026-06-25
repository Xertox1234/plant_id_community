"""Forum inline-image upload (Spec 2 PR-3): 4-layer validation + happy path.

Mirrors backend/docs/patterns/security/file-upload.md. The route is
topic-independent (POST /forum/images/) — see api/views.PostImageUploadView.
"""

import io
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image as PILImage
from rest_framework.test import APIClient
from wagtail.images import get_image_model
from wagtail_forum.collections import get_forum_image_collection
from wagtail_forum.conf import get_setting

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")

URL = "/forum/images/"


def _jpeg(width=10, height=10):
    buf = io.BytesIO()
    PILImage.new("RGB", (width, height), color="red").save(buf, format="JPEG")
    buf.seek(0)
    return buf.read()


def _upload(name="ok.jpg", content=None, content_type="image/jpeg"):
    return SimpleUploadedFile(
        name, content if content is not None else _jpeg(), content_type=content_type
    )


def _auth_client():
    client = APIClient()
    client.force_authenticate(User.objects.create_user(username="up", password="x"))
    return client


@pytest.mark.django_db
def test_upload_requires_authentication():
    resp = APIClient().post(URL, {"image": _upload()}, format="multipart")
    assert resp.status_code == 401


@pytest.mark.django_db
def test_valid_image_uploads_into_forum_collection_and_returns_shape():
    resp = _auth_client().post(URL, {"image": _upload()}, format="multipart")
    assert resp.status_code == 201
    assert set(resp.data) == {"id", "url", "alt", "width", "height"}
    assert resp.data["url"].startswith("http://testserver")
    image = get_image_model().objects.get(id=resp.data["id"])
    assert image.collection_id == get_forum_image_collection().id


@pytest.mark.django_db
def test_missing_file_rejected():
    resp = _auth_client().post(URL, {}, format="multipart")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_invalid_extension_rejected():
    # Layer 1: a .php payload renamed nowhere near an image extension.
    bad = SimpleUploadedFile(
        "hack.php", b'<?php echo "x"; ?>', content_type="application/x-php"
    )
    resp = _auth_client().post(URL, {"image": bad}, format="multipart")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_invalid_mime_rejected():
    # Layer 2: a jpg extension but a non-image declared content type.
    bad = _upload(name="a.jpg", content=_jpeg(), content_type="application/x-php")
    resp = _auth_client().post(URL, {"image": bad}, format="multipart")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_oversized_file_rejected():
    # Layer 3: passes extension+MIME but exceeds the size cap.
    big = b"x" * (get_setting("IMAGE_MAX_SIZE_BYTES") + 1)
    resp = _auth_client().post(URL, {"image": _upload(content=big)}, format="multipart")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_non_image_bytes_rejected():
    # Layer 4: a correct extension + MIME but the bytes are not a real image.
    bad = _upload(content=b"this is not an image")
    resp = _auth_client().post(URL, {"image": bad}, format="multipart")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_oversized_dimensions_rejected():
    # Layer 4: decodes as a valid JPEG but exceeds the dimension cap.
    huge = _jpeg(width=get_setting("IMAGE_MAX_WIDTH") + 1, height=10)
    resp = _auth_client().post(
        URL, {"image": _upload(content=huge)}, format="multipart"
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_decompression_bomb_rejected():
    # Layer 4: PIL raises DecompressionBombError before the file is stored.
    with patch("PIL.Image.open") as mock_open:
        mock_open.side_effect = PILImage.DecompressionBombError("too many pixels")
        resp = _auth_client().post(URL, {"image": _upload()}, format="multipart")
    assert resp.status_code == 400
    assert get_image_model().objects.count() == 0


@pytest.mark.django_db
def test_image_round_trips_through_create_and_read():
    """The real user path end-to-end: upload an image, post a reply whose body
    references it (plus heading/code blocks), and read the whole body back. This
    exercises membership validation -> to_python storage -> serialize_forum_body
    (rewritten in PR-3a) for image AND the text/struct block types together."""
    from wagtail.models import Page
    from wagtail_forum.models import (
        ForumBoard,
        ForumIndex,
        ForumProfile,
        Post,
        Topic,
        TrustLevel,
    )
    from wagtail_forum.workflow import ensure_default_workflow

    ensure_default_workflow()
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    author = User.objects.create_user(username="mem", password="x")
    profile = ForumProfile.for_user(author)
    profile.trust_level = TrustLevel.MEMBER  # autopublish, so the reply goes live
    profile.save()
    topic = Topic.objects.create(
        board=board, title="T", slug="t", author=author, live=True
    )
    Post.objects.create(
        topic=topic,
        author=author,
        is_opening_post=True,
        live=True,
        body=[{"type": "paragraph", "value": "<p>op</p>"}],
    )

    client = APIClient()
    client.force_authenticate(author)

    upload = client.post(URL, {"image": _upload()}, format="multipart")
    assert upload.status_code == 201
    image_id = upload.data["id"]

    reply = client.post(
        f"/forum/topics/{topic.id}/posts/",
        {
            "body": [
                {"type": "paragraph", "value": "<p>look</p>"},
                {"type": "image", "value": image_id},
                {"type": "heading", "value": "Notes"},
                {"type": "code", "value": {"language": "py", "code": "x = 1"}},
            ]
        },
        format="json",
    )
    assert reply.status_code == 201
    assert reply.data["status"] == "published"  # MEMBER trust autopublishes

    listing = client.get(f"/forum/topics/{topic.id}/posts/")
    assert listing.status_code == 200
    # The published reply is in the live listing — proves to_python stored it.
    bodies = [p["body"] for p in listing.data["results"] if p["id"] == reply.data["id"]]
    assert len(bodies) == 1
    blocks = {b["type"]: b["value"] for b in bodies[0]}
    assert set(blocks) == {"paragraph", "image", "heading", "code"}
    assert blocks["paragraph"] == "<p>look</p>"
    assert blocks["heading"] == "Notes"
    assert blocks["code"] == {"language": "py", "code": "x = 1"}
    assert blocks["image"]["id"] == image_id
    assert blocks["image"]["url"].startswith("http://testserver")
    assert blocks["image"]["width"] > 0 and blocks["image"]["height"] > 0
