"""Todo 364: EMAIL_* migrated to MAILERS, and RemovedInDjango70Warning is a
real gate (pytest.ini `error::`), not just a visible log line."""

import warnings

import pytest
from apps.core.checks import check_default_mailer
from apps.core.mail_backends import ConfiguredSMTPBackend
from apps.core.mail_config import (
    CONFIGURED_SMTP_BACKEND,
    DJANGO_SMTP_BACKEND,
    build_default_mailer,
)
from django.conf import DEPRECATED_EMAIL_SETTINGS, settings
from django.core import mail
from django.core.mail.backends import smtp
from django.core.mail.backends.base import BaseEmailBackend
from django.test import override_settings
from django.utils.deprecation import RemovedInDjango70Warning


class LoggingSMTPBackend(smtp.EmailBackend):
    """A custom SMTP subclass set through EMAIL_BACKEND (todo 454)."""


class ConfiguredLoggingSMTPBackend(ConfiguredSMTPBackend):
    """The supported way to customise SMTP: subclass the credential keeper."""


class ApiMailBackend(BaseEmailBackend):
    """A non-SMTP backend that takes the connection options (an HTTP API)."""

    def __init__(
        self,
        *,
        host=None,
        port=None,
        use_tls=None,
        use_ssl=None,
        timeout=None,
        username=None,
        password=None,
        **kwargs,
    ):
        super().__init__(**kwargs)

    def send_messages(self, email_messages):
        return len(email_messages)


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


def _mailers_for(backend):
    return {"default": build_default_mailer(backend, **SMTP_ENV)}


def test_the_system_check_fails_an_smtp_subclass_that_would_lose_its_login():
    """Todo 454: mail_config wraps only Django's own SMTP backend, so a
    subclass gets plain username/password OPTIONS, and Wagtail's
    get_connection(username=None, password=None) nulls them out."""
    with override_settings(MAILERS=_mailers_for(f"{__name__}.LoggingSMTPBackend")):
        # The failure mode the check refuses, shown for real.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RemovedInDjango70Warning)
            backend = mail.get_connection(username=None, password=None)
        assert backend.username is None
        [error] = check_default_mailer(None)
    assert error.id == "core.E364"
    assert "LoggingSMTPBackend" in error.msg


def test_the_system_check_fails_a_configured_smtp_subclass_set_through_the_env():
    # EMAIL_BACKEND pointing at ConfiguredSMTPBackend (or a subclass) is not
    # swapped by mail_config, so it gets plain username/password OPTIONS and
    # loses them the same way: the check tests the credentials, not the class.
    path = f"{__name__}.ConfiguredLoggingSMTPBackend"
    with override_settings(MAILERS=_mailers_for(path)):
        [error] = check_default_mailer(None)
    assert error.id == "core.E364"


def test_the_system_check_passes_vanilla_smtp_without_credentials():
    with override_settings(MAILERS=_smtp_mailers(username="", password="")):
        assert check_default_mailer(None) == []


def test_the_system_check_passes_an_smtp_subclass_on_a_no_auth_relay():
    """Todo 537: empty credentials rebuild as None, but SMTP open() logs in
    only when both are truthy, so a no-auth relay has no login to lose. The
    check must not fail `manage.py check` and the deploy for it."""
    mailers = {
        "default": build_default_mailer(
            f"{__name__}.LoggingSMTPBackend",
            **{**SMTP_ENV, "username": "", "password": ""},
        )
    }
    with override_settings(MAILERS=mailers):
        assert check_default_mailer(None) == []


class LoginRequiredSMTPBackend(smtp.EmailBackend):
    """An SMTP subclass that refuses to be built without a login."""

    def __init__(self, *, username=None, password=None, **kwargs):
        if username is None:
            raise ValueError("this relay needs a login")
        super().__init__(username=username, password=password, **kwargs)


def test_the_system_check_names_a_backend_that_cannot_take_the_legacy_call():
    """Todo 537: the mailer itself builds, so "cannot be built" would send
    the reader to EMAIL_BACKEND's path and variables for the wrong reason."""
    path = f"{__name__}.LoginRequiredSMTPBackend"
    with override_settings(MAILERS=_mailers_for(path)):
        [error] = check_default_mailer(None)
    assert error.id == "core.E364"
    assert "cannot be built" not in error.msg
    assert "cannot be rebuilt for a get_connection(" in error.msg
    assert "this relay needs a login" in error.msg


def test_the_system_check_accepts_a_configured_smtp_subclass():
    options = _smtp_mailers()["default"]["OPTIONS"]
    mailers = {
        "default": {
            "BACKEND": f"{__name__}.ConfiguredLoggingSMTPBackend",
            "OPTIONS": options,
        }
    }
    with override_settings(MAILERS=mailers):
        assert check_default_mailer(None) == []


def test_the_system_check_accepts_a_non_smtp_backend():
    with override_settings(MAILERS=_mailers_for(f"{__name__}.ApiMailBackend")):
        assert check_default_mailer(None) == []
