"""Admin-editable forum tunables (Wagtail quick wins, item 1).

``ForumSettings`` (a Wagtail generic setting) exposes a handful of
``WAGTAILFORUM_*`` tunables as nullable fields; ``forum_settings.provide`` is
the package's override provider. Precedence: a non-blank DB value, then the
``WAGTAILFORUM_<NAME>`` Django setting, then the package default.

The provider keeps a process memo plus a shared-cache token (see the module
docstring) so steady-state reads cost no DB query. Each test below starts from
a cold memo and leaves the process "known empty" — the row it wrote is rolled
back with the test transaction, and a stale memo would leak that row into
whichever test runs next.
"""

import pytest
from apps.forum_host import forum_settings
from apps.forum_host.models import ForumSettings
from django.core.cache import cache
from django.db import DatabaseError
from django.test import override_settings
from django.urls import reverse
from wagtail_forum import conf
from wagtail_forum.conf import get_setting
from wagtail_forum.models import TrustLevel
from wagtail_forum.spam.heuristic import HeuristicSpamBackend

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _cold_then_known_empty():
    cache.delete(forum_settings.CACHE_KEY)
    forum_settings._memo = None
    yield
    cache.delete(forum_settings.CACHE_KEY)
    # The test's row is rolled back with its transaction; leave the memo in
    # the state a fresh load would produce so later query-count-pinned tests
    # don't pay this process's first-load query inside their counted block.
    forum_settings._memo = (None, {})


def test_provider_is_registered_with_the_package():
    assert forum_settings.provide in conf._override_providers


def test_blank_row_inherits_django_setting_then_default():
    ForumSettings.objects.create()  # every field blank

    with override_settings(WAGTAILFORUM_REPORT_AUTO_HIDE_THRESHOLD=5):
        assert get_setting("REPORT_AUTO_HIDE_THRESHOLD") == 5
    assert get_setting("SPAM_MAX_LINKS") == conf.DEFAULTS["SPAM_MAX_LINKS"]


def test_db_value_wins_over_django_setting():
    ForumSettings.objects.create(report_auto_hide_threshold=1)

    with override_settings(WAGTAILFORUM_REPORT_AUTO_HIDE_THRESHOLD=5):
        assert get_setting("REPORT_AUTO_HIDE_THRESHOLD") == 1


def test_no_row_at_all_inherits():
    assert not ForumSettings.objects.exists()
    assert (
        get_setting("EXPERTS_MIN_TRUST_LEVEL")
        == conf.DEFAULTS["EXPERTS_MIN_TRUST_LEVEL"]
    )


def test_banned_words_are_one_per_line_and_whitespace_only_inherits():
    row = ForumSettings.objects.create(spam_banned_words="  spam \n\n buy now\n")
    assert get_setting("SPAM_BANNED_WORDS") == ["spam", "buy now"]

    row.spam_banned_words = " \n \n"
    row.save()
    with override_settings(WAGTAILFORUM_SPAM_BANNED_WORDS=["x"]):
        assert get_setting("SPAM_BANNED_WORDS") == ["x"]


def test_zero_is_a_real_override_not_blank():
    ForumSettings.objects.create(spam_max_links=0)
    assert get_setting("SPAM_MAX_LINKS") == 0


def test_trust_level_fields_round_trip_as_ints():
    ForumSettings.objects.create(
        experts_min_trust_level=TrustLevel.LEADER,
        trust_autopublish_level=TrustLevel.NEW,
    )
    assert get_setting("EXPERTS_MIN_TRUST_LEVEL") == 4
    assert get_setting("TRUST_AUTOPUBLISH_LEVEL") == 0


def test_save_invalidates_the_memo():
    row = ForumSettings.objects.create(badge_botanist_threshold=3)
    assert get_setting("BADGE_BOTANIST_THRESHOLD") == 3  # memo warm

    row.badge_botanist_threshold = 4
    row.save()

    assert get_setting("BADGE_BOTANIST_THRESHOLD") == 4


def test_delete_invalidates_the_memo():
    row = ForumSettings.objects.create(badge_botanist_threshold=3)
    assert get_setting("BADGE_BOTANIST_THRESHOLD") == 3

    row.delete()

    assert (
        get_setting("BADGE_BOTANIST_THRESHOLD")
        == conf.DEFAULTS["BADGE_BOTANIST_THRESHOLD"]
    )


def test_unmapped_name_never_touches_the_db(django_assert_num_queries):
    with django_assert_num_queries(0):
        get_setting("TOPIC_MAX_TAGS")


