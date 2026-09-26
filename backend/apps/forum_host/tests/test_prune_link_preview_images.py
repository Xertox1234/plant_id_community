"""prune_link_preview_images (todo 428 slice D).

Storage is Django's in-memory backend; a file's age comes from freezing the
clock while it is saved. Posts and revisions are real rows, because the whole
point is which bodies count as references.
"""

import io
import logging
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from django.utils import timezone
from freezegun import freeze_time
from wagtail.models import Page, Revision
from wagtail_forum.models import ForumBoard, ForumIndex, Post, Topic

User = get_user_model()

PREFIX = "forum/link-previews/"
A = PREFIX + "a" * 64 + ".webp"
B = PREFIX + "b" * 64 + ".webp"
C = PREFIX + "c" * 64 + ".webp"


@pytest.fixture(autouse=True)
def media_storage():
    with override_settings(
        STORAGES={
            "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
            "staticfiles": {
                "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
            },
        },
    ):
        yield


@pytest.fixture
def topic(db):
    author = User.objects.create_user(username="ada")
    index = Page.objects.get(id=1).add_child(
        instance=ForumIndex(title="Forum", slug="forum")
    )
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    return Topic.objects.create(board=board, title="T", slug="t", author=author)


@pytest.fixture
def prune_log(caplog):
    """The ``apps`` logger does not propagate to root, where caplog listens."""
    command_logger = logging.getLogger(
        "apps.forum_host.management.commands.prune_link_preview_images"
    )
    command_logger.addHandler(caplog.handler)
    with caplog.at_level("INFO", logger=command_logger.name):
        yield caplog
    command_logger.removeHandler(caplog.handler)


def store(name, age=timedelta(hours=25)):
    with freeze_time(timezone.now() - age):
        saved = default_storage.save(name, ContentFile(b"webp"))
    assert saved == name
    return name


def card(image):
    return {
        "type": "link_preview",
        "value": {
            "url": "https://example.com/",
            "title": "Example",
            "description": "",
            "image": image,
            "site_name": "",
            "domain": "example.com",
        },
    }


def post(topic, *blocks, live=True):
    return Post.objects.create(
        topic=topic, author=topic.author, body=list(blocks), live=live
    )


def stored():
    try:
        return {PREFIX + f for f in default_storage.listdir(PREFIX.rstrip("/"))[1]}
    except FileNotFoundError:
        return set()


def prune(*args):
    out = io.StringIO()
    call_command("prune_link_preview_images", *args, stdout=out)
    return out.getvalue()


# --- what is deleted -------------------------------------------------------------


def test_an_old_unreferenced_image_is_deleted_and_a_referenced_one_kept(
    topic, prune_log
):
    store(A)
    store(B)
    post(topic, card(A))

    output = prune()

    assert stored() == {A}
    assert f"[PRUNE] deleted {B}" in prune_log.text
    assert "[PRUNE] link-preview images: 2 stored" in output
    assert "deleted 1, 0 failed" in output


def test_an_orphaned_suffixed_duplicate_is_deleted(topic):
    """A concurrent store can leave ``<hash>_AbCdEfG.webp`` behind. It never
    passes is_cached_image_name, so nothing serves it, and only this command
    ever removes it."""
    duplicate = store(PREFIX + "a" * 64 + "_AbCdEfG.webp")

    prune()

    assert duplicate not in stored()


def test_files_outside_the_prefix_are_never_touched(topic):
    other = store("forum/images/photo.jpg")
    sibling = store("forum/link-previews-old/" + "a" * 64 + ".webp")

    prune()

    assert default_storage.exists(other)
    assert default_storage.exists(sibling)


def test_no_prefix_directory_yet_is_a_clean_run(topic):
    assert "[PRUNE] link-preview images: 0 stored" in prune()


# --- what counts as a reference ------------------------------------------------------


def test_an_image_used_only_by_a_pending_revision_is_kept(topic):
    """A post waiting for moderation exists only as a revision (todos 422/423):
    its row does not carry the card yet."""
    store(A)
    pending = post(topic, card(A), live=False)
    pending.save_revision()
    pending.body = []
    pending.save(update_fields=["body"])

    prune()

    assert stored() == {A}


def test_an_image_used_only_by_a_historical_revision_is_kept(topic):
    """The edit-history sheet shows old revisions, so an image edited out of
    the live body must survive while the revision holding it exists."""
    store(A)
    store(B)
    edited = post(topic, card(A))
    edited.save_revision().publish()
    edited.body = [card(B)]
    edited.save_revision().publish()
    edited.refresh_from_db()
    assert edited.body.raw_data[0]["value"]["image"] == B

    prune()

    assert stored() == {A, B}


def test_an_image_used_by_an_unpublished_post_is_kept(topic):
    store(A)
    post(topic, card(A), live=False)

    prune()

    assert stored() == {A}


def test_deleting_the_post_releases_its_images(topic):
    """Deleting a post cascades its revisions, so the image is orphaned."""
    store(A)
    gone = post(topic, card(A))
    gone.save_revision().publish()
    gone.delete()

    prune()

    assert stored() == set()


def test_an_unreadable_revision_body_deletes_nothing(topic):
    store(A)
    broken = post(topic)
    revision = broken.save_revision()
    Revision.objects.filter(pk=revision.pk).update(content={"body": "[{not json"})

    with pytest.raises(CommandError, match="unreadable body"):
        prune()

    assert stored() == {A}


# --- the safety rails --------------------------------------------------------------


def test_an_image_younger_than_the_grace_period_is_kept(topic):
    store(A, age=timedelta(hours=23))

    output = prune()

    assert stored() == {A}
    assert "1 younger than 24h" in output


def test_dry_run_deletes_nothing_and_reports_what_would_go(topic, prune_log):
    store(A)
    store(B)
    post(topic, card(A))

    output = prune("--dry-run")

    assert stored() == {A, B}
    assert f"[PRUNE] would delete {B}" in prune_log.text
    assert "would delete 1" in output


@pytest.mark.parametrize("prefix", ["", "/", "forum/link-previews"])
def test_a_blank_root_or_unterminated_prefix_is_refused(topic, prefix):
    store(A)
    store("forum/images/photo.jpg")

    with override_settings(WAGTAILFORUM_LINK_PREVIEW_IMAGE_PREFIX=prefix):
        with pytest.raises(CommandError, match="refusing to run"):
            prune()

    assert stored() == {A}
    assert default_storage.exists("forum/images/photo.jpg")


def test_a_failed_delete_fails_the_run_after_trying_the_rest(topic):
    store(A)
    store(B)
    real_delete = default_storage.delete

    def delete(name):
        if name == A:
            raise OSError("storage down")
        real_delete(name)

    with patch.object(default_storage, "delete", side_effect=delete):
        with pytest.raises(CommandError, match="1 image"):
            prune()

    assert stored() == {A}
