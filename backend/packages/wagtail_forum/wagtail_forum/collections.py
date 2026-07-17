"""The forum's image collection (Spec 2 PR-3).

Inline post images upload into this Wagtail collection, and a post body may only
reference images that live in it (membership-checked in ``api/sanitize.py`` —
closes the audit-L5 IDOR-by-reference). The collection is created lazily and
idempotently so neither the upload view nor body validation depends on a
separate seeding step.
"""

from django.db import transaction
from wagtail.models import Collection

from .conf import get_setting


def get_forum_image_collection():
    """Return the forum image collection, creating it under root if absent.

    Collection.name has no unique constraint, so bare check-then-create can
    race two concurrent first callers into duplicate collections (audit
    2026-07-17 L2). Double-checked locking: the steady-state read stays
    lock-free; only the create path serializes on the root collection row.
    """
    name = get_setting("IMAGE_COLLECTION_NAME")
    root = Collection.get_first_root_node()
    existing = root.get_children().filter(name=name).first()
    if existing is not None:
        return existing
    with transaction.atomic():
        locked_root = Collection.objects.select_for_update().get(pk=root.pk)
        existing = locked_root.get_children().filter(name=name).first()
        if existing is not None:
            return existing
        return locked_root.add_child(name=name)
