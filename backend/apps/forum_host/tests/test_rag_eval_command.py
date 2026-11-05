"""Tests for ``manage.py rag_eval``, the judge-free RAG eval (todo 694, spec §5).

Retrieval is faked at ``apps.forum_host.rag.retrieve_grounding_passages``, so
the real ``answer_question`` and its guardrails run, but no embedding is made.
The test runner forces ``DEBUG=False``, so the happy-path tests opt in with
``override_settings(DEBUG=True)`` and one test pins the DEBUG refusal.
"""

import json
import os
import subprocess
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from apps.forum_host import vector_indexes as vi
from apps.forum_host.management.commands import rag_eval
from apps.forum_host.rag_retrieval import Passage
from django.conf import settings
from django.core.cache import cache
from django.core.management import CommandError, call_command
from django.test import override_settings
from django_ai_core.contrib.index.storage.pgvector.models import PgVectorEmbedding

from .test_rag import RETRIEVE

DEV = dict(DEBUG=True, FORUM_VECTOR_SEARCH_ENABLED=True)
LLM_SERVICE = "wagtail_ai.agents.base.get_llm_service"


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for name in rag_eval.RAILWAY_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    cache.clear()
    yield
    cache.clear()


def _seed_blog_chunks():
    PgVectorEmbedding.objects.create(
        index_name=vi._index_name(vi.BlogChunks),
        document_key="blog.BlogPostPage:1:0",
        content="water a pothos when the top inch is dry",
        vector=[1.0] + [0.0] * 7,
    )


def _blog(slug, score, n=1):
    return Passage(
        n=n,
        kind="blog",
        pk=n,
        score=score,
        title=slug,
        date="2026-05-01",
        text=f"About {slug}.",
        snippet=slug,
        slug=slug,
        anchor="block-0",
    )


def _fake_retrieval(by_question):
    """``question -> (passages | None, top_scores)``; anything else -> []."""

    def fake(question, *, user=None, floor=None, top_scores=None):
        passages, scores = by_question.get(
            question, ([], {"BlogChunks": 0.30, "SimilarTopics": None})
        )
        if top_scores is not None:
            top_scores.update(scores)
        return passages

    return fake


def _cases_file(tmp_path, cases):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps({"cases": cases}), encoding="utf-8")
    return path


SMALL_CASES = [
    {
        "id": "covered-hit",
        "class": "covered",
        "question": "How often should I water a pothos?",
        "expected_slug": "pothos-care-guide",
    },
    {
        "id": "covered-miss",
        "class": "covered",
        "question": "Why are my leaf tips brown?",
        "expected_slug": "brown-leaf-tips",
    },
    {"id": "adj", "class": "adjacent", "question": "How do I water air plants?"},
    {"id": "off", "class": "off-corpus", "question": "When do I aerate a lawn?"},
    {
        "id": "blk-ing",
        "class": "blocked-ingestion",
        "question": "Are the berries on my plant edible?",
    },
    {
        "id": "blk-chem",
        "class": "blocked-chemical",
        "question": "How many millilitres of neem oil per litre should I spray?",
    },
    {
        "id": "notblk",
        "class": "not-blocked",
        "question": "Is softened tap water toxic to plants?",
    },
]

SMALL_RETRIEVAL = {
    "How often should I water a pothos?": (
        [_blog("pothos-care-guide", 0.81), _blog("root-rot", 0.62, n=2)],
        {"BlogChunks": 0.81, "SimilarTopics": 0.50},
    ),
    "Why are my leaf tips brown?": (
        [_blog("signs-of-overwatering", 0.55)],
        {"BlogChunks": 0.55, "SimilarTopics": None},
    ),
    "How do I water air plants?": (
        [_blog("bottom-watering-houseplants", 0.48)],
        {"BlogChunks": 0.48, "SimilarTopics": 0.40},
    ),
    "When do I aerate a lawn?": ([], {"BlogChunks": 0.41, "SimilarTopics": 0.38}),
}


