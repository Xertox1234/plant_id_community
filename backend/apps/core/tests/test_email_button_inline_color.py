"""Email buttons carry their colors inline.

Gmail paints a link its own blue unless the color is on the ``<a>`` itself:
the ``.btn-primary`` rule in ``emails/base.html`` still gave the button its
green background, so the newsletter confirmation showed blue text on green.
"""

import re

from django.conf import settings
from django.test import SimpleTestCase

EMAIL_TEMPLATES = settings.BASE_DIR / "templates" / "emails"
BUTTON = re.compile(r'<a\b[^>]*\bclass="btn\b[^"]*"[^>]*>')


class EmailButtonInlineColorTests(SimpleTestCase):
    def test_every_button_sets_color_and_background_inline(self):
        buttons = {
            path.name: BUTTON.findall(path.read_text())
            for path in sorted(EMAIL_TEMPLATES.glob("*.html"))
        }
        found = sum(len(tags) for tags in buttons.values())
        self.assertGreater(found, 0, "no email buttons found; is the path right?")
        missing = [
            f"{name}: {tag}"
            for name, tags in buttons.items()
            for tag in tags
            if not re.search(r'style="[^"]*(?<![-\w])color:', tag)
            or "background-color:" not in tag
        ]
        self.assertEqual(missing, [])
