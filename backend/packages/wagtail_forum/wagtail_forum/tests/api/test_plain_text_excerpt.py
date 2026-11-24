"""``plain_text_excerpt``: what search hits, the home peek, reply emails, the
moderation queues and the AI features show of a post (F139)."""

from types import SimpleNamespace

import pytest
from wagtail_forum.api.views import plain_text_excerpt


def _excerpt(*blocks, limit=200):
    raw = [{"type": kind, "value": value} for kind, value in blocks]
    return plain_text_excerpt(SimpleNamespace(raw_data=raw), limit)


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ("<p>Sun &amp; shade<br/>Water weekly</p>", "Sun & shade Water weekly"),
        ("<p>one</p><p>two</p>", "one two"),
        ("<ul><li>a</li><li>b</li></ul><p>c</p>", "a b c"),
        ("<p>list</p>tail<ul><li>a</li></ul>", "list tail a"),
        ("<p>a&nbsp;&nbsp;b</p>", "a b"),
        ("<p>&nbsp;</p>", ""),
        # Inline tags join nothing and split nothing.
        ("<p>un<b>believ</b>able, <i>really</i>.</p>", "unbelievable, really."),
        # Escaped markup is text the author typed: it stays, as text.
        ("<p>use &lt;b&gt; not &amp;lt;</p>", "use <b> not &lt;"),
    ],
)
def test_paragraph_text_reads_as_written(html, expected):
    assert _excerpt(("paragraph", html)) == expected


def test_plain_text_blocks_keep_their_literal_text():
    # Heading, quote, post_quote and code are plain text by contract: an
    # entity in one is what the author typed, so it is not decoded.
    assert (
        _excerpt(
            ("heading", "A &amp; B"),
            ("quote", "C &lt; D"),
            ("post_quote", {"post": 1, "text": "E &amp; F"}),
            ("code", {"language": "html", "code": "&nbsp;"}),
        )
        == "A &amp; B C &lt; D E &amp; F &nbsp;"
    )


def test_the_limit_counts_decoded_text():
    assert _excerpt(("paragraph", "<p>&amp;&amp;&amp;&amp;</p>"), limit=3) == "&&&"


# strip_tags refuses this (SuspiciousOperation): a member may type it in a
# quote, and an excerpt that raises stops the erasure of their account.
HOSTILE = "<a" * 60 + "x" * 1000


@pytest.mark.parametrize("kind", ["quote", "heading", "paragraph"])
def test_text_that_strip_tags_refuses_is_still_excerpted(kind):
    assert _excerpt((kind, HOSTILE), limit=50).startswith("<a<a")
