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
# The old brand spelling (todo 649), built so this file never matches its own guard.
OLD_BRAND = "Houseplant" + "-MD"
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
                "site_name": "Houseplant MD",
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


class HtmlToTextPreheaderAndDataHrefTests(SimpleTestCase):
    """Todo 639 findings 1 and 7."""

    def test_the_hidden_preheader_is_not_body_text(self):
        # base.html alone: its default preheader and default content.
        html = render_to_string("emails/base.html", {})
        self.assertIn("Stay connected with your plant community", html)
        text = html_to_text(html)
        self.assertNotIn("Stay connected", text)
        self.assertIn("This is a default email template.", text)

    def test_data_href_is_never_read_as_the_link(self):
        text = html_to_text('<p><a data-href="x" href="https://y.example">L</a></p>')
        self.assertEqual(text, "L (https://y.example)\n")

    def test_a_hidden_style_holding_the_other_quote_is_still_hidden(self):
        """Todo 649 finding 3: the style value may contain the other quote."""
        for html in (
            "<div style=\"font-family:'x'; display:none\">Preview</div><p>Body</p>",
            "<div style='font-family:\"x\"; display:none'>Preview</div><p>Body</p>",
        ):
            with self.subTest(html=html):
                self.assertEqual(html_to_text(html), "Body\n")

    def test_a_hidden_div_holding_a_nested_div_is_hidden_whole(self):
        """Todo 649 finding 3: nested divs are counted, not cut at the first
        closing tag."""
        html = (
            '<div style="display: none">Pre <div>inner</div> tail</div>'
            "<div>Body</div>"
        )
        self.assertEqual(html_to_text(html), "Body\n")


class OldBrandSpellingTests(SimpleTestCase):
    """Todo 649 finding 4 (owner decision 2026-10-12): the product is
    "Houseplant MD". The hyphenated spelling is gone from backend code and
    templates, so no default, template or feed can mail or serve it again."""

    SKIP_DIRS = {"venv", ".venv", "node_modules", "staticfiles", "__pycache__", "media"}

    def test_the_old_spelling_is_gone_from_backend_code_and_templates(self):
        files = [
            path
            for path in BACKEND.rglob("*")
            if path.suffix in {".py", ".html", ".txt"}
            and path.is_file()
            and not self.SKIP_DIRS.intersection(path.relative_to(BACKEND).parts)
        ]
        self.assertGreater(len(files), 100, "is the path right?")
        offenders = [
            str(path.relative_to(BACKEND))
            for path in files
            if OLD_BRAND in path.read_text(errors="ignore")
        ]
        self.assertEqual(offenders, [])


# SITE_NAME pinned (todo 649 finding 2): a dev .env may still set the old name.
@override_settings(SITE_URL="https://web.example/", SITE_NAME="Houseplant MD")
class BlogPostLayoutTests(TestCase):
    """Todo 639 finding 6: blog_post.html has no live caller, so the
    per-family tests in apps/users/tests/test_email_presentation.py cannot
    reach it; this sends it through EmailService and applies the same
    mail-safe checks."""

    def test_blog_post_is_mail_safe_and_links_real_routes(self):
        from datetime import datetime, timezone

        post = {
            "title": "Repotting a monstera",
            "slug": "repotting-a-monstera",
            "excerpt": "Roots first.",
            "summary": "",
            "published_date": datetime(2026, 10, 1, tzinfo=timezone.utc),
            "reading_time": 4,
            "author": {"get_full_name": "Fern Gully", "username": "fern"},
            "category": {"name": "Care"},
            "key_points": ["Water less"],
            "tags": [{"name": "aroids"}, {"name": "repotting"}],
        }
        related = [{"title": "Light", "slug": "light", "category": {"name": "Care"}}]
        from django.contrib.auth import get_user_model

        reader = get_user_model().objects.create_user(
            username="reader", email="reader@example.com", first_name="Rae"
        )
        self.assertTrue(
            EmailService().send_email(
                email_type=EmailType.BLOG_POST,
                recipient=reader,
                subject="New post",
                template_name="blog_post",
                context={"post": post, "related_posts": related},
                respect_preferences=False,
            )
        )
        [message] = mail.outbox
        html = message.alternatives[0][0]
        body = html.partition("<body")[2]

        self.assertIn('role="presentation"', body)
        self.assertNotIn("display: flex", html)
        self.assertNotIn("inline-flex", html)
        self.assertNotIn("gradient", html)
        hrefs = HREF.findall(html)
        self.assertNotIn("", hrefs)
        self.assertEqual([h for h in hrefs if "#!" in h or "example//" in h], [])
        for url in (
            "https://web.example/blog/repotting-a-monstera",
            "https://web.example/blog/light",
            "https://web.example/blog",
            "https://web.example/forum",
            "https://web.example/settings",
        ):
            self.assertIn(url, hrefs)
            self.assertIn(url, message.body)
        for tag in re.findall(r"<a\b[^>]*>", html):
            self.assertRegex(tag, r'style="[^"]*(?<![-\w])color:')
        self.assertNotIn(OLD_BRAND, html)
        # The preheader (the excerpt) is not where the text part opens.
        self.assertFalse(message.body.startswith("Roots first."))
