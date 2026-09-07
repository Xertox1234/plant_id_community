"""Data migration 0038: bare image PKs -> the ImageBlock dict.

The acceptance criterion is not "some post looks right" — it is **zero bare PKs
remain anywhere**, in live bodies AND in revisions. Wagtail's
``ImageBlock.bulk_to_python`` only takes its legacy branch when EVERY value in
the batch is an int, so a single survivor sharing a batch with a migrated dict
falls through to ``StructBlock.bulk_to_python`` and raises on ``int.get()``.
Wagtail builds those batches (admin listings, search indexing, ReferenceIndex),
and the forum's own read path walks ``raw_data`` instead — so a survivor breaks
the CMS while every API test stays green. Hence the sweep assertions below.

The migration functions are called directly with the real app registry:
``apps.get_model`` has the same interface as the historical one, and the model
fields the migration touches are unchanged by it.
"""

import json

import pytest
from django.apps import apps as global_apps
from django.contrib.auth import get_user_model
from wagtail.images import get_image_model
from wagtail.images.tests.utils import get_test_image_file
from wagtail.models import Page, Revision
from wagtail_forum.collections import get_forum_image_collection

User = get_user_model()


def _migration():
    """Import the migration module by its dotted path (leading digits)."""
    import importlib

    return importlib.import_module(
        "wagtail_forum.migrations.0038_normalise_forum_image_blocks"
    )


def _forum_image(description=""):
    return get_image_model().objects.create(
        title="IMG_2481.jpg",
        description=description,
        file=get_test_image_file(),
        collection=get_forum_image_collection(),
    )


def _legacy_post(author, topic, image_ids):
    """A Post whose stored body holds BARE PKs, as pre-0037 rows do.

    Written past the field descriptor on purpose: assigning through it would run
    ImageBlock.to_python/get_prep_value and normalise the value on the way in,
    so `body=[{"type": "image", "value": pk}]` can no longer produce a legacy
    row. `.update()` with a JSON string is stored verbatim (StreamField extends
    models.Field, whose get_prep_value passes a non-StreamValue through).
    """
    from wagtail_forum.models import Post

    post = Post.objects.create(topic=topic, author=author, live=True, body=[])
    raw = [{"type": "image", "value": pk, "id": f"b{pk}"} for pk in image_ids]
    Post.objects.filter(pk=post.pk).update(body=json.dumps(raw))
    post.refresh_from_db()
    return post


def _bare_pk_count():
    """Every bare-PK image value left in live bodies + Post revisions."""
    from django.contrib.contenttypes.models import ContentType
    from wagtail_forum.models import Post

    def bare(raw_list):
        return sum(
            1
            for b in raw_list
            if isinstance(b, dict)
            and b.get("type") == "image"
            and isinstance(b.get("value"), int)
        )

    total = sum(bare(p.body.raw_data) for p in Post.objects.all())
    post_type = ContentType.objects.get_for_model(Post)
    for rev in Revision.objects.filter(content_type=post_type):
        body = rev.content.get("body")
        if isinstance(body, str):
            body = json.loads(body)
        if isinstance(body, list):
            total += bare(body)
    return total


@pytest.fixture
def topic(db):
    from wagtail_forum.models import ForumBoard, ForumIndex, Topic

    author = User.objects.create_user(username="mig-author")
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    return author, Topic.objects.create(
        board=board, title="T", slug="t", author=author, live=True
    )


@pytest.mark.django_db
def test_forward_migration_leaves_no_bare_pk_in_bodies_or_revisions(topic):
    author, t = topic
    described = _forum_image(description="A monstera leaf")
    blank = _forum_image(description="")
    post = _legacy_post(author, t, [described.id, blank.id])

    # A revision carrying the same legacy body — Post is RevisionMixin, so a
    # revert would otherwise re-introduce the bare PK long after the migration.
    revision = post.save_revision(user=author)
    legacy_raw = [
        {"type": "image", "value": described.id, "id": "r1"},
        {"type": "image", "value": blank.id, "id": "r2"},
    ]
    content = revision.content
    content["body"] = json.dumps(legacy_raw)
    Revision.objects.filter(pk=revision.pk).update(content=content)

    assert _bare_pk_count() == 4, "fixture should start with 4 bare PKs"

    _migration().forwards(global_apps, None)

    # THE acceptance criterion.
    assert _bare_pk_count() == 0

    post.refresh_from_db()
    values = [b["value"] for b in post.body.raw_data if b["type"] == "image"]
    # A described image keeps its words; a blank one becomes decorative rather
    # than alt_text="" — the pair ImageBlock.clean() refuses.
    assert values[0] == {
        "image": described.id,
        "alt_text": "A monstera leaf",
        "decorative": False,
    }
    assert values[1] == {"image": blank.id, "alt_text": "", "decorative": True}

    revision.refresh_from_db()
    rev_values = [
        b["value"] for b in json.loads(revision.content["body"]) if b["type"] == "image"
    ]
    assert rev_values[0]["alt_text"] == "A monstera leaf"
    assert rev_values[1]["decorative"] is True


@pytest.mark.django_db
def test_migration_is_idempotent(topic):
    author, t = topic
    image = _forum_image(description="stable")
    post = _legacy_post(author, t, [image.id])
    mig = _migration()

    mig.forwards(global_apps, None)
    post.refresh_from_db()
    # list(): raw_data is a RawDataView, which has no __eq__ — comparing two of
    # them falls back to identity and would pass for any content at all.
    once = list(post.body.raw_data)

    mig.forwards(global_apps, None)
    post.refresh_from_db()
    assert list(post.body.raw_data) == once


@pytest.mark.django_db
def test_backwards_restores_the_bare_pk(topic):
    author, t = topic
    image = _forum_image(description="round trip")
    post = _legacy_post(author, t, [image.id])
    mig = _migration()

    mig.forwards(global_apps, None)
    assert _bare_pk_count() == 0

    mig.backwards(global_apps, None)
    post.refresh_from_db()
    assert [b["value"] for b in post.body.raw_data if b["type"] == "image"] == [
        image.id
    ]


@pytest.mark.django_db
def test_forward_migration_leaves_an_already_migrated_body_untouched(topic):
    """A dict value must not be re-wrapped or have its alt overwritten."""
    from wagtail_forum.models import Post

    author, t = topic
    image = _forum_image(description="the image row says this")
    post = Post.objects.create(topic=t, author=author, live=True, body=[])
    raw = [
        {
            "type": "image",
            "value": {
                "image": image.id,
                "alt_text": "but THIS usage says that",
                "decorative": False,
            },
            "id": "b1",
        }
    ]
    Post.objects.filter(pk=post.pk).update(body=json.dumps(raw))

    _migration().forwards(global_apps, None)

    post.refresh_from_db()
    assert post.body.raw_data[0]["value"]["alt_text"] == "but THIS usage says that"