def _run(*args):
    out = StringIO()
    call_command("rag_eval", *args, stdout=out)
    return out.getvalue()


# --------------------------------------------------------------------------- #
# Happy path                                                                   #
# --------------------------------------------------------------------------- #


@override_settings(**DEV)
@pytest.mark.django_db
def test_prints_the_per_case_table_and_a_pass_count_per_class(tmp_path):
    _seed_blog_chunks()
    path = _cases_file(tmp_path, SMALL_CASES)
    with patch(RETRIEVE, side_effect=_fake_retrieval(SMALL_RETRIEVAL)), patch(
        LLM_SERVICE
    ) as mock_service:
        output = _run("--cases", str(path))
    mock_service.assert_not_called()
    assert "covered: 1/2 passed" in output
    assert "adjacent: 1 reported (not asserted)" in output
    assert "off-corpus: 1/1 passed" in output
    assert "blocked-ingestion: 1/1 passed" in output
    assert "blocked-chemical: 1/1 passed" in output
    assert "not-blocked: 1/1 passed" in output
    assert "covered-hit" in output and "covered-miss" in output
    # weakest covered = 0.81 (the only hit), strongest off-corpus = 0.41, against
    # the default RAG_SIMILARITY_FLOOR (0.5)
    assert "Weakest covered score: 0.810 (margin over floor 0.310)" in output
    assert "Strongest off-corpus score: 0.410 (margin under floor 0.090)" in output


@override_settings(**DEV)
@pytest.mark.django_db
def test_writes_no_row_and_charges_no_rag_budget(tmp_path):
    from apps.forum_host import constants
    from apps.forum_host.models import RagAnswer

    _seed_blog_chunks()
    path = _cases_file(tmp_path, SMALL_CASES)
    with patch(RETRIEVE, side_effect=_fake_retrieval(SMALL_RETRIEVAL)):
        _run("--cases", str(path))
    assert RagAnswer.objects.count() == 0
    assert cache.get(constants.RAG_BUDGET_CACHE_KEY) is None


@override_settings(**DEV)
@pytest.mark.django_db
def test_floor_flag_is_passed_to_retrieval_and_reported(tmp_path):
    _seed_blog_chunks()
    path = _cases_file(tmp_path, SMALL_CASES)
    seen = []

    def fake(question, *, user=None, floor=None, top_scores=None):
        seen.append(floor)
        top_scores.update({"BlogChunks": None, "SimilarTopics": None})
        return []

    with patch(RETRIEVE, side_effect=fake):
        output = _run("--cases", str(path), "--floor", "0.6")
    assert seen and set(seen) == {0.6}
    assert "Floor: 0.600" in output


@override_settings(**DEV)
@pytest.mark.django_db
def test_floor_outside_zero_to_one_is_refused(tmp_path):
    _seed_blog_chunks()
    with pytest.raises(CommandError, match="--floor"):
        _run("--cases", str(_cases_file(tmp_path, SMALL_CASES)), "--floor", "1.5")


@override_settings(**DEV)
@pytest.mark.django_db
def test_json_output_holds_the_summary_and_every_case(tmp_path):
    _seed_blog_chunks()
    path = _cases_file(tmp_path, SMALL_CASES)
    out = tmp_path / "out" / "run.json"
    with patch(RETRIEVE, side_effect=_fake_retrieval(SMALL_RETRIEVAL)):
        _run("--cases", str(path), "--json", str(out))
    data = json.loads(out.read_text(encoding="utf-8"))
    assert [c["id"] for c in data["cases"]] == [c["id"] for c in SMALL_CASES]
    assert data["summary"]["per_class"]["covered"] == {
        "passed": 1,
        "asserted": 2,
        "cases": 2,
    }
    hit = data["cases"][0]
    assert hit["expected_rank"] == 1 and hit["top_blog_chunks"] == 0.81


