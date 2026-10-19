"""Live forum updates: the id-only events sent to open topic sockets.

Spec: docs/superpowers/specs/2026-10-18-forum-live-replies-design.md. A
message says only "post N in topic T changed": no body, no author, no counts.
Each client then fetches through REST, which applies visibility and per-viewer
fields. The receivers that call ``broadcast`` live in ``live_receivers``; the
consumer that delivers to sockets lives in ``consumers``.
"""

import logging
from typing import Optional

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import transaction

logger = logging.getLogger(__name__)

PROTOCOL_VERSION = 1
# The channels message type; a consumer handles it as ``forum_live_event``.
EVENT_HANDLER_TYPE = "forum.live.event"
POST_KINDS = frozenset({"post.created", "post.updated", "post.removed"})
TOPIC_KINDS = frozenset({"topic.updated", "topic.removed"})


def topic_group(topic_id: int) -> str:
    return f"forum.topic.{int(topic_id)}"


def build_event(kind: str, topic_id: int, post_id: Optional[int] = None) -> dict:
    """The wire message. ``post.*`` kinds need a post id; ``topic.*`` take none."""
    if kind in POST_KINDS:
        if post_id is None:
            raise ValueError(f"{kind} needs a post_id")
        return {
            "v": PROTOCOL_VERSION,
            "type": kind,
            "topic_id": int(topic_id),
            "post_id": int(post_id),
        }
    if kind in TOPIC_KINDS:
        if post_id is not None:
            raise ValueError(f"{kind} takes no post_id")
        return {"v": PROTOCOL_VERSION, "type": kind, "topic_id": int(topic_id)}
    raise ValueError(f"unknown live event kind: {kind}")


def broadcast(kind: str, topic_id: int, post_id: Optional[int] = None) -> None:
    """Send ``kind`` to the topic's sockets once the current transaction commits.

    Nothing is sent while ``FORUM_LIVE_UPDATES_ENABLED`` is off, or for a write
    that rolls back.
    """
    if not settings.FORUM_LIVE_UPDATES_ENABLED:
        return
    event = build_event(kind, topic_id, post_id)
    group = topic_group(topic_id)
    transaction.on_commit(lambda: _send(group, event))


def _send(group: str, event: dict) -> None:
    """Deliver one event. Never raises: a failed send must not fail the write
    (the reader still has REST, and the web client its fallback poll)."""
    try:
        async_to_sync(get_channel_layer().group_send)(
            group, {"type": EVENT_HANDLER_TYPE, "event": event}
        )
    except Exception as exc:
        logger.warning(
            "[FORUM_LIVE] send failed kind=%s topic=%s: %s",
            event.get("type"),
            event.get("topic_id"),
            type(exc).__name__,
        )
