"""System checks for apps.core."""

from django.core.checks import Error, register


@register()
def check_default_mailer(app_configs, **kwargs):
    """Build MAILERS["default"] (todo 364) so a bad backend path, an option
    the backend does not take, or an incompatible combination (use_tls with
    use_ssl) fails `manage.py check` and the deploy, instead of every send.
    Building the backend opens no connection."""
    from django.core import mail

    try:
        mail.mailers["default"]
    except Exception as exc:
        return [
            Error(
                f"MAILERS['default'] cannot be built: {exc}",
                hint="Check EMAIL_BACKEND and the EMAIL_* variables.",
                id="core.E364",
            )
        ]
    return []
