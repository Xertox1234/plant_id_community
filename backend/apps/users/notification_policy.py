"""Account-wide notification switches (todo 620; docs/notifications-policy.md).

``User.email_notifications`` and ``User.forum_notifications`` are the master
switches shown on web Settings and the mobile profile. They sit above the
forum's per-event matrix and digest choice and are never overwritten by them:

- ``email_notifications`` off: no optional email at all, the forum digest
  included. Security email (verification, password reset, security alerts)
  is exempt. The blog newsletter is a separate, double-opt-in consent and is
  not gated by it.
- ``forum_notifications`` off: no forum push and no forum email.

Neither switch opens an address nobody proved: optional forum email, the
digest included, goes only to an account that verified its current address
(``email_verification``; audit 2026-11-24 F211).

``EmailService._should_send_email`` applies the same rule to every email it
sends; the forum digest is sent by the wagtail_forum package, which asks
``digest_recipient_filter`` through ``WAGTAILFORUM_DIGEST_RECIPIENT_FILTER``.
"""

from django.db.models import Q

from .email_verification import verified_email_q


def digest_recipient_filter() -> Q:
    """``WAGTAILFORUM_DIGEST_RECIPIENT_FILTER``'s callable: the accounts the
    forum digest may be sent to."""
    return Q(email_notifications=True, forum_notifications=True) & verified_email_q()
