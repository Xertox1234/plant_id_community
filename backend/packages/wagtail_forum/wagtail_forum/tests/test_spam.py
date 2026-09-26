from types import SimpleNamespace
from unittest import mock

import pytest
from wagtail_forum.blocks import ForumBodyBlock
from wagtail_forum.conf import get_setting
from wagtail_forum.spam import get_spam_backend
from wagtail_forum.spam.base import extract_text
from wagtail_forum.spam.heuristic import URL_RE as URL_COUNT
from wagtail_forum.spam.heuristic import HeuristicSpamBackend


class _FakeBody:
    """Mimic a StreamValue: iterating yields blocks with a .value."""

    def __init__(self, text):
        self._blocks = [SimpleNamespace(value=text)]

    def __iter__(self):
        return iter(self._blocks)


def test_default_backend_is_heuristic():
    assert isinstance(get_spam_backend(), HeuristicSpamBackend)


def test_clean_text_passes():
    obj = SimpleNamespace(title="Hello", body=_FakeBody("a normal post"))
    assert get_spam_backend().check(obj).is_clean is True


def test_too_many_links_flagged():
    spammy = "http://a.com http://b.com http://c.com http://d.com http://e.com"
    obj = SimpleNamespace(title="", body=_FakeBody(spammy))
    result = HeuristicSpamBackend().check(obj)
    assert result.is_clean is False
    assert "link" in result.reason.lower()


def test_banned_word_flagged(settings):
    settings.WAGTAILFORUM_SPAM_BANNED_WORDS = ["casino"]
    obj = SimpleNamespace(title="Win big", body=_FakeBody("visit my Casino now"))
    result = get_spam_backend().check(obj)
    assert result.is_clean is False
    assert "casino" in result.reason.lower()


def test_opening_post_text_includes_topic_title(settings):
    # A Post has no title field; the topic title (user input on the same create
    # request) must be screened with the opening post or title spam publishes
    # unscreened (audit M1).
    settings.WAGTAILFORUM_SPAM_BANNED_WORDS = ["casino"]
    post = SimpleNamespace(
        is_opening_post=True,
        topic=SimpleNamespace(title="Best casino deals"),
        body=_FakeBody("a perfectly normal body"),
    )
    result = get_spam_backend().check(post)
    assert result.is_clean is False
    assert "casino" in result.reason.lower()


def test_check_text_screens_already_flattened_text(settings):
    # check() delegates to check_text() so a composite backend can flatten a
    # StreamField body once and screen the same string with both passes.
    settings.WAGTAILFORUM_SPAM_BANNED_WORDS = ["casino"]
    result = HeuristicSpamBackend().check_text("visit my Casino now")
    assert result.is_clean is False
    assert "casino" in result.reason.lower()


def test_check_text_and_check_agree_on_the_same_object(settings):
    settings.WAGTAILFORUM_SPAM_BANNED_WORDS = ["casino"]
    backend = HeuristicSpamBackend()
    obj = SimpleNamespace(title="Win big", body=_FakeBody("visit my Casino now"))

    via_obj = backend.check(obj)
    via_text = backend.check_text(backend.extract_text(obj))

    assert via_obj.is_clean == via_text.is_clean is False
    assert via_obj.reason == via_text.reason


@pytest.mark.django_db
def test_extract_text_flattens_an_embed_to_its_url_without_the_finder():
    # Todo 426: str(EmbedValue) is its provider HTML, so flattening an embed
    # block with str() looked the URL up in the embed cache and, on a miss,
    # fetched it from the provider in the middle of spam screening.
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    body = ForumBodyBlock().to_python(
        [
            {"type": "paragraph", "value": "<p>watch this</p>"},
            {"type": "embed", "value": url},
        ]
    )
    post = SimpleNamespace(body=body)
    with mock.patch(
        "wagtail.embeds.embeds.get_finder_for_embed",
        side_effect=AssertionError("extract_text must not call an embed finder"),
    ) as finder:
        text = extract_text(post)
    finder.assert_not_called()
    assert url in text
    assert "<iframe" not in text


def test_default_autopublish_level_is_member():
    assert get_setting("TRUST_AUTOPUBLISH_LEVEL") == 2


def test_get_setting_returns_isolated_copies():
    # Mutating a returned mutable default must NOT poison the shared DEFAULTS,
    # so the next read still sees the pristine default (guards the deepcopy fix).
    first = get_setting("SPAM_BANNED_WORDS")
    first.append("injected")
    assert get_setting("SPAM_BANNED_WORDS") == []


def _card_body(*blocks):
    return SimpleNamespace(body=ForumBodyBlock().to_python(list(blocks)))


def test_extract_text_flattens_a_link_card_to_its_url():
    # Todo 428: a card's title and description were written by the linked
    # page, not the author — screening them could reject a post for a
    # stranger's words (and the page chose them, not the member).
    url = "https://example.com/page"
    post = _card_body(
        {
            "type": "link_preview",
            "value": {
                "url": url,
                "title": "casino jackpot",
                "description": "casino",
                "image": "",
                "site_name": "x",
                "domain": "example.com",
            },
        }
    )
    text = extract_text(post)
    assert url in text
    assert "casino" not in text


def test_an_autolinked_url_counts_as_one_link():
    # The server auto-links bare URLs (todo 428), storing each as
    # <a href="X">X</a>: two typed links must not read as four.
    html = (
        '<p><a href="https://a.example/" rel="nofollow">https://a.example/</a> and '
        '<a href="https://b.example/?x=1&amp;y=2">https://b.example/?x=1&amp;y=2</a>'
        "</p>"
    )
    post = _card_body({"type": "paragraph", "value": html})
    text = extract_text(post)
    assert len(URL_COUNT.findall(text)) == 2
    assert HeuristicSpamBackend().check(post).is_clean is True


def test_a_link_hiding_its_address_still_counts():
    html = (
        '<p><a href="https://spam.example/">click</a> '
        '<a href="https://spam.example/2">https://other.example/</a></p>'
    )
    text = extract_text(_card_body({"type": "paragraph", "value": html}))
    assert "https://spam.example/" in text
    assert "https://spam.example/2" in text


def test_four_distinct_autolinked_urls_are_still_too_many():
    links = " ".join(
        f'<a href="https://s{n}.example/">https://s{n}.example/</a>' for n in range(4)
    )
    post = _card_body({"type": "paragraph", "value": f"<p>{links}</p>"})
    assert HeuristicSpamBackend().check(post).is_clean is False