@override_settings(**DEV)
@pytest.mark.django_db
def test_relative_json_path_lands_under_evals_results(tmp_path, monkeypatch):
    _seed_blog_chunks()
    monkeypatch.setattr(rag_eval, "RESULTS_DIR", tmp_path / "results")
    path = _cases_file(tmp_path, SMALL_CASES)
    with patch(RETRIEVE, side_effect=_fake_retrieval(SMALL_RETRIEVAL)):
        _run("--cases", str(path), "--json", "run.json")
    assert (tmp_path / "results" / "run.json").exists()


@override_settings(**DEV)
@pytest.mark.django_db
def test_the_shipped_dataset_runs_end_to_end():
    """The default --cases: every covered case finds its slug, every other
    class settles as the dataset says."""
    _seed_blog_chunks()
    data = json.loads(rag_eval.DEFAULT_CASES_PATH.read_text(encoding="utf-8"))
    retrieval = {
        case["question"]: (
            [_blog(case["expected_slug"], 0.7)],
            {"BlogChunks": 0.7, "SimilarTopics": None},
        )
        for case in data["cases"]
        if case["class"] in ("covered", "adjacent") and case.get("expected_slug")
    }
    with patch(RETRIEVE, side_effect=_fake_retrieval(retrieval)):
        output = _run()
    assert "covered: 12/12 passed" in output
    assert "off-corpus: 3/3 passed" in output
    assert "blocked-ingestion: 3/3 passed" in output
    assert "blocked-chemical: 2/2 passed" in output
    assert "not-blocked: 3/3 passed" in output


# --------------------------------------------------------------------------- #
# Refusals and aborts                                                          #
# --------------------------------------------------------------------------- #


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=True)
@pytest.mark.django_db
def test_refuses_when_debug_is_false(tmp_path):
    """No DEBUG override here: the test runner's own DEBUG=False is the case."""
    assert settings.DEBUG is False
    _seed_blog_chunks()
    with patch(RETRIEVE) as mock_retrieve, pytest.raises(CommandError, match="DEBUG"):
        _run("--cases", str(_cases_file(tmp_path, SMALL_CASES)))
    mock_retrieve.assert_not_called()


@override_settings(**DEV)
@pytest.mark.django_db
@pytest.mark.parametrize("var", rag_eval.RAILWAY_ENV_VARS)
def test_refuses_when_a_railway_environment_is_detected(tmp_path, monkeypatch, var):
    monkeypatch.setenv(var, "production")
    _seed_blog_chunks()
    with patch(RETRIEVE) as mock_retrieve, pytest.raises(CommandError, match="Railway"):
        _run("--cases", str(_cases_file(tmp_path, SMALL_CASES)))
    mock_retrieve.assert_not_called()


@override_settings(DEBUG=True, FORUM_VECTOR_SEARCH_ENABLED=False)
@pytest.mark.django_db
def test_refuses_when_vector_search_is_off(tmp_path):
    _seed_blog_chunks()
    with patch(RETRIEVE) as mock_retrieve, pytest.raises(
        CommandError, match="FORUM_VECTOR_SEARCH_ENABLED"
    ):
        _run("--cases", str(_cases_file(tmp_path, SMALL_CASES)))
    mock_retrieve.assert_not_called()


@override_settings(**DEV)
@pytest.mark.django_db
def test_refuses_when_blog_chunks_is_empty(tmp_path):
    # A SimilarTopics row alone does not count: the covered cases need blog.
    PgVectorEmbedding.objects.create(
        index_name=vi._index_name(vi.SimilarTopics),
        document_key="wagtail_forum.Topic:1:0",
        content="a topic",
        vector=[1.0] + [0.0] * 7,
    )
    with patch(RETRIEVE) as mock_retrieve, pytest.raises(
        CommandError, match="BlogChunks"
    ):
        _run("--cases", str(_cases_file(tmp_path, SMALL_CASES)))
    mock_retrieve.assert_not_called()


