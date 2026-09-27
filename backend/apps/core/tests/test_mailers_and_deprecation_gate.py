"""Todo 364: EMAIL_* migrated to MAILERS, and RemovedInDjango70Warning is a
real gate (pytest.ini `error::`), not just a visible log line."""

import warnings

import pytest
from apps.core.checks import check_default_mailer
from apps.core.mail_config import (
    CONFIGURED_SMTP_BACKEND,
    DJANGO_SMTP_BACKEND,
    build_default_mailer,
)
from django.conf import DEPRECATED_EMAIL_SETTINGS, settings
from django.core import mail
from django.test import override_settings
from django.utils.deprecation import RemovedInDjango70Warning

SMTP_ENV = dict(
    host="smtp.example.com",
    port=2525,
    use_tls=True,
    use_ssl=False,
    username="relay-user",
    password="relay-pass",  # pragma: allowlist secret
    timeout=30,
)


def test_a_first_party_removed_in_django70_warning_fails_the_run():
    # Raised, not merely shown: pytest.ini promotes the class to an error.
    with pytest.raises(RemovedInDjango70Warning):
        warnings.warn("first-party use of a removed API", RemovedInDjango70Warning)


def test_settings_define_mailers_and_no_deprecated_email_setting():
    assert "default" in settings.MAILERS
    for name in DEPRECATED_EMAIL_SETTINGS:
        assert not settings.is_overridden(name), name


def test_sending_uses_the_default_mailer_without_a_warning():
    # The test runner swaps every mailer for locmem; a send must go through
    # it with no deprecation (the gate above would turn one into an error).
    mail.send_mail("s", "b", None, ["to@example.com"])
    assert len(mail.outbox) == 1


def test_django_smtp_becomes_the_credential_keeping_backend():
    mailer = build_default_mailer(DJANGO_SMTP_BACKEND, **SMTP_ENV)
    assert mailer["BACKEND"] == CONFIGURED_SMTP_BACKEND
    assert mailer["OPTIONS"]["host"] == "smtp.example.com"
    assert mailer["OPTIONS"]["configured_username"] == "relay-user"


def test_another_backend_gets_the_options_rather_than_losing_the_host():
    # Not one of Django's connectionless backends: it keeps the options, so
    # a mismatch fails core.E364 instead of falling back to localhost:25.
    mailer = build_default_mailer("myproject.mail.SmtpWithLogging", **SMTP_ENV)
    assert mailer["BACKEND"] == "myproject.mail.SmtpWithLogging"
    assert mailer["OPTIONS"]["host"] == "smtp.example.com"
    assert mailer["OPTIONS"]["username"] == "relay-user"


def test_console_backend_gets_no_options():
    backend = "django.core.mail.backends.console.EmailBackend"
    assert build_default_mailer(backend, **SMTP_ENV) == {
        "BACKEND": backend,
        "OPTIONS": {},
    }


def _smtp_mailers(**overrides):
    return {
        "default": build_default_mailer(
            DJANGO_SMTP_BACKEND, **{**SMTP_ENV, **overrides}
        )
    }


def test_a_legacy_none_credential_override_keeps_the_configured_login():
    """Wagtail's admin send_mail calls get_connection(username=None,
    password=None); Django merges those OVER the mailer's OPTIONS. With
    plain options the SMTP backend would never log in (review round 1)."""
    with override_settings(MAILERS=_smtp_mailers()):
        with warnings.catch_warnings():
            # get_connection() itself is deprecated; that is Wagtail's call.
            warnings.simplefilter("ignore", RemovedInDjango70Warning)
            backend = mail.get_connection(username=None, password=None)
        assert backend.username == "relay-user"
        assert backend.password == "relay-pass"  # pragma: allowlist secret

        # An explicit credential still wins.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RemovedInDjango70Warning)
            backend = mail.get_connection(username="other", password="x")
        assert backend.username == "other"


def test_the_system_check_passes_for_a_buildable_mailer():
    with override_settings(MAILERS=_smtp_mailers()):
        assert check_default_mailer(None) == []


def test_the_system_check_fails_an_unbuildable_mailer():
    # use_tls with use_ssl is refused by Django's SMTP backend; before the
    # check it surfaced only at the first send, inside an except-and-log.
    with override_settings(MAILERS=_smtp_mailers(use_ssl=True)):
        [error] = check_default_mailer(None)
    assert error.id == "core.E364"
