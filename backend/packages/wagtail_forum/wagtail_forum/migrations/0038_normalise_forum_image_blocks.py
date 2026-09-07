"""Normalise every stored image block from the bare PK to the ImageBlock dict.

Migration 0037 swapped ``ImageChooserBlock`` for ``ImageBlock``. Wagtail reads
the old bare-PK shape transparently (``ImageBlock.to_python`` /
``bulk_to_python`` special-case an int), so nothing is *broken* without this
migration — but ``bulk_to_python``'s legacy branch only fires when EVERY value
in the batch is an int:

    if values and all(value is None or isinstance(value, int) for value in values):

A batch mixing one un-migrated PK with one new dict falls through to
``StructBlock.bulk_to_python``, which calls ``.get()`` on the int and raises.
Wagtail builds those batches itself — admin listings, search indexing,
ReferenceIndex rebuilds — and the forum's own read path never resolves the
StreamValue (it walks ``raw_data``), so an un-migrated row would break the CMS
while every API test stayed green. Normalising removes the mixed state entirely.

Revisions are rewritten too, not just live bodies: ``Post`` is
``DraftStateMixin`` + ``RevisionMixin``, so a revision carries its own
serialised body. Skipping them would let a revert re-introduce a bare PK long
after this migration ran.

Alt text: a pre-0037 block had none of its own — it lived on
``Image.description``. That value is copied into the block's ``alt_text``, and
an EMPTY one becomes ``decorative=True`` rather than ``alt_text=""``, because
``ImageBlock.clean()`` rejects "no alt text and not decorative": mapping the
back-catalogue to the latter would make every legacy image un-editable in the
Wagtail admin. A blank alt genuinely IS a decorative declaration — it is what
the composer's "Skip" button has always meant.
"""

import json

from django.conf import settings
from django.db import migrations

CHUNK = 500


def _iter_image_blocks(raw_data):
    """Yield each image block dict in *raw_data* (a list of block dicts)."""
    for block in raw_data:
        if isinstance(block, dict) and block.get("type") == "image":
            yield block


def _load_body(body):
    """Return *body* as a list of block dicts, or None if it is not usable.

    A live ``Post.body`` reads back as a ``StreamValue`` (``.raw_data``); a
    revision stores the field's serialised form, which is a JSON string.
    """
    if body is None:
        return None
    if isinstance(body, str):
        try:
            loaded = json.loads(body)
        except (TypeError, ValueError):
            return None
        return loaded if isinstance(loaded, list) else None
    if isinstance(body, list):
        return body
    # StreamValue.raw_data is a RawDataView (a MutableSequence), NOT a list —
    # an isinstance(..., list) check here silently returns None and the
    # migration converts nothing while still reporting success.
    raw = getattr(body, "raw_data", None)
    if raw is None:
        return None
    try:
        return list(raw)
    except TypeError:
        return None


def _forward_value(value, descriptions):
    """bare PK -> {'image', 'alt_text', 'decorative'}; leave a dict untouched."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None  # already a dict, or unrecognisable — do not touch
    alt = (descriptions.get(value) or "").strip()
    return {"image": value, "alt_text": alt, "decorative": not alt}


def _reverse_value(value):
    """{'image': N, ...} -> N. alt_text/decorative are dropped.

    Not lossless, and cannot be: the pre-0037 shape has nowhere to put them.
    The read path falls back to ``Image.description``, which is where a
    round-tripped body's alt came from in the first place.
    """
    if isinstance(value, dict) and isinstance(value.get("image"), int):
        return value["image"]
    return None


def _rewrite(apps, schema_editor, convert, needs_descriptions):
    Post = apps.get_model("wagtail_forum", "Post")
    Revision = apps.get_model("wagtailcore", "Revision")
    ContentType = apps.get_model("contenttypes", "ContentType")
    Image = apps.get_model(*_image_model_label(apps))

    descriptions = {}
    if needs_descriptions:
        descriptions = dict(Image.objects.values_list("id", "description"))

    # --- live bodies -------------------------------------------------------
    updates = []
    for post in Post.objects.only("id", "body").iterator(chunk_size=CHUNK):
        raw = _load_body(post.body)
        if raw is None:
            continue
        changed = False
        for block in _iter_image_blocks(raw):
            new_value = convert(block.get("value"), descriptions)
            if new_value is not None:
                block["value"] = new_value
                changed = True
        if changed:
            # StreamField extends models.Field, NOT JSONField: get_prep_value
            # passes a non-StreamValue straight through, so a plain list would
            # be stored as its Python repr. A JSON string is what the column
            # wants.
            post.body = json.dumps(raw)
            updates.append(post)
        if len(updates) >= CHUNK:
            Post.objects.bulk_update(updates, ["body"])
            updates = []
    if updates:
        Post.objects.bulk_update(updates, ["body"])

    # --- revisions ---------------------------------------------------------
    post_type = ContentType.objects.filter(
        app_label="wagtail_forum", model="post"
    ).first()
    if post_type is None:
        return
    revisions = []
    for revision in Revision.objects.filter(content_type=post_type).iterator(
        chunk_size=CHUNK
    ):
        content = revision.content
        if not isinstance(content, dict):
            continue
        raw = _load_body(content.get("body"))
        if raw is None:
            continue
        changed = False
        for block in _iter_image_blocks(raw):
            new_value = convert(block.get("value"), descriptions)
            if new_value is not None:
                block["value"] = new_value
                changed = True
        if changed:
            # Revision.content is a JSONField holding the model's serialised
            # form, in which a StreamField is itself a JSON *string*.
            content["body"] = json.dumps(raw)
            revision.content = content
            revisions.append(revision)
        if len(revisions) >= CHUNK:
            Revision.objects.bulk_update(revisions, ["content"])
            revisions = []
    if revisions:
        Revision.objects.bulk_update(revisions, ["content"])


def _image_model_label(apps):
    """Resolve WAGTAILIMAGES_IMAGE_MODEL to (app_label, model_name)."""
    label = getattr(settings, "WAGTAILIMAGES_IMAGE_MODEL", "wagtailimages.Image")
    app_label, _, model_name = label.partition(".")
    return app_label, model_name


def forwards(apps, schema_editor):
    _rewrite(apps, schema_editor, _forward_value, needs_descriptions=True)


def backwards(apps, schema_editor):
    _rewrite(
        apps,
        schema_editor,
        lambda value, _descriptions: _reverse_value(value),
        needs_descriptions=False,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("wagtail_forum", "0037_alter_post_body"),
        ("wagtailcore", "0001_initial"),
        ("contenttypes", "0001_initial"),
        # This migration READS Image.description, so the image model's table
        # must exist first. With the default model that happens to hold via
        # 0002/0019, but the package is reusable and a host may swap in a custom
        # WAGTAILIMAGES_IMAGE_MODEL, which has no such ordering guarantee on a
        # fresh migrate.
        migrations.swappable_dependency(
            getattr(settings, "WAGTAILIMAGES_IMAGE_MODEL", "wagtailimages.Image")
        ),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
