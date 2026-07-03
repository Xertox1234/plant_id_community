import logging

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from wagtail.models import Workflow, WorkflowContentType, WorkflowTask

from .conf import get_setting
from .models import ForumProfile, Post, Topic
from .models.moderation import SpamCheckTask

logger = logging.getLogger("wagtail_forum")

DEFAULT_WORKFLOW_NAME = "Forum moderation"


def ensure_default_workflow():
    """Idempotently create the moderation workflow and assign it to Topic/Post."""
    workflow, _ = Workflow.objects.get_or_create(name=DEFAULT_WORKFLOW_NAME)
    task, _ = SpamCheckTask.objects.get_or_create(name="Spam check")
    WorkflowTask.objects.get_or_create(
        workflow=workflow, task=task, defaults={"sort_order": 0}
    )
    for model in (Topic, Post):
        # Note: get_or_create keys on content_type, so this does NOT override a
        # workflow a host has already assigned to Topic/Post — it only fills it
        # in when absent. Idempotent and host-assignment-preserving.
        WorkflowContentType.objects.get_or_create(
            content_type=ContentType.objects.get_for_model(model),
            defaults={"workflow": workflow},
        )
    return workflow


def submit_for_moderation(obj, user):
    """Route a Post by trust. Returns 'published' or 'pending'.

    Liveness policy (Plan 1A): content is born live, so we force it to a draft
    (live=False) and only publish it here. Trusted users (trust >=
    TRUST_AUTOPUBLISH_LEVEL) publish immediately. Others run the moderation
    workflow: clean content auto-approves -> the single-task workflow finishes ->
    publish; flagged content is rejected and stays a draft (status 'pending').

    Security:
    - Publishing runs as the SYSTEM (user=None). Forum authors are not Wagtail
      editors; the trust/spam logic is the publish authority. Passing a real user
      to publish() would raise PublishPermissionError; passing None skips the
      editor permission check by design.
    - Fail CLOSED: if no moderation workflow is configured, an untrusted post is
      left as a draft rather than published unscreened.
    - The opening-post -> topic publish is guarded by an author match so one user
      can never force someone else's draft topic live (IDOR).
    """
    if obj.live:  # API callers already create drafts; skip the redundant UPDATE
        obj.live = False
        obj.save(update_fields=["live"])
    # Trust gates the *author's* content, so derive it from obj.author — NEVER the
    # caller. Otherwise a privileged caller (or a 1C bug) could launder an
    # untrusted author's content through their own trust level and skip screening.
    profile = ForumProfile.for_user(obj.author)
    revision = obj.save_revision(user=user)

    if profile.trust_level >= get_setting("TRUST_AUTOPUBLISH_LEVEL"):
        revision.publish(user=None)
    else:
        workflow = obj.get_workflow()
        if workflow is None:
            # Fail closed: no workflow -> leave untrusted content as a draft.
            pass
        else:
            workflow.start(obj, None)
    obj.refresh_from_db()

    # Publish the topic only when its own author's opening post goes live.
    # The author check prevents forcing someone else's draft topic live (IDOR).
    if (
        obj.live
        and obj.is_opening_post
        and not obj.topic.live
        and obj.topic.author_id == obj.author_id
    ):
        obj.topic.save_revision(user=user).publish(user=None)

    # Notify hosts of the moderation outcome (e.g. to push-notify the author).
    from .signals import moderation_decided, notify

    status = "published" if obj.live else "pending"
    notify(moderation_decided, sender=type(obj), obj=obj, status=status)
    return status


def _edit_is_trusted(obj: Post, acting_as_moderator: bool) -> bool:
    """Whether an edit may autopublish.

    Trust is the AUTHOR's, never the caller's, so a privileged caller cannot
    launder an untrusted author's edit through their own trust level. The one
    exception is an account-deleted author (Post.author is SET_NULL, so
    obj.author is None): there is no author trust to derive from. Only a
    moderator can reach such an edit (the view requires change_post when
    request.user != post.author), and a redaction must take effect immediately
    rather than leave the un-redacted body live behind a pending revision — so
    the moderator's authority gates autopublish in that case (finding #2).
    """
    if obj.author is None:
        return acting_as_moderator
    profile = ForumProfile.for_user(obj.author)
    return profile.trust_level >= get_setting("TRUST_AUTOPUBLISH_LEVEL")


