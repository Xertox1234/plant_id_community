"""Fan-out helper for persisted in-app notifications (todo 253 slice 1, audit C2).

Host-agnostic: callers (currently ``apps/forum_host/notifications.py``) decide
WHO gets notified and WHEN to enqueue delivery (push/email); this module only
persists the rows. Call it inside the ambient transaction so a Notification
never survives a rolled-back publish; deferring delivery to
``transaction.on_commit`` is the caller's responsibility.
"""

from typing import Iterable, Optional

from django.contrib.auth.models import AbstractBaseUser

from .models import Notification, Post, Topic


def create_notifications(
    *,
    recipients: Iterable[Optional[AbstractBaseUser]],
    verb: str,
    actor: Optional[AbstractBaseUser] = None,
    topic: Optional[Topic] = None,
    post: Optional[Post] = None,
) -> list[Notification]:
    """Create one Notification per recipient, idempotently.

    Skips any recipient equal to `actor` (no self-notifications) — a defensive
    check independent of any self-notify guard a caller may already apply, so
    the helper stays safe for callers that fan out to a wider audience (e.g. a
    later slice's subscriber list) without re-deriving this rule themselves.

    Idempotent per (recipient, verb, post) via ``bulk_create(ignore_conflicts=
    True)`` against the model's unique constraint — firing the same event
    twice (e.g. a retried signal) does not duplicate a recipient's row. Returns
    the attempted (not necessarily persisted) Notification instances — with
    ``ignore_conflicts=True``, Django cannot map ON CONFLICT DO NOTHING rows
    back to their inputs, so it leaves ``.pk`` unset on EVERY returned
    instance, not just skipped ones. A caller that needs a real pk (or needs
    to know which rows were newly inserted) must re-fetch from the DB instead
    of relying on this return value.
    """
    to_create = [
        Notification(
            recipient=recipient, actor=actor, verb=verb, topic=topic, post=post
        )
        for recipient in recipients
        if recipient is not None and (actor is None or recipient.pk != actor.pk)
    ]
    if not to_create:
        return []
    return Notification.objects.bulk_create(to_create, ignore_conflicts=True)
