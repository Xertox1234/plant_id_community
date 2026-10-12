"""Email links reach a real web route, and text parts are readable (todo 622).

The welcome buttons used ``#!/identify`` and ``#!/forum``: the web app is a
BrowserRouter app routed on the pathname, so both opened the home page. And a
template with no .txt was sent with ``strip_tags(html)`` as its text part,
which kept the whole stylesheet and dropped every button URL.
"""

import re

from apps.core.services.email_service import EmailService, EmailType, html_to_text
from django.conf import settings
from django.core import mail
from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase, override_settings

BACKEND = settings.BASE_DIR
WEB_SRC = BACKEND.parent / "web" / "src"
HREF = re.compile(r'href="([^"]*)"')
EMAIL_TEMPLATE_DIRS = [
    BACKEND / "templates" / "emails",
    BACKEND / "templates" / "account" / "email",
    BACKEND / "templates" / "wagtail_forum" / "email",
    BACKEND / "packages" / "wagtail_forum" / "wagtail_forum" / "templates",
]


@override_settings(SITE_URL="https://web.example/")
class WelcomeLinksTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        self.user = get_user_model().objects.create_user(
            username="newcomer", email="newcomer@example.com", first_name="Nia"
        )
        self.assertTrue(EmailService().send_welcome_email(self.user))
        [self.message] = mail.outbox
        self.html = self.message.alternatives[0][0]

    def test_buttons_open_identify_and_forum_at_the_configured_origin(self):
        hrefs = HREF.findall(self.html)
        self.assertIn("https://web.example/identify", hrefs)
        self.assertIn("https://web.example/forum", hrefs)
        self.assertEqual([h for h in hrefs if "#!" in h or "example//" in h], [])

    def test_text_part_is_written_not_stripped(self):
        body = self.message.body
        self.assertIn("Identify your first plant: https://web.example/identify\n", body)
        self.assertIn("Explore the forums: https://web.example/forum\n", body)
        self.assertIn("Hi Nia,", body)
        for source in (".email-container", "{", "font-family", "<"):
            self.assertNotIn(source, body)


class WebRoutesTests(SimpleTestCase):
    """The paths the emails link to are routes the web app defines, and the app
    routes on the pathname (BrowserRouter), so no ``#!`` link can reach them."""

    def test_email_destinations_are_pathname_routes(self):
        app = (WEB_SRC / "App.tsx").read_text()
        main = (WEB_SRC / "main.tsx").read_text()
        self.assertIn("BrowserRouter", main)
        self.assertNotIn("HashRouter", main + app)
        for path in (
            "/identify",
            "/forum",
            "/forum/:categorySlug/:threadSlug",
            "/blog/:slug",
            "/settings",
            "/unsubscribe",
            "/verify-email",
        ):
            with self.subTest(path=path):
                self.assertIn(f'path="{path}"', app)

    def test_no_email_template_uses_a_hashbang_link(self):
        templates = [
            path
            for directory in EMAIL_TEMPLATE_DIRS
            for path in directory.rglob("*")
            if path.suffix in {".html", ".txt"}
        ]
        self.assertGreater(len(templates), 10, "is the path right?")
        offenders = [str(p) for p in templates if "#!" in p.read_text()]
        self.assertEqual(offenders, [])


class HtmlToTextTests(SimpleTestCase):
    """The fallback for a template with no .txt (owner: keep a safe fallback,
    but never raw strip_tags)."""

    def test_rendered_html_keeps_links_and_drops_the_stylesheet(self):
        html = render_to_string(
            "emails/generic_notification.html",
            {
                "site_name": "Houseplant-MD",
                "notification_title": "Ready",
                "notification_message": "Your result & care notes are ready.",
                "action_url": "https://web.example/identify?a=1&b=2",
                "preferences_url": "https://web.example/settings",
            },
        )
        text = html_to_text(html)

        self.assertIn("View Details (https://web.example/identify?a=1&b=2)", text)
        self.assertIn("Email preferences (https://web.example/settings)", text)
        self.assertIn("Your result & care notes are ready.", text)
        for source in ("<", "{", "font-family", "mso-", "&amp;"):
            self.assertNotIn(source, text)
        self.assertNotIn("\n\n\n", text)

    def test_script_comment_and_anchor_only_links(self):
        text = html_to_text(
            "<html><head><title>T</title></head><body><!-- hidden -->"
            "<script>alert(1)</script><p>Go <a href='#top'>up</a> or "
            '<a href="https://x.example/a">https://x.example/a</a>.</p></body></html>'
        )
        self.assertEqual(text, "Go up or https://x.example/a.\n")


class FallbackSendTests(TestCase):
    def test_a_template_without_txt_is_sent_with_html_to_text(self):
        with override_settings(SITE_URL="https://web.example"):
            sent = EmailService().send_email(
                email_type=EmailType.COMMUNITY_UPDATE,
                recipient="fallback@example.com",
                subject="Fallback",
                template_name="generic_notification",
                context={"action_url": "https://web.example/forum"},
                respect_preferences=False,
            )
        self.assertTrue(sent)
        [message] = mail.outbox
        self.assertIn("View Details (https://web.example/forum)", message.body)
        self.assertNotIn("{", message.body)
        self.assertNotIn("<", message.body)
