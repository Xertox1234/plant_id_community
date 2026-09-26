"""Bare URLs in a paragraph become links on write (todo 428), so a link in
prose is tappable on every client — the mobile composer never links one."""

import pytest
from wagtail_forum.api.sanitize import autolink_rich_text

REL = ' rel="noopener noreferrer nofollow"'


def _a(url, text=None):
    return f'<a href="{url}"{REL}>{text or url}</a>'


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        # Mobile shape: bare text, lines joined by <br>.
        ("see https://x.example/a", f"see {_a('https://x.example/a')}"),
        (
            "https://a.example<br>https://b.example",
            f"{_a('https://a.example')}<br>{_a('https://b.example')}",
        ),
        # Sentence punctuation and a wrapping bracket belong to the prose.
        ("<p>see https://x.example/a.</p>", f"<p>see {_a('https://x.example/a')}.</p>"),
        ("<p>(https://x.example/a)</p>", f"<p>({_a('https://x.example/a')})</p>"),
        # A balanced bracket belongs to the link.
        (
            "<p>https://en.wikipedia.org/wiki/Foo_(bar)</p>",
            f"<p>{_a('https://en.wikipedia.org/wiki/Foo_(bar)')}</p>",
        ),
        # An escaped & round-trips escaped, in the href and the text.
        (
            "<p>https://x.example/?a=1&amp;b=2</p>",
            f"<p>{_a('https://x.example/?a=1&amp;b=2')}</p>",
        ),
        # Already a link: not linked again. A URL in code is code.
        (
            '<p><a href="https://x.example/">https://x.example/</a></p>',
            f"<p>{_a('https://x.example/')}</p>",
        ),
        (
            '<p><a href="https://x.example/">read https://y.example/</a></p>',
            f"<p>{_a('https://x.example/', 'read https://y.example/')}</p>",
        ),
        (
            "<p><code>curl https://x.example/</code></p>",
            "<p><code>curl https://x.example/</code></p>",
        ),
        # No host, no link; other schemes are text.
        ("<p>https:// is a scheme</p>", "<p>https:// is a scheme</p>"),
        ("<p>see https://.</p>", "<p>see https://.</p>"),
        ("<p>ftp://x.example/</p>", "<p>ftp://x.example/</p>"),
        # Text that looks like markup stays text.
        (
            "<p>&lt;b&gt;https://x.example/&lt;/b&gt;</p>",
            f"<p>&lt;b&gt;{_a('https://x.example/')}&lt;/b&gt;</p>",
        ),
    ],
)
def test_autolink(html, expected):
    assert autolink_rich_text(html) == expected


def test_autolink_is_idempotent():
    once = autolink_rich_text("<p>see https://x.example/a, and https://y.example</p>")
    assert autolink_rich_text(once) == once


def test_autolink_output_is_sanitized():
    out = autolink_rich_text(
        '<p onclick="x()">https://x.example/<script>y()</script></p>'
    )
    assert "onclick" not in out
    assert "<script" not in out
    assert _a("https://x.example/") in out
