"""Todo 452: the django-taggit and Wagtail admin mail Django 7.0 shims.

pytest.ini turns RemovedInDjango70Warning into an error, with no third-party
exemption, so each behaviour test below also proves its call site is quiet.
The "still needed" tests fail loudly when an upgrade fixes a call site
upstream (delete that shim) or moves past a version ceiling (re-check, bump).
"""

import logging
import warnings

import pytest
from apps.core import django70_compat
from django.contrib.auth import get_user_model
from django.core import mail
from django.db import connection
from django.utils.deprecation import RemovedInDjango70Warning
from taggit.managers import ExtraJoinRestriction
from wagtail.admin import mail as wagtail_mail


def _compiler():
    return get_user_model().objects.all().query.get_compiler(connection=connection)


# --- the shims are installed, and still needed -------------------------------


def test_both_shims_are_applied_at_startup():
    assert django70_compat.applied() == {"taggit": True, "wagtail": True}
    assert ExtraJoinRestriction.as_sql is django70_compat._extra_join_restriction_as_sql
    assert wagtail_mail.get_connection is django70_compat.mailers_get_connection


def test_installing_twice_keeps_the_upstream_originals():
    django70_compat.install()
    assert (
        django70_compat.ORIGINAL_TAGGIT_AS_SQL
        is not django70_compat._extra_join_restriction_as_sql
    )
    assert (
        django70_compat.ORIGINAL_WAGTAIL_GET_CONNECTION
        is not django70_compat.mailers_get_connection
    )
    assert django70_compat.applied() == {"taggit": True, "wagtail": True}


def test_taggit_still_needs_its_shim():
    assert django70_compat.taggit_source_needs_shim(
        django70_compat.ORIGINAL_TAGGIT_AS_SQL
    ), (
        "django-taggit's ExtraJoinRestriction.as_sql no longer calls "
        "quote_name_unless_alias(): the upstream fix shipped. Delete the taggit "
        "shim from apps/core/django70_compat.py and its tests here (todo 452)."
    )


def test_taggit_is_within_the_shim_version_ceiling():
    assert django70_compat.taggit_version_within_ceiling(), (
        "django-taggit is newer than TAGGIT_SHIM_MAX_VERSION, so the shim is "
        "off. Check whether the new release still calls "
        "quote_name_unless_alias(): if so, bump the ceiling; if not, delete "
        "the shim (todo 452)."
    )


def test_wagtail_still_needs_its_shim():
    assert django70_compat.wagtail_source_needs_shim(wagtail_mail), (
        "wagtail/admin/mail.py no longer calls get_connection(): the upstream "
        "fix shipped. Delete the Wagtail shim from apps/core/django70_compat.py "
        "and its tests here (todo 452)."
    )


def test_wagtail_is_within_the_shim_version_ceiling():
    assert django70_compat.wagtail_version_within_ceiling(), (
        "Wagtail is newer than WAGTAIL_SHIM_MAX_VERSION, so the shim is off. "
        "Check whether wagtail/admin/mail.py still calls get_connection(): if "
        "so, bump the ceiling; if not, delete the shim (todo 452)."
    )


def test_the_upstream_taggit_call_would_trip_the_gate():
    restriction = ExtraJoinRestriction("taggit_taggeditem", "content_type_id", [7])
    with pytest.raises(RemovedInDjango70Warning, match="quote_name_unless_alias"):
        django70_compat.ORIGINAL_TAGGIT_AS_SQL(restriction, _compiler(), connection)


def test_the_upstream_wagtail_call_would_trip_the_gate():
    with pytest.raises(RemovedInDjango70Warning, match="get_connection"):
        django70_compat.ORIGINAL_WAGTAIL_GET_CONNECTION()


# --- django-taggit -----------------------------------------------------------


@pytest.mark.parametrize("content_types", [[7], [7, 8, 9]])
def test_taggit_shim_emits_the_same_sql_without_a_warning(content_types):
    restriction = ExtraJoinRestriction(
        "taggit_taggeditem", "content_type_id", content_types
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RemovedInDjango70Warning)
        expected = django70_compat.ORIGINAL_TAGGIT_AS_SQL(
            restriction, _compiler(), connection
        )
    with warnings.catch_warnings():
        warnings.simplefilter("error", RemovedInDjango70Warning)
        assert restriction.as_sql(_compiler(), connection) == expected
    qn = connection.ops.quote_name
    assert expected[0].startswith(f"{qn('taggit_taggeditem')}.{qn('content_type_id')}")
    assert expected[1] == content_types


