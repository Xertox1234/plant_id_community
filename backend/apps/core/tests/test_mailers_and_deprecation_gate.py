"""Todo 364: EMAIL_* migrated to MAILERS, and RemovedInDjango70Warning is a
real gate (pytest.ini `error::`), not just a visible log line."""

import importlib
import warnings

import pytest
from django.conf import DEPRECATED_EMAIL_SETTINGS, settings
from django.core import mail
from django.utils.deprecation import RemovedInDjango70Warning


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


def _mailers_for(monkeypatch, backend):
    """Re-evaluate settings.py's MAILERS for an EMAIL_BACKEND value."""
    monkeypatch.setenv("EMAIL_BACKEND", backend)
    monkeypatch.setenv("EMAIL_HOST", "smtp.example.com")
    monkeypatch.setenv("EMAIL_PORT", "2525")
    import plant_community_backend.settings as project_settings

    return importlib.reload(project_settings).MAILERS["default"]


@pytest.fixture
def reload_settings_back(monkeypatch):
    yield
    # Restore the real environment BEFORE reloading: this fixture tears down
    # ahead of monkeypatch, so without undo() the reload re-reads the patch.
    monkeypatch.undo()
    import plant_community_backend.settings as project_settings

    importlib.reload(project_settings)


def test_smtp_backend_gets_the_connection_options(monkeypatch, reload_settings_back):
    mailer = _mailers_for(monkeypatch, "django.core.mail.backends.smtp.EmailBackend")
    assert mailer["OPTIONS"]["host"] == "smtp.example.com"
    assert mailer["OPTIONS"]["port"] == 2525


def test_an_smtp_subclass_also_gets_them_rather_than_losing_the_host(
    monkeypatch, reload_settings_back
):
    # A backend that is not one of Django's connection-less ones keeps the
    # options: a mismatch must fail loudly, not fall back to localhost:25.
    mailer = _mailers_for(monkeypatch, "myproject.mail.SmtpWithLogging")
    assert mailer["OPTIONS"]["host"] == "smtp.example.com"


def test_console_backend_gets_no_options(monkeypatch, reload_settings_back):
    # A mailer given an option its backend does not take raises.
    mailer = _mailers_for(monkeypatch, "django.core.mail.backends.console.EmailBackend")
    assert mailer["OPTIONS"] == {}
