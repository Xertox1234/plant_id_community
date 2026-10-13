"""Quiet hours (todo 624): the window math, across zones and DST, and the
member's settings on ``forum/me/profile/``.

Owner decision 2026-10-12: opt-in, default 22:00-07:00 in the client-reported
IANA zone (UTC if unknown), held deliveries released at the window's end.
"""

import datetime

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from wagtail_forum.models import ForumProfile
from wagtail_forum.quiet_hours import is_valid_zone, quiet_release, resolve_zone

User = get_user_model()
UTC = datetime.timezone.utc
T = datetime.time
NIGHT = (T(22, 0), T(7, 0))


def utc(*args):
    return datetime.datetime(*args, tzinfo=UTC)


def test_off_or_empty_window_never_holds():
    now = utc(2026, 6, 1, 4, 0)
    assert quiet_release(False, *NIGHT, "UTC", now) is None
    # start == end is an empty window, never a 24-hour one.
    assert quiet_release(True, T(9, 0), T(9, 0), "UTC", now) is None


@pytest.mark.parametrize(
    "now, release",
    [
        # 22:00 is inside (start inclusive), held to tomorrow's 07:00.
        (utc(2026, 6, 1, 22, 0), utc(2026, 6, 2, 7, 0)),
        (utc(2026, 6, 1, 23, 59), utc(2026, 6, 2, 7, 0)),
        # After midnight: held to this morning's 07:00.
        (utc(2026, 6, 2, 3, 0), utc(2026, 6, 2, 7, 0)),
        # 07:00 is outside (end exclusive), and so is the day.
        (utc(2026, 6, 2, 7, 0), None),
        (utc(2026, 6, 2, 12, 0), None),
        (utc(2026, 6, 2, 21, 59), None),
    ],
)
def test_a_window_across_midnight(now, release):
    assert quiet_release(True, *NIGHT, "UTC", now) == release


def test_a_same_day_window():
    window = (T(13, 0), T(15, 30))
    assert quiet_release(True, *window, "", utc(2026, 6, 1, 14, 0)) == utc(
        2026, 6, 1, 15, 30
    )
    assert quiet_release(True, *window, "", utc(2026, 6, 1, 12, 59)) is None
    assert quiet_release(True, *window, "", utc(2026, 6, 1, 15, 30)) is None


def test_the_window_is_local_time_in_the_member_zone():
    # 05:00 UTC is 23:00 the evening before in Denver (MDT, UTC-6).
    now = utc(2026, 6, 2, 5, 0)
    assert quiet_release(True, *NIGHT, "America/Denver", now) == utc(2026, 6, 2, 13, 0)
    # And 13:30 in Kolkata (UTC+5:30), a half-hour zone: outside.
    assert quiet_release(True, *NIGHT, "Asia/Kolkata", utc(2026, 6, 2, 8, 0)) is None
    # 22:30 in Kolkata is 17:00 UTC: held to 07:00 IST = 01:30 UTC.
    assert quiet_release(True, *NIGHT, "Asia/Kolkata", utc(2026, 6, 2, 17, 0)) == utc(
        2026, 6, 3, 1, 30
    )


def test_spring_forward_releases_at_local_seven():
    # US DST starts 2026-03-08 at 02:00 local. 23:00 MST on the 7th is 06:00
    # UTC; 07:00 MDT on the 8th is 13:00 UTC: a 7-hour hold, not 8.
    now = utc(2026, 3, 8, 6, 0)
    release = quiet_release(True, *NIGHT, "America/Denver", now)
    assert release == utc(2026, 3, 8, 13, 0)
    assert release - now == datetime.timedelta(hours=7)


def test_fall_back_releases_at_local_seven():
    # US DST ends 2026-11-01 at 02:00 local. 23:00 MDT on Oct 31 is 05:00
    # UTC; 07:00 MST on Nov 1 is 14:00 UTC: a 9-hour hold, not 8.
    now = utc(2026, 11, 1, 5, 0)
    release = quiet_release(True, *NIGHT, "America/Denver", now)
    assert release == utc(2026, 11, 1, 14, 0)
    assert release - now == datetime.timedelta(hours=9)
    # The repeated 01:30 hour (both offsets) is inside the window either way.
    for hour in (7, 8):  # 01:30 MDT, then 01:30 MST
        assert quiet_release(
            True, *NIGHT, "America/Denver", utc(2026, 11, 1, hour, 30)
        ) == utc(2026, 11, 1, 14, 0)


