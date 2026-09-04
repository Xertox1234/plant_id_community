"""``get_setting`` resolution order (Wagtail quick wins, item 1).

A host may register an *override provider* — a callable ``provider(name)``
that returns a value or ``conf.MISSING``. Providers are consulted before the
``WAGTAILFORUM_<NAME>`` Django setting, which is consulted before the package
default. The package never imports the host (``test_reusability``); the host
plugs itself in at ``AppConfig.ready()``.
"""

import pytest
from django.test import override_settings
from wagtail_forum import conf
from wagtail_forum.conf import (
    MISSING,
    get_setting,
    register_override_provider,
    unregister_override_provider,
)


@pytest.fixture
def provider():
    """Register a provider for the test and always unregister it after."""
    registered = []

    def register(fn):
        register_override_provider(fn)
        registered.append(fn)
        return fn

    yield register
    for fn in registered:
        unregister_override_provider(fn)


def test_provider_value_wins_over_django_setting(provider):
    provider(lambda name: 7 if name == "SPAM_MAX_LINKS" else MISSING)
    with override_settings(WAGTAILFORUM_SPAM_MAX_LINKS=5):
        assert get_setting("SPAM_MAX_LINKS") == 7


def test_missing_falls_back_to_django_setting_then_default(provider):
    provider(lambda name: MISSING)
    with override_settings(WAGTAILFORUM_SPAM_MAX_LINKS=5):
        assert get_setting("SPAM_MAX_LINKS") == 5
    assert get_setting("SPAM_MAX_LINKS") == conf.DEFAULTS["SPAM_MAX_LINKS"]


def test_provider_value_is_deep_copied(provider):
    words = ["a"]
    provider(lambda name: words if name == "SPAM_BANNED_WORDS" else MISSING)

    got = get_setting("SPAM_BANNED_WORDS")
    got.append("b")

    assert words == ["a"]


def test_unknown_name_raises_before_consulting_providers(provider):
    seen = []
    provider(lambda name: seen.append(name) or MISSING)

    with pytest.raises(KeyError):
        get_setting("NOT_A_SETTING")

    assert seen == []


def test_register_is_idempotent_and_unregister_removes(provider):
    def fn(name):
        return 9 if name == "SPAM_MAX_LINKS" else MISSING

    provider(fn)
    register_override_provider(fn)  # second registration is a no-op
    assert get_setting("SPAM_MAX_LINKS") == 9

    unregister_override_provider(fn)  # one unregister undoes both
    assert get_setting("SPAM_MAX_LINKS") == conf.DEFAULTS["SPAM_MAX_LINKS"]


def test_unregister_unknown_provider_is_a_noop():
    unregister_override_provider(lambda name: MISSING)
