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
``{topic_title}`` and ``{actor}``.
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
        # No email arm: this is a positive, low-urgency event and the bell +
        # push already carry it. Adding a subject/body here would not send one
        # anyway — the answer_accepted branch in notifications.py enqueues no
        # email task (see this module's "whitelist is a feature" note).
    ),
    "mention": ForumEventCopy(
        push_title='You were mentioned in "{topic_title}"',
        push_title_without_topic="You were mentioned on the forum",
        push_body="{actor} mentioned you",
        # No email arm on purpose. Mention delivery runs entirely through the
        # package's own notification path; the email method that once carried
        # mention copy had zero call sites and was deleted with this change
        # (todo 287). Adding an email arm here would not wire one up — it
        # needs a caller.
    ),
}


def push_content(event: str, topic_title: str, actor: str) -> tuple[str, str] | None:
    """Render the FCM tray ``(title, body)`` for *event*, or ``None`` if silent.

    ``topic_title`` is expected pre-truncated by the caller (the cap is a push
    transport concern, not copy). ``actor`` is expected pre-defaulted.
    """
    copy = FORUM_NOTIFICATION_COPY.get(event)
    if copy is None or copy.push_title is None or copy.push_body is None:
        return None
    if topic_title:
        title = copy.push_title.format(topic_title=topic_title, actor=actor)
    else:
        title = copy.push_title_without_topic or ""
    return title, copy.push_body.format(topic_title=topic_title, actor=actor)


def email_content(event: str, topic_title: str, actor: str) -> tuple[str, str] | None:
    """Render the email ``(subject, body)`` for *event*, or ``None`` if the
    event has no email arm."""
    copy = FORUM_NOTIFICATION_COPY.get(event)
    if copy is None or copy.email_subject is None or copy.email_body is None:
        return None
    return (
        copy.email_subject.format(topic_title=topic_title, actor=actor),
        copy.email_body.format(topic_title=topic_title, actor=actor),
    )