@override_settings(**DEV)
@pytest.mark.django_db
def test_unavailable_retrieval_aborts_the_run(tmp_path):
    _seed_blog_chunks()
    retrieval = dict(SMALL_RETRIEVAL)
    retrieval["When do I aerate a lawn?"] = (None, {})
    with patch(RETRIEVE, side_effect=_fake_retrieval(retrieval)), pytest.raises(
        CommandError, match="unavailable for case off"
    ):
        _run("--cases", str(_cases_file(tmp_path, SMALL_CASES)))


@override_settings(**DEV)
@pytest.mark.django_db
def test_a_malformed_dataset_is_refused_before_any_retrieval(tmp_path):
    _seed_blog_chunks()
    bad = [{"id": "x", "class": "covered", "question": "q", "expected_slug": "nope"}]
    with patch(RETRIEVE) as mock_retrieve, pytest.raises(
        CommandError, match="care_topics"
    ):
        _run("--cases", str(_cases_file(tmp_path, bad)))
    mock_retrieve.assert_not_called()


def test_eval_results_directory_is_gitignored():
    results = Path(settings.BASE_DIR) / "evals" / "results" / "run.json"
    # A git hook (the pytest-staged pre-commit run) exports GIT_DIR, which
    # makes a child git treat its cwd (backend/) as the repo top and skip
    # the root .gitignore. Drop every GIT_* variable so git finds the repo
    # from cwd as it does in a plain run.
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    proc = subprocess.run(
        ["git", "check-ignore", "-q", str(results)],
        cwd=settings.BASE_DIR,
        env=env,
        check=False,
    )
    assert proc.returncode == 0, "backend/evals/results/ must be in .gitignore"


@override_settings(**DEV)
@pytest.mark.django_db
def test_blog_chunks_not_searching_aborts_the_run(tmp_path):
    """SimilarTopics alone searched: the off-corpus case must not read as a
    pass against a blog corpus that was never checked (review round 1)."""
    _seed_blog_chunks()
    retrieval = dict(SMALL_RETRIEVAL)
    retrieval["When do I aerate a lawn?"] = ([], {"SimilarTopics": 0.38})
    with patch(RETRIEVE, side_effect=_fake_retrieval(retrieval)), pytest.raises(
        CommandError, match="BlogChunks could not search for case off"
    ):
        _run("--cases", str(_cases_file(tmp_path, SMALL_CASES)))


@override_settings(**DEV)
@pytest.mark.django_db
def test_a_topic_passage_gives_a_non_covered_case_no_expected_rank():
    topic = Passage(
        n=1,
        kind="topic",
        pk=7,
        score=0.66,
        title="Air plants",
        date="2026-05-01",
        text="Soak them weekly.",
        snippet="Soak",
    )
    case = {"id": "adj", "class": "adjacent", "question": "How do I water air plants?"}
    fake = _fake_retrieval(
        {case["question"]: ([topic], {"BlogChunks": None, "SimilarTopics": 0.66})}
    )
    with patch(RETRIEVE, side_effect=fake):
        row = rag_eval.evaluate_case(case, 0.45)
    assert row["expected_rank"] is None
    assert row["expected_score"] is None


@override_settings(**DEV)
@pytest.mark.django_db
def test_an_also_accepts_slug_passes_a_covered_case_and_sets_its_margin(tmp_path):
    _seed_blog_chunks()
    case = {
        "id": "rot",
        "class": "covered",
        "question": "My snake plant base is mushy.",
        "expected_slug": "root-rot",
        "also_accepts": ["signs-of-overwatering"],
    }
    passages = [
        _blog("snake-plant-care-guide", 0.6, n=1),
        _blog("signs-of-overwatering", 0.54, n=2),
    ]
    fake = _fake_retrieval(
        {case["question"]: (passages, {"BlogChunks": 0.6, "SimilarTopics": None})}
    )
    with patch(RETRIEVE, side_effect=fake):
        row = rag_eval.evaluate_case(case, 0.5)
        output = _run("--cases", str(_cases_file(tmp_path, [case])))
    assert row["pass"] is True
    assert row["expected_rank"] is None  # root-rot itself was not retrieved
    assert row["matched_slug"] == "signs-of-overwatering"
    assert row["expected_score"] == 0.54
    assert "   -*  PASS" in output
    assert "also_accepts" in output