def submit_edit_for_moderation(
    obj: Post, user, *, acting_as_moderator: bool = False
) -> str:
    """Re-screen an EDITED post WITHOUT unpublishing live content (Spec 2 Q2).

    The caller has already set obj.body to the new, validated StreamField value.
    Unlike submit_for_moderation (create-shaped: force-drafts live=False then
    publishes), an edit must never take approved content dark:

    - Trusted edit: publish the new revision immediately.
    - Untrusted edit: save a new revision and (re)start the moderation workflow.
      Clean content auto-approves -> publishes; flagged content is rejected and
      the revision stays pending while the live row keeps its last-approved body.
      live is NEVER forced False; obj.save() is NEVER called with the new body.

    Trust derives from obj.author (see _edit_is_trusted); acting_as_moderator
    only matters for an account-deleted (author=None) post. `edited` is set in
    memory and captured in the revision, so publish() writes it back atomically
    with the body — it flips to True iff the edit goes live.

    Persistence contract (finding #3): save_revision runs BEFORE the critical
    section, so a failure there propagates — nothing is persisted, an explicit
    error, never a fake 'pending'. Only the publish / workflow submission is
    wrapped; a failure there leaves the saved revision pending, which IS truthful
    (the live row keeps serving and a revision really is queued).

    Concurrency (finding #13): the publish is guarded by a row lock plus a
    liveness re-read, so a PATCH racing a moderator DELETE cannot resurrect a
    just-unpublished post.

    Returns 'published' (the edit is now live) or 'pending' (awaiting moderation,
    or superseded by a concurrent take-down).
    """
    from .signals import moderation_decided, notify

    obj.edited = True  # captured in the revision; published atomically with body
    trusted = _edit_is_trusted(obj, acting_as_moderator)
    # save_revision BEFORE the critical section: a failure here means nothing was
    # persisted, so it must propagate (never reported as a fake 'pending').
    revision = obj.save_revision(user=user)
    try:
        with transaction.atomic():
            # Lock the row and re-read liveness UNDER the lock: a PATCH racing a
            # DELETE must not silently overwrite the take-down with publish().
            locked = Post.objects.select_for_update().get(pk=obj.pk)
            if not locked.live:
                # A concurrent take-down won; leave the edit as a draft revision
                # rather than resurrecting the post.
                pass
            elif trusted:
                revision.publish(user=None)
            else:
                workflow = obj.get_workflow()
                if workflow is not None:
                    # A prior flagged edit leaves an active (NEEDS_CHANGES)
                    # workflow state; Wagtail forbids two active states per
                    # object, so a naive start() would raise ValidationError and
                    # wedge the post at 'pending' forever. Cancel the stale state,
                    # then screen the new revision from scratch (finding #1).
                    current_state = obj.current_workflow_state
                    if current_state is not None:
                        current_state.cancel(user=None)
                    workflow.start(obj, None)
                # else fail closed: no workflow -> the edit stays a pending revision.
    except Exception:
        # The revision IS saved and the live row keeps serving its last-approved
        # body, so 'pending' below is truthful (finding #3). Only a moderation-
        # step failure lands here; a pre-revision failure propagated above. The
        # except is OUTSIDE the atomic block, so the savepoint has already rolled
        # back — the connection is clean for the refresh_from_db that follows.
        logger.exception(
            "[ERROR] submit_edit_for_moderation moderation step failed for post %s",
            obj.pk,
        )
    obj.refresh_from_db()
    # has_unpublished_changes is True after save_revision and cleared by publish();
    # it is the single signal of whether the edit reached the live row.
    status = "pending" if obj.has_unpublished_changes else "published"
    # Notify hosts of the edit outcome AFTER the critical section, with the same
    # contract as the create path (finding #4).
    notify(moderation_decided, sender=type(obj), obj=obj, status=status)
    return status
