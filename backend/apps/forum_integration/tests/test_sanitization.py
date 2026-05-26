from apps.forum_integration.sanitization import sanitize_forum_html
from django.test import SimpleTestCase


class SanitizeForumHtmlTests(SimpleTestCase):
    def test_strips_script_tags(self):
        dirty = "<p>hi</p><script>alert(1)</script>"
        clean = sanitize_forum_html(dirty)
        self.assertNotIn("<script", clean)
        self.assertIn("<p>hi</p>", clean)

    def test_strips_event_handlers_and_js_urls(self):
        self.assertNotIn("onerror", sanitize_forum_html("<img src=x onerror=alert(1)>"))
        self.assertNotIn(
            "javascript:", sanitize_forum_html('<a href="javascript:alert(1)">x</a>')
        )

    def test_keeps_allowed_formatting(self):
        html = (
            '<p><strong>bold</strong> <em>i</em> <a href="https://x.com">link</a></p>'
        )
        clean = sanitize_forum_html(html)
        self.assertIn("<strong>bold</strong>", clean)
        self.assertIn('href="https://x.com"', clean)

    def test_keeps_heading_tags(self):
        html = "<h1>a</h1><h2>b</h2><h3>c</h3><h4>d</h4><h5>e</h5><h6>f</h6>"
        clean = sanitize_forum_html(html)
        for tag in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            self.assertIn(f"<{tag}>", clean)

    def test_keeps_mention_data_attributes(self):
        html = '<span class="mention" data-mention="alice" data-mention-id="42">@alice</span>'
        clean = sanitize_forum_html(html)
        self.assertIn('data-mention="alice"', clean)
        self.assertIn('data-mention-id="42"', clean)

    def test_keeps_code_block(self):
        html = '<pre class="language-python"><code class="language-python">x = 1</code></pre>'
        clean = sanitize_forum_html(html)
        self.assertIn("<pre", clean)
        self.assertIn("<code", clean)

    def test_empty_string_passthrough(self):
        self.assertEqual("", sanitize_forum_html(""))

    def test_none_passthrough(self):
        self.assertIsNone(sanitize_forum_html(None))
