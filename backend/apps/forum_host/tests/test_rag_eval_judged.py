"""Tests for ``manage.py rag_eval_judged``, the judged RAG eval (spec §6-7).

Retrieval is faked at ``apps.forum_host.rag.retrieve_grounding_passages`` and
both provider clients are fakes, so the real ``answer_question`` and its
guardrails run with no network call and no spend. The test runner forces
``DEBUG=False``, so the happy-path tests opt in with ``override_settings``.
"""

import json
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from apps.forum_host import constants
from apps.forum_host.management.commands import rag_eval
from apps.forum_host.management.commands import rag_eval_judged as judged
from apps.forum_host.rag_retrieval import Passage
from django.core.cache import cache
from django.core.management import CommandError, call_command
from django.test import override_settings

from .test_rag import RETRIEVE

DEV = dict(DEBUG=True, FORUM_VECTOR_SEARCH_ENABLED=True)
FAKE_KEY = "test-not-a-real-key"
PROD_MODEL = "gpt-4o-mini"
NEW_MODEL = "gpt-candidate"
PRICES = {**constants.EVAL_PRICES_PER_MTOK, NEW_MODEL: (0.15, 0.60)}

Q_POTHOS = "How often should I water a pothos?"
Q_AIR = "How do I water air plants?"
CASES = [
    {
        "id": "covered-pothos",
        "class": "covered",
        "question": Q_POTHOS,
        "expected_slug": "pothos-care-guide",
    },
    {"id": "adj-air", "class": "adjacent", "question": Q_AIR},
    {"id": "off", "class": "off-corpus", "question": "When do I aerate a lawn?"},
]


def _blog(slug, n=1, pk=None):
    return Passage(
        n=n,
        kind="blog",
        pk=pk or n,
        score=0.8,
        title=slug,
        date="2026-05-01",
        text=f"About {slug}.",
        snippet=slug,
        slug=slug,
        anchor="block-0",
    )


def _retrieval(by_question):
    def fake(question, *, user=None, floor=None, top_scores=None):
        if top_scores is not None:
            top_scores.update({"BlogChunks": 0.8, "SimilarTopics": None})
        result = by_question.get(question, [])
        return result() if callable(result) else result

    return fake


RETRIEVAL = {Q_POTHOS: [_blog("pothos-care-guide")], Q_AIR: [_blog("air")]}


class FakeOpenAI:
    """``replies[model]`` is the text each model returns (or a callable of
    the prompt). Usage is fixed at 1000 in / 100 out per call."""

    def __init__(self, replies, usage=(1000, 100)):
        self.replies = replies
        self.usage = usage
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, *, model, messages, timeout=None):
        self.calls.append(model)
        reply = self.replies[model]
        text = reply(messages[0]["content"]) if callable(reply) else reply
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
            usage=SimpleNamespace(
                prompt_tokens=self.usage[0], completion_tokens=self.usage[1]
            ),
        )


def _verdict(g, r, s):
    return {
        "groundedness": {"score": g, "reason": "g"},
        "relevance": {"score": r, "reason": "r"},
        "safety": {"score": s, "reason": "s"},
    }


class FakeJudge:
    """``scores(answer) -> verdict dict`` (or a raw string). Usage is fixed
    at 3000 in / 1000 out per call."""

    def __init__(self, scores, stop_reason="end_turn", usage=(3000, 1000)):
        self.scores = scores
        self.stop_reason = stop_reason
        self.usage = usage
        self.calls = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        content = kwargs["messages"][0]["content"]
        answer = content.split("----- ANSWER -----\n")[1].split("\n----- END")[0]
        verdict = self.scores(answer)
        text = verdict if isinstance(verdict, str) else json.dumps(verdict)
        return SimpleNamespace(
            stop_reason=self.stop_reason,
            content=[SimpleNamespace(type="text", text=text)],
            usage=SimpleNamespace(
                input_tokens=self.usage[0], output_tokens=self.usage[1]
            ),
        )


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for name in rag_eval.RAILWAY_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(judged, "anthropic_api_key", lambda: FAKE_KEY)
    monkeypatch.setattr(judged, "blog_chunks_empty", lambda: False)
    monkeypatch.setattr(judged, "production_model", lambda: PROD_MODEL)
    monkeypatch.setattr(constants, "EVAL_PRICES_PER_MTOK", PRICES)
    cache.clear()
    yield
    cache.clear()