def test_an_end_inside_the_spring_forward_gap_still_releases_after_it():
    # A 01:00-02:30 window on 2026-03-08: 02:30 does not exist that night.
    # The release lands once the clock has jumped, never before the window.
    now = utc(2026, 3, 8, 8, 30)  # 01:30 MST
    release = quiet_release(True, T(1, 0), T(2, 30), "America/Denver", now)
    assert release is not None and release > now
    assert release <= utc(2026, 3, 8, 9, 30)  # by 03:30 MDT


def test_an_unknown_or_missing_zone_is_utc():
    now = utc(2026, 6, 1, 23, 0)
    expected = utc(2026, 6, 2, 7, 0)
    for zone in ("", None, "Mars/Olympus_Mons", "../etc/passwd"):
        assert resolve_zone(zone) is UTC
        assert quiet_release(True, *NIGHT, zone, now) == expected
    assert is_valid_zone("America/Denver")
    assert not is_valid_zone("Mars/Olympus_Mons")
    assert not is_valid_zone("")


@pytest.mark.django_db
@pytest.mark.urls("wagtail_forum.tests.api.urls")
def test_profile_quiet_hours_are_off_by_default_and_round_trip():
    user = User.objects.create_user(username="quietapi")
    client = APIClient()
    client.force_authenticate(user)

    data = client.get("/forum/me/profile/").data
    assert data["quiet_hours_enabled"] is False
    assert (data["quiet_hours_start"], data["quiet_hours_end"]) == ("22:00", "07:00")
    assert data["time_zone"] == ""

    resp = client.patch(
        "/forum/me/profile/",
        {
            "quiet_hours_enabled": True,
            "quiet_hours_start": "21:30",
            "quiet_hours_end": "06:45",
            "time_zone": "America/Denver",
        },
        format="json",
    )
    assert resp.status_code == 200, resp.data
    profile = ForumProfile.for_user(user)
    assert profile.quiet_hours_enabled is True
    assert (profile.quiet_hours_start, profile.quiet_hours_end) == (
        T(21, 30),
        T(6, 45),
    )
    assert profile.time_zone == "America/Denver"
    assert client.get("/forum/me/profile/").data["quiet_hours_start"] == "21:30"


@pytest.mark.django_db
@pytest.mark.urls("wagtail_forum.tests.api.urls")
@pytest.mark.parametrize(
    "payload",
    [
        {"quiet_hours_start": "25:00"},
        # An empty window (start == end) would show quiet hours on and hold
        # nothing (review round 2): 07:00 is the stored end.
        {"quiet_hours_enabled": True, "quiet_hours_start": "07:00"},
        {"quiet_hours_start": "06:00", "quiet_hours_end": "06:00"},
        {"quiet_hours_end": "seven"},
        {"quiet_hours_enabled": "sometimes"},
    ],
)
def test_bad_quiet_hours_are_a_400_and_change_nothing(payload):
    user = User.objects.create_user(username="quietbad")
    client = APIClient()
    client.force_authenticate(user)

    resp = client.patch("/forum/me/profile/", payload, format="json")

    assert resp.status_code == 400, resp.data
    profile = ForumProfile.for_user(user)
    assert profile.quiet_hours_enabled is False
    assert profile.time_zone == ""


@pytest.mark.django_db
@pytest.mark.urls("wagtail_forum.tests.api.urls")
def test_an_unknown_zone_is_stored_as_utc_and_does_not_block_the_save():
    # The clients attach the device zone to every quiet-hours save; one this
    # server's tzdata lacks reads as UTC rather than refusing the toggle
    # (review round 2, PR #1132).
    user = User.objects.create_user(username="quietunknown")
    client = APIClient()
    client.force_authenticate(user)
    ForumProfile.for_user(user)
    ForumProfile.objects.filter(user=user).update(time_zone="America/Denver")

    resp = client.patch(
        "/forum/me/profile/",
        {"quiet_hours_enabled": True, "time_zone": "Mars/Olympus_Mons"},
        format="json",
    )

    assert resp.status_code == 200, resp.data
    assert resp.data["time_zone"] == ""
    profile = ForumProfile.for_user(user)
    assert (profile.quiet_hours_enabled, profile.time_zone) == (True, "")


@pytest.mark.django_db
@pytest.mark.urls("wagtail_forum.tests.api.urls")
def test_moving_one_end_away_from_the_other_is_accepted():
    user = User.objects.create_user(username="quietmove")
    client = APIClient()
    client.force_authenticate(user)

    resp = client.patch(
        "/forum/me/profile/", {"quiet_hours_end": "06:00"}, format="json"
    )

    assert resp.status_code == 200, resp.data
    assert ForumProfile.for_user(user).quiet_hours_end == T(6, 0)
