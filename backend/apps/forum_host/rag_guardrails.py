"""Deterministic guardrails for RAG plant-care answers (todo 289 / M13).

Three of the design doc's five layers live here as PRODUCT RULES — plain
functions with no model in the loop, so they are testable by table and cannot
be talked out of by a prompt:

- Guardrail 2, ``classify_blocked_question``: human/animal ingestion
  (edibility, toxicity, medicinal use) and pesticide/chemical dosing are never
  answered from community content. Classified BEFORE retrieval, so a blocked
  question costs nothing. The class list was reviewed and signed off by a
  human on 2026-08-29 (todo 289 Work Log, gate 4). The patterns are
  deliberately over-inclusive on the harm side — a false referral costs the
  user a rephrase; a false answer about what a toddler can eat costs more —
  but NOT so broad that ordinary care questions ("something is eating my
  hostas") get a poison-control referral; the tests pin both directions.
- Guardrail 3, ``validate_citations``: ``[n]`` markers that resolve to no
  retrieved passage are dropped; the caller suppresses an answer left with
  zero valid citations.
- Guardrail 1, ``is_no_information``: the sentinel the prompt asks for when
  the passages do not answer the question.
"""

import re

from . import constants

INGESTION = "ingestion"
CHEMICAL_DOSING = "chemical_dosing"

# Who might eat/drink the plant — people and companion animals. Pests are
# deliberately absent: "slugs are eating my lettuce" is a care question.
_EATERS = (
    r"(?:i|we|you|they|he|she|someone|"
    r"(?:my|our|the|a|his|her|their)\s+)?"
    r"(?:kids?|children|child|toddlers?|babies|baby|son|daughter|husband|wife|"
    r"friend|dogs?|cats?|pupp(?:y|ies)|kittens?|pets?|rabbits?|bunn(?:y|ies)|"
    r"horses?|birds?|parrots?|hamsters?|guinea\s+pigs?|"
    r"i|we|you|they|he|she|someone)"
)
_INGEST_VERBS = (
    r"(?:eat|eats|eating|ate|eaten|drink|drinks|drinking|drank|drunk|ingest|"
    r"ingests|ingesting|ingested|consume|consumes|consuming|consumed|chew|"
    r"chews|chewing|chewed|nibble|nibbles|nibbling|nibbled|lick|licks|licking|"
    r"licked|swallow|swallows|swallowing|swallowed|taste|tastes|tasting|tasted)"
)
_PROTECTED = (
    r"(?:cats?|dogs?|pets?|kids?|children|toddlers?|babies|humans?|people|"
    r"animals?|rabbits?|birds?|horses?|reptiles?|livestock)"
)

_INGESTION_RE = re.compile(
    r"\b(?:"
    # "can I eat", "is it safe to eat", "can my dog eat"
    rf"(?:can|could|should|may|safe\s+to|ok\s+to|okay\s+to)\s+(?:{_EATERS}\s+)?{_INGEST_VERBS}"
    # "my dog ate", "the cat keeps eating", "my toddler just chewed on" — a
    # person/animal subject within two words of an ingestion verb
    rf"|{_EATERS}\s+(?:\w+\s+){{0,2}}?{_INGEST_VERBS}"
    # toxicity
    # toxicity — but not plant NAMES ("poison ivy") or harm TO plants
    # ("toxic to plants"); both are ordinary care questions.
    r"|toxic(?:ity)?(?!\s+(?:to|for)\s+(?:my\s+|the\s+|house)?plants?\b)"
    r"|poison(?:ous|ed|ing)?(?!\s+(?:ivy|oak|sumac|hemlock)\b)|venomous"
    # "safe for cats", "pet-friendly", "child safe"
    rf"|safe\s+(?:for|around)\s+(?:my\s+|our\s+)?{_PROTECTED}"
    r"|(?:pet|cat|dog|child|kid|baby|toddler|animal)[-\s]?(?:safe|friendly|proof\s+plant)"
    # edibility / medicinal use / recreational use
    r"|edible|inedible|medicinal|medicine|tincture|poultice|salve|decoction"
    r"|herbal\s+tea|tea\s+from|make\s+tea|brew(?:ing)?\s+(?:a\s+)?tea"
    r"|get\s+high|hallucinogen\w*|psychoactive"
    r")\b",
    re.I,
)

# Pesticides, fungicides, herbicides and their common actives. Fertiliser is
# deliberately NOT here: "how much should I fertilize" is ordinary plant care
# and the harm ceiling is the plant's, not a person's.
_CHEMICAL_RE = re.compile(
    r"\b(?:neem|imidacloprid|pyrethr\w+|permethrin|spinosad|malathion|carbaryl|"
    r"glyphosate|roundup|copper\s+(?:fungicide|sulfate|sulphate|soap)|captan|"
    r"chlorothalonil|myclobutanil|fungicides?|pesticides?|insecticides?|"
    r"herbicides?|miticides?|acaricides?|systemic|bacillus\s+thuringiensis|"
    r"insecticidal\s+soap|horticultural\s+oil|dormant\s+oil|bleach)\b",
    re.I,
)
_DOSING_RE = re.compile(
    r"\b(?:how\s+much|how\s+many|how\s+strong|ratio|dilut\w*|concentrat\w*|"
    r"per\s+(?:gallon|gal|liter|litre|quart|pint|cup|l)|tsp|tbsp|teaspoons?|"
    r"tablespoons?|ml|milliliters?|millilitres?|oz|ounces?|ppm|percent|"
    r"dos(?:e|es|age|ing)|mix(?:ing)?\s+rate|strength|amount)\b",
    re.I,
)


def classify_blocked_question(question: str) -> str | None:
    """``INGESTION`` / ``CHEMICAL_DOSING`` for a blocked question, else ``None``."""
    text = " ".join((question or "").split())
    if not text:
        return None
    if _INGESTION_RE.search(text):
        return INGESTION
    if _CHEMICAL_RE.search(text) and _DOSING_RE.search(text):
        return CHEMICAL_DOSING
    return None


_CITATION_RE = re.compile(r"\[\s*(\d+(?:\s*,\s*\d+)*)\s*\]")


def validate_citations(answer: str, passage_count: int) -> tuple[str, list[int]]:
    """Drop ``[n]`` markers that do not resolve to a retrieved passage.

    Returns ``(cleaned text, sorted valid passage numbers)``. Inside a comma
    list only the invalid members are dropped. An empty list means the answer
    is unsourced and must be suppressed by the caller.
    """
    valid: set[int] = set()

    def keep_valid(match: re.Match) -> str:
        numbers = [int(n) for n in re.split(r"\s*,\s*", match.group(1))]
        kept = [n for n in numbers if 1 <= n <= passage_count]
        valid.update(kept)
        return f"[{', '.join(str(n) for n in kept)}]" if kept else ""

    text = _CITATION_RE.sub(keep_valid, answer or "")
    # A dropped marker leaves "monthly ." behind — tidy the space before
    # punctuation and any doubled spaces.
    text = re.sub(r"[ \t]+([.,;:!?])", r"\1", text)
    text = re.sub(r"[ \t]{2,}", " ", text).strip()
    return text, sorted(valid)


# Built from the constant the prompt asks for, so the two cannot drift.
_NO_INFORMATION_RE = re.compile(
    rf"^\W*{re.escape(constants.RAG_NO_INFORMATION_SENTINEL)}\W*$", re.I
)


def is_no_information(reply: str) -> bool:
    """True when the whole reply is the sentinel (whitespace, quotes and
    trailing punctuation tolerated); prose that merely contains it is not."""
    return bool(_NO_INFORMATION_RE.match((reply or "").strip()))
