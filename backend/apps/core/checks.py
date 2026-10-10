"""System checks for apps.core."""

from django.core.checks import Error, register


@register()
def check_default_mailer(app_configs, **kwargs):
    """Build MAILERS["default"] (todo 364) so a bad backend path, an option
    the backend does not take, or an incompatible combination (use_tls with
    use_ssl) fails `manage.py check` and the deploy, instead of every send.
    Building the backend opens no connection.

    An SMTP backend that loses its login to a legacy
    ``get_connection(username=None, password=None)`` call is refused too
    (todo 454). Django merges those kwargs over the mailer's OPTIONS, and
    Wagtail's admin mail makes that call. mail_config keeps the credentials
    only for Django's own SMTP backend, so an SMTP subclass set through
    EMAIL_BACKEND would send without logging in. The check rebuilds the
    backend the way that merge would and compares the credentials."""
    from django.conf import settings
    from django.core import mail
    from django.core.mail.backends.smtp import EmailBackend as SMTPEmailBackend

    try:
        backend = mail.mailers["default"]
        if not isinstance(backend, SMTPEmailBackend):
            return []
        # What MailersHandler.create_connection builds for that legacy call.
        options = settings.MAILERS["default"].get("OPTIONS", {})
        merged = type(backend)(
            alias="default", **{**options, "username": None, "password": None}
        )
    except Exception as exc:
        return [
            Error(
                f"MAILERS['default'] cannot be built: {exc}",
                hint="Check EMAIL_BACKEND and the EMAIL_* variables.",
                id="core.E364",
            )
        ]
    if (merged.username, merged.password) != (backend.username, backend.password):
        return [
            Error(
                f"MAILERS['default'] uses {type(backend).__module__}."
                f"{type(backend).__qualname__}, an SMTP backend that loses its "
                "credentials to a get_connection(username=None, password=None) "
                "call.",
                hint=(
                    "Set EMAIL_BACKEND to django.core.mail.backends.smtp."
                    "EmailBackend (mail_config keeps its credentials)."
                ),
                id="core.E364",
            )
        ]
    return []
