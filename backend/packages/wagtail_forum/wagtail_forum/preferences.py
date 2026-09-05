"""Per-channel notification preferences (todo 343) — the package half.

Members choose, per event, whether it also reaches them by ``push`` and —
where an email arm exists — by ``email``. In-app notifications are always on
(Discourse precedent) and are not a preference. ``NOTIFICATION_MATRIX`` lists
exactly the (event, channel) cells that have a delivery path: a cell that
nothing sends is not offered, so a stored preference can never be inert. The
tray-silent ``moderation_decided`` push is a client sync signal with no
in-app row, so it is not an event here and stays ungated.

Storage is a SPARSE overrides map on ``ForumProfile``; the effective matrix is
the host's ``NOTIFICATION_DEFAULTS`` deep-merged with the overrides (each
missing cell falling back to the package's own defaults), so a default change
flows to every untouched cell.

The host's push/email tasks ask ``wants_channel(overrides, event, channel)``
before sending. Events are the fan-out event names (``reply_added``,
``answer_accepted``) or verb values (``mention``, ``quote``) — ``EVENT_VERBS``
maps them; an event nobody mapped is NOT gated, so a future event cannot be
silently dropped by an old preference row.
"""

from __future__ import annotations

from copy import deepcopy

from .conf import DEFAULTS, get_setting

# Every (event, channel) cell that has a delivery path. The verbs are the
# NotificationVerb values (pinned by test_preference_verbs_track_notification_
# verbs); kept literal so this module stays importable before the app
# registry is ready (host tasks import it at module level).
NOTIFICATION_MATRIX: dict[str, tuple[str, ...]] = {
    "reply": ("push", "email"),
    "mention": ("push",),
    "quote": ("push",),
    "solution": ("push",),
}
NOTIFICATION_VERBS: tuple[str, ...] = tuple(NOTIFICATION_MATRIX)
NOTIFICATION_CHANNELS: tuple[str, ...] = ("push", "email")

# Fan-out event name -> preference verb. Batch pushes for mentions/quotes are
# enqueued with the NotificationVerb value itself, so those map to themselves.
EVENT_VERBS: dict[str, str] = {
    "reply_added": "reply",
    "reply": "reply",
    "mention": "mention",
    "quote": "quote",
    "answer_accepted": "solution",
    "solution": "solution",
}


class InvalidPreferences(ValueError):
    """A client payload that is not a partial {verb: {channel: bool}} matrix."""


def default_preferences() -> dict[str, dict[str, bool]]:
    """The host's default matrix, every wired cell present: a cell the host's
    ``NOTIFICATION_DEFAULTS`` leaves out falls back to the PACKAGE default for
    that same cell (one source of truth, conf.DEFAULTS), never a literal."""
    configured = get_setting("NOTIFICATION_DEFAULTS")
    configured = configured if isinstance(configured, dict) else {}
    package = DEFAULTS["NOTIFICATION_DEFAULTS"]
    matrix: dict[str, dict[str, bool]] = {}
    for verb, channels in NOTIFICATION_MATRIX.items():
        row = configured.get(verb)
        row = row if isinstance(row, dict) else {}
        matrix[verb] = {
            channel: bool(row.get(channel, package[verb][channel]))
            for channel in channels
        }
    return matrix


def resolve_preferences(overrides) -> dict[str, dict[str, bool]]:
    """The effective matrix for a member: defaults deep-merged with their
    stored overrides. Junk in stored data (an unknown verb/channel, an unwired
    cell, a non-bool) is ignored rather than raised — a read must never 500
    over a row written by an older release."""
    matrix = default_preferences()
    if not isinstance(overrides, dict):
        return matrix
    for verb, row in overrides.items():
        if verb not in matrix or not isinstance(row, dict):
            continue
        for channel, value in row.items():
            if channel in matrix[verb] and isinstance(value, bool):
                matrix[verb][channel] = value
    return matrix


def wants_channel(overrides, event: str, channel: str) -> bool:
    """Whether a member with these overrides wants *event* on *channel*.
    Unmapped events and cells outside the matrix are not gated (True)."""
    verb = EVENT_VERBS.get(str(event))
    if verb is None or channel not in NOTIFICATION_MATRIX[verb]:
        return True
    return resolve_preferences(overrides)[verb][channel]


def validate_preferences(payload) -> dict[str, dict[str, bool]]:
    """Normalize a client's PARTIAL matrix, rejecting anything outside the
    wired cells or non-boolean values."""
    if not isinstance(payload, dict):
        raise InvalidPreferences("Notification preferences must be an object.")
    cleaned: dict[str, dict[str, bool]] = {}
    for verb, row in payload.items():
        if verb not in NOTIFICATION_MATRIX:
            raise InvalidPreferences(f"Unknown notification event: {verb}")
        if not isinstance(row, dict):
            raise InvalidPreferences(f"Preferences for {verb} must be an object.")
        for channel, value in row.items():
            if channel not in NOTIFICATION_CHANNELS:
                raise InvalidPreferences(f"Unknown notification channel: {channel}")
            if channel not in NOTIFICATION_MATRIX[verb]:
                raise InvalidPreferences(
                    f"{channel.capitalize()} is not available for {verb}."
                )
            if not isinstance(value, bool):
                raise InvalidPreferences("Preference values must be true or false.")
            cleaned.setdefault(verb, {})[channel] = value
    return cleaned


def merge_preferences(existing, partial) -> dict[str, dict[str, bool]]:
    """Stored overrides + a validated partial -> new sparse overrides. Cells
    the partial does not mention keep their stored value; a junk-valued
    stored verb (an older release's row) is replaced, never dereferenced."""
    merged = deepcopy(existing) if isinstance(existing, dict) else {}
    for verb, row in partial.items():
        target = merged.get(verb)
        if not isinstance(target, dict):
            target = {}
        target.update(row)
        merged[verb] = target
    return merged
