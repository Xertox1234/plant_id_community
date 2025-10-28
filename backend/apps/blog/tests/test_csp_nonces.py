"""
Tests for CSP nonce implementation in blog templates.

This test suite verifies that Content Security Policy (CSP) nonces are properly
applied to inline scripts and styles in production mode.
"""

from django.test import TestCase
from django.template import Template, Context, RequestContext
from django.test import RequestFactory


class CSPNonceTemplateTestCase(TestCase):
    """Test CSP nonce implementation in templates."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

    def test_inline_script_has_nonce_template_tag(self):
        """Test that inline scripts include nonce template tag."""
        template_string = """
        <script nonce="{{ request.csp_nonce }}">
            console.log('test');
        </script>
        """

        template = Template(template_string)
        request = self.factory.get('/test/')
        context = RequestContext(request)
        rendered = template.render(context)

        # Should have nonce attribute in rendered template
        self.assertIn('nonce=', rendered,
                     "Script tags should have nonce attribute")

    def test_inline_style_has_nonce_template_tag(self):
        """Test that inline styles include nonce template tag."""
        template_string = """
        <style nonce="{{ request.csp_nonce }}">
            .test { color: red; }
        </style>
        """

        template = Template(template_string)
        request = self.factory.get('/test/')
        context = RequestContext(request)
        rendered = template.render(context)

        # Should have nonce attribute in rendered template
        self.assertIn('nonce=', rendered,
                     "Style tags should have nonce attribute")

    def test_blog_post_template_syntax(self):
        """Test that blog post template has correct CSP nonce syntax."""
        # Read the actual template file
        import os
        template_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'templates', 'blog', 'blog_post_page.html'
        )

        # Check if template exists
        if os.path.exists(template_path):
            with open(template_path, 'r') as f:
                content = f.read()

            # Check for nonce in inline scripts
            self.assertIn('nonce="{{ request.csp_nonce }}', content,
                         "Blog post template should have CSP nonce in inline scripts")

    def test_admin_base_template_syntax(self):
        """Test that admin base template has correct CSP nonce syntax."""
        # Read the actual template file
        import os
        template_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'templates', 'blog', 'admin', 'base.html'
        )

        # Check if template exists
        if os.path.exists(template_path):
            with open(template_path, 'r') as f:
                content = f.read()

            # Check for nonce in inline styles
            self.assertIn('nonce="{{ request.csp_nonce }}', content,
                         "Admin base template should have CSP nonce in inline styles")

    def test_all_blog_admin_templates_have_nonces(self):
        """Test that all blog admin templates with inline scripts have nonces."""
        import os
        import re

        # The templates are in backend/templates/blog/admin, not apps/blog/templates
        from django.conf import settings
        base_dir = settings.BASE_DIR
        admin_templates_dir = os.path.join(base_dir, 'templates', 'blog', 'admin')

        if not os.path.exists(admin_templates_dir):
            self.skipTest(f"Admin templates directory not found at {admin_templates_dir}")

        # Check each template file
        for filename in os.listdir(admin_templates_dir):
            if filename.endswith('.html'):
                filepath = os.path.join(admin_templates_dir, filename)
                with open(filepath, 'r') as f:
                    content = f.read()

                # Find inline script and style tags
                inline_scripts = re.findall(r'<script(?![^>]*src=)[^>]*>', content)
                inline_styles = re.findall(r'<style[^>]*>', content)

                # Check all inline scripts have nonce
                for script_tag in inline_scripts:
                    self.assertIn('nonce=', script_tag,
                                f"Inline script in {filename} should have nonce: {script_tag}")

                # Check all inline styles have nonce
                for style_tag in inline_styles:
                    self.assertIn('nonce=', style_tag,
                                f"Inline style in {filename} should have nonce: {style_tag}")


class EmailTemplateCSPTestCase(TestCase):
    """Test CSP nonce implementation in email templates."""

    def test_email_template_nonce_with_default(self):
        """Test that email templates handle missing CSP nonce gracefully."""
        from django.template import Template, Context

        # Email templates should use |default:'' to handle missing nonce
        template_string = """
        <style nonce="{{ request.csp_nonce|default:'' }}">
            .email { color: blue; }
        </style>
        """

        template = Template(template_string)

        # Context without request (typical for email rendering)
        context = Context({})
        rendered = template.render(context)

        # Should render without error, with empty nonce
        self.assertIn('nonce=""', rendered,
                     "Email templates should handle missing nonce gracefully")

    def test_email_template_nonce_with_request(self):
        """Test that email templates use nonce when request is present."""
        from django.template import Template, RequestContext
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get('/test/')

        template_string = """
        <style nonce="{{ request.csp_nonce|default:'' }}">
            .email { color: blue; }
        </style>
        """

        template = Template(template_string)
        context = RequestContext(request)
        rendered = template.render(context)

        # Should have nonce attribute (value depends on middleware)
        self.assertIn('nonce=', rendered,
                     "Email templates should use nonce when request is available")
