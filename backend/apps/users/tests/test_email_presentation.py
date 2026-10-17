"""Every live email family, rendered for real (todo 622).

One builder per family sends the message the way production does and returns
it from the outbox, so each assertion below reads what a recipient gets: the
plain-text part (AC: action URLs, no stylesheet), the HTML layout (shared
mail-safe base, preheader in <body>, inline essential styling), and the
security-mail policy (no optional-mail footer, sent whatever the preferences).

Legacy templates with no live caller (blog_post, forum_mention, forum_digest,
disease_alert, identification_result, the allauth signup confirmation) are
deliberately not here: the owner's 2026-10-12 decision covers live families.
"""

import re
from datetime import timedelta

import pytest
from apps.blog import newsletter, newsletter_digest
from apps.blog.models import BlogNewsletter
from apps.core.services.email_service import EmailService, EmailType
from apps.core.services.notification_service import NotificationService
from apps.users.account_links import deliver_provider_linked_notice
from apps.users.email_verification import (
    deliver_verification_email,
    mark_email_verified,
)
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import Client, override_settings
from django.utils import timezone
from wagtail_forum.digest import Digest, DigestTopic, send_digest

User = get_user_model()

SITE = "https://web.example"
API = "https://api.example"
HOSTILE = "<script>x</script>"
HREF = re.compile(r'href="([^"]*)"')
SECURITY = ("verification", "provider_linked", "password_reset")


def _one(sent_before):
    new = mail.outbox[sent_before:]
    assert len(new) == 1, [m.subject for m in new]
    return new[0]


def _user(username="mailee", **fields):
    return User.objects.create_user(
        username=username, email=f"{re.sub(r'\W', '', username)}@example.com", **fields
    )


def welcome():
    n = len(mail.outbox)
    assert EmailService().send_welcome_email(_user("welcomed", first_name="Wanda"))
    return _one(n)


def forum_reply():
    n = len(mail.outbox)
    topic = f"{SITE}/forum/1-general/2-yellow-leaves"
    assert NotificationService().send_forum_reply_notification(
        user=_user("follower"),
        topic_title="Yellow leaves",
        reply_author="Fern",
        reply_excerpt="Check the drainage & the light.",
        topic_url=topic,
        post_url=f"{topic}#post-3",
    )
    return _one(n)


def forum_event():
    """The optional mention email (todo 624); quote and accepted-answer
    email share its template."""
    n = len(mail.outbox)
    topic = f"{SITE}/forum/1-general/2-yellow-leaves"
    assert NotificationService().send_forum_event_notification(
        user=_user("mentioned"),
        event="mention",
        topic_title="Yellow leaves",
        actor_name="Fern",
        post_excerpt="@mentioned what do you think?",
        topic_url=topic,
        post_url=f"{topic}#post-4",
    )
    return _one(n)


def forum_reply_coalesced():
    """Several replies folded into one email (todo 624)."""
    n = len(mail.outbox)
    topic = f"{SITE}/forum/1-general/2-yellow-leaves"
    assert NotificationService().send_forum_reply_notification(
        user=_user("busyfollower"),
        topic_title="Yellow leaves",
        reply_author="Fern",
        reply_excerpt="The newest of three.",
        topic_url=topic,
        post_url=f"{topic}#post-9",
        count=3,
    )
    return _one(n)


def newsletter_confirm():
    n = len(mail.outbox)
    assert newsletter.request_confirmation("reader@example.com")
    return _one(n)


def newsletter_issue():
    n = len(mail.outbox)
    subscriber = BlogNewsletter.objects.create(email="weekly@example.com")
    post = newsletter_digest.DigestPost(
        title="Repotting a monstera",
        url=f"{SITE}/blog/repotting-a-monstera",
        excerpt="Roots first.",
        published_at=timezone.now(),
    )
    assert newsletter_digest.send(subscriber, [post])
    return _one(n)


def forum_digest():
    n = len(mail.outbox)
    user = _user("digester")
    topic = DigestTopic(
        id=2,
        title="Yellow leaves",
        url=f"{SITE}/forum/1-general/2-yellow-leaves",
        board_title="General",
        reply_count=4,
        last_post_at=timezone.now(),
        new_replies=2,
    )
    digest = Digest(
        user=user,
        since=timezone.now() - timedelta(days=7),
        display_name="Digester",
        watched=[topic],
    )
    assert send_digest(digest)
    return _one(n)


