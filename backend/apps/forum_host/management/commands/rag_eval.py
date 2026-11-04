"""Management command: the judge-free RAG eval, phase 1 (todo 694).

Design: ``docs/superpowers/specs/2026-11-03-llm-eval-design.md`` §5. Runs every
case in ``backend/evals/datasets/rag-cases.json`` through ``answer_question``
with ``generate=None, persist=False, charge=False``: no completion call, no
``RagAnswer`` row, none of the live ``RAG_BUDGET_LIMIT``. The only spend is the
question embeddings, charged to ``EMBED_BUDGET`` (about 2 units per
non-blocked case).

Never run on a production shell. It refuses when ``DEBUG`` is False, when a
Railway environment is detected, when ``FORUM_VECTOR_SEARCH_ENABLED`` is off,
and when the ``BlogChunks`` index is empty: each would make every covered case
fail for a reason that is not the code. A case whose retrieval comes back
``unavailable`` (embedding budget exhausted, provider down) aborts the run as
an environment error; it is never counted as a pass or a case failure.

Case failures do not change the exit status: the command reports. Recipe for
loading the corpus into a dev DB: ``backend/evals/README.md``.
"""

import json
import os
from pathlib import Path
from typing import Any

from apps.blog.care_topics import CARE_TOPICS
from apps.forum_host import constants
from apps.forum_host.rag import (
    STATUS_NO_INFORMATION,
    STATUS_REFERRAL,
    STATUS_UNAVAILABLE,
    RagOutcome,
    answer_question,
)
from apps.forum_host.rag_guardrails import CHEMICAL_DOSING, INGESTION
from apps.forum_host.vector_indexes import BlogChunks, _index_name
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django_ai_core.contrib.index.storage.pgvector.models import PgVectorEmbedding

EVALS_DIR = Path(settings.BASE_DIR) / "evals"
DEFAULT_CASES_PATH = EVALS_DIR / "datasets" / "rag-cases.json"
RESULTS_DIR = EVALS_DIR / "results"

# Any of these in the environment means the process runs on Railway (the
# platform injects them into every deployment and `railway ssh` shell).
RAILWAY_ENV_VARS = (
    "RAILWAY_ENVIRONMENT",
    "RAILWAY_ENVIRONMENT_NAME",
    "RAILWAY_PROJECT_ID",
    "RAILWAY_SERVICE_ID",
)

COVERED = "covered"
ADJACENT = "adjacent"
OFF_CORPUS = "off-corpus"
BLOCKED_INGESTION = "blocked-ingestion"
BLOCKED_CHEMICAL = "blocked-chemical"
NOT_BLOCKED = "not-blocked"
CASE_CLASSES = (
    COVERED,
    ADJACENT,
    OFF_CORPUS,
    BLOCKED_INGESTION,
    BLOCKED_CHEMICAL,
    NOT_BLOCKED,
)
# The guardrail reason each blocked class must come back with.
BLOCKED_REASONS = {BLOCKED_INGESTION: INGESTION, BLOCKED_CHEMICAL: CHEMICAL_DOSING}

# Every case field is forwarded to the check or marked metadata (spec §3,
# field-forwarding rule): `question` goes to answer_question, `class` and
# `expected_slug` drive the assertion, `id` labels the row, `notes` is
# metadata and never forwarded.
CASE_FIELDS = {"id", "class", "question", "expected_slug", "notes"}
REQUIRED_FIELDS = {"id", "class", "question"}


def care_topic_slugs() -> set[str]:
    return {slug for slug, _title, _focus in CARE_TOPICS}