def _cases_file(tmp_path, cases=CASES):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps({"cases": cases}), encoding="utf-8")
    return path


def _run(tmp_path, openai_client, judge_client, *args, retrieval=RETRIEVAL):
    out = StringIO()
    with (
        patch(RETRIEVE, side_effect=_retrieval(retrieval)),
        patch.object(judged, "make_openai_client", return_value=openai_client),
        patch.object(judged, "make_judge_client", return_value=judge_client),
        override_settings(**DEV),
    ):
        call_command(
            "rag_eval_judged",
            "--new-model",
            NEW_MODEL,
            "--cases",
            str(_cases_file(tmp_path)),
            "--json",
            str(tmp_path / "out.json"),
            *args,
            stdout=out,
        )
    return out.getvalue(), json.loads((tmp_path / "out.json").read_text())


def _good(model_answer):
    return {PROD_MODEL: model_answer, NEW_MODEL: model_answer}


# --------------------------------------------------------------------------- #
# Refusals: nothing is called


def test_refuses_without_anthropic_key(tmp_path, monkeypatch):
    monkeypatch.setattr(judged, "anthropic_api_key", lambda: "")
    openai_client, judge_client = FakeOpenAI({}), FakeJudge(lambda a: _verdict(9, 9, 9))
    with pytest.raises(CommandError, match="ANTHROPIC_API_KEY"):
        _run(tmp_path, openai_client, judge_client)
    assert openai_client.calls == [] and judge_client.calls == []


def test_refuses_when_debug_off(tmp_path):
    with pytest.raises(CommandError, match="DEBUG is False"):
        call_command("rag_eval_judged", "--new-model", NEW_MODEL, stdout=StringIO())


def test_refuses_on_railway(tmp_path, monkeypatch):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    with pytest.raises(CommandError, match="Railway"):
        _run(tmp_path, FakeOpenAI({}), FakeJudge(lambda a: _verdict(9, 9, 9)))


def test_refuses_an_unpriced_model(tmp_path, monkeypatch):
    monkeypatch.setattr(
        constants, "EVAL_PRICES_PER_MTOK", constants.EVAL_PRICES_PER_MTOK.copy()
    )
    del constants.EVAL_PRICES_PER_MTOK[NEW_MODEL]
    openai_client = FakeOpenAI({})
    with pytest.raises(CommandError, match=f"no price for {NEW_MODEL}"):
        _run(tmp_path, openai_client, FakeJudge(lambda a: _verdict(9, 9, 9)))
    assert openai_client.calls == []


def test_refuses_when_the_projection_is_over_the_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(constants, "EVAL_SPEND_CAP_USD", 0.01)
    openai_client, judge_client = FakeOpenAI({}), FakeJudge(lambda a: _verdict(9, 9, 9))
    with pytest.raises(CommandError, match="projected cost"):
        _run(tmp_path, openai_client, judge_client)
    assert openai_client.calls == [] and judge_client.calls == []


def test_projection_scales_with_cases_and_runs():
    models = (PROD_MODEL, NEW_MODEL)
    one = judged.project_cost(1, 1, models)
    assert one > 0
    assert judged.project_cost(4, 3, models) == pytest.approx(one * 12)


# --------------------------------------------------------------------------- #
# The comparison


def test_judges_both_arms_on_covered_and_adjacent_only(tmp_path):
    openai_client = FakeOpenAI(_good("Water when the top inch is dry [1]."))
    judge_client = FakeJudge(lambda a: _verdict(8, 7, 10))
    out, result = _run(tmp_path, openai_client, judge_client)

    assert [r["id"] for r in result["cases"]] == ["covered-pothos", "adj-air"]
    assert openai_client.calls == [PROD_MODEL, NEW_MODEL] * 2
    assert len(judge_client.calls) == 4
    s = result["summary"]
    assert s["means"]["old"] == {"groundedness": 8, "relevance": 7, "safety": 10}
    assert s["means"]["new"] == s["means"]["old"]
    assert s["regressions"] == []
    assert s["deltas"]["covered-pothos"] == {
        "groundedness": 0,
        "relevance": 0,
        "safety": 0,
    }
    assert s["old_model"] == PROD_MODEL and s["new_model"] == NEW_MODEL
    assert "Regressions (new lower by 2+): 0" in out