def test_steady_state_mapped_read_costs_no_query(django_assert_num_queries):
    ForumSettings.objects.create(spam_max_links=1)
    get_setting("SPAM_MAX_LINKS")  # first read loads + memoises

    with django_assert_num_queries(0):
        assert get_setting("SPAM_MAX_LINKS") == 1
        assert (
            get_setting("REPORT_AUTO_HIDE_THRESHOLD")
            == conf.DEFAULTS["REPORT_AUTO_HIDE_THRESHOLD"]
        )


def test_cross_process_token_forces_a_reload():
    """Another worker saving the row bumps the shared token; this process's
    memo must be dropped even though no local signal fired."""
    row = ForumSettings.objects.create(spam_max_links=1)
    assert get_setting("SPAM_MAX_LINKS") == 1
    ForumSettings.objects.filter(pk=row.pk).update(spam_max_links=2)  # no signal
    assert get_setting("SPAM_MAX_LINKS") == 1  # memo still trusted

    cache.set(forum_settings.CACHE_KEY, "other-worker", None)

    assert get_setting("SPAM_MAX_LINKS") == 2


def test_missing_token_keeps_trusting_the_memo():
    """A flushed cache (cache.clear() in tests, a Redis restart in prod) must
    not turn every read into a DB query."""
    ForumSettings.objects.create(spam_max_links=1)
    assert get_setting("SPAM_MAX_LINKS") == 1
    ForumSettings.objects.update(spam_max_links=2)  # no signal
    cache.delete(forum_settings.CACHE_KEY)

    assert get_setting("SPAM_MAX_LINKS") == 1


def test_db_error_degrades_to_inherit(monkeypatch):
    def boom():
        raise DatabaseError("relation does not exist")

    monkeypatch.setattr(forum_settings, "_load_values", boom)

    assert get_setting("SPAM_MAX_LINKS") == conf.DEFAULTS["SPAM_MAX_LINKS"]


def test_heuristic_spam_backend_honours_the_db_override():
    """End-to-end through a real consumer: with max links 0, one link is spam."""
    ForumSettings.objects.create(spam_max_links=0)

    result = HeuristicSpamBackend().check_text("see https://example.com")

    assert not result.is_clean
    assert result.reason == "Too many links"


def test_settings_edit_page_is_reachable_in_admin(client, django_user_model):
    admin = django_user_model.objects.create_superuser(username="root", email="r@x.io")
    client.force_login(admin)

    resp = client.get(
        reverse("wagtailsettings:edit", args=["forum_host", "forumsettings"]),
        follow=True,
    )

    assert resp.status_code == 200
    assert b"report_auto_hide_threshold" in resp.content


# --- review round 1 (code-review, 2026-09-04) ---------------------------------


def test_shared_token_rotates_only_after_the_save_commits(
    django_capture_on_commit_callbacks,
):
    """post_save fires INSIDE the admin edit view's atomic block. Rotating the
    cross-worker token there lets another worker reload the still-uncommitted
    OLD row under the NEW token and memoise it for good. The local memo reset
    stays synchronous; only the token waits for commit."""
    row = ForumSettings.objects.create(spam_max_links=1)
    assert get_setting("SPAM_MAX_LINKS") == 1
    token_before = cache.get(forum_settings.CACHE_KEY)

    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        row.spam_max_links = 2
        row.save()
        assert cache.get(forum_settings.CACHE_KEY) == token_before
        assert get_setting("SPAM_MAX_LINKS") == 2  # local memo was dropped

    for callback in callbacks:
        callback()
    assert cache.get(forum_settings.CACHE_KEY) != token_before


def test_token_is_written_with_a_finite_ttl(django_capture_on_commit_callbacks):
    """docs/rules/caching.md: never cache without expiry. A missing token is a
    designed-for state, so a TTL costs nothing."""
    from unittest.mock import patch

    from apps.forum_host import constants

    with patch.object(
        forum_settings.cache, "set", wraps=forum_settings.cache.set
    ) as spy:
        # The test itself runs in a transaction, so the on_commit write must
        # be captured and executed explicitly.
        with django_capture_on_commit_callbacks(execute=True):
            forum_settings.invalidate()

    spy.assert_called_once()
    assert spy.call_args.args[2] == constants.FORUM_SETTINGS_TOKEN_TTL_SECONDS > 0


def test_help_text_renders_a_zero_deployment_value_as_zero():
    from apps.forum_host.models import _inherits

    with override_settings(WAGTAILFORUM_SPAM_MAX_LINKS=0):
        text = _inherits("SPAM_MAX_LINKS", "Links.")

    assert text.endswith("(0).")
