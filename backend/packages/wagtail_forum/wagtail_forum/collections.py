"""The forum's image collection (Spec 2 PR-3).

Inline post images upload into this Wagtail collection, and a post body may only
reference images that live in it (membership-checked in ``api/sanitize.py`` —
closes the audit-L5 IDOR-by-reference). The collection is created lazily and
idempotently so neither the upload view nor body validation depends on a
separate seeding step.
"""

from wagtail.models import Collection

from .conf import get_setting


def get_forum_image_collection():
    """Return the forum image collection, creating it under root if absent."""
    name = get_setting("IMAGE_COLLECTION_NAME")
    root = Collection.get_first_root_node()
    existing = root.get_children().filter(name=name).first()
    if existing is not None:
        return existing
    return root.add_child(name=name)