def test_judge_sees_the_exact_prompt_and_pinned_settings(tmp_path):
    openai_prompts = []

    def reply(prompt):
        openai_prompts.append(prompt)
        return "Water weekly [1]."

    judge_client = FakeJudge(lambda a: _verdict(9, 9, 9))
    _run(tmp_path, FakeOpenAI({PROD_MODEL: reply, NEW_MODEL: reply}), judge_client)

    call = judge_client.calls[0]
    assert call["model"] == constants.EVAL_JUDGE_MODEL == "claude-sonnet-5-5"
    assert call["output_config"]["effort"] == constants.EVAL_JUDGE_EFFORT
    assert call["output_config"]["format"]["schema"] == judged.JUDGE_SCHEMA
    assert openai_prompts[0] in call["messages"][0]["content"]


def test_lists_a_regression_of_two_or_more(tmp_path):
    replies = {PROD_MODEL: "Old answer [1].", NEW_MODEL: "New answer [1]."}
    judge_client = FakeJudge(
        lambda a: _verdict(9, 9, 9) if a.startswith("Old") else _verdict(6, 8, 9)
    )
    out, result = _run(tmp_path, FakeOpenAI(replies), judge_client)

    regs = result["summary"]["regressions"]
    assert {(r["id"], r["dimension"], r["delta"]) for r in regs} == {
        ("covered-pothos", "groundedness", -3),
        ("adj-air", "groundedness", -3),
    }
    assert "covered-pothos: groundedness -3.00" in out


def test_invented_citation_fails_the_arm_and_is_not_judged(tmp_path):
    # answer_question would strip [7] and keep [1]: only the raw reply shows it.
    replies = {PROD_MODEL: "Fine [1].", NEW_MODEL: "Fine [1], also [7]."}
    judge_client = FakeJudge(lambda a: _verdict(9, 9, 9))
    _out, result = _run(tmp_path, FakeOpenAI(replies), judge_client)

    new = result["cases"][0]["arms"]["new"]
    assert new["passed"] is False
    assert "[7]" in new["failure"]
    assert new["scores"] is None
    assert result["summary"]["counts"]["new"]["assertion_failures"] == 2
    assert len(judge_client.calls) == 2  # the old arm only, both cases


def test_passages_only_is_counted_not_judged(tmp_path):
    replies = {
        PROD_MODEL: "Fine [1].",
        NEW_MODEL: constants.RAG_NO_INFORMATION_SENTINEL,
    }
    judge_client = FakeJudge(lambda a: _verdict(9, 9, 9))
    _out, result = _run(tmp_path, FakeOpenAI(replies), judge_client)

    counts = result["summary"]["counts"]["new"]
    assert counts["passages_only"] == 2
    assert counts["judged"] == 0
    assert counts["assertion_failures"] == 0
    assert result["summary"]["deltas"] == {}


def test_a_case_whose_arms_saw_different_passages_is_not_judged(tmp_path):
    seen = iter([[_blog("pothos-care-guide")], [_blog("root-rot", pk=9)]])
    retrieval = {Q_POTHOS: lambda: next(seen), Q_AIR: [_blog("air")]}
    judge_client = FakeJudge(lambda a: _verdict(9, 9, 9))
    _out, result = _run(
        tmp_path, FakeOpenAI(_good("Fine [1].")), judge_client, retrieval=retrieval
    )

    assert result["cases"][0]["note"] == judged.PASSAGE_MISMATCH
    assert result["summary"]["passage_mismatches"] == 1
    assert len(judge_client.calls) == 2  # adj-air only


def test_no_information_case_is_reported_not_reached(tmp_path):
    retrieval = {Q_POTHOS: [_blog("pothos-care-guide")]}  # Q_AIR -> []
    openai_client = FakeOpenAI(_good("Fine [1]."))
    _out, result = _run(
        tmp_path,
        openai_client,
        FakeJudge(lambda a: _verdict(9, 9, 9)),
        retrieval=retrieval,
    )

    air = result["cases"][1]["arms"]
    assert air["old"]["status"] == judged.NOT_REACHED
    assert air["old"]["passed"] is None
    assert openai_client.calls == [PROD_MODEL, NEW_MODEL]


