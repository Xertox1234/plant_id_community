"""Tests for the RAG answer record + wrong-answer report loop (todo 289 / M13,
design doc guardrail 5): the host-owned ``RagAnswer``/``RagAnswerReport``
models, the report endpoint, and the CMS moderation listing.

Host-owned rather than the package ``Report`` model: that one hard-FKs a post
or a message (exactly-one check constraint), penalises the CONTENT AUTHOR's
flag count and auto-hides past a threshold — none of which applies to an AI
answer that has no author and was never posted.
"""

import pytest
from apps.forum_host import constants
from apps.forum_host.models import RagAnswer, RagAnswerReport
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import Client, override_settings
from django.urls import reverse
from freezegun import freeze_time
from rest_framework.test import APIClient

User = get_user_model()


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def _answer(user=None, question="how often should I water a pothos"):
    user = user or User.objects.create_user(username="asker")
    return RagAnswer.objects.create(
        user=user,
        question=question,
        answer="Water only when the top inch is dry [1].",
        sources=[{"n": 1, "kind": "blog", "title": "Killed by kindness"}],
        prompt_version=constants.RAG_PROMPT_VERSION,
    )


# --------------------------------------------------------------------------- #
# Models                                                                       #
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_one_report_per_user_per_answer_is_enforced_by_the_database():
    answer = _answer()
    RagAnswerReport.objects.create(answer=answer, reporter=answer.user, detail="wrong")
    with pytest.raises(IntegrityError), transaction.atomic():
        RagAnswerReport.objects.create(
            answer=answer, reporter=answer.user, detail="again"
        )


@pytest.mark.django_db
def test_report_defaults_to_open_and_lists_newest_first():
    answer = _answer()
    first = RagAnswerReport.objects.create(answer=answer, reporter=answer.user)
    other = User.objects.create_user(username="other-reporter")
    second = RagAnswerReport.objects.create(answer=answer, reporter=other)
    assert first.status == RagAnswerReport.Status.OPEN
    assert first.resolved_at is None and first.resolved_by is None
    assert list(RagAnswerReport.objects.all()) == [second, first]


@pytest.mark.django_db
def test_deleting_an_answer_cascades_its_reports():
    answer = _answer()
    RagAnswerReport.objects.create(answer=answer, reporter=answer.user)
    answer.delete()
    assert RagAnswerReport.objects.count() == 0


@pytest.mark.django_db
def test_answer_question_is_truncated_for_the_moderation_list():
    answer = _answer(question="x" * 200)
    report = RagAnswerReport.objects.create(answer=answer, reporter=answer.user)
    assert len(report.answer_question) == constants.RAG_REPORT_QUESTION_PREVIEW_CHARS
    assert report.answer_question.endswith("…")


@pytest.mark.django_db
def test_moderation_queryset_select_relates_every_list_column():
    """The list columns read answer→question, reporter and resolved_by; without
    these legs the CMS list is an N+1 per row. Pinned on the queryset rather than
    a full-page query count: a Wagtail admin page carries dozens of unrelated
    queries that change across Wagtail upgrades."""
    from apps.forum_host.wagtail_hooks import RagAnswerReportViewSet
    from django.test import RequestFactory

    request = RequestFactory().get("/cms/")
    request.user = User.objects.create_superuser(
        username="qs-mod", email="q@example.com"
    )
    qs = RagAnswerReportViewSet().get_queryset(request)
    assert qs.query.select_related == {
        "answer": {"user": {}},
        "reporter": {},
        "resolved_by": {},
    }


# --------------------------------------------------------------------------- #
# POST /forum/care/answers/<id>/report/                                        #
# --------------------------------------------------------------------------- #


def _report_url(answer):
    return f"/api/v1/forum/care/answers/{answer.pk}/report/"


