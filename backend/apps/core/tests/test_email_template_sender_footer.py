"""Every email names its sender and gives a postal address (todo 703).

CASL s. 6(2) with SOR/2012-36 s. 2(1)(d), and CAN-SPAM 15 U.S.C.
7704(a)(5)(A)(iii), want both on commercial email. The values are settings
(``EMAIL_SENDER_NAME``, ``EMAIL_SENDER_ADDRESS``) printed by the
``email_sender`` template tags, so this test walks every template under
``backend/**/templates/`` that is an email, renders each file's own source,
and fails when the sender is missing. A new email template cannot ship
without the footer. Email built in code without a template (the security
lockout notice's ``send_mail`` in ``apps/core/security.py``) is outside this
walk; it is account mail, not commercial email.
"""

import re
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.http import HttpResponse
from django.template import engines
from django.template.loader import render_to_string
from django.test import SimpleTestCase, override_settings
from django.urls import include, path

SENDER_NAME = "Sender Test Co"
SENDER_ADDRESS = "123 Test Street, Testville AB T0T 0T0"

BACKEND_DIR = Path(settings.BASE_DIR)
# Directories that hold no template of ours.
SKIP_DIRS = {"venv", ".venv", "node_modules", "staticfiles", "static", "media"}
# A template is an email when it sits under an `email/` or `emails/` folder of
# a templates root: emails/…, account/email/…, wagtail_forum/email/….
EMAIL_PATH = re.compile(r"(^|/)emails?/")


def _template_roots() -> list[Path]:
    roots = []
    for root in BACKEND_DIR.rglob("templates"):
        rel_parts = root.relative_to(BACKEND_DIR).parts
        if root.is_dir() and not SKIP_DIRS.intersection(rel_parts):
            roots.append(root)
    return roots


def email_templates() -> list[tuple[str, Path]]:
    """(name relative to its templates root, file) for every email template.

    Partials (a leading ``_``) are skipped: they are included by the
    templates found here, and the footer partials are what is under test.
    """
    found = []
    for root in _template_roots():
        for file in root.rglob("*"):
            if not file.is_file() or file.suffix not in {".html", ".txt"}:
                continue
            name = file.relative_to(root).as_posix()
            if EMAIL_PATH.search(name) and not file.name.startswith("_"):
                found.append((name, file))
    return sorted(found)


class _User:
    """Enough of a user for the templates that read one."""

    first_name = "Ada"
    username = "ada"
    email = "ada@example.com"
    pk = 1

    def get_username(self):
        return self.username

    def __str__(self):
        return self.username


class _Anything:
    """Any attribute is another ``_Anything``: for objects such as ``post``
    whose fields a template reads, including as a filter's argument (a
    missing filter argument raises rather than rendering empty)."""

    published_date = datetime(2026, 1, 1)
    published_at = datetime(2026, 1, 1)

    def __getattr__(self, name):
        return _Anything()

    def __str__(self):
        return "x"

    def __len__(self):
        return 0

    def __iter__(self):
        return iter(())


def _context() -> dict:
    return {
        "user": _User(),
        "mentioned_user": _User(),
        "post": _Anything(),
        "display_name": "Ada",
        "site_name": "Houseplant MD",
        "site_url": "https://web.example",
        "app_url": "https://web.example",
        "preferences_url": "https://web.example/settings",
        "unsubscribe_url": "https://web.example/unsubscribe?token=t",
        "settings_url": "https://web.example/settings",
        "watched": [],
        "trending": [],
        "posts": [],
    }


def _render(file: Path) -> str:
    return engines["django"].from_string(file.read_text()).render(_context())


def _stub(request, *args, **kwargs):
    return HttpResponse()


# disease_alert.html and forum_digest.html (core) still reverse the retired
# `forum:` and `plant_identification:` URL names, so they cannot render
# against the real URLconf at all. Stub routes let this test reach their
# footer; the dead names are a separate, older bug.
urlpatterns = [
    path(
        "forum/",
        include(
            (
                [
                    path("", _stub, name="index"),
                    path("c/<slug>/", _stub, name="category"),
                    path("t/<int:pk>/", _stub, name="topic"),
                    path("new/", _stub, name="create_topic"),
                    path("recent/", _stub, name="recent_topics"),
                ],
                "forum",
            )
        ),
    ),
    path(
        "diagnosis/",
        include(([path("", _stub, name="diagnosis")], "plant_identification")),
    ),
]


@override_settings(
    EMAIL_SENDER_NAME=SENDER_NAME,
    EMAIL_SENDER_ADDRESS=SENDER_ADDRESS,
    ROOT_URLCONF=__name__,
)
class EveryEmailTemplateNamesTheSenderTests(SimpleTestCase):
    def test_the_walk_finds_the_email_templates(self):
        names = [name for name, _ in email_templates()]
        # A broken walk that finds nothing would pass every assertion below.
        self.assertGreaterEqual(len(names), 25, names)
        for expected in (
            "emails/base.html",
            "emails/welcome_email.txt",
            "emails/newsletter_digest.html",
            "account/email/password_reset_key_message.html",
            "wagtail_forum/email/digest.txt",
        ):
            self.assertIn(expected, names)
        # The forum package's own copies, not only the host's shadows.
        self.assertTrue(
            any("packages/wagtail_forum" in str(p) for _, p in email_templates())
        )

    def test_every_email_template_prints_the_sender_name_and_address(self):
        for _name, file in email_templates():
            with self.subTest(template=str(file.relative_to(BACKEND_DIR))):
                rendered = _render(file)
                self.assertIn(SENDER_NAME, rendered)
                self.assertIn(SENDER_ADDRESS, rendered)

    def test_allauth_text_email_prints_the_sender(self):
        # allauth's own .txt messages live in its package and extend
        # account/email/base_message.txt, which the host shadows.
        rendered = render_to_string(
            "account/email/password_reset_key_message.txt",
            {
                "password_reset_url": "https://web.example/reset"  # pragma: allowlist secret
            },
        )
        self.assertIn(SENDER_NAME, rendered)
        self.assertIn(SENDER_ADDRESS, rendered)

    def test_html_footer_survives_a_template_that_overrides_the_footer_block(self):
        source = (
            '{% extends "emails/base.html" %}{% block footer %}custom{% endblock %}'
        )
        rendered = engines["django"].from_string(source).render({})
        self.assertIn("custom", rendered)
        self.assertIn(SENDER_ADDRESS, rendered)


def _tag(name: str) -> str:
    """Render one footer tag alone: the tag reads the settings itself."""
    source = "{% load email_sender %}{% " + name + " %}"
    return engines["django"].from_string(source).render({})


@override_settings(EMAIL_SENDER_NAME="", EMAIL_SENDER_ADDRESS="")
class BlankSenderTests(SimpleTestCase):
    """Until launch both are blank (todo 724): no empty sender line."""

    def test_text_footer_prints_nothing(self):
        self.assertEqual(_tag("email_sender_footer_text").strip(), "")

    def test_html_footer_prints_nothing(self):
        self.assertEqual(_tag("email_sender_footer").strip(), "")


@override_settings(EMAIL_SENDER_NAME=SENDER_NAME, EMAIL_SENDER_ADDRESS="")
class PartialSenderTests(SimpleTestCase):
    def test_the_tag_reads_the_settings(self):
        self.assertIn(SENDER_NAME, _tag("email_sender_footer_text"))

    def test_name_alone_prints_without_a_dangling_break(self):
        rendered = _tag("email_sender_footer")
        self.assertIn(SENDER_NAME, rendered)
        self.assertNotIn("<br>", rendered)