# --- Wagtail admin mail ------------------------------------------------------


def test_wagtail_bare_get_connection_is_the_default_mailer():
    with warnings.catch_warnings():
        warnings.simplefilter("error", RemovedInDjango70Warning)
        conn = wagtail_mail.get_connection()
        legacy = wagtail_mail.get_connection(
            username=None, password=None, fail_silently=None
        )
    assert conn.alias == "default"
    assert legacy.alias == "default"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"fail_silently": True},
        {"username": "someone"},
        {"password": "not-a-real-secret"},  # pragma: allowlist secret
        {"timeout": 5},
    ],
)
def test_wagtail_shim_leaves_any_other_call_to_the_deprecated_function(kwargs):
    with pytest.raises(RemovedInDjango70Warning, match="get_connection"):
        wagtail_mail.get_connection(**kwargs)


def test_wagtail_send_mail_without_a_connection_sends_quietly():
    with warnings.catch_warnings():
        warnings.simplefilter("error", RemovedInDjango70Warning)
        sent = wagtail_mail.send_mail("Subject", "Body", ["to@example.com"])
    assert sent == 1
    assert len(mail.outbox) == 1
    assert mail.outbox[0].extra_headers["Auto-Submitted"] == "auto-generated"


class _ProbeNotifier(wagtail_mail.EmailNotificationMixin, wagtail_mail.Notifier):
    """A Wagtail email notifier, driven through its public __call__ path."""

    notification = "approved"

    def __init__(self, recipient):
        super().__init__((object,))
        self.recipient = recipient

    def get_recipient_users(self, instance, **kwargs):
        return {self.recipient}


@pytest.mark.django_db
def test_wagtail_workflow_notification_emails_send_through_the_mailer(
    monkeypatch, caplog
):
    recipient = get_user_model().objects.create_user(
        username="moderator452",
        email="moderator452@example.com",
        password="not-a-real-secret",  # pragma: allowlist secret
    )
    monkeypatch.setattr(
        wagtail_mail,
        "render_to_string",
        lambda template, context: f"rendered {template}",
    )
    caplog.set_level(logging.ERROR, logger="wagtail.admin")
    with warnings.catch_warnings():
        warnings.simplefilter("error", RemovedInDjango70Warning)
        # OpenedConnection.__exit__ swallows any exception raised while the
        # connection is open, so only the return value and outbox prove a send.
        ok = _ProbeNotifier(recipient)(instance=object())
    assert ok is True
    assert [m.to for m in mail.outbox] == [["moderator452@example.com"]]
    assert not [r for r in caplog.records if r.name == "wagtail.admin"]


def test_unreadable_source_skips_the_shim_instead_of_failing_startup(monkeypatch):
    """Todo 452 review: a bytecode-only install has no source, and
    inspect.getsource raises. The probe answers "not needed" and startup goes
    on."""

    def no_source(obj):
        raise OSError("could not get source code")

    monkeypatch.setattr(django70_compat.inspect, "getsource", no_source)
    assert django70_compat.taggit_source_needs_shim(object()) is False
    assert django70_compat.wagtail_source_needs_shim(object()) is False


def test_the_wagtail_probe_matches_only_a_bare_call():
    """Todo 452 review: mailers.get_connection( or my_get_connection( is not
    the deprecated call, so a fixed upstream would not keep the shim."""
    probe = django70_compat.WAGTAIL_DEPRECATED_CALL
    assert probe.search("    connection = get_connection()")
    assert probe.search("x = get_connection(fail_silently=True)")
    assert not probe.search("connection = mail.mailers.get_connection()")
    assert not probe.search("connection = my_get_connection()")


def test_the_shims_apply_only_from_django_6_1_up_to_7_0(monkeypatch):
    """Todo 452 review: before 6.1 quote_name_unless_alias() left aliases
    unquoted, so the taggit shim would change the SQL there."""
    for version, expected in (
        ((6, 0, 3), False),
        ((6, 1, 1), True),
        ((7, 0, 0), False),
    ):
        monkeypatch.setattr(django70_compat.django, "VERSION", version + ("final", 0))
        assert django70_compat._django_needs_shims() is expected, version