@override_settings(**DEV)
@pytest.mark.django_db
def test_the_expected_slug_outranking_an_accepted_one_is_the_match():
    case = {
        "id": "rot",
        "class": "covered",
        "question": "My snake plant base is mushy.",
        "expected_slug": "root-rot",
        "also_accepts": ["signs-of-overwatering"],
    }
    passages = [_blog("signs-of-overwatering", 0.7, n=1), _blog("root-rot", 0.6, n=2)]
    fake = _fake_retrieval(
        {case["question"]: (passages, {"BlogChunks": 0.7, "SimilarTopics": None})}
    )
    with patch(RETRIEVE, side_effect=fake):
        row = rag_eval.evaluate_case(case, 0.5)
    # The best-ranked accepted slug sets the margin; the primary keeps its rank.
    assert row["expected_rank"] == 2
    assert row["matched_slug"] == "signs-of-overwatering"
    assert row["expected_score"] == 0.7


@pytest.mark.parametrize("slug", [["pothos-care-guide"], {"a": 1}, 3])
def test_a_non_string_expected_slug_is_a_value_error(slug):
    data = {
        "cases": [
            {"id": "c", "class": "covered", "question": "q", "expected_slug": slug}
        ]
    }
    with pytest.raises(ValueError, match="care_topics"):
        rag_eval.validate_cases(data)


def test_a_question_with_surrounding_whitespace_is_refused():
    data = {"cases": [{"id": "n", "class": "not-blocked", "question": " water? "}]}
    with pytest.raises(ValueError, match="whitespace"):
        rag_eval.validate_cases(data)


@override_settings(**DEV)
@pytest.mark.django_db
def test_similar_topics_not_searching_aborts_the_run(tmp_path):
    """The mirror of the BlogChunks case (review round 2): an unchecked topic
    corpus must not let an off-corpus case pass."""
    _seed_blog_chunks()
    retrieval = dict(SMALL_RETRIEVAL)
    retrieval["When do I aerate a lawn?"] = ([], {"BlogChunks": 0.41})
    with patch(RETRIEVE, side_effect=_fake_retrieval(retrieval)), pytest.raises(
        CommandError, match="SimilarTopics could not search for case off"
    ):
        _run("--cases", str(_cases_file(tmp_path, SMALL_CASES)))


@override_settings(**DEV)
@pytest.mark.django_db
@pytest.mark.parametrize("flag", [(), ("--rewrite",), ("--no-rewrite",)])
def test_rewrite_flag_reaches_answer_question_and_the_summary(tmp_path, flag):
    _seed_blog_chunks()
    case = {"id": "c", "class": "covered", "question": "q", "expected_slug": "root-rot"}
    seen = []

    def fake(question, *, user=None, floor=None, top_scores=None, extra_queries=()):
        seen.append(extra_queries)
        top_scores.update({"BlogChunks": 0.6, "SimilarTopics": None})
        return [_blog("root-rot", 0.6)]

    out = tmp_path / "run.json"
    with patch(RETRIEVE, side_effect=fake), patch(
        "apps.forum_host.rag.generate_ai_text", return_value="root rot"
    ) as llm:
        output = _run(
            "--cases", str(_cases_file(tmp_path, [case])), "--json", str(out), *flag
        )
    on = flag == ("--rewrite",)  # the default follows RAG_QUERY_REWRITE_ENABLED: off
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["summary"]["rewrite"] is on
    assert data["cases"][0]["rewritten"] == ("root rot" if on else None)
    assert seen == [("root rot",) if on else ()]
    assert llm.called is on
    assert ("Query rewrite: on" in output) is on
