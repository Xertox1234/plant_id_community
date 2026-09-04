"""Forum searches feed Wagtail's search-terms report (Wagtail quick wins, item 5).

The host ``SearchView`` overrides the package's ``record_search`` hook to call
``Query.get(q).add_hit()`` from ``wagtail.contrib.search_promotions``. Only
the first result page counts (paging is the same search), the string is capped
to the ``Query`` column, and a failure to log can never fail the search or
change its cache headers.
"""

import logging

import pytest
from django.apps import apps
from django.core.cache import cache
from rest_framework.test import APIClient
from wagtail.contrib.search_promotions.models import Query, QueryDailyHits
from wagtail.search.utils import MAX_QUERY_STRING_LENGTH

SEARCH = "/api/v1/forum/search/"
LOGGER = "apps.forum_host.search_hits"

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _fresh_ratelimit_counters():
    cache.clear()  # the search throttle is keyed by client IP in the cache


def _hits(query_string):
    return sum(
        QueryDailyHits.objects.filter(query__query_string=query_string).values_list(
            "hits", flat=True
        )
    )


def test_search_promotions_is_installed():
    assert apps.is_installed("wagtail.contrib.search_promotions")


def test_a_search_records_one_hit_for_the_normalised_query():
    resp = APIClient().get(SEARCH, {"q": "  Monstera   Leaf "})

    assert resp.status_code == 200
    assert _hits("monstera leaf") == 1


def test_later_result_pages_do_not_record_hits():
    client = APIClient()
    client.get(SEARCH, {"q": "monstera", "page": 1})
    client.get(SEARCH, {"q": "monstera", "page": 2})

    assert _hits("monstera") == 1


def test_an_empty_query_records_nothing():
    resp = APIClient().get(SEARCH, {"q": "   "})

    assert resp.status_code == 200
    assert Query.objects.count() == 0


def test_the_logged_query_is_capped_to_the_column_length():
    resp = APIClient().get(SEARCH, {"q": "a" * 300})

    assert resp.status_code == 200
    assert Query.objects.get().query_string == "a" * MAX_QUERY_STRING_LENGTH


def test_a_logging_failure_does_not_fail_the_search(monkeypatch, caplog):
    def boom(self, date=None):
        raise RuntimeError("hits table unavailable")

    monkeypatch.setattr(Query, "add_hit", boom)
    # The project's "apps" loggers don't propagate to root (settings.LOGGING),
    # so caplog only sees this logger with its handler attached directly.
    log = logging.getLogger(LOGGER)
    log.addHandler(caplog.handler)
    try:
        with caplog.at_level(logging.WARNING, logger=LOGGER):
            resp = APIClient().get(SEARCH, {"q": "monstera"})
    finally:
        log.removeHandler(caplog.handler)

    assert resp.status_code == 200
    assert resp.json()["topics"] == []
    assert any("monstera" in r.getMessage() for r in caplog.records)


def test_anonymous_search_stays_publicly_cacheable():
    resp = APIClient().get(SEARCH, {"q": "monstera"})

    assert resp["Cache-Control"].startswith("public, s-maxage=")
