import logging
from contextlib import contextmanager
from contextvars import ContextVar

from wagtail.models import Task, TaskState

from ..spam import get_spam_backend

logger = logging.getLogger("wagtail_forum")

# Set by ``screen_without_publishing()``: the spam check about to run is a
# re-screen whose clean verdict must not publish (todo 579).
_screen_only = ContextVar("wagtail_forum_screen_only", default=False)


@contextmanager
def screen_without_publishing():
    """Run a spam screen whose clean verdict publishes nothing (todo 579).

    Used for an edit to a never-published opening post: the screen runs and
    its verdict is recorded on the revision, but the moderator's approval of
    the thread stays the gate that publishes it. See
    :meth:`SpamCheckTask.start`."""
    token = _screen_only.set(True)
    try:
        yield
    finally:
        _screen_only.reset(token)


def _finish_without_publishing(user=None):
    """Stands in for ``WorkflowState.on_finish`` on a screen-only run: the
    workflow ends APPROVED, and nothing is published."""


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

    A backend that raises fails CLOSED with a record (todo 561): the task is
    rejected with the error as its comment, so the content is held in
    NEEDS_CHANGES and the pending page's Approve has the revision this task
    state holds to publish. Before, the exception rolled the whole workflow
    back and left no state, and the pending page had to guess a crashed edit
    from a moderator's draft by who saved the revision.

    A never-published opening post is screened without being published on a
    re-screen (todo 579, owner decision 2026-10-10): an edit to it, or any
    screen after its first one. A clean verdict approves the task, and the
    workflow finishes APPROVED, but its finish action is replaced for this run
    so nothing goes live. The moderator's approval of the thread publishes it.
    The first screen (the create path) still publishes clean content: that is
    how an untrusted member's clean topic goes live without a moderator.
    """

    def start(self, workflow_state, user=None):
        task_state = super().start(workflow_state, user=user)
        # Check the content that will actually be PUBLISHED (the latest revision),
        # not the live DB row. The finish action publishes get_latest_revision();
        # if we checked content_object (the saved row) instead, a clean-saved post
        # whose latest revision was edited to spam would pass the check and then
        # publish the spam (a time-of-check/time-of-use bypass).
        row = workflow_state.content_object
        obj = row.get_latest_revision_as_object()
        try:
            result = get_spam_backend().check(obj)
        except Exception as exc:
            logger.exception(
                "[ERROR] wagtail_forum spam check failed for %s %s; held",
                type(row).__name__,
                row.pk,
            )
            task_state.reject(
                user=user,
                comment=f"The spam check could not run: {type(exc).__name__}",
                update=False,
            )
            return task_state
        if result.is_clean:
            if self._screens_without_publishing(row, task_state):
                # The outer update() calls finish() on this same instance, and
                # finish() calls self.on_finish: an instance attribute shadows
                # the class's finish action for this run only.
                workflow_state.on_finish = _finish_without_publishing
            task_state.approve(user=user, update=False)
        else:
            task_state.reject(user=user, comment=result.reason, update=False)
        return task_state

    @staticmethod
    def _screens_without_publishing(row, task_state):
        """Whether a clean verdict on ``row`` must not publish it (todo 579):
        a never-published opening post, screened by an edit
        (``screen_without_publishing``) or screened before. Never a post that
        was published once (``first_published_at`` set): those are not this
        rule's, so a taken-down post keeps its own rules."""
        from .posts import Post

        if not isinstance(row, Post) or not row.is_opening_post:
            return False
        if row.live or row.first_published_at is not None:
            return False
        if _screen_only.get():
            return True
        return (
            TaskState.objects.filter(
                workflow_state__base_content_type=row.get_base_content_type(),
                workflow_state__object_id=str(row.pk),
            )
            .exclude(pk=task_state.pk)
            .exists()
        )
