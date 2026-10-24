"""Record who changed a garden object in its audit trail (todo 606).

``AuditlogMiddleware`` cannot do this: it runs before DRF authenticates the
JWT, so ``request.user`` is anonymous there. This mixin sets the actor after
``initial()`` has authenticated the request, so every LogEntry a garden view
writes carries the user as ``actor``.

That is what lets the account-deletion purge in ``garden_calendar/auditlog.py``
find rows for garden objects the user deleted earlier: the object is gone, so
ownership can no longer match its rows, but the actor still does. No remote
address is recorded.

Why not auditlog's own ``set_actor`` (todo 631): auditlog 3.4.1 connects a
``pre_save`` receiver per call with ``dispatch_uid=("set_actor", time.time())``
and disconnects it by that uid on exit. Two threaded requests that start in
the same clock tick share one uid, so one receiver: the first to finish
disconnects it, and the other's later LogEntries get a NULL actor and escape
the purge. Here one receiver is connected once, for the process
(``connect_actor_receiver``, called from ``garden_calendar/auditlog.py``), and
the actor lives in a ``ContextVar``, which is per thread and per request.
"""

from contextlib import ExitStack, contextmanager
from contextvars import ContextVar

from auditlog import get_logentry_model
from django.contrib.auth import get_user_model
from django.db.models.signals import pre_save

_garden_actor: ContextVar = ContextVar("garden_audit_actor", default=None)

_RECEIVER_UID = "garden_calendar.audit_actor.attach_actor"


def attach_actor(sender, instance, **kwargs):
    """``pre_save`` on LogEntry: name the current garden actor, if any.

    Leaves an actor someone else already set alone, as auditlog's own
    receiver does."""
    actor = _garden_actor.get()
    if actor is None or instance.actor_id is not None:
        return
    if isinstance(actor, get_user_model()):
        instance.actor = actor
        instance.actor_email = getattr(actor, "email", None)


def connect_actor_receiver():
    """Connect ``attach_actor`` once; the fixed uid makes a repeat a no-op."""
    pre_save.connect(
        attach_actor, sender=get_logentry_model(), dispatch_uid=_RECEIVER_UID
    )


@contextmanager
def garden_audit_actor(user):
    """Every LogEntry saved inside the block, in this context, names ``user``."""
    token = _garden_actor.set(user)
    try:
        yield
    finally:
        _garden_actor.reset(token)


class AuditActorMixin:
    """Sets the authenticated user as the auditlog actor for the request."""

    def dispatch(self, request, *args, **kwargs):
        # The stack closes however dispatch ends, an unhandled exception
        # included, so the request's actor never outlives it.
        with ExitStack() as stack:
            self._audit_actor_stack = stack
            return super().dispatch(request, *args, **kwargs)  # type: ignore[misc]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)  # type: ignore[misc]
        user = request.user
        if user is not None and user.is_authenticated:
            self._audit_actor_stack.enter_context(garden_audit_actor(user))