def test_generation_failure_is_an_unscored_failure(tmp_path):
    def boom(prompt):
        raise RuntimeError("provider down")

    replies = {PROD_MODEL: "Fine [1].", NEW_MODEL: boom}
    _out, result = _run(
        tmp_path, FakeOpenAI(replies), FakeJudge(lambda a: _verdict(9, 9, 9))
    )

    new = result["cases"][0]["arms"]["new"]
    assert new["status"] == judged.GENERATION_FAILED
    assert new["passed"] is False


def test_retrieval_unavailable_aborts(tmp_path):
    with pytest.raises(CommandError, match="Retrieval was unavailable"):
        _run(
            tmp_path,
            FakeOpenAI(_good("Fine [1].")),
            FakeJudge(lambda a: _verdict(9, 9, 9)),
            retrieval={Q_POTHOS: None},
        )


@pytest.mark.parametrize(
    "verdict,stop_reason",
    [
        (_verdict(9, 9, 11), "end_turn"),
        ("not json", "end_turn"),
        (_verdict(9, 9, 9), "max_tokens"),
        (_verdict(9, 9, 9), "refusal"),
    ],
)
def test_an_unusable_verdict_marks_the_arm_judge_failed(tmp_path, verdict, stop_reason):
    judge_client = FakeJudge(lambda a: verdict, stop_reason=stop_reason)
    _out, result = _run(tmp_path, FakeOpenAI(_good("Fine [1].")), judge_client)

    arm = result["cases"][0]["arms"]["old"]
    assert arm["status"] == judged.JUDGE_FAILED
    assert arm["scores"] is None
    assert result["summary"]["counts"]["old"]["judge_failed"] == 2


# --------------------------------------------------------------------------- #
# Spend


def test_spend_is_measured_from_usage(tmp_path):
    _out, result = _run(
        tmp_path, FakeOpenAI(_good("Fine [1].")), FakeJudge(lambda a: _verdict(9, 9, 9))
    )
    gen = judged.call_cost(PROD_MODEL, 1000, 100)
    judge_call = judged.call_cost(constants.EVAL_JUDGE_MODEL, 3000, 1000)
    s = result["summary"]
    assert s["calls"] == 8
    assert s["spent_usd"] == pytest.approx(4 * gen + 4 * judge_call)
    assert s["stopped_at_cap"] is False


def test_stops_after_the_call_that_crosses_the_cap(tmp_path, monkeypatch):
    # The projection passes, but each judge call really costs $0.20.
    monkeypatch.setattr(constants, "EVAL_SPEND_CAP_USD", 0.30)
    monkeypatch.setattr(constants, "EVAL_EST_JUDGE_OUTPUT_TOKENS", 1)
    monkeypatch.setattr(constants, "EVAL_EST_JUDGE_INPUT_TOKENS", 1)
    judge_client = FakeJudge(lambda a: _verdict(9, 9, 9), usage=(0, 20_000))
    out = StringIO()
    with (
        patch(RETRIEVE, side_effect=_retrieval(RETRIEVAL)),
        patch.object(
            judged, "make_openai_client", return_value=FakeOpenAI(_good("Fine [1]."))
        ),
        patch.object(judged, "make_judge_client", return_value=judge_client),
        override_settings(**DEV),
        pytest.raises(CommandError, match="passed the \\$0.30 cap"),
    ):
        call_command(
            "rag_eval_judged",
            "--new-model",
            NEW_MODEL,
            "--cases",
            str(_cases_file(tmp_path)),
            stdout=out,
        )
    # $0.20 after the first judge call, $0.40 after the second: stop there.
    assert len(judge_client.calls) == 2
    assert "Spent $0.4" in out.getvalue()


def test_runs_repeat_and_average_the_paired_difference(tmp_path):
    scores = iter([9, 6, 9, 9, 9, 8, 9, 9])  # old/new alternating per call
    judge_client = FakeJudge(lambda a: _verdict(next(scores), 9, 9))
    _out, result = _run(
        tmp_path, FakeOpenAI(_good("Fine [1].")), judge_client, "--runs", "2"
    )

    assert [r["run"] for r in result["cases"]] == [1, 1, 2, 2]
    # covered-pothos: run 1 delta -3, run 2 delta -1 -> mean -2: a regression.
    assert result["summary"]["deltas"]["covered-pothos"]["groundedness"] == -2
    assert [r["id"] for r in result["summary"]["regressions"]] == ["covered-pothos"]
