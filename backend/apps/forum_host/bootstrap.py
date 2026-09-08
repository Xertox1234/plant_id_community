import logging

from django.db.models.signals import post_migrate

logger = logging.getLogger(__name__)


def ensure_forum_bootstrap(sender, **kwargs):
    """Idempotently create the moderation workflow + Forum Moderators group,
    and wire forum members' + moderators' Wagtail image permissions.

    Connected to post_migrate (after Django has created Permission rows). Guarded
    to run once — when forum_host's own post_migrate fires — by which point
    wagtail_forum is fully migrated and its permissions exist (forum_host is
    listed after wagtail_forum in INSTALLED_APPS).
    """
    if getattr(sender, "label", None) != "forum_host":
        return

    from django.contrib.auth.models import Group, Permission
    from wagtail_forum.workflow import ensure_default_workflow

    ensure_default_workflow()

    group, _ = Group.objects.get_or_create(name="Forum Moderators")
    # DraftStateMixin snippets get publish_* perms (created by create_permissions
    # once wagtail_forum is fully migrated), alongside the standard CRUD perms.
    # filter() assigns whatever matched, so the list stays correct even if a
    # Wagtail version drops one.
    perms = Permission.objects.filter(
        content_type__app_label="wagtail_forum",
        content_type__model__in=["topic", "post", "report"],
        codename__in=[
            "view_topic",
            "change_topic",
            "delete_topic",
            "view_post",
            "change_post",
            "delete_post",
            "publish_topic",
            "publish_post",
            # Reports (todo 345): the moderation queue and the Report
            # snippet's inspect/edit views are gated on Report permissions,
            # so without these a moderator could unpublish a post but never
            # open, action, or dismiss the report that flagged it.
            "view_report",
            "change_report",
        ],
    ) | Permission.objects.filter(
        # Without access_admin a moderator-only user cannot log into /cms/ at all.
        content_type__app_label="wagtailadmin",
        codename="access_admin",
    )
    # add(), not set(): this runs on EVERY post_migrate, and set() would strip
    # permissions an admin granted to the group (host-customization-preserving,
    # like ensure_default_workflow).
    group.permissions.add(*perms)

    _ensure_forum_image_permissions()


def _ensure_forum_image_permissions():
    """Idempotently wire Wagtail's OWN image-ownership permission system to
    forum members and moderators, on the forum's dedicated image collection.

    ``wagtail.permission_policies.collections.CollectionOwnershipPermissionPolicy``
    (the policy ``wagtail.images`` uses) already encodes "add implies
    edit/delete of what you personally uploaded" and treats "choose" as its
    own, separately-granted permission -- see that module for the exact
    rules. This function is the ``GroupCollectionPermission`` wiring that
    policy needs to do anything for our users; without it every check it
    makes returns False and the forum's image API would have to reinvent
    ownership checks by hand instead of using Wagtail's own.

    - Forum Members: ``add_image`` + ``choose_image`` on the forum
      collection. ``add`` is what makes the policy treat a member as able to
      edit/delete images THEY uploaded there; ``choose`` is what the
      personal-reuse endpoint checks, so it enforces Wagtail's real
      permission rather than a parallel invented one.
    - Forum Moderators: ``change_image`` on the forum collection.
      ``CollectionOwnershipPermissionPolicy`` treats "delete" as equivalent
      to "change" (Wagtail's own docs: "deletion is considered equivalent to
      editing"), so this alone covers deleting ANY forum image, not just
      ones a moderator uploaded themselves.

    ``GroupCollectionPermission.unique_together = (group, collection,
    permission)`` makes ``get_or_create`` here naturally idempotent -- unlike
    the Meta-permission block above, there is nothing an admin could grant
    through this exact (group, collection, permission) triple for this
    function to accidentally strip, so no separate add()-not-set() dance is
    needed here.
    """
    from django.contrib.auth.models import Group, Permission
    from wagtail.models import GroupCollectionPermission
    from wagtail_forum.collections import get_forum_image_collection

    collection = get_forum_image_collection()
    image_perms = {
        p.codename: p
        for p in Permission.objects.filter(
            content_type__app_label="wagtailimages",
            content_type__model="image",
            codename__in=["add_image", "choose_image", "change_image"],
        )
    }

    # `.get(codename)`, not `image_perms[codename]`: this runs in a
    # `post_migrate` receiver, so a KeyError here aborts `manage.py migrate`
    # — a failed deploy rather than a warning — the moment a Wagtail version
    # renames or drops one of these codenames, or a database is rebuilt with
    # the wagtailimages content types missing. Same reasoning as the
    # Meta-permission block above, which filters rather than indexes so "the
    # list stays correct even if a Wagtail version drops one".
    missing = [
        codename
        for codename in ("add_image", "choose_image", "change_image")
        if codename not in image_perms
    ]
    if missing:
        logger.warning(
            "[FORUM] Skipping image permissions for %s — codename(s) absent "
            "from wagtailimages. Forum image upload/reuse will be unavailable "
            "until this is resolved.",
            ", ".join(missing),
        )

    members, _ = Group.objects.get_or_create(name="Forum Members")
    for codename in ("add_image", "choose_image"):
        permission = image_perms.get(codename)
        if permission is None:
            continue
        GroupCollectionPermission.objects.get_or_create(
            group=members,
            collection=collection,
            permission=permission,
        )

    moderators, _ = Group.objects.get_or_create(name="Forum Moderators")
    change_image = image_perms.get("change_image")
    if change_image is not None:
        GroupCollectionPermission.objects.get_or_create(
            group=moderators,
            collection=collection,
            permission=change_image,
        )


def connect():
    post_migrate.connect(
        ensure_forum_bootstrap, dispatch_uid="forum_host.ensure_forum_bootstrap"
    )
