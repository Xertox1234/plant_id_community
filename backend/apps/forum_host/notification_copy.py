"""Single source of forum notification copy (todo 287).

Before this module the same forum event was phrased independently in two
backend places — the email subject/body in
``apps/core/services/notification_service.py`` and the FCM tray title/body in
``apps/forum_host/tasks.py::_notification_content`` — and they had already
drifted apart. Any copy edit (or a future i18n pass) had to find both by hand,
and missing one shipped inconsistent wording rather than an error.

**Why the table lives here and not in `apps/core`.**
``notification_service`` is not forum-specific — it also serves plant-care
reminders, identification results and newsletters. So the forum owns its copy
and the core service reads it, not the other way round. The core service takes
this as a *function-level* import to keep the app-level dependency direction
loose and rule out an import cycle with ``forum_host.tasks``.

**The push-tray whitelist is a feature, not an oversight.**
An event with no ``push_title`` renders no tray entry. That is load-bearing:
``workflow.py`` fires ``moderation_decided`` with ``status="published"`` on
every routine trust-autopublished post, reply and edit, so a generic fallback
would tray-popup "Your post was published" at users for their own ordinary
posts. Absent event, or event present with no push copy → ``None``. Never a
default. Pinned by ``test_tasks.py``'s tray-silence cases.

**The web bell is deliberately still a third home.**
``web/src/components/layout/NotificationBell.tsx`` cannot import a Python
table. Converging it means serving the label from the API, not duplicating
this table in TypeScript — out of scope here, and noted in that file.

Placeholders are `str.format` fields, filled by the caller:
``{topic_title}``, ``{actor}`` and, for a coalesced reply (todo 624),
``{count}``.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ForumEventCopy:
    """Wording for one forum event across every surface that renders it.

    Every field is optional. A surface with no copy for an event does not
    notify on that surface — it does not fall back to generic wording.
    """

    #: FCM tray title when the topic title is known.
    push_title: str | None = None
    #: FCM tray title when it is not (missing/blank ``topic_title``).
    push_title_without_topic: str | None = None
    #: FCM tray body.
    push_body: str | None = None
    #: Email subject line.
    email_subject: str | None = None
    #: Email preview/summary line (the ``message`` passed to the notifier).
    email_body: str | None = None


#: event name -> copy. Event names arrive as plain strings: Celery
#: JSON-serialises ``NotificationVerb.MENTION`` to ``"mention"`` through the
#: broker, so this is keyed by the wire value, not the enum.
FORUM_NOTIFICATION_COPY: dict[str, ForumEventCopy] = {
    "reply_added": ForumEventCopy(
        push_title='New reply in "{topic_title}"',
        push_title_without_topic="New forum reply",
        push_body="{actor} replied",
        email_subject="New reply in: {topic_title}",
        email_body="{actor} replied to a topic you're following",
    ),
    "answer_accepted": ForumEventCopy(
        push_title='Your answer was accepted in "{topic_title}"',
        push_title_without_topic="Your answer was accepted",
        push_body="{actor} marked your reply as the answer",
        # Optional email, off by default (todo 624, owner decision
        # 2026-10-12): send_forum_email_batch sends it.
        email_subject="Your answer was accepted in: {topic_title}",
        email_body="{actor} marked your reply as the answer",
    ),
    "quote": ForumEventCopy(
        push_title='Your post was quoted in "{topic_title}"',
        push_title_without_topic="Your post was quoted on the forum",
        push_body="{actor} quoted your post",
        email_subject="Your post was quoted in: {topic_title}",
        email_body="{actor} quoted your post",
    ),
    "mention": ForumEventCopy(
        push_title='You were mentioned in "{topic_title}"',
        push_title_without_topic="You were mentioned on the forum",
        push_body="{actor} mentioned you",
        email_subject="You were mentioned in: {topic_title}",
        email_body="{actor} mentioned you",
    ),
    # Several replies on one topic folded into one message (todo 624). Not
    # an event of its own: ``reply_added`` renders it when count > 1.
    "replies_coalesced": ForumEventCopy(
        push_title='{count} new replies in "{topic_title}"',
        push_title_without_topic="{count} new forum replies",
        push_body="Latest from {actor}",
        email_subject="{count} new replies in: {topic_title}",
        email_body="{count} new replies on a topic you're following",
    ),
}


def _copy_key(event: str, count: int) -> str:
    return "replies_coalesced" if event == "reply_added" and count > 1 else event


def push_content(
    event: str, topic_title: str, actor: str, count: int = 1
) -> tuple[str, str] | None:
    """Render the FCM tray ``(title, body)`` for *event*, or ``None`` if silent.

    ``topic_title`` is expected pre-truncated by the caller (the cap is a push
    transport concern, not copy). ``actor`` is expected pre-defaulted.
    """
    if event not in FORUM_NOTIFICATION_COPY:
        return None
    # The whitelist check sits on the copy actually rendered: a coalesced
    # reply reads ``replies_coalesced``, whose push arm matches ``reply_added``'s.
    copy = FORUM_NOTIFICATION_COPY[_copy_key(event, count)]
    if copy.push_title is None or copy.push_body is None:
        return None
    fields = {"topic_title": topic_title, "actor": actor, "count": count}
    if topic_title:
        title = copy.push_title.format(**fields)
    else:
        title = (copy.push_title_without_topic or "").format(**fields)
    return title, copy.push_body.format(**fields)


def email_content(
    event: str, topic_title: str, actor: str, count: int = 1
) -> tuple[str, str] | None:
    """Render the email ``(subject, body)`` for *event*, or ``None`` if the
    event has no email arm. ``count`` > 1 renders a coalesced reply."""
    if event not in FORUM_NOTIFICATION_COPY:
        return None
    copy = FORUM_NOTIFICATION_COPY[_copy_key(event, count)]
    if copy.email_subject is None or copy.email_body is None:
        return None
    fields = {"topic_title": topic_title, "actor": actor, "count": count}
    return copy.email_subject.format(**fields), copy.email_body.format(**fields)
