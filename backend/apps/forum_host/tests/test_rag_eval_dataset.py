"""Validation of the RAG eval dataset, ``backend/evals/datasets/rag-cases.json``
(todo 694, spec §5 and §8).

A malformed case is caught here, for free, instead of after a run that spent
embeddings. No DB, no network: it reads the JSON file only.
"""

import json
from collections import Counter

import pytest
from apps.forum_host.management.commands.rag_eval import (
    BLOCKED_REASONS,
    CASE_CLASSES,
    COVERED,
    DEFAULT_CASES_PATH,
    validate_cases,
)
from apps.forum_host.rag_guardrails import classify_blocked_question

MIN_CASES = 20


def _data():
    return json.loads(DEFAULT_CASES_PATH.read_text(encoding="utf-8"))


def _cases():
    return validate_cases(_data())


def test_dataset_passes_the_commands_own_schema_check():
    cases = _cases()
    assert len(cases) >= MIN_CASES


def test_every_class_is_represented():
    counts = Counter(case["class"] for case in _cases())
    assert set(counts) == set(CASE_CLASSES)


def test_ids_are_unique():
    ids = [case["id"] for case in _cases()]
    assert len(ids) == len(set(ids))


def test_blocked_class_of_every_case_matches_the_guardrail():
    """Blocked cases come back with their reason; every other case is not
    blocked, so phase 1's failures are about retrieval, never the dataset."""
    for case in _cases():
        got = classify_blocked_question(case["question"])
        assert got == BLOCKED_REASONS.get(case["class"]), case["id"]


def test_covered_cases_name_a_care_topics_slug():
    covered = [case for case in _cases() if case["class"] == COVERED]
    assert covered
    # validate_cases already rejects an unknown slug; pin that it is checked.
    assert all(case["expected_slug"] for case in covered)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda c: c.update({"class": "nonsense"}), "unknown class"),
        (lambda c: c.update({"expected_slug": "no-such-article"}), "care_topics"),
        (lambda c: c.update({"surprise": 1}), "unknown fields"),
        (lambda c: c.pop("question"), "missing fields"),
        (lambda c: c.update({"question": "  "}), "non-empty"),
    ],
)
def test_schema_check_rejects_a_broken_case(mutate, message):
    data = _data()
    covered = next(c for c in data["cases"] if c["class"] == COVERED)
    mutate(covered)
    with pytest.raises(ValueError, match=message):
        validate_cases(data)


def test_schema_check_rejects_a_duplicate_id_and_a_slug_on_a_non_covered_case():
    data = _data()
    data["cases"].append(dict(data["cases"][0]))
    with pytest.raises(ValueError, match="duplicate id"):
        validate_cases(data)

    data = _data()
    other = next(c for c in data["cases"] if c["class"] != COVERED)
    other["expected_slug"] = "root-rot"
    with pytest.raises(ValueError, match="only covered"):
        validate_cases(data)
