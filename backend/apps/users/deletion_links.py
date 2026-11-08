"""The emailed account-deletion link (Plan B task 6).

A link carries ``signing.dumps({"u": pk, "n": nonce})``. The nonce also sits in
the cache under ``account-delete:<pk>`` for the link's lifetime, so a link
works once (confirming deletes the nonce) and only the newest link works (a
new request replaces the nonce). The link is built in the Celery worker, so
the token never travels through the broker.
"""

from __future__ import annotations

import logging
import secrets
from typing import TYPE_CHECKING
from urllib.parse import urlencode

from django.conf import settings
from django.core import signing
from django.core.cache import DEFAULT_CACHE_ALIAS, cache, caches
from django.template.loader import render_to_string
from django.utils.crypto import constant_time_compare

from .constants import (
    ACCOUNT_DELETE_LINK_CACHE_PREFIX,
    ACCOUNT_DELETE_LINK_NONCE_BYTES,
    ACCOUNT_DELETE_LINK_PATH,
    ACCOUNT_DELETE_LINK_SALT,
    ACCOUNT_DELETE_LINK_SUBJECT,
    ACCOUNT_DELETE_LINK_TTL_SECONDS,
)

if TYPE_CHECKING:
    from .models import User

logger = logging.getLogger(__name__)


class DeletionLinkInvalid(Exception):
    """Forged, expired, already used or superseded. One exception on purpose:
    the caller must not tell a stranger which."""


def _cache_key(user_pk: int) -> str:
    return f"{ACCOUNT_DELETE_LINK_CACHE_PREFIX}{user_pk}"


def make_deletion_link(user: User) -> str:
    """Store a fresh nonce for ``user`` (replacing any earlier one) and return
    the web confirm URL that carries it."""
    nonce = secrets.token_urlsafe(ACCOUNT_DELETE_LINK_NONCE_BYTES)
    cache.set(_cache_key(user.pk), nonce, timeout=ACCOUNT_DELETE_LINK_TTL_SECONDS)
    token = signing.dumps({"u": user.pk, "n": nonce}, salt=ACCOUNT_DELETE_LINK_SALT)
    base = (getattr(settings, "SITE_URL", "") or "").rstrip("/")
    return f"{base}{ACCOUNT_DELETE_LINK_PATH}?{urlencode({'token': token})}"


def consume_deletion_token(token: object) -> int:
    """Return the user pk ``token`` names and use it up.

    Checks the signature, the age and the stored nonce. The nonce is deleted
    before the caller acts, and only the caller whose delete removed it wins,
    so two concurrent confirms cannot both pass. Raises ``DeletionLinkInvalid``.
    """
    if not isinstance(token, str) or not token:
        raise DeletionLinkInvalid()
    try:
        payload = signing.loads(
            token,
            salt=ACCOUNT_DELETE_LINK_SALT,
            max_age=ACCOUNT_DELETE_LINK_TTL_SECONDS,
        )
    except signing.BadSignature as exc:  # SignatureExpired included
        raise DeletionLinkInvalid() from exc
    if not isinstance(payload, dict):
        raise DeletionLinkInvalid()
    user_pk, nonce = payload.get("u"), payload.get("n")
    if not isinstance(user_pk, int) or not isinstance(nonce, str):
        raise DeletionLinkInvalid()
    if not _take_nonce(_cache_key(user_pk), nonce):
        raise DeletionLinkInvalid()
    return user_pk


# Delete KEYS[1] only if it still holds ARGV[1], in one step on the server.
_COMPARE_AND_DELETE = (
    "if redis.call('GET', KEYS[1]) == ARGV[1] then "
    "return redis.call('DEL', KEYS[1]) else return 0 end"
)


def _take_nonce(key: str, nonce: str) -> bool:
    """Delete the stored nonce if it equals ``nonce``; True if this call did.

    On Redis (every deployed environment, and the test run) the compare and
    the delete are one Lua script, so of two racing confirms only one wins,
    and a superseded link can never delete, or win against, the current
    nonce. The value is compared in django-redis's serialised form, which is
    exactly what ``cache.set`` stored. Any other backend (a local in-memory
    cache) gets the non-atomic get, compare and delete.
    """
    from django_redis.cache import RedisCache
    from redis.exceptions import RedisError

    backend = caches[DEFAULT_CACHE_ALIAS]
    if isinstance(backend, RedisCache):
        client = backend.client
        try:
            deleted = client.get_client(write=True).eval(
                _COMPARE_AND_DELETE,
                1,
                client.make_key(key),
                client.encode(nonce),
            )
        except RedisError as exc:
            # Fail closed, like a cache read that IGNORE_EXCEPTIONS turns
            # into a miss: the link reads as invalid.
            logger.error(
                f"[ACCOUNT DELETE] Could not check a deletion link nonce: "
                f"{type(exc).__name__}"
            )
            return False
        return bool(deleted)

    stored = backend.get(key)
    if not isinstance(stored, str) or not constant_time_compare(stored, nonce):
        return False
    return bool(backend.delete(key))


def deliver_deletion_link(user: User) -> bool:
    """Build a link and send it to ``user``. Called by the Celery task only.
    False on a failed send or render, so the task retries."""
    from apps.core.services.email_service import EmailService

    service = EmailService()
    context = {"site_name": service.site_name, "confirm_url": make_deletion_link(user)}
    try:
        text = render_to_string("emails/account_delete_confirm.txt", context)
        html = render_to_string("emails/account_delete_confirm.html", context)
    except Exception as exc:
        # The type only: the context holds the signed link.
        logger.error(
            f"[ACCOUNT DELETE] Could not render the deletion link for account "
            f"{user.pk}: {type(exc).__name__}"
        )
        return False
    return service.send_transactional_email(
        recipient=user,
        subject=ACCOUNT_DELETE_LINK_SUBJECT,
        message=text,
        html_message=html,
    )
