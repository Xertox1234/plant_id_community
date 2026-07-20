"""Regression tests for EmailService silent-failure modes (todo 267).

These pin three defects that made EmailService report success when an email did
not actually reach an inbox, plus the .txt-fallback that lets .html-only
templates send at all. They also replace the retired manual
`backend/test_email_templates.py` smoke script (finding 4) with real,
CI-collected coverage.
"""

from apps.core.models import EmailNotification
from apps.core.services.email_service import EmailService, EmailType
from apps.core.services.notification_service import NotificationService
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase

User = get_user_model()

# .html-only templates that render cleanly from the base context alone — used to
# prove the strip_tags(html) fallback for a missing .txt (finding 2). Templates
# that need bespoke context vars (blog_post→`post`, new_forum_topic→`subscriber`)
# or a `{% url %}` namespace not present here (seasonal_care/forum_digest→`forum`,
# disease_alert→`diagnosis`) are intentionally excluded: those .html render
# failures are a PRE-EXISTING issue (masked until now because every one of these
# templates no-op'd at the missing-.txt step), out of scope for this todo — and
# handled non-silently by the .html hard-failure path either way. See the todo's
# Work Log.
FALLBACK_RENDERABLE_TEMPLATES = [
    "welcome_email",
    "plant_care_reminder",
    "newsletter",
    "generic_notification",
]


class SendEmailZeroRecipientsTests(TestCase):
    """Finding 1: send_email() must treat a 0-recipient send() as a failure."""

    def test_blank_recipient_returns_false_and_does_not_track(self):
        # A blank recipient address → EmailMessage.recipients() filters it out →
        # EmailMessage.send() returns 0 WITHOUT raising. Before the fix,
        # send_email() ignored that count, tracked a phantom send, and returned
        # True.
        result = EmailService().send_email(
            email_type=EmailType.NEWSLETTER,
            recipient="",
            subject="Should not send",
            template_name="welcome_email",
            respect_preferences=False,
        )
        self.assertFalse(result)
        self.assertEqual(len(mail.outbox), 0)
        # No phantom tracking row for the message that reached zero inboxes.
        self.assertFalse(
            EmailNotification.objects.filter(subject="Should not send").exists()
        )

    def test_real_recipient_still_returns_true(self):
        user = User.objects.create_user(username="reach", email="reach@example.com")
        result = EmailService().send_email(
            email_type=EmailType.NEWSLETTER,
            recipient=user,
            subject="Delivered",
            template_name="welcome_email",
            respect_preferences=False,
        )
        self.assertTrue(result)
        self.assertEqual(len(mail.outbox), 1)


class TxtFallbackTests(TestCase):
    """Finding 2: a missing .txt must fall back to stripped HTML, not no-op."""

    def test_html_only_templates_fall_back_to_stripped_html(self):
        user = User.objects.create_user(username="tmpl", email="tmpl@example.com")
        for name in FALLBACK_RENDERABLE_TEMPLATES:
            with self.subTest(template=name):
                mail.outbox = []
                result = EmailService().send_email(
                    email_type=EmailType.NEWSLETTER,
                    recipient=user,
                    subject=f"Subject {name}",
                    template_name=name,
                    respect_preferences=False,
                )
                # These templates ship no .txt; before finding 2 they raised
                # TemplateDoesNotExist → silent `return False`. Now they send,
                # with a strip_tags(html) plain-text body.
                self.assertTrue(result, f"{name} failed to send")
                self.assertEqual(len(mail.outbox), 1, f"{name} did not reach outbox")
                self.assertTrue(
                    mail.outbox[0].body.strip(), f"{name} sent an empty text body"
                )

    def test_forum_reply_uses_its_real_txt_template(self):
        # forum_reply is the one EmailType with a real .txt sibling — it must
        # still render that, not the fallback (guards against the fallback
        # shadowing a real .txt).
        user = User.objects.create_user(username="freply", email="fr@example.com")
        result = EmailService().send_email(
            email_type=EmailType.FORUM_REPLY,
            recipient=user,
            subject="Reply",
            template_name="forum_reply",
            context={"topic_title": "Succulents", "author_name": "Greenthumb"},
            respect_preferences=False,
        )
        self.assertTrue(result)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(mail.outbox[0].body.strip())

    def test_missing_html_is_still_a_hard_failure(self):
        # The .txt fallback must NOT mask a genuinely missing .html body.
        result = EmailService().send_email(
            email_type=EmailType.NEWSLETTER,
            recipient="hardfail@example.com",
            subject="No such template",
            template_name="template_that_does_not_exist",
            respect_preferences=False,
        )
        self.assertFalse(result)
        self.assertEqual(len(mail.outbox), 0)


class WelcomeEmailCanaryTests(TestCase):
    """Finding 2 canary: welcome_email has no .txt, so it used to silently
    no-op at the render step for every newly verified user."""

    def test_send_welcome_email_actually_delivers(self):
        user = User.objects.create_user(
            username="welcomed", email="welcomed@example.com", first_name="Wanda"
        )
        result = EmailService().send_welcome_email(user)
        self.assertTrue(result)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(mail.outbox[0].body.strip())


class IdentificationResultContentTests(TestCase):
    """Finding 3: send_identification_result_notification's context keys must
    match identification_result.html's actual vars, so the real values render
    (not a mostly-blank email with empty href="" buttons)."""

    def test_real_values_render_and_no_empty_hrefs(self):
        user = User.objects.create_user(username="ided", email="ided@example.com")
        result = NotificationService().send_identification_result_notification(
            user=user,
            plant_name="Philodendron Brasil",
            confidence=0.92,
            identifier_name="PlantAI",
            result_url="https://plantcommunity.com/identify/result/789",
        )
        self.assertTrue(result)
        self.assertEqual(len(mail.outbox), 1)
        html = mail.outbox[0].alternatives[0][0]
        # The values the sender actually supplies must appear in the body.
        self.assertIn("Philodendron Brasil", html)
        self.assertIn("92.0% confidence", html)
        self.assertIn("PlantAI", html)
        self.assertIn("https://plantcommunity.com/identify/result/789", html)
        # The unsupplied care_guide_url / forum_url references were removed, so
        # no button/link renders with a dangling empty href.
        self.assertNotIn('href=""', html)
