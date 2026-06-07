from django.contrib.contenttypes.models import ContentType
from wagtail.models import Workflow, WorkflowContentType, WorkflowTask

from .conf import get_setting
from .models import ForumProfile, Post, Topic
from .models.moderation import SpamCheckTask

DEFAULT_WORKFLOW_NAME = "Forum moderation"


def ensure_default_workflow():
    """Idempotently create the moderation workflow and assign it to Topic/Post."""
    workflow, _ = Workflow.objects.get_or_create(name=DEFAULT_WORKFLOW_NAME)
    task, _ = SpamCheckTask.objects.get_or_create(name="Spam check")
    WorkflowTask.objects.get_or_create(
        workflow=workflow, task=task, defaults={"sort_order": 0}
    )
    for model in (Topic, Post):
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

    return "published" if obj.live else "pending"