def _client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.mark.django_db
def test_reporting_own_answer_returns_reported_true_and_creates_an_open_report():
    answer = _answer()
    resp = _client_for(answer.user).post(
        _report_url(answer),
        {"detail": "Pothos should not be watered daily"},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.json() == {"reported": True}
    report = RagAnswerReport.objects.get()
    assert (report.answer, report.reporter, report.detail) == (
        answer,
        answer.user,
        "Pothos should not be watered daily",
    )
    assert report.status == RagAnswerReport.Status.OPEN


@pytest.mark.django_db
def test_repeat_report_is_idempotent_200_with_one_row():
    answer = _answer()
    client = _client_for(answer.user)
    assert (
        client.post(_report_url(answer), {"detail": "wrong"}, format="json").status_code
        == 200
    )
    assert (
        client.post(
            _report_url(answer), {"detail": "still wrong"}, format="json"
        ).status_code
        == 200
    )
    assert RagAnswerReport.objects.count() == 1
    assert RagAnswerReport.objects.get().detail == "wrong"  # first report wins


@pytest.mark.django_db
def test_detail_is_optional():
    answer = _answer()
    resp = _client_for(answer.user).post(_report_url(answer), {}, format="json")
    assert resp.status_code == 200
    assert RagAnswerReport.objects.get().detail == ""


@pytest.mark.django_db
def test_reporting_another_users_answer_is_404_not_403():
    """An answer is private to its asker; a 403 would confirm the id exists."""
    answer = _answer()
    stranger = User.objects.create_user(username="stranger")
    resp = _client_for(stranger).post(
        _report_url(answer), {"detail": "x"}, format="json"
    )
    assert resp.status_code == 404
    assert RagAnswerReport.objects.count() == 0


@pytest.mark.django_db
def test_anonymous_report_is_401():
    answer = _answer()
    resp = APIClient().post(_report_url(answer), {"detail": "x"}, format="json")
    assert resp.status_code == 401


@pytest.mark.django_db
def test_overlong_or_non_string_detail_is_400():
    answer = _answer()
    client = _client_for(answer.user)
    too_long = "x" * (constants.RAG_REPORT_DETAIL_MAX_CHARS + 1)
    assert (
        client.post(
            _report_url(answer), {"detail": too_long}, format="json"
        ).status_code
        == 400
    )
    assert (
        client.post(_report_url(answer), {"detail": ["x"]}, format="json").status_code
        == 400
    )
    assert client.post(_report_url(answer), [1, 2], format="json").status_code == 400
    assert RagAnswerReport.objects.count() == 0


@override_settings(FORUM_RAG_ENABLED=False, FORUM_VECTOR_SEARCH_ENABLED=False)
@pytest.mark.django_db
def test_report_endpoint_works_when_the_feature_flags_are_off():
    """Deliberately NOT flag-gated: reporting spends nothing, and turning the
    feature off after a bad answer must not stop the user reporting it."""
    answer = _answer()
    resp = _client_for(answer.user).post(
        _report_url(answer), {"detail": "x"}, format="json"
    )
    assert resp.status_code == 200


@override_settings(FORUM_RATELIMITS={"report_create": "1/h"})
@pytest.mark.django_db
def test_report_is_throttled_per_user_under_the_report_create_rate():
    user = User.objects.create_user(username="reporter")
    first, second = _answer(user), _answer(user, question="second question")
    client = _client_for(user)
    with freeze_time("2026-09-01 12:00:00"):
        assert client.post(_report_url(first), {}, format="json").status_code == 200
        assert client.post(_report_url(second), {}, format="json").status_code == 429


# --------------------------------------------------------------------------- #
# The moderation queue — a CMS snippet listing next to the package's Reports   #
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_moderation_listing_and_inspect_view_show_a_report_to_staff():
    """Guardrail 5 is only real if a human can read what the user saw: the
    list shows the question; the inspect view shows the answer text and the
    sources, without a shell."""
    answer = _answer(question="how often should I water a pothos")
    RagAnswerReport.objects.create(
        answer=answer, reporter=answer.user, detail="Daily is wrong"
    )
    admin = User.objects.create_superuser(username="rag-mod", email="mod@example.com")
    client = Client()
    client.force_login(admin)

    listing = client.get(
        reverse(RagAnswerReport.snippet_viewset.get_url_name("list")), secure=True
    )
    assert listing.status_code == 200
    assert b"how often should I water a pothos" in listing.content

    report = RagAnswerReport.objects.get()
    inspect = client.get(
        reverse(
            RagAnswerReport.snippet_viewset.get_url_name("inspect"), args=(report.pk,)
        ),
        secure=True,
    )
    assert inspect.status_code == 200
    assert b"Water only when the top inch is dry [1]." in inspect.content
    assert b"Killed by kindness" in inspect.content
    assert b"Daily is wrong" in inspect.content
