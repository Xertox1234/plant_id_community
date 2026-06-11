from types import SimpleNamespace

from wagtail_forum.conf import get_setting
from wagtail_forum.spam import get_spam_backend
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


def test_default_autopublish_level_is_member():
    assert get_setting("TRUST_AUTOPUBLISH_LEVEL") == 2


def test_get_setting_returns_isolated_copies():
    # Mutating a returned mutable default must NOT poison the shared DEFAULTS,
    # so the next read still sees the pristine default (guards the deepcopy fix).
    first = get_setting("SPAM_BANNED_WORDS")
    first.append("injected")
    assert get_setting("SPAM_BANNED_WORDS") == []
