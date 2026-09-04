"""Forum post images in Wagtail's ReferenceIndex (Wagtail quick wins, item 3).

``Post`` is a registered snippet, so Wagtail already indexes the images its
body references — the image usage view and the delete confirmation list the
posts natively. What the package adds is read-side only: a warning when an
image that a LIVE post still shows is deleted (the post keeps a dangling
block). Deletion is never blocked.
"""

import logging

import pytest
from django.contrib.auth import get_user_model
from wagtail.images import get_image_model
from wagtail.images.tests.utils import get_test_image_file
from wagtail.models import Page, ReferenceIndex
from wagtail_forum.models import ForumBoard, ForumIndex, Post, Topic

User = get_user_model()
LOGGER = "wagtail_forum"

pytestmark = pytest.mark.django_db


def _image():
    return get_image_model().objects.create(
        title="seedling", file=get_test_image_file()
    )


def _post_showing(image, *, live=True):
    author = User.objects.create_user(username="author")
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    topic = Topic.objects.create(
        board=board, title="Seedling help", slug="seedling-help", author=author
    )
    return Post.objects.create(
        topic=topic,
        author=author,
        is_opening_post=True,
        live=live,
        body=[("image", image)],
    )


def _warnings(caplog):
    return [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]


def test_a_post_body_image_is_in_the_reference_index():
    image = _image()
    post = _post_showing(image)

    refs = ReferenceIndex.get_references_to(image)

    assert list(refs.values_list("object_id", flat=True)) == [str(post.pk)]


def test_the_image_usage_view_lists_the_post(client):
    image = _image()
    post = _post_showing(image)
    client.force_login(User.objects.create_superuser(username="root", email="r@x.io"))

    resp = client.get(f"/cms/images/usage/{image.pk}/")

    assert resp.status_code == 200
    assert str(post) in resp.content.decode()


def test_deleting_an_image_a_live_post_shows_logs_a_warning(caplog):
    image = _image()
    post = _post_showing(image)

    with caplog.at_level(logging.WARNING, logger=LOGGER):
        image.delete()

    assert any(
        f"post {post.pk}" in m and f"topic {post.topic_id}" in m
        for m in _warnings(caplog)
    ), _warnings(caplog)


def test_deletion_is_not_blocked():
    image = _image()
    _post_showing(image)

    image.delete()

    assert not get_image_model().objects.filter(pk=image.pk).exists()


def test_deleting_an_image_only_an_unpublished_post_shows_is_silent(caplog):
    image = _image()
    _post_showing(image, live=False)

    with caplog.at_level(logging.WARNING, logger=LOGGER):
        image.delete()

    assert _warnings(caplog) == []


def test_deleting_an_unreferenced_image_is_silent(caplog):
    image = _image()

    with caplog.at_level(logging.WARNING, logger=LOGGER):
        image.delete()

    assert _warnings(caplog) == []