def verification(username="verifyme"):
    n = len(mail.outbox)
    assert deliver_verification_email(_user(username))
    return _one(n)


def provider_linked(username="linked"):
    n = len(mail.outbox)
    assert deliver_provider_linked_notice(_user(username), "google")
    return _one(n)


def password_reset():
    user = _user("resetter")
    mark_email_verified(user)
    n = len(mail.outbox)
    cache.clear()  # allauth rate-limits reset requests per address
    Client().post("/accounts/password/reset/", {"email": user.email})
    return _one(n)


FAMILIES = {
    "welcome": welcome,
    "forum_reply": forum_reply,
    "forum_reply_coalesced": forum_reply_coalesced,
    "forum_event": forum_event,
    "newsletter_confirm": newsletter_confirm,
    "newsletter_digest": newsletter_issue,
    "forum_digest": forum_digest,
    "verification": verification,
    "provider_linked": provider_linked,
    "password_reset": password_reset,
}


def _html(message):
    [(html, mimetype)] = message.alternatives
    assert mimetype == "text/html"
    return html


@pytest.fixture(params=sorted(FAMILIES))
def sent(request, db):
    """(family name, the message it sent), on fixed public origins."""
    with override_settings(SITE_URL=SITE, API_PUBLIC_URL=API):
        mail.outbox.clear()
        yield request.param, FAMILIES[request.param]()


# --- text alternatives -------------------------------------------------------


def test_text_part_carries_every_action_url_and_no_markup(sent):
    family, message = sent
    body = message.body
    urls = [url for url in HREF.findall(_html(message)) if url.startswith("http")]

    assert urls, f"{family}: the HTML part has no links"
    for url in urls:
        assert url.replace("&amp;", "&") in body, f"{family}: {url} not in text"
    for source in ("<style", "<script", "<a ", "<p", "{", "font-family", ".email-"):
        assert source not in body, f"{family}: {source!r} leaked into the text"
    assert len(body.strip().splitlines()) >= 3, f"{family}: {body!r}"


# --- layout ------------------------------------------------------------------


def test_html_uses_the_shared_mail_safe_layout(sent):
    family, message = sent
    html = _html(message)
    head, _, body = html.partition("<body")

    # One layout for every family: the base template's presentation tables.
    assert 'class="email-container"' in body, family
    assert 'role="presentation"' in body, family
    assert '<meta name="color-scheme" content="light">' in head, family
    # The preheader is the first element of <body>, never inside <head>.
    assert "display: none" not in head, family
    assert (
        body.split(">", 1)[1].lstrip().startswith('<div style="display: none')
    ), family
    # Mail-safe: no flexbox layout, and every link has a real destination.
    assert "display: flex" not in html and "inline-flex" not in html, family
    assert 'href=""' not in html, family
    assert "#!/" not in html, family


def test_links_and_buttons_carry_their_colors_inline(sent):
    """Gmail paints a link its own blue unless the color is on the <a>."""
    family, message = sent
    links = re.findall(r"<a\b[^>]*>", _html(message))

    assert links, f"{family}: no link found"
    for tag in links:
        assert re.search(r'style="[^"]*(?<![-\w])color:', tag), (family, tag)
        if "padding:" in tag:  # a button: its fill must be inline too
            assert "background-color:" in tag, (family, tag)


def test_security_mail_has_no_optional_mail_footer(sent):
    family, message = sent
    html = _html(message)
    footer = html.rsplit("border-top: 1px solid #e9ecef", 1)[1]

    if family in SECURITY:
        assert "security message" in footer, family
        assert "Unsubscribe" not in html and "/settings" not in html, family
        assert "List-Unsubscribe" not in message.extra_headers, family
    else:
        assert "security message" not in footer, family


# --- meaning and escaping ----------------------------------------------------


