from django.db.models.signals import post_migrate


def ensure_forum_bootstrap(sender, **kwargs):
    """Idempotently create the moderation workflow + Forum Moderators group.

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
        content_type__model__in=["topic", "post"],
        codename__in=[
            "view_topic",
            "change_topic",
            "delete_topic",
            "view_post",
            "change_post",
            "delete_post",
            "publish_topic",
            "publish_post",
        ],
    )
    group.permissions.set(perms)


def connect():
    post_migrate.connect(
        ensure_forum_bootstrap, dispatch_uid="forum_host.ensure_forum_bootstrap"
    )
