"""Copy-table consolidation tests (todo 287).

The existing wording assertions live in ``test_tasks.py`` (the tray) and stay
there — they are the regression guard that this refactor changed no user-facing
string. What is pinned HERE is the property those tests cannot see: that both
backend surfaces now read ONE source, and that the tray's event whitelist
survived the consolidation.
"""

from dataclasses import replace

import pytest
from apps.forum_host.notification_copy import (
    FORUM_NOTIFICATION_COPY,
    ForumEventCopy,
    email_content,
    push_content,
)


def test_email_and_tray_read_the_same_table_entry(monkeypatch):
    """The actual consolidation claim, asserted by moving the source of truth.

    A string-equality test would pass just as well against two hard-coded
    copies that happen to agree. Editing the table instead proves both
    surfaces are downstream of it: change one entry, and both the email
    subject and the tray title must change.
    """
    from apps.core.services.notification_service import NotificationService
    from apps.forum_host.tasks import _notification_content

    monkeypatch.setitem(
        FORUM_NOTIFICATION_COPY,
        "reply_added",
        replace(
            FORUM_NOTIFICATION_COPY["reply_added"],
            push_title="TRAY {topic_title}",
            email_subject="MAIL {topic_title}",
        ),
    )

    captured = {}

    def _capture(self, **kwargs):
        captured.update(kwargs)
        return {"email": True}

    monkeypatch.setattr(NotificationService, "send_notification", _capture)
    NotificationService().send_forum_reply_notification(
        user=None,
        topic_title="Repotting",
        reply_author="Alice",
        reply_excerpt="…",
        topic_url="/t/1/",
    )
    assert captured["title"] == "MAIL Repotting"

    title, _body = _notification_content(
        "reply_added", {"topic_title": "Repotting", "actor_name": "Alice"}
    )
    assert title == "TRAY Repotting"


def test_a_missing_email_arm_returns_false_instead_of_raising(monkeypatch):
    """`send_forum_email_batch`'s retry config is justified by its docstring's
    claim that the send loop "can never raise" — email has no collapse-key
    dedup, so a retry after a partial send would double-email everyone.

    An unpacking TypeError on a missing email arm would break that: it is not
    in `autoretry_for`, so it would abort the batch mid-loop and silently skip
    every remaining recipient. The live path must degrade to False.
    """
    from apps.core.services.notification_service import NotificationService

    monkeypatch.setitem(
        FORUM_NOTIFICATION_COPY,
        "reply_added",
        replace(
            FORUM_NOTIFICATION_COPY["reply_added"],
            email_subject=None,
            email_body=None,
        ),
    )

    sent = NotificationService().send_forum_reply_notification(
        user=None,
        topic_title="Repotting",
        reply_author="Alice",
        reply_excerpt="…",
        topic_url="/t/1/",
    )

    assert sent is False


def test_an_event_absent_from_the_table_renders_no_tray_entry():
    assert push_content("some_future_event", "Topic", "Alice") is None


def test_an_event_with_email_copy_but_no_push_copy_stays_tray_silent(monkeypatch):
    """The whitelist is the point, not a side effect.

    ``workflow.py`` fires ``moderation_decided`` with ``status="published"`` on
    every routine trust-autopublished post, so a table entry gaining an email
    arm must NOT start popping a tray notification through a generic fallback.
    """
    monkeypatch.setitem(
        FORUM_NOTIFICATION_COPY,
        "moderation_decided",
        ForumEventCopy(email_subject="Decision on your post", email_body="Decided"),
    )

    assert push_content("moderation_decided", "Topic", "Alice") is None
    assert email_content("moderation_decided", "Topic", "Alice") is not None


def test_email_content_is_none_for_an_event_with_no_email_arm():
    # Mention delivery runs entirely through the package's own notification
    # path; there is no live mention email, so the table must not imply one.
    assert email_content("mention", "Topic", "Alice") is None
    assert push_content("mention", "Topic", "Alice") is not None


@pytest.mark.parametrize(
    "module_path,literals",
    [
        (
            "apps/forum_host/tasks.py",
            [
                'New reply in "',
                "New forum reply",
                "You were mentioned",
                " replied",
                " mentioned you",
            ],
        ),
        (
            "apps/core/services/notification_service.py",
            ["New reply in: ", "replied to a topic you're following"],
        ),
    ],
)
def test_no_inline_forum_copy_remains_in_either_home(module_path, literals):
    """AC 1 verbatim: neither home contains an inline subject/title/body string.

    A source scan rather than a behavioural assertion, because the failure this
    guards against is someone re-adding a literal *alongside* the table lookup
    — which no behavioural test would notice until the two drifted.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    source = (root / module_path).read_text()
    # Strip the docstrings/comments that legitimately quote old wording when
    # explaining the consolidation.
    code = "\n".join(
        line
        for line in source.splitlines()
        if not line.lstrip().startswith(("#", '"""', "'''", "``", "-", "*"))
    )
    for literal in literals:
        assert literal not in code, (
            f"{module_path} still carries inline copy {literal!r} — forum "
            "notification wording belongs in notification_copy.py"
        )


def test_every_table_entry_actually_renders_somewhere():
    """An entry that renders nowhere is a silent no-op that reads like coverage.

    Asserts the SAME conditions the renderers check — ``push_content`` needs
    ``push_title`` *and* ``push_body``, ``email_content`` needs both email
    fields — not a weaker "has a title" proxy, which a half-filled entry would
    satisfy while still notifying no one.
    """
    for event, copy in FORUM_NOTIFICATION_COPY.items():
        renders_push = bool(copy.push_title and copy.push_body)
        renders_email = bool(copy.email_subject and copy.email_body)
        assert renders_push or renders_email, (
            f"{event} has a table entry but renders nowhere — half-filled "
            "surfaces are silently dropped by push_content/email_content"
        )


def test_a_push_entry_always_carries_a_no_topic_title():
    """``push_content`` falls back to ``push_title_without_topic`` when the
    topic title is missing, and a missing fallback would render a BLANK tray
    title rather than fail — so require the pair."""
    for event, copy in FORUM_NOTIFICATION_COPY.items():
        if copy.push_title:
            assert (
                copy.push_title_without_topic
            ), f"{event} would push a blank title when topic_title is empty"


def test_every_template_in_the_table_formats():
    """Moving from f-strings to ``str.format`` templates introduced a failure
    class f-strings cannot have: a typo'd or unbalanced placeholder, which
    raises ``KeyError``/``ValueError`` at SEND time.

    Renders every field in the table so a bad placeholder fails here instead.
    """
    fields = (
        "push_title",
        "push_title_without_topic",
        "push_body",
        "email_subject",
        "email_body",
    )
    for event, copy in FORUM_NOTIFICATION_COPY.items():
        for field in fields:
            template = getattr(copy, field)
            if template is None:
                continue
            try:
                template.format(topic_title="T", actor="A")
            except (KeyError, IndexError, ValueError) as exc:
                raise AssertionError(
                    f"{event}.{field} is not a renderable template: {exc!r}"
                ) from exc