@pytest.mark.django_db
# SITE_NAME pinned (todo 649 finding 2): the exact subject must not depend on
# a SITE_NAME a dev .env may set.
@override_settings(SITE_URL=SITE, API_PUBLIC_URL=API, SITE_NAME="Houseplant MD")
def test_security_notices_keep_their_meaning():
    verify = verification()
    linked = provider_linked()
    reset = password_reset()

    assert verify.subject == "Confirm your email for Houseplant MD"
    for part in (verify.body, _html(verify)):
        assert "/verify-email?key=" in part
        assert "works for 3 days, and only while signed in" in part
        assert "If it wasn't you, don't open the link" in part.replace("&#x27;", "'")
    assert "Google sign-in was connected" in linked.subject
    for part in (linked.body, _html(linked)):
        assert f"{API}/accounts/password/reset/" in part
        assert "other devices and browsers were signed out" in part
    for part in (reset.body, _html(reset)):
        assert re.search(r"/accounts/password/reset/key/\S+", part)
    assert "Your password won" in _html(reset)


@pytest.mark.django_db
@override_settings(SITE_URL=SITE, API_PUBLIC_URL=API)
def test_security_notices_escape_the_username():
    for build, suffix in ((verification, "1"), (provider_linked, "2")):
        message = build(HOSTILE + suffix)
        html = _html(message)
        assert HOSTILE not in html, build.__name__
        assert f"&lt;script&gt;x&lt;/script&gt;{suffix}" in html, build.__name__
        # Plain text is not HTML: the name reads as typed there.
        assert f'"{HOSTILE}{suffix}"' in message.body, build.__name__


# --- optional vs required mail -----------------------------------------------


@pytest.mark.django_db
@override_settings(SITE_URL=SITE, API_PUBLIC_URL=API)
def test_optional_mail_keeps_its_unsubscribe_link_and_headers():
    reply = forum_reply()
    issue = newsletter_issue()
    digest = forum_digest()

    for message in (reply, issue, digest):
        header = message.extra_headers["List-Unsubscribe"]
        link = header.strip("<>")
        assert link.startswith(API) or link.startswith(SITE), header
        assert message.extra_headers["List-Unsubscribe-Post"] == (
            "List-Unsubscribe=One-Click"
        )
    assert f"{SITE}/unsubscribe?token=" in _html(reply)
    assert f"{SITE}/settings" in reply.body
    assert "Unsubscribe from this digest" in _html(digest)
    assert f"{SITE}/newsletter/unsubscribe?token=" in issue.body


@pytest.mark.django_db
@override_settings(SITE_URL=SITE, API_PUBLIC_URL=API)
def test_important_event_and_coalesced_mail_read_as_what_they_are():
    event = forum_event()
    coalesced = forum_reply_coalesced()

    assert event.subject == "You were mentioned in: Yellow leaves"
    assert "Fern mentioned you" in event.body
    assert "because you turned it on" in event.body
    assert event.extra_headers["List-Unsubscribe-Post"] == (
        "List-Unsubscribe=One-Click"
    )
    assert coalesced.subject == "3 new replies in: Yellow leaves"
    for part in (coalesced.body, _html(coalesced)):
        assert "3 new replies" in part and "The newest of three." in part


@pytest.mark.django_db
@override_settings(SITE_URL=SITE, API_PUBLIC_URL=API)
def test_required_mail_ignores_optional_mail_preferences():
    service = EmailService()
    opted_out = User(email_notifications=False, forum_notifications=False)
    for required in (
        EmailType.ACCOUNT_VERIFICATION,
        EmailType.PASSWORD_RESET,
        EmailType.SECURITY_ALERT,
    ):
        assert service._should_send_email(opted_out, required), required
    assert not service._should_send_email(opted_out, EmailType.FORUM_REPLY)

    quiet = {"email_notifications": False, "forum_notifications": False}
    for username, deliver in (
        ("quiet-verify", lambda u: deliver_verification_email(u)),
        ("quiet-linked", lambda u: deliver_provider_linked_notice(u, "google")),
        ("quiet-welcome", lambda u: EmailService().send_welcome_email(u)),
    ):
        user = _user(username, **quiet)
        mail.outbox.clear()
        assert deliver(user), username
        assert [m.to for m in mail.outbox] == [[user.email]], username

    # ...while the optional reply email to the same kind of account is held.
    user = _user("quiet-reply", **quiet)
    mail.outbox.clear()
    assert not NotificationService().send_forum_reply_notification(
        user=user,
        topic_title="t",
        reply_author="a",
        reply_excerpt="e",
        topic_url=f"{SITE}/forum/1-b/2-t",
    )
    assert mail.outbox == []


