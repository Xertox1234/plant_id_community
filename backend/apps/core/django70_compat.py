"""Shims for third-party calls to APIs that Django 7.0 removes (todo 452).

pytest.ini turns every ``RemovedInDjango70Warning`` into an error (todo 364).
Two third-party frames still raise one, and neither has an upstream fix yet,
so this module patches each call site narrowly instead of exempting it:

- django-taggit: ``taggit.managers.ExtraJoinRestriction.as_sql`` calls
  ``compiler.quote_name_unless_alias()`` (Django ticket #36795). The shim
  calls ``compiler.quote_name()``, which is what the deprecated method
  delegates to in Django 6.1, so the SQL is byte-identical.
- Wagtail: ``wagtail/admin/mail.py`` sends moderation and workflow
  notifications through ``get_connection()``. The shim rebinds that module's
  ``get_connection`` name so the bare call returns ``mailers.default`` (the
  ``MAILERS["default"]`` connection). Any other call shape (a backend path,
  real credentials, ``fail_silently=True`` or an unknown option) still goes
  to Django's ``get_connection()``, so the gate keeps failing loudly on it.

Each shim is version-guarded three ways: Django below 7.0, the package at or
below the newest version known to need it, and the package's own source still
calling the deprecated API. When a guard is false, the shim is not applied.
``apps/core/tests/test_django70_compat.py`` fails when an upgrade makes a shim
unnecessary (delete it then) or moves past the ceiling (re-check, then bump).
"""

from __future__ import annotations

import inspect
import logging
import re

import django

logger = logging.getLogger(__name__)

# The newest release of each package that is known to need its shim. Bump a
# ceiling only after confirming the new release still calls the deprecated API.
TAGGIT_SHIM_MAX_VERSION = (6, 1, 0)
WAGTAIL_SHIM_MAX_VERSION = (8, 0)

TAGGIT_DEPRECATED_CALL = "quote_name_unless_alias"
# A bare call only: mailers.get_connection( or a name ending in it is not the
# deprecated function.
WAGTAIL_DEPRECATED_CALL = re.compile(r"(?<![.\w])get_connection\(")

# The upstream objects as found before patching, so the tests can inspect the
# original source rather than the shim. Filled by install().
ORIGINAL_TAGGIT_AS_SQL = None
ORIGINAL_WAGTAIL_GET_CONNECTION = None

_applied: dict[str, bool] = {"taggit": False, "wagtail": False}


def _django_needs_shims() -> bool:
    # From 6.1 the deprecated quote_name_unless_alias() only delegates to
    # quote_name(), which is what makes the taggit shim's SQL identical.
    return (6, 1) <= django.VERSION[:2] < (7, 0)


def _source(obj) -> str:
    """The object's source, or "" when it cannot be read (a bytecode-only
    install): a compat probe must never stop the app from starting."""
    try:
        return inspect.getsource(obj)
    except (OSError, TypeError):
        logger.warning("[COMPAT] django70_compat: no source for %r", obj)
        return ""


def _version_tuple(version, length: int) -> tuple:
    return tuple(int(part) for part in version[:length])


def taggit_source_needs_shim(as_sql) -> bool:
    """True when taggit's own ``as_sql`` still calls the deprecated method."""
    return TAGGIT_DEPRECATED_CALL in _source(as_sql)


def wagtail_source_needs_shim(module) -> bool:
    """True when Wagtail's admin mail module still calls ``get_connection()``."""
    return bool(WAGTAIL_DEPRECATED_CALL.search(_source(module)))


def taggit_version_within_ceiling() -> bool:
    import taggit

    return _version_tuple(taggit.VERSION, 3) <= TAGGIT_SHIM_MAX_VERSION


def wagtail_version_within_ceiling() -> bool:
    import wagtail

    return _version_tuple(wagtail.VERSION, 2) <= WAGTAIL_SHIM_MAX_VERSION


def _extra_join_restriction_as_sql(self, compiler, connection):
    """``ExtraJoinRestriction.as_sql`` with ``quote_name`` (taggit 6.1.0)."""
    qn = compiler.quote_name
    if len(self.content_types) == 1:
        extra_where = f"{qn(self.alias)}.{qn(self.col)} = %s"
    else:
        extra_where = "{}.{} IN ({})".format(
            qn(self.alias),
            qn(self.col),
            ",".join(["%s"] * len(self.content_types)),
        )
    return extra_where, self.content_types


# The keywords Wagtail's admin mail passes; None or False means "not set".
_WAGTAIL_DEFAULT_MAILER_KWARGS = frozenset({"username", "password", "fail_silently"})


def mailers_get_connection(*args, **kwargs):
    """Wagtail admin mail's ``get_connection``, routed through MAILERS.

    Wagtail calls it bare (``send_emails``, ``send_notification``) or as
    ``get_connection(username=None, password=None, fail_silently=None)``
    (``send_mail`` without a connection). Both mean "the default mailer",
    whose OPTIONS already carry the configured credentials. Any other call
    goes unchanged to Django's deprecated function, which warns.
    """
    from django.core import mail

    if (
        not args
        and set(kwargs) <= _WAGTAIL_DEFAULT_MAILER_KWARGS
        and all(value is None or value is False for value in kwargs.values())
    ):
        return mail.mailers.default
    return mail.get_connection(*args, **kwargs)


def _install_taggit() -> None:
    global ORIGINAL_TAGGIT_AS_SQL
    from taggit.managers import ExtraJoinRestriction

    current = ExtraJoinRestriction.as_sql
    if current is _extra_join_restriction_as_sql:
        return
    ORIGINAL_TAGGIT_AS_SQL = current
    if not (taggit_version_within_ceiling() and taggit_source_needs_shim(current)):
        logger.warning(
            "[COMPAT] django70_compat: taggit shim not applied (version or source changed)"
        )
        return
    ExtraJoinRestriction.as_sql = _extra_join_restriction_as_sql
    _applied["taggit"] = True


def _install_wagtail() -> None:
    global ORIGINAL_WAGTAIL_GET_CONNECTION
    from wagtail.admin import mail as wagtail_mail

    current = getattr(wagtail_mail, "get_connection", None)
    if current is mailers_get_connection:
        return
    ORIGINAL_WAGTAIL_GET_CONNECTION = current
    if not (
        current is not None
        and wagtail_version_within_ceiling()
        and wagtail_source_needs_shim(wagtail_mail)
    ):
        logger.warning(
            "[COMPAT] django70_compat: Wagtail mail shim not applied (version or source changed)"
        )
        return
    wagtail_mail.get_connection = mailers_get_connection
    _applied["wagtail"] = True


def install() -> None:
    """Apply both shims. Idempotent; called from CoreConfig.ready()."""
    if not _django_needs_shims():
        return
    _install_taggit()
    _install_wagtail()


def applied() -> dict[str, bool]:
    return dict(_applied)
