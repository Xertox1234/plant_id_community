"""Mail backends (todo 364)."""

from django.core.mail.backends.smtp import EmailBackend


class ConfiguredSMTPBackend(EmailBackend):
    """Django's SMTP backend, keeping the configured credentials.

    Under MAILERS, Django merges a legacy ``get_connection(**kwargs)`` call's
    kwargs OVER the mailer's OPTIONS. Wagtail's ``admin/mail.py`` ``send_mail``
    (CMS comment and moderation notifications) calls
    ``get_connection(username=None, password=None)``, so plain OPTIONS
    credentials become None, the backend never logs in, and an authenticated
    relay refuses the mail. Here a None username/password means "use the
    configured one"; an explicit value still wins.
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
