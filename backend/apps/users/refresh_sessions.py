"""Refresh-session rules for ``token_refresh`` (todo 705 M5, audit 2026-11-10).

A refresh session is the chain of refresh tokens that rotation produces from
one sign-in. Two rules end it:

* an absolute cap: ``REFRESH_SESSION_MAX_AGE_SECONDS`` from the sign-in,
  carried through every rotation in ``REFRESH_SESSION_START_CLAIM``
  (``authentication.issue_refresh_token`` writes it);
* reuse: a ROTATED refresh token presented again means two parties hold the
  chain, so every refresh token the account has is blacklisted and everyone
  signs in again. Rotated means ``token_refresh`` blacklisted it while
  issuing its successor (``mark_rotated``, a ``RotatedRefreshToken`` row). A
  token blacklisted any other way (logout, a refused refresh, a revocation
  such as a first provider link) is not reuse: it gets a plain 401.
"""

from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any, Optional

from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.exceptions import TokenBackendError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.state import token_backend
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)

from .constants import (
    REFRESH_REUSE_GRACE_SECONDS,
    REFRESH_SESSION_MAX_AGE_SECONDS,
    REFRESH_SESSION_START_CLAIM,
)
from .models import RotatedRefreshToken

logger = logging.getLogger(__name__)


def session_start_of(token: Any) -> Optional[int]:
    """The session start a refresh token carries, as epoch seconds.

    A token minted before todo 705 has no claim; its ``iat`` stands in, which
    starts its cap at its last rotation. None when neither is readable.
    """
    for claim in (REFRESH_SESSION_START_CLAIM, "iat"):
        try:
            value = token.get(claim)
        except Exception:  # noqa: BLE001 - a malformed claim is "unknown"
            value = None
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return int(value)
    return None


def session_expired(session_start: Optional[int], now: Optional[float] = None) -> bool:
    """True once the session is older than the cap. An unknown start is not
    expired here: the token's own ``exp`` still bounds it."""
    if session_start is None:
        return False
    now = time.time() if now is None else now
    return now - session_start > REFRESH_SESSION_MAX_AGE_SECONDS


def end_sessions_on_reuse(raw_token: str) -> Optional[tuple[str, int]]:
    """End every session of the account a REUSED refresh token belongs to.

    Returns ``(user id, refresh tokens revoked)``, or None when the token is
    not a reuse. Reuse is a token that is genuinely ours (signature and expiry
    verified FIRST, so a forged token naming a victim's user id cannot end the
    victim's sessions) and that a refresh ROTATED more than
    ``REFRESH_REUSE_GRACE_SECONDS`` ago. A younger rotation is two tabs
    refreshing with one cookie at once: refused by the caller, not reuse. A
    token blacklisted by anything but rotation (no ``RotatedRefreshToken``)
    is never reuse, however old.

    Detection fires once per token: its ``RotatedRefreshToken`` row is deleted
    in the transaction that revokes the account's tokens, so a later replay of
    the same stolen token is a plain 401 and cannot log the owner out again
    after they sign in afresh (todo 705 review round 2). Two replays at once
    both try the delete; only the one that deleted the row revokes.
    """
    try:
        # simplejwt hints Token, but decodes an encoded token string.
        payload = token_backend.decode(raw_token, verify=True)  # type: ignore[arg-type]
    except TokenBackendError:
        return None
    if payload.get(api_settings.TOKEN_TYPE_CLAIM) != "refresh":
        return None
    jti = payload.get(api_settings.JTI_CLAIM)
    user_id = payload.get(api_settings.USER_ID_CLAIM)
    if not jti or user_id is None:
        return None
    cutoff = timezone.now() - timedelta(seconds=REFRESH_REUSE_GRACE_SECONDS)
    with transaction.atomic():
        deleted, _ = RotatedRefreshToken.objects.filter(
            token__jti=jti, rotated_at__lte=cutoff
        ).delete()
        if not deleted:
            return None
        revoked = revoke_all_refresh_tokens(str(user_id))
    return str(user_id), revoked


def mark_rotated(jti: str) -> None:
    """Record that a refresh rotated the token ``jti``. Call it only from the
    rotation in ``token_refresh``, after ``blacklist()`` (which ensures the
    outstanding row) and in the same transaction. Idempotent: two overlapping
    rotations of one token write one row and never raise (ON CONFLICT DO
    NOTHING)."""
    outstanding = OutstandingToken.objects.only("id").get(jti=jti)
    RotatedRefreshToken.objects.bulk_create(
        [RotatedRefreshToken(token=outstanding)], ignore_conflicts=True
    )


def revoke_all_refresh_tokens(user_id: str) -> int:
    """Blacklist every outstanding refresh token of the account; the count."""
    live = list(
        OutstandingToken.objects.filter(
            user_id=user_id, blacklistedtoken__isnull=True
        ).only("id")
    )
    BlacklistedToken.objects.bulk_create(
        [BlacklistedToken(token=token) for token in live], ignore_conflicts=True
    )
    return len(live)