# --- todo 639 follow-ups -------------------------------------------------------


@pytest.mark.django_db
@override_settings(SITE_URL=SITE, API_PUBLIC_URL=API)
def test_required_mail_passes_preferences_through_send_email():
    """Finding 4: drive the preference check through send_email itself (the
    loop above never reaches _should_send_email)."""
    quiet = {"email_notifications": False, "forum_notifications": False}
    user = _user("quiet-required", **quiet)
    service = EmailService()
    mail.outbox.clear()
    for required in (
        EmailType.ACCOUNT_VERIFICATION,
        EmailType.PASSWORD_RESET,
        EmailType.SECURITY_ALERT,
    ):
        assert service.send_email(
            email_type=required,
            recipient=user,
            subject=required,
            template_name="generic_notification",
            respect_preferences=True,
        ), required
    assert not service.send_email(
        email_type=EmailType.FORUM_REPLY,
        recipient=user,
        subject="held",
        template_name="generic_notification",
        respect_preferences=True,
    )
    assert [m.subject for m in mail.outbox] == [
        EmailType.ACCOUNT_VERIFICATION,
        EmailType.PASSWORD_RESET,
        EmailType.SECURITY_ALERT,
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "module, deliver",
    [
        (
            "apps.users.email_verification",
            lambda u: deliver_verification_email(u),
        ),
        (
            "apps.users.account_links",
            lambda u: deliver_provider_linked_notice(u, "google"),
        ),
    ],
)
def test_a_template_error_is_a_failed_send_not_a_raise(module, deliver):
    """Finding 2: False lets the Celery task retry and log its give-up.

    Todo 649 finding 1: the log names the exception's type, never its text,
    which a template error can fill with a context value such as the signed
    link."""
    from unittest import mock

    user = _user(f"broken-{module.rsplit('.', 1)[1]}")
    mail.outbox.clear()
    echoed = "verify-email?key=FAKE-SIGNED-TOKEN"
    with (
        mock.patch(f"{module}.render_to_string", side_effect=ValueError(echoed)),
        mock.patch(f"{module}.logger") as logger,
    ):
        assert deliver(user) is False
    assert mail.outbox == []
    [call] = logger.error.call_args_list
    assert call.args[0].startswith("[EMAIL]") and "ValueError" in call.args[0]
    assert "FAKE-SIGNED-TOKEN" not in call.args[0]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "task_name, module, args",
    [
        ("send_verification_email_task", "apps.users.email_verification", ()),
        ("send_provider_linked_notice_task", "apps.users.account_links", ("google",)),
    ],
)
def test_a_template_error_makes_the_task_retry(task_name, module, args):
    """Todo 649 finding 5: the reason a render failure returns False is that
    the Celery task then retries. ``push_request`` + a mocked ``retry``
    (docs/rules/celery.md), since ``.apply()`` ignores the countdown."""
    from unittest import mock

    from apps.users import tasks
    from celery.exceptions import Retry

    task = getattr(tasks, task_name)
    user = _user(f"retry-{task_name[5:13]}")
    mail.outbox.clear()
    task.push_request(retries=0)
    try:
        with (
            mock.patch(f"{module}.render_to_string", side_effect=ValueError("x")),
            mock.patch.object(task, "retry", side_effect=Retry()) as retry,
            pytest.raises(Retry),
        ):
            task.run(user.pk, *args)
    finally:
        task.pop_request()
    retry.assert_called_once()
    assert mail.outbox == []


@pytest.mark.django_db
@override_settings(SITE_URL=SITE, API_PUBLIC_URL=API, SITE_NAME="Leafy Place")
def test_security_notices_name_the_site_one_way():
    """Finding 8: subject and body both read SITE_NAME."""
    for message in (verification("named1"), provider_linked("named2")):
        assert "Leafy Place" in message.subject
        assert "Leafy Place" in message.body
        assert "Leafy Place" in _html(message)
        for part in (message.subject, message.body, _html(message)):
            assert "Houseplant" not in part


def test_site_name_fallback_is_the_product_name():
    """Finding 8: the name mail falls back to is the one the subjects used."""
    from django.conf import settings

    with override_settings():
        del settings.SITE_NAME
        assert EmailService().site_name == "Houseplant MD"
