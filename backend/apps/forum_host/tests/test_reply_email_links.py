"""Reply emails link to the reply itself (todo 622).

The web thread page gives each post ``id="post-<id>"``
(web/src/pages/forum/ThreadDetailPage.tsx), and push already opens the topic at
that anchor. The email used to link only the topic. These tests drive the real
batch task and read the rendered message, both parts.
"""

import re

import pytest
from apps.forum_host.tasks import send_forum_email_batch
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex, Post, Topic

User = get_user_model()
HREF = re.compile(r'href="([^"]*)"')


def _reply(prefix):
    owner = User.objects.create_user(
        username=f"{prefix}-owner", email=f"{prefix}-owner@example.com"
    )
    replier = User.objects.create_user(
        username=f"{prefix}-replier", email=f"{prefix}-replier@example.com"
    )
    index = Page.objects.get(id=1).add_child(
        instance=ForumIndex(title=prefix, slug=prefix)
    )
    board = index.add_child(
        instance=ForumBoard(title=f"{prefix} board", slug=f"{prefix}-board")
    )
    topic = Topic.objects.create(
        board=board, title="Yellow leaves", slug="yellow-leaves", author=owner
    )
    post = Post.objects.create(
        topic=topic,
        author=replier,
        body=[{"type": "paragraph", "value": "<p>Check the drainage.</p>"}],
    )
    return owner, board, topic, post


def _send(owner, post):
    send_forum_email_batch("reply_added", [owner.pk], {"post_id": str(post.pk)})
    [message] = mail.outbox
    return message, message.alternatives[0][0]


@pytest.mark.django_db
@pytest.mark.parametrize("origin", ["https://web.example", "https://web.example/"])
def test_reply_email_opens_the_reply_on_the_canonical_thread_path(origin):
    owner, board, topic, post = _reply("rl")
    topic_url = (
        f"https://web.example/forum/{board.id}-{board.slug}/{topic.id}-{topic.slug}"
    )
    post_url = f"{topic_url}#post-{post.pk}"

    with override_settings(SITE_URL=origin):
        message, html = _send(owner, post)

    hrefs = HREF.findall(html)
    # The main button opens the reply; the topic itself stays the fallback.
    assert hrefs.count(post_url) == 1, hrefs
    assert topic_url in hrefs
    assert f"Read the reply: {post_url}\n" in message.body
    assert f"View topic to unfollow: {topic_url}\n" in message.body
    # A trailing-slash origin never doubles the slash.
    for url in hrefs + [message.body]:
        assert "example//" not in url


@pytest.mark.django_db
def test_reply_email_without_a_post_link_falls_back_to_the_topic():
    """A caller that passes only ``topic_url`` (the old signature) still gets
    a working button: the topic, never an empty href."""
    from apps.core.services.notification_service import NotificationService

    user = User.objects.create_user(username="rl-fallback", email="rlf@example.com")
    sent = NotificationService().send_forum_reply_notification(
        user=user,
        topic_title="Yellow leaves",
        reply_author="Fern",
        reply_excerpt="Check the drainage.",
        topic_url="https://web.example/forum/1-b/2-t",
    )

    assert sent is True
    [message] = mail.outbox
    html = message.alternatives[0][0]
    assert 'href=""' not in html
    assert HREF.findall(html).count("https://web.example/forum/1-b/2-t") == 2
    assert "Read the reply: https://web.example/forum/1-b/2-t\n" in message.body


@pytest.mark.django_db
@pytest.mark.parametrize("origin", [None, ""])
def test_an_unset_site_url_does_not_fail_the_batch(origin):
    """Todo 639 finding 5: SITE_URL None or empty must not raise an
    AttributeError a Celery retry can never fix; the email still goes out."""
    owner, board, topic, post = _reply("nsnone" if origin is None else "nsempty")

    with override_settings(SITE_URL=origin):
        message, html = _send(owner, post)

    assert f"/forum/{board.id}-{board.slug}/{topic.id}-{topic.slug}" in html
    assert "None" not in message.body
