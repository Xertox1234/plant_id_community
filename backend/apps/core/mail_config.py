"""Build MAILERS["default"] from the EMAIL_* environment variables (todo 364).

Imported by settings.py, so it must not import Django or any app code.
"""

from __future__ import annotations

from typing import Any, Dict

DJANGO_SMTP_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
# Django's SMTP backend with the configured credentials kept when a legacy
# get_connection(username=None, password=None) call would null them out.
CONFIGURED_SMTP_BACKEND = "apps.core.mail_backends.ConfiguredSMTPBackend"
# Django's own backends that open no connection: a mailer given an option its
# backend does not take raises, so these get none.
CONNECTIONLESS_EMAIL_BACKENDS = frozenset(
    {
        "django.core.mail.backends.console.EmailBackend",
        "django.core.mail.backends.locmem.EmailBackend",
        "django.core.mail.backends.dummy.EmailBackend",
    }
)


def build_default_mailer(
    backend: str,
    *,
    host: str,
    port: int,
    use_tls: bool,
    use_ssl: bool,
    username: str,
    password: str,
    timeout: int,
) -> Dict[str, Any]:
    """The MAILERS["default"] entry for an EMAIL_BACKEND value.

    Every backend but the connectionless ones gets the SMTP connection
    options, so a backend that cannot take them fails the `core.E364`
    system check at deploy rather than dropping the host and falling back
    to localhost:25. Django's SMTP backend is swapped for
    ConfiguredSMTPBackend (see its docstring).
    """
    if backend in CONNECTIONLESS_EMAIL_BACKENDS:
        return {"BACKEND": backend, "OPTIONS": {}}
    options: Dict[str, Any] = {
        "host": host,
        "port": port,
        "use_tls": use_tls,
        "use_ssl": use_ssl,
        "timeout": timeout,
    }
    if backend == DJANGO_SMTP_BACKEND:
        return {
            "BACKEND": CONFIGURED_SMTP_BACKEND,
            "OPTIONS": {
                **options,
                "configured_username": username,
                "configured_password": password,
            },
        }
    return {
        "BACKEND": backend,
        "OPTIONS": {**options, "username": username, "password": password},
    }
