"""Per-device FCM registrations, shared by forum and care pushes (todo 621).

The only writer of ``PushDevice``. Every send path reads its targets through
``device_tokens_for_users`` and forgets a dead one through
``forget_device_token``.

Deploy skew. Before this module an account held one token, on
``ForumProfile.fcm_token``. That column stays for now:

- an app build from before todo 621 still PATCHes it on ``/forum/me/profile/``;
  the host view mirrors each write here (``apps/forum_host/api.py``);
- a backend instance from before the deploy still reads it during the
  rollover.

So the send path targets the union of an account's ``PushDevice`` tokens and
its legacy token, and every removal clears the legacy column too when it
holds the same token. Once no supported build writes the column it can go.
"""

import logging

from django.db import IntegrityError, transaction
from django.db.models import Q

logger = logging.getLogger(__name__)

# Retries of a registration that lost a uniqueness race to a concurrent one.
# The winner's row is committed by then, so one more release sees it.
_REGISTER_ATTEMPTS = 3


def register_device(
    user,
    token: str,
    installation_id: str | None = None,
    platform: str = "",
    *,
    legacy: bool = False,
):
    """Register ``token`` as one of ``user``'s devices; returns the row.

    Releases the token, and the installation, from every other row first, in
    the same transaction: a token belongs to exactly one account (a shared
    device signed into a new account stops receiving the old one's pushes),
    and an installation holds one token (a rotated token replaces the old
    one instead of leaving it to receive duplicates). Never touches another
    device of ``user``.

    The legacy ``ForumProfile.fcm_token`` column follows the same rule: the
    token leaves every other account's column, and a replaced row's token
    leaves every column, whichever account held it. A registration through
    ``/push-devices/`` (``legacy=False``) also takes the token out of
    ``user``'s own column, so an old build's profile write can never release
    an upgraded phone. ``legacy=True`` is the profile-PATCH mirror: it keeps
    the column it was just given, and never overwrites the installation id
    or platform an upgraded install recorded.

    An account keeps at most ``PUSH_DEVICE_MAX_PER_ACCOUNT`` devices: past
    it, the least recently registered (``updated_at``, which every
    re-registration bumps) are evicted in the same transaction, never the
    device being registered (todo 650).

    Raises ``IntegrityError`` only when it lost the race to concurrent
    registrations of the same token or installation every time; callers
    report it as a conflict the client can retry.
    """
    from wagtail_forum.models import ForumProfile

    from .models import PushDevice

    installation_id = installation_id or None
    for attempt in range(_REGISTER_ATTEMPTS):
        try:
            with transaction.atomic():
                clash = Q(token=token)
                if installation_id:
                    clash |= Q(installation_id=installation_id)
                # Lock and delete exactly the rows read, so every deleted
                # row's token is also cleared from the column below.
                replaced = list(
                    PushDevice.objects.select_for_update()
                    .filter(clash)
                    .exclude(user=user, token=token)
                    .order_by("pk")
                    .values_list("pk", "token")
                )
                if replaced:
                    PushDevice.objects.filter(
                        pk__in=[pk for pk, _ in replaced]
                    ).delete()
                column = Q(fcm_token=token)
                if legacy:
                    column &= ~Q(user=user)
                old_tokens = [old for _, old in replaced if old != token]
                if old_tokens:
                    column |= Q(fcm_token__in=old_tokens)
                ForumProfile.objects.filter(column).update(fcm_token="")
                # ``user`` always: when a concurrent registration of this
                # token wins the insert, update_or_create re-reads that row
                # and must still move it to this account.
                defaults = {"user": user}
                if not legacy:
                    if platform:
                        defaults["platform"] = platform[:16]
                    if installation_id:
                        defaults["installation_id"] = installation_id
                device, _created = PushDevice.objects.update_or_create(
                    token=token,
                    defaults=defaults,
                    create_defaults={
                        "user": user,
                        "installation_id": installation_id,
                        "platform": platform[:16],
                    },
                )
                _evict_oldest_devices(user, keep=device.pk)
            return device
        except IntegrityError:
            if attempt == _REGISTER_ATTEMPTS - 1:
                raise
            logger.info(
                "[PUSH] device registration raced another; retrying (user=%s)",
                user.pk,
            )
    raise AssertionError("unreachable")  # pragma: no cover