def validate_cases(data: Any) -> list[dict]:
    """The dataset's schema. Raises ``ValueError`` naming the first problem.

    Shared by the command (before any embedding is spent) and the dataset's
    pytest validation, so the two can never disagree.
    """
    if not isinstance(data, dict) or not isinstance(data.get("cases"), list):
        raise ValueError("the dataset must be an object with a 'cases' list")
    cases: list[dict] = data["cases"]
    slugs = care_topic_slugs()
    seen: set[str] = set()
    for i, case in enumerate(cases):
        if not isinstance(case, dict):
            raise ValueError(f"case {i} is not an object")
        label = case.get("id", f"#{i}")
        unknown = set(case) - CASE_FIELDS
        if unknown:
            raise ValueError(f"case {label}: unknown fields {sorted(unknown)}")
        missing = REQUIRED_FIELDS - set(case)
        if missing:
            raise ValueError(f"case {label}: missing fields {sorted(missing)}")
        for key in ("id", "question"):
            if not isinstance(case[key], str) or not case[key].strip():
                raise ValueError(f"case {label}: '{key}' must be a non-empty string")
        if len(case["question"]) > constants.RAG_QUESTION_MAX_CHARS:
            raise ValueError(f"case {label}: question is over the ask view's cap")
        if case["id"] in seen:
            raise ValueError(f"case {label}: duplicate id")
        seen.add(case["id"])
        if case["class"] not in CASE_CLASSES:
            raise ValueError(f"case {label}: unknown class {case['class']!r}")
        if case["class"] == COVERED:
            if case.get("expected_slug") not in slugs:
                raise ValueError(
                    f"case {label}: expected_slug must be a care_topics.py slug"
                )
        elif "expected_slug" in case:
            raise ValueError(f"case {label}: only covered cases take expected_slug")
    return cases


def railway_detected() -> bool:
    return any(os.environ.get(name) for name in RAILWAY_ENV_VARS)


def blog_chunks_empty() -> bool:
    # Counted on the shared table by index name: instantiating BlogChunks
    # would build the OpenAI transformer and need a key.
    return not PgVectorEmbedding.objects.filter(
        index_name=_index_name(BlogChunks)
    ).exists()


def _top(outcome: RagOutcome, index: str) -> float | None:
    return outcome.top_scores.get(index)


def evaluate_case(case: dict, floor: float) -> dict:
    """Run one case and return its result row. Raises ``CommandError`` when
    retrieval was unavailable: an environment error, not a case result."""
    outcome = answer_question(
        case["question"], generate=None, persist=False, charge=False, floor=floor
    )
    if outcome.status == STATUS_UNAVAILABLE:
        raise CommandError(
            f"Retrieval was unavailable for case {case['id']} (embedding budget "
            "exhausted or provider down). Aborting: this is an environment "
            "error, not a case result."
        )
    cls = case["class"]
    slugs = [p.slug if p.kind == "blog" else None for p in outcome.passages]
    expected = case.get("expected_slug")
    rank = slugs.index(expected) + 1 if expected in slugs else None
    expected_score = outcome.passages[rank - 1].score if rank else None
    referral = outcome.status == STATUS_REFERRAL

    passed: bool | None
    if cls == COVERED:
        passed = not referral and rank is not None
    elif cls == ADJACENT:
        passed = None  # reported, not asserted: the floor is tuned on this class
    elif cls == OFF_CORPUS:
        passed = outcome.status == STATUS_NO_INFORMATION
    elif cls in BLOCKED_REASONS:
        passed = referral and outcome.blocked_reason == BLOCKED_REASONS[cls]
    else:  # NOT_BLOCKED
        passed = not referral

    return {
        "id": case["id"],
        "class": cls,
        "outcome": outcome.status,
        "blocked_reason": outcome.blocked_reason,
        "top_blog_chunks": _top(outcome, "BlogChunks"),
        "top_similar_topics": _top(outcome, "SimilarTopics"),
        "expected_slug": expected,
        "expected_rank": rank,
        "expected_score": expected_score,
        "cleared_floor": bool(outcome.passages),
        "pass": passed,
    }


def summarise(rows: list[dict], floor: float) -> dict:
    per_class: dict[str, dict[str, int]] = {}
    for cls in CASE_CLASSES:
        asserted = [r for r in rows if r["class"] == cls and r["pass"] is not None]
        reported = [r for r in rows if r["class"] == cls]
        if not reported:
            continue
        per_class[cls] = {
            "passed": sum(1 for r in asserted if r["pass"]),
            "asserted": len(asserted),
            "cases": len(reported),
        }
    covered_scores = [
        r["expected_score"]
        for r in rows
        if r["class"] == COVERED and r["expected_score"] is not None
    ]
    weakest = min(covered_scores) if covered_scores else None
    off_scores = [
        s
        for r in rows
        if r["class"] == OFF_CORPUS
        for s in (r["top_blog_chunks"], r["top_similar_topics"])
        if s is not None
    ]
    strongest_off = max(off_scores) if off_scores else None
    return {
        "floor": floor,
        "per_class": per_class,
        "weakest_covered_score": weakest,
        "weakest_covered_margin": None if weakest is None else weakest - floor,
        "strongest_off_corpus_score": strongest_off,
        "strongest_off_corpus_margin": (
            None if strongest_off is None else floor - strongest_off
        ),
    }


