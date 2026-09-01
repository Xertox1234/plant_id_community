"""Tests for the RAG guardrails (todo 289 / M13): the blocked-question
classifier (guardrail 2), citation validation (guardrail 3) and the
no-information sentinel (guardrail 1).

These are PRODUCT RULES, not model behaviour — pure, deterministic, no LLM —
which is exactly why they can be pinned by a table.
"""

import pytest
from apps.forum_host.rag_guardrails import (
    CHEMICAL_DOSING,
    INGESTION,
    classify_blocked_question,
    is_no_information,
    validate_citations,
)

# --------------------------------------------------------------------------- #
# Guardrail 2 — blocked question classes (signed off 2026-08-29)              #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "question",
    [
        "is pothos toxic to cats",
        "Is this plant poisonous?",
        "can I eat nasturtium leaves",
        "can my dog eat monstera",
        "my dog ate a monstera leaf, what do I do",
        "my toddler just chewed on a philodendron",
        "the cat keeps eating my spider plant, is that ok",
        "is this safe for toddlers",
        "are pothos pet-friendly",
        "which houseplants are safe for cats and dogs",
        "is aloe edible",
        "medicinal uses of aloe vera",
        "how do I make a tincture from echinacea",
        "chamomile herbal tea for sleep",
        "can you get high from this plant",
    ],
)
def test_ingestion_and_toxicity_questions_are_blocked(question):
    assert classify_blocked_question(question) == INGESTION


@pytest.mark.parametrize(
    "question",
    [
        "how much neem oil per gallon of water",
        "imidacloprid dilution ratio for houseplants",
        "how many tsp of copper fungicide per liter",
        "what concentration of insecticidal soap should I use",
        "what's the right dose of systemic insecticide for a monstera",
    ],
)
def test_pesticide_and_chemical_dosing_questions_are_blocked(question):
    assert classify_blocked_question(question) == CHEMICAL_DOSING


@pytest.mark.parametrize(
    "question",
    [
        # Ordinary care — the forum's bread and butter.
        "how often should I water a pothos",
        "why are the leaves on my fiddle leaf fig turning yellow",
        "repotting a snake plant",
        "how much light does a monstera need",
        "how much should I fertilize my pothos in winter",
        # Pests eating the PLANT are not a person or pet eating the plant.
        "something is eating my hostas at night",
        "my basil leaves are being eaten by something",
        "slugs are eating my lettuce, how do I stop them",
        "how do I treat aphids on my tomatoes",
        # A chemical term WITHOUT a dosing term is a fine question.
        "is neem oil safe for pothos leaves?",
        "does insecticidal soap work on spider mites",
        # Words that look like the blocked classes but are not.
        "cat-proof shelf for my plants",
        "compost tea for tomatoes",
        "natural remedy for powdery mildew",
        "",
    ],
)
def test_ordinary_care_questions_are_not_blocked(question):
    assert classify_blocked_question(question) is None


def test_classifier_is_case_and_punctuation_insensitive():
    assert classify_blocked_question("IS POTHOS TOXIC TO CATS?!") == INGESTION
    assert (
        classify_blocked_question("How much NEEM OIL, per gallon??") == CHEMICAL_DOSING
    )


# --------------------------------------------------------------------------- #
# Guardrail 3 — citation validation                                           #
# --------------------------------------------------------------------------- #


def test_valid_markers_survive_and_are_listed():
    text, valid = validate_citations(
        "Water less [1]. Yellow leaves mean too much [2].", 2
    )
    assert text == "Water less [1]. Yellow leaves mean too much [2]."
    assert valid == [1, 2]


def test_invented_indices_are_dropped_from_the_text():
    """A model can invent a passage number; a marker that resolves to nothing
    would be a citation to nowhere, so it is removed rather than rendered."""
    text, valid = validate_citations("Water less [1]. Feed monthly [7].", 2)
    assert text == "Water less [1]. Feed monthly."
    assert valid == [1]


def test_comma_lists_keep_only_valid_members():
    text, valid = validate_citations("Water less [1, 9]. Prune in spring [3,2].", 3)
    assert text == "Water less [1]. Prune in spring [3, 2]."
    assert valid == [1, 2, 3]


def test_zero_valid_citations_returns_an_empty_list():
    """The caller suppresses the answer on an empty list — a citation-free
    answer is exactly the ungrounded output this feature must not emit."""
    text, valid = validate_citations("Water less [4]. Feed monthly [5].", 2)
    assert valid == []
    assert "[" not in text


def test_answer_without_any_marker_has_no_valid_citations():
    _, valid = validate_citations("Water less often.", 3)
    assert valid == []


# --------------------------------------------------------------------------- #
# Guardrail 1 — the no-information sentinel                                   #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "reply",
    ["NO_INFORMATION", "  no_information.\n", '"NO_INFORMATION"', "No_Information!"],
)
def test_no_information_sentinel_is_detected_with_whitespace_and_punctuation(reply):
    assert is_no_information(reply) is True


@pytest.mark.parametrize(
    "reply",
    [
        "There is no information on watering [1].",
        "NO_INFORMATION about light, but [1]",
        "",
    ],
)
def test_prose_is_not_the_sentinel(reply):
    assert is_no_information(reply) is False
