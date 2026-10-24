"""Mail backends (todo 364)."""

from django.core.mail.backends.smtp import EmailBackend


class SuppressionFilterMixin:
    """Drop suppressed recipients before a backend sends (todo 625).

    The backstop for every send path, including the ones that never ask
    ``email_feedback.is_suppressed`` themselves (the forum digest, the blog
    newsletter, Django's and Wagtail's own mail). Mail carrying
    List-Unsubscribe is optional mail; see ``email_feedback`` for the policy.
    A message left with no recipient is not sent and is not counted.
    """

    def send_messages(self, email_messages):
        from .email_feedback import filter_suppressed_messages

        kept = filter_suppressed_messages(email_messages or [])
        if not kept:
            return 0
        return super().send_messages(kept)  # type: ignore[misc]


class ConfiguredSMTPBackend(SuppressionFilterMixin, EmailBackend):
    """Django's SMTP backend, keeping the configured credentials.

    Under MAILERS, Django merges a legacy ``get_connection(**kwargs)`` call's
    kwargs OVER the mailer's OPTIONS. Wagtail's ``admin/mail.py`` ``send_mail``
    (CMS comment and moderation notifications) calls
    ``get_connection(username=None, password=None)``, so plain OPTIONS
    credentials become None, the backend never logs in, and an authenticated
    relay refuses the mail. Here a None username/password means "use the
    configured one"; an explicit value still wins. Suppressed recipients
    are removed first (``SuppressionFilterMixin``, todo 625).
    """

    def __init__(
        self,
        *,
        configured_username=None,
        configured_password=None,
        username=None,
        password=None,
        **kwargs,
    ):
        super().__init__(
            username=configured_username if username is None else username,
            password=configured_password if password is None else password,
            **kwargs,
        )
