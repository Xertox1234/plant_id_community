"""Record who changed a garden object in its audit trail (todo 606).

``AuditlogMiddleware`` cannot do this: it runs before DRF authenticates the
JWT, so ``request.user`` is anonymous there. This mixin enters auditlog's
``set_actor`` after ``initial()`` has authenticated the request, so every
LogEntry a garden view writes carries the user as ``actor``.

That is what lets the account-deletion purge in ``garden_calendar/auditlog.py``
find rows for garden objects the user deleted earlier: the object is gone, so
ownership can no longer match its rows, but the actor still does. No remote
address is recorded.
"""

from contextlib import ExitStack

from auditlog.context import set_actor


class AuditActorMixin:
    """Sets the authenticated user as the auditlog actor for the request."""

    def dispatch(self, request, *args, **kwargs):
        # The stack closes however dispatch ends, an unhandled exception
        # included, so the per-request signal receiver never outlives it.
        with ExitStack() as stack:
            self._audit_actor_stack = stack
            return super().dispatch(request, *args, **kwargs)

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        user = request.user
        if user is not None and user.is_authenticated:
            self._audit_actor_stack.enter_context(set_actor(user))
