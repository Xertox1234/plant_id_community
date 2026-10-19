"""Settings for live forum replies (slice 2)."""

from django.conf import settings


def test_live_updates_flag_defaults_off():
    """The kill switch ships off; slice 5 turns it on after the owner's
    device check. The test env sets no value, so this pins the default."""
    assert settings.FORUM_LIVE_UPDATES_ENABLED is False
