from wagtail.models import Task

from ..spam import get_spam_backend


class SpamCheckTask(Task):
    """An automated moderation task: approves clean content, rejects flagged.

    Resolution happens synchronously inside ``start()``. We pass ``update=False``
    to ``approve()``/``reject()`` because ``start()`` runs *inside*
    ``WorkflowState.update()`` before our task state is assigned as the workflow's
    ``current_task_state``. Letting approve/reject call ``update()`` themselves
    re-enters ``start()`` against the stale current state and recurses infinitely
    (and leaves the workflow half-open). With ``update=False`` we return the
    already-resolved task state, and Wagtail's outer ``update()`` (its documented
    auto-approve path) progresses the workflow: APPROVED -> finish -> publish via
    WAGTAIL_FINISH_WORKFLOW_ACTION; REJECTED -> NEEDS_CHANGES (stays a draft for a
    human to publish from the admin).

    Publication is a *system* action: the caller starts this workflow with
    ``user=None`` so the finish-action publish skips Wagtail's editor permission
    check (forum authors are not Wagtail editors; the spam check is the authority).
    """

    def start(self, workflow_state, user=None):
        task_state = super().start(workflow_state, user=user)
        result = get_spam_backend().check(workflow_state.content_object)
        if result.is_clean:
            task_state.approve(user=user, update=False)
        else:
            task_state.reject(user=user, comment=result.reason, update=False)
        return task_state
