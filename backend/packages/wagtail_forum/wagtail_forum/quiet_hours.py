"""Quiet hours (todo 624): when a member's window holds a delivery, and
until when.

Host-agnostic and pure: the host's send tasks ask ``quiet_release`` for each
recipient and hold the delivery until the returned instant. The in-app
inbox is never held, and nothing here knows about security mail: the host
simply never asks for it.

The window is wall-clock time in the member's IANA zone, so it follows
daylight saving: 22:00-07:00 in America/Denver is 22:00-07:00 local on both
sides of a transition, and its length in UTC changes by an hour that night.
A zone this server cannot resolve, or none, means UTC (owner decision
2026-10-12). Start == end is an empty window, never a 24-hour one.
"""

from __future__ import annotations

import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

UTC = datetime.timezone.utc


def resolve_zone(name) -> datetime.tzinfo:
    """The member's zone, or UTC for a blank or unknown name."""
    if not isinstance(name, str) or not name.strip():
        return UTC
    try:
        return ZoneInfo(name.strip())
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return UTC


def is_valid_zone(name: str) -> bool:
    """Whether ``name`` is an IANA zone this server can resolve."""
    if not isinstance(name, str) or not name.strip() or len(name) > 64:
        return False
    try:
        ZoneInfo(name.strip())
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return False
    return True


def quiet_release(enabled, start, end, zone_name, now) -> datetime.datetime | None:
    """When the quiet window holding ``now`` ends (an aware UTC datetime),
    or None when ``now`` is outside it, quiet hours are off, or the window
    is empty.

    ``start``/``end`` are naive ``datetime.time`` wall-clock values. A window
    whose start is after its end crosses midnight (22:00-07:00).
    """
    if not enabled or start is None or end is None or start == end:
        return None
    zone = resolve_zone(zone_name)
    local = now.astimezone(zone)
    wall = local.time().replace(tzinfo=None)
    if start < end:
        if not (start <= wall < end):
            return None
        end_date = local.date()
    else:
        if wall >= start:
            end_date = local.date() + datetime.timedelta(days=1)
        elif wall < end:
            end_date = local.date()
        else:
            return None
    # Wall-clock end in the member's zone: zoneinfo applies that day's
    # offset, so the release lands at the local end time across DST.
    release = datetime.datetime.combine(end_date, end, tzinfo=zone).astimezone(UTC)
    if release <= now:
        # Only reachable when the end time falls in a spring-forward gap
        # that has already passed: nothing to hold.
        return None
    return release


def profile_release(profile, now) -> datetime.datetime | None:
    """``quiet_release`` for a ForumProfile (or any object with its fields)."""
    return quiet_release(
        getattr(profile, "quiet_hours_enabled", False),
        getattr(profile, "quiet_hours_start", None),
        getattr(profile, "quiet_hours_end", None),
        getattr(profile, "time_zone", ""),
        now,
    )
