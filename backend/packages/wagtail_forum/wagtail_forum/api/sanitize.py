import html
from html.parser import HTMLParser
from urllib.parse import urlparse

from rest_framework import serializers

from ..blocks import ForumBodyBlock

# Schemes permitted in rich-text <a href>. Everything else (javascript:, data:,
# vbscript:, file:, ...) is rejected. Relative/anchor hrefs (no scheme) are allowed.
ALLOWED_HREF_SCHEMES = {"http", "https", "mailto"}


class _HrefCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for name, value in attrs:
                if name == "href" and value is not None:
                    self.hrefs.append(value)


def _href_is_safe(href):
    # HTMLParser already decodes HTML entities in attribute values; unescape again
    # defensively, then drop ASCII control/whitespace chars that browsers strip
    # before parsing the scheme (defeats "java\tscript:" / "java&#115;cript:").
    value = html.unescape(href)
    value = "".join(ch for ch in value if ord(ch) > 0x20).strip()
    if value == "" or value.startswith("/") or value.startswith("#"):
        return True  # empty, relative path, or in-page anchor
    scheme = urlparse(value).scheme.lower()
    if scheme == "":
        return True  # relative reference (no scheme)
    return scheme in ALLOWED_HREF_SCHEMES


def validate_forum_body(value):
    """Validate a forum post body (raw StreamField list-of-dicts).

    1. Dry-run to_python so a malformed body is a 400, not a 500.
    2. Reject any rich-text <a href> whose scheme is not allowlisted (stored XSS):
       direct API POSTs bypass the Wagtail editor's href filtering.
    Returns the original value on success; raises serializers.ValidationError otherwise.
    """
    try:
        stream_value = ForumBodyBlock().to_python(value)
    except Exception as exc:  # malformed StreamField payload
        raise serializers.ValidationError({"body": "Invalid post body."}) from exc
    for child in stream_value:
        source = getattr(child.value, "source", None)  # RichText blocks expose .source
        if not source:
            continue
        collector = _HrefCollector()
        collector.feed(source)
        for href in collector.hrefs:
            if not _href_is_safe(href):
                raise serializers.ValidationError(
                    {"body": "Unsafe link scheme in rich text."}
                )
    return value