def _evict_oldest_devices(user, *, keep: int) -> None:
    """Remove ``user``'s least recently registered devices past the cap,
    never ``keep``. A phone in daily use re-registers on launch, so it is
    never the one evicted ahead of a stale row.

    Inside ``register_device``'s transaction. Silent to the client (owner
    decision 2026-10-16): the evicted device is simply no longer reached, as
    after a dead-token report. Clears the legacy column when it holds an
    evicted token, which the send path would otherwise still target.
    """
    from wagtail_forum.models import ForumProfile

    from .constants import PUSH_DEVICE_MAX_PER_ACCOUNT
    from .models import PushDevice

    others = (
        PushDevice.objects.filter(user=user)
        .exclude(pk=keep)
        .order_by("-updated_at", "-pk")
        .values_list("pk", "token")
    )
    evicted = list(others[PUSH_DEVICE_MAX_PER_ACCOUNT - 1 :])
    if not evicted:
        return
    PushDevice.objects.filter(pk__in=[pk for pk, _ in evicted]).delete()
    ForumProfile.objects.filter(
        user=user, fcm_token__in=[token for _, token in evicted]
    ).update(fcm_token="")
    logger.info(
        "[PUSH] device cap reached; evicted %s oldest device(s) (user=%s)",
        len(evicted),
        user.pk,
    )


def unregister_device(user, token: str) -> int:
    """Remove ``token`` from ``user``'s devices; returns rows removed.

    Matches on the token AND the account, so a sign-out removes only the
    device signing out: never another device of the account, never the same
    device after another account claimed it, and never a newer token the
    device rotated to. Clears the legacy column when it holds this token.
    """
    from wagtail_forum.models import ForumProfile

    from .models import PushDevice

    with transaction.atomic():
        removed, _ = PushDevice.objects.filter(user=user, token=token).delete()
        ForumProfile.objects.filter(user=user, fcm_token=token).update(fcm_token="")
    return removed


def forget_device_token(user_id: int, token: str) -> int:
    """Forget a token FCM reported dead, for this account only.

    Called from a send failure handler, so it matches the exact token that
    failed: a device that re-registered a new token while the send was in
    flight keeps it, and the account's other devices are untouched. Returns
    the number of registrations removed, legacy column included.
    """
    from wagtail_forum.models import ForumProfile

    from .models import PushDevice

    with transaction.atomic():
        removed, _ = PushDevice.objects.filter(user_id=user_id, token=token).delete()
        cleared = ForumProfile.objects.filter(user_id=user_id, fcm_token=token).update(
            fcm_token=""
        )
    return removed + cleared


def device_tokens_for_users(user_ids) -> dict[int, list[str]]:
    """Each account's device tokens, ``{user_id: [token, ...]}``.

    The union of ``PushDevice`` and the legacy column (see the module
    docstring), deduplicated, legacy first and devices from least to most
    recently registered (``updated_at``), so a send loop is deterministic. Accounts with no device are
    absent.

    At most the ``PUSH_DEVICE_MAX_PER_ACCOUNT`` most recently registered
    devices per account, so rows from before the cap (todo 650), kept until
    that account next registers, never stretch a send loop. The legacy
    column adds at most one more token, so the bound is the cap plus one.
    """
    from wagtail_forum.models import ForumProfile

    from .constants import PUSH_DEVICE_MAX_PER_ACCOUNT
    from .models import PushDevice

    user_ids = list(user_ids)
    if not user_ids:
        return {}
    tokens: dict[int, list[str]] = {}
    for user_id, token in (
        ForumProfile.objects.filter(user_id__in=user_ids)
        .exclude(fcm_token="")
        .values_list("user_id", "fcm_token")
    ):
        tokens.setdefault(user_id, []).append(token)
    newest: dict[int, list[str]] = {}
    for user_id, token in (
        PushDevice.objects.filter(user_id__in=user_ids)
        .order_by("-updated_at", "-pk")
        .values_list("user_id", "token")
    ):
        kept = newest.setdefault(user_id, [])
        if len(kept) < PUSH_DEVICE_MAX_PER_ACCOUNT:
            kept.append(token)
    for user_id, kept in newest.items():
        held = tokens.setdefault(user_id, [])
        for token in reversed(kept):
            if token not in held:
                held.append(token)
    return tokens


def is_registered(user_id: int, token: str) -> bool:
    """Whether ``token`` is still one of this account's devices."""
    return token in device_tokens_for_users([user_id]).get(user_id, [])
