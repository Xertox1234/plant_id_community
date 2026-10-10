"""System checks for apps.core."""

from django.core.checks import Error, register

# What get_connection(username=None, password=None) merges over the
# mailer's OPTIONS (django.core.mail.handler.MailersHandler.create_connection).
_LEGACY_OVERRIDES = {"username": None, "password": None}


def _logs_in(backend) -> bool:
    # SMTP EmailBackend.open() logs in only when both are truthy.
    return bool(backend.username and backend.password)


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
    backend the way that merge would, and fails only when the configured
    backend logs in and the rebuild does not keep that login: a no-auth
    relay (empty credentials) has no login to lose (todo 537)."""
    from django.conf import settings
    from django.core import mail
    from django.core.mail.backends.smtp import EmailBackend as SMTPEmailBackend

    try:
        backend = mail.mailers["default"]
    except Exception as exc:
        return [
            Error(
                f"MAILERS['default'] cannot be built: {exc}",
                hint="Check EMAIL_BACKEND and the EMAIL_* variables.",
                id="core.E364",
            )
        ]
    if not isinstance(backend, SMTPEmailBackend) or not _logs_in(backend):
        return []
    backend_name = f"{type(backend).__module__}.{type(backend).__qualname__}"
    try:
        # The same kwargs MailersHandler.create_connection passes for that
        # legacy call, _ignore_unknown_kwargs included (todo 537).
        options = settings.MAILERS["default"].get("OPTIONS", {})
        merged = type(backend)(
            alias="default",
            **{
                **options,
                **_LEGACY_OVERRIDES,
                "_ignore_unknown_kwargs": set(_LEGACY_OVERRIDES),
            },
        )
    except Exception as exc:
        return [
            Error(
                f"MAILERS['default'] builds, but {backend_name} cannot be "
                "rebuilt for a get_connection(username=None, password=None) "
                f"call: {exc}",
                hint=(
                    "Wagtail's admin mail makes that call. Set EMAIL_BACKEND to "
                    "django.core.mail.backends.smtp.EmailBackend (mail_config "
                    "keeps its credentials)."
                ),
                id="core.E364",
            )
        ]
    if (merged.username, merged.password) != (backend.username, backend.password):
        return [
            Error(
                f"MAILERS['default'] uses {backend_name}, an SMTP backend that "
                "loses its credentials to a get_connection(username=None, "
                "password=None) call.",
                hint=(
                    "Set EMAIL_BACKEND to django.core.mail.backends.smtp."
                    "EmailBackend (mail_config keeps its credentials)."
                ),
                id="core.E364",
            )
        ]
    return []
