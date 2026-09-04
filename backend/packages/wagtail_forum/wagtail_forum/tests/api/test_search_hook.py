"""``SearchView.record_search`` — the host hook for query-hit logging
(Wagtail quick wins, item 5). The package view calls it with the query
*after* its own bounding (max chars, max terms), so a host that logs hits
records what was actually searched, and only when there was a query."""

import pytest
from django.test import override_settings
from rest_framework.test import APIRequestFactory
from wagtail_forum.api.views import SearchView

pytestmark = pytest.mark.django_db


class _Spy(SearchView):
    seen = None

    def record_search(self, request, *, query, page):
        _Spy.seen.append((query, page))


@pytest.fixture(autouse=True)
def _reset_spy():
    _Spy.seen = []


def _get(params):
    return _Spy.as_view()(APIRequestFactory().get("/forum/search/", params))


def test_hook_receives_the_bounded_query_and_the_page():
    with override_settings(WAGTAILFORUM_SEARCH_MAX_QUERY_CHARS=5):
        resp = _get({"q": "abcdefgh", "page": "3"})

    assert resp.status_code == 200
    assert _Spy.seen == [("abcde", 3)]


def test_hook_is_not_called_for_an_empty_query():
    resp = _get({"q": "   "})

    assert resp.status_code == 200
    assert _Spy.seen == []


def test_default_hook_is_a_noop():
    assert SearchView().record_search(None, query="x", page=1) is None