def _fmt(score: float | None) -> str:
    return "-" if score is None else f"{score:.3f}"


class Command(BaseCommand):
    help = (
        "Phase 1 RAG eval (todo 694): run the judge-free cases against a dev DB "
        "holding the corpus. Embeddings only; no completion call, no rows, no "
        "RAG budget. Never on a production shell."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--cases",
            default=str(DEFAULT_CASES_PATH),
            help="Path to the cases JSON (default: evals/datasets/rag-cases.json).",
        )
        parser.add_argument(
            "--floor",
            type=float,
            help=(
                "Similarity floor for this run (0..1). Default: "
                "RAG_SIMILARITY_FLOOR. Measures a floor before it is changed."
            ),
        )
        parser.add_argument(
            "--json",
            metavar="OUT",
            help=(
                "Also write the results as JSON. A bare name or relative path "
                "lands under evals/results/ (gitignored)."
            ),
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "Refusing to run: DEBUG is False. rag_eval runs against a dev DB "
                "only, never on a production shell."
            )
        if railway_detected():
            raise CommandError(
                "Refusing to run: a Railway environment was detected. rag_eval "
                "runs against a dev DB only, never on a production shell."
            )
        if not getattr(settings, "FORUM_VECTOR_SEARCH_ENABLED", False):
            raise CommandError(
                "Refusing to run: FORUM_VECTOR_SEARCH_ENABLED is off, so every "
                "retrieval would come back empty."
            )
        floor = options["floor"]
        if floor is None:
            floor = constants.RAG_SIMILARITY_FLOOR
        elif not 0.0 <= floor <= 1.0:
            raise CommandError("--floor must be between 0 and 1.")

        path = Path(options["cases"])
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            cases = validate_cases(data)
        except (OSError, ValueError) as exc:
            raise CommandError(f"Cannot load cases from {path}: {exc}") from exc

        if blog_chunks_empty():
            raise CommandError(
                "Refusing to run: the BlogChunks index is empty. Load the corpus "
                "and run `manage.py rebuild_indexes SimilarTopics BlogChunks` "
                "first (evals/README.md)."
            )

        rows = [evaluate_case(case, floor) for case in cases]
        summary = summarise(rows, floor)
        self._print(rows, summary)

        if options["json"]:
            out = Path(options["json"])
            if not out.is_absolute():
                out = RESULTS_DIR / out
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(
                json.dumps({"summary": summary, "cases": rows}, indent=2) + "\n",
                encoding="utf-8",
            )
            self.stdout.write(f"Wrote {out}")

    def _print(self, rows: list[dict], summary: dict) -> None:
        header = (
            f"{'id':<32} {'class':<18} {'outcome':<15} {'blog':>6} "
            f"{'topics':>6} {'rank':>4}  pass"
        )
        self.stdout.write(header)
        self.stdout.write("-" * len(header))
        for r in rows:
            verdict = "-" if r["pass"] is None else ("PASS" if r["pass"] else "FAIL")
            rank = "-" if r["expected_rank"] is None else str(r["expected_rank"])
            self.stdout.write(
                f"{r['id']:<32} {r['class']:<18} {r['outcome']:<15} "
                f"{_fmt(r['top_blog_chunks']):>6} {_fmt(r['top_similar_topics']):>6} "
                f"{rank:>4}  {verdict}"
            )
        self.stdout.write("")
        self.stdout.write(f"Floor: {summary['floor']:.3f}")
        for cls, counts in summary["per_class"].items():
            if counts["asserted"]:
                self.stdout.write(
                    f"{cls}: {counts['passed']}/{counts['asserted']} passed"
                )
            else:
                self.stdout.write(f"{cls}: {counts['cases']} reported (not asserted)")
        self.stdout.write(
            "Weakest covered score: "
            f"{_fmt(summary['weakest_covered_score'])} "
            f"(margin over floor {_fmt(summary['weakest_covered_margin'])})"
        )
        self.stdout.write(
            "Strongest off-corpus score: "
            f"{_fmt(summary['strongest_off_corpus_score'])} "
            f"(margin under floor {_fmt(summary['strongest_off_corpus_margin'])})"
        )
