"""Tests for ``answer_question``, the RAG pipeline the ask view and
``manage.py rag_eval`` share (todo 694, spec §4).

The view's own responses are pinned by ``test_rag.py`` (unchanged by the
extraction); these pin the side-effect switches the eval depends on.
"""

from unittest.mock import MagicMock, patch

import pytest
from apps.forum_host import constants
from apps.forum_host.models import RagAnswer
from apps.forum_host.rag import (
    STATUS_ANSWERED,
    STATUS_BUDGET_EXHAUSTED,
    STATUS_NO_INFORMATION,
    STATUS_REFERRAL,
    STATUS_RETRIEVED,
    answer_question,
)
from apps.forum_host.rag_guardrails import CHEMICAL_DOSING, INGESTION
from django.contrib.auth import get_user_model
from django.core.cache import cache

from .test_rag import QUESTION, RETRIEVE, _passages

# What generate_ai_text resolves at call time: the completion client itself.
LLM_SERVICE = "wagtail_ai.agents.base.get_llm_service"


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def _exhaust_rag_budget():
    cache.set(constants.RAG_BUDGET_CACHE_KEY, constants.RAG_BUDGET_LIMIT, 3600)


@pytest.mark.django_db
def test_persist_false_charge_false_writes_no_row_and_charges_nothing():
    """The answered path is exercised, so 'no row, no charge' is not vacuous."""
    generate = MagicMock(return_value="Water when dry [1].")
    with patch(RETRIEVE, return_value=_passages(1)):
        outcome = answer_question(
            QUESTION, generate=generate, persist=False, charge=False
        )
    assert outcome.status == STATUS_ANSWERED
    assert outcome.citations == [1]
    assert outcome.answer_id is None
    generate.assert_called_once()
    assert RagAnswer.objects.count() == 0
    assert cache.get(constants.RAG_BUDGET_CACHE_KEY) is None


@pytest.mark.django_db
def test_charge_false_ignores_an_exhausted_budget():
    _exhaust_rag_budget()
    with patch(RETRIEVE, return_value=_passages(1)):
        outcome = answer_question(QUESTION, generate=None, charge=False)
    assert outcome.status == STATUS_RETRIEVED
    assert cache.get(constants.RAG_BUDGET_CACHE_KEY) == constants.RAG_BUDGET_LIMIT


@pytest.mark.django_db
def test_defaults_persist_and_charge_as_the_view_did():
    user = get_user_model().objects.create_user(username="ragasker", is_premium=True)
    generate = MagicMock(return_value="Water when dry [1].")
    with patch(RETRIEVE, return_value=_passages(1)):
        outcome = answer_question(QUESTION, user=user, generate=generate)
    assert outcome.status == STATUS_ANSWERED
    assert RagAnswer.objects.filter(pk=outcome.answer_id, user=user).exists()
    assert cache.get(constants.RAG_BUDGET_CACHE_KEY) == 1


@pytest.mark.django_db
def test_generate_none_returns_after_retrieval_with_zero_completion_calls():
    """Zero calls on the completion client itself (what generate_ai_text
    resolves inside), not on a patched default."""
    passages = _passages(3)
    with patch(RETRIEVE, return_value=passages), patch(LLM_SERVICE) as mock_service:
        outcome = answer_question(QUESTION, generate=None, persist=False, charge=False)
    mock_service.assert_not_called()
    mock_service.return_value.completion.assert_not_called()
    assert outcome.status == STATUS_RETRIEVED
    assert outcome.passages == passages
    assert [p.slug for p in outcome.passages if p.kind == "blog"] == [
        "article-1",
        "article-3",
    ]
    assert RagAnswer.objects.count() == 0


@pytest.mark.django_db
def test_generate_none_with_nothing_above_the_floor_is_no_information():
    with patch(RETRIEVE, return_value=[]), patch(LLM_SERVICE) as mock_service:
        outcome = answer_question(QUESTION, generate=None, persist=False, charge=False)
    assert outcome.status == STATUS_NO_INFORMATION
    mock_service.assert_not_called()


@pytest.mark.django_db
def test_default_generate_is_resolved_at_call_time():
    """No def-time binding: a patch of the module global reaches the default."""
    with patch(RETRIEVE, return_value=_passages(1)), patch(
        "apps.forum_host.rag.generate_ai_text", return_value="ok [1]"
    ) as mock_generate:
        outcome = answer_question(QUESTION, persist=False, charge=False)
    mock_generate.assert_called_once()
    assert outcome.status == STATUS_ANSWERED


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("question", "reason"),
    [
        ("My cat chewed a peace lily leaf. Is she going to be okay?", INGESTION),
        ("How many millilitres of neem oil per litre should I spray?", CHEMICAL_DOSING),
    ],
)
def test_blocked_question_still_gets_its_referral_when_the_budget_is_exhausted(
    question, reason
):
    _exhaust_rag_budget()
    with patch(RETRIEVE) as mock_retrieve:
        outcome = answer_question(question, generate=MagicMock())
    assert outcome.status == STATUS_REFERRAL
    assert outcome.blocked_reason == reason
    assert outcome.referral_message
    mock_retrieve.assert_not_called()


@pytest.mark.django_db
def test_exhausted_budget_returns_budget_exhausted_before_retrieval():
    _exhaust_rag_budget()
    generate = MagicMock()
    with patch(RETRIEVE) as mock_retrieve:
        outcome = answer_question(QUESTION, generate=generate)
    assert outcome.status == STATUS_BUDGET_EXHAUSTED
    mock_retrieve.assert_not_called()
    generate.assert_not_called()


@pytest.mark.django_db
def test_floor_and_top_scores_are_threaded_through_retrieval():
    def fake_retrieve(question, *, user=None, floor=None, top_scores=None):
        assert floor == 0.6
        top_scores.update({"BlogChunks": 0.71, "SimilarTopics": None})
        return []

    with patch(RETRIEVE, side_effect=fake_retrieve):
        outcome = answer_question(
            QUESTION, generate=None, persist=False, charge=False, floor=0.6
        )
    assert outcome.top_scores == {"BlogChunks": 0.71, "SimilarTopics": None}
