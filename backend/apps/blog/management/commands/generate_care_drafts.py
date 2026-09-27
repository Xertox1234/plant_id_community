"""Draft about 50 AI care articles for the owner to spot-check (todo 445).

Each topic in ``apps.blog.care_topics.CARE_TOPICS`` becomes an UNPUBLISHED
``BlogPostPage`` tagged ``care-guide`` under the blog index. The command never
publishes: the owner reviews each draft in the CMS and publishes it (todo 445
AC 3). Mobile care guides (todo 386) list published posts with that tag.

Todo 330's hard-blocked classes (ingestion, toxicity, pesticide or chemical
dosing) are kept out twice: the topic list is screened before any call, and
every generated paragraph is screened afterwards. The screen is the RAG
guardrail's ``classify_blocked_question`` PLUS ``_TREATMENT_RE``, which flags
any named treatment or remedy. The guardrail was built for questions and
only blocks a chemical when a dose word is in the same sentence, so "spray
with neem oil weekly" passed it (PR #855 review). A flagged paragraph is
dropped. A draft left with too little text is skipped and reported. It is not
retried, because the AI layer caches identical prompts.

Idempotent: a topic whose slug is already a child of the index is skipped, so
a re-run after a partial failure fills the gaps the provider did not cause.
"""

import json
import re
from typing import Any

from apps.blog.care_topics import CARE_GUIDE_TAG, CARE_TOPICS
from apps.blog.constants import (
    CARE_DRAFT_AI_TIMEOUT_SECONDS,
    CARE_DRAFT_MAX_PARAGRAPHS_PER_SECTION,
    CARE_DRAFT_MAX_SECTIONS,
    CARE_DRAFT_MAX_TEXT_CHARS,
    CARE_DRAFT_MIN_PARAGRAPHS,
    CARE_DRAFT_TARGET_SECTIONS,
)
from apps.blog.models import BlogIndexPage, BlogPostPage
from apps.forum_host.rag_guardrails import classify_blocked_question
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.html import escape

PROMPT = """You are writing a practical houseplant care article for a plant \
community website. Title: "{title}". Cover: {focus}.

Rules:
- Plain, friendly, accurate advice for beginners. No marketing.
- Do NOT discuss whether any plant is safe or toxic for people or pets, or \
eating, tasting or medicinal use of plants.
- Do NOT name or recommend any pesticide, insecticide, fungicide, neem, \
insecticidal soap, horticultural oil or other chemical treatment, and give no \
amounts or dilutions for any product. Do not mention treatments at all, not \
even to say one is not needed. For fertilizer, say to follow the label.
- No links, no HTML, no markdown.

Reply with ONLY a JSON object of this shape:
{{"introduction": "two or three sentences", "sections": [{{"heading": \
"short heading", "paragraphs": ["paragraph", "paragraph"]}}]}}
Use {min_sections} to {max_sections} sections."""

# Any named pest, disease or weed treatment, or a household remedy used as
# one. Content-oriented: a care article may not name one at all, dose or not.
_TREATMENT_RE = re.compile(
    r"\b(?:neem|pyrethr\w*|permethrin|imidacloprid|spinosad|malathion|carbaryl|"
    r"glyphosate|roundup|captan|chlorothalonil|myclobutanil|copper\s+"
    r"(?:fungicide|sulfate|sulphate|soap)|fungicides?|pesticides?|"
    r"insecticides?|herbicides?|miticides?|acaricides?|systemic|"
    r"bacillus\s+thuringiensis|mosquito\s+(?:bits|dunks)|insecticidal|"
    r"horticultural\s+oil|dormant\s+oil|oil\s+sprays?|essential\s+oils?|"
    r"(?:rubbing|isopropyl)\s+alcohol|alcohol|isopropyl|dish\s+soap|"
    r"soapy\s+water|soap|detergents?|sulfur|sulphur|hydrogen\s+peroxide|"
    r"peroxide|diatomaceous\s+earth|vinegar|baking\s+soda|"
    # "bleach" the product, not sun that bleaches leaves.
    r"(?:with|of|diluted|household)\s+bleach|bleach\s+(?:solution|and\s+water))\b",
    re.I,
)


def is_blocked(text: str) -> bool:
    """True for text in todo 330's classes or naming any treatment."""
    return bool(classify_blocked_question(text) or _TREATMENT_RE.search(text))


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = " ".join(value.split())
    return value[:CARE_DRAFT_MAX_TEXT_CHARS] if value else None


def parse_article(raw: str) -> dict | None:
    """The model's JSON as ``{"introduction": str, "sections": [...]}``, or
    None when it is missing or malformed."""
    if not isinstance(raw, str):
        return None
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(raw[start : end + 1])
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    introduction = _text(data.get("introduction"))
    raw_sections = data.get("sections")
    if not introduction or not isinstance(raw_sections, list):
        return None
    sections = []
    for section in raw_sections[:CARE_DRAFT_MAX_SECTIONS]:
        if not isinstance(section, dict):
            continue
        heading = _text(section.get("heading"))
        paragraphs = section.get("paragraphs")
        if not heading or not isinstance(paragraphs, list):
            continue
        texts = [
            t
            for t in (
                _text(p) for p in paragraphs[:CARE_DRAFT_MAX_PARAGRAPHS_PER_SECTION]
            )
            if t
        ]
        if texts:
            sections.append({"heading": heading, "paragraphs": texts})
    return {"introduction": introduction, "sections": sections} if sections else None


def screen_article(article: dict) -> tuple[dict | None, int]:
    """Drop every paragraph ``is_blocked`` flags: todo 330's classes (the RAG
    guardrail) or any named treatment (``_TREATMENT_RE``).

    Returns ``(article, dropped)``. The article is None when the introduction
    is blocked or fewer than ``CARE_DRAFT_MIN_PARAGRAPHS`` paragraphs survive.
    """
    if is_blocked(article["introduction"]):
        return None, 0
    dropped = 0
    sections = []
    for section in article["sections"]:
        if is_blocked(section["heading"]):
            dropped += len(section["paragraphs"])
            continue
        kept = [p for p in section["paragraphs"] if not is_blocked(p)]
        dropped += len(section["paragraphs"]) - len(kept)
        if kept:
            sections.append({"heading": section["heading"], "paragraphs": kept})
    if sum(len(s["paragraphs"]) for s in sections) < CARE_DRAFT_MIN_PARAGRAPHS:
        return None, dropped
    return {"introduction": article["introduction"], "sections": sections}, dropped


def to_blocks(article: dict) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    for section in article["sections"]:
        blocks.append(("heading", section["heading"]))
        for paragraph in section["paragraphs"]:
            blocks.append(("paragraph", f"<p>{escape(paragraph)}</p>"))
    return blocks


class Command(BaseCommand):
    help = (
        "Draft AI care articles as UNPUBLISHED blog posts tagged care-guide "
        "(todo 445). Never publishes; skips topics that already exist."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--author",
            help="Username of the drafts' author (required unless --dry-run).",
        )
        parser.add_argument(
            "--only",
            nargs="+",
            metavar="SLUG",
            help="Draft only these topic slugs.",
        )
        parser.add_argument(
            "--limit", type=int, help="Draft at most this many new topics."
        )
        parser.add_argument(
            "--index",
            metavar="SLUG_OR_ID",
            help="Slug or page id of the BlogIndexPage to draft under "
            "(required when there is more than one).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List what would be drafted. No AI calls, no writes.",
        )

    def handle(self, *args, **options):
        from apps.blog.wagtail_ai_v3_integration import generate_ai_text

        topics = list(CARE_TOPICS)
        if options["only"]:
            wanted = set(options["only"])
            unknown = wanted - {slug for slug, _, _ in topics}
            if unknown:
                raise CommandError(
                    f"Unknown topic slug(s): {', '.join(sorted(unknown))}"
                )
            topics = [t for t in topics if t[0] in wanted]

        blocked = [
            slug for slug, title, focus in topics if is_blocked(f"{title}. {focus}")
        ]
        if blocked:
            raise CommandError(
                "Topic(s) fall in todo 330's hard-blocked classes: "
                + ", ".join(blocked)
            )

        index = self._resolve_index(options["index"])
        # Slugs are unique among an index's children of ANY page type, so a
        # category or author page with a topic's slug also blocks it.
        existing = set(
            index.get_children()
            .filter(slug__in=[slug for slug, _, _ in topics])
            .values_list("slug", flat=True)
        )
        todo = [t for t in topics if t[0] not in existing]
        if options["limit"] is not None:
            todo = todo[: max(options["limit"], 0)]

        if options["dry_run"]:
            for slug, title, _ in todo:
                self.stdout.write(f"would draft  {slug}  ({title})")
            self.stdout.write(
                f"dry run: {len(todo)} to draft, {len(existing)} already exist"
            )
            return

        if not options["author"]:
            raise CommandError("--author is required (the drafts' author).")
        User = get_user_model()
        try:
            author = User.objects.get(username=options["author"])
        except User.DoesNotExist as exc:
            raise CommandError(f"No user named {options['author']!r}.") from exc
        created, failed, screened, dropped_total = [], [], [], 0
        for slug, title, focus in todo:
            try:
                raw = generate_ai_text(
                    PROMPT.format(
                        title=title,
                        focus=focus,
                        min_sections=CARE_DRAFT_TARGET_SECTIONS[0],
                        max_sections=CARE_DRAFT_TARGET_SECTIONS[1],
                    ),
                    timeout=CARE_DRAFT_AI_TIMEOUT_SECONDS,
                )
            except Exception as exc:  # one topic's failure must not stop the run
                failed.append(slug)
                self.stderr.write(f"[ERROR] {slug}: AI call failed: {exc}")
                continue
            article = parse_article(raw)
            if article is None:
                failed.append(slug)
                self.stderr.write(f"[ERROR] {slug}: the reply was not valid JSON")
                continue
            article, dropped = screen_article(article)
            dropped_total += dropped
            if article is None:
                screened.append(slug)
                self.stderr.write(
                    f"[ERROR] {slug}: too little text passed the guardrail screen"
                )
                continue
            try:
                self._create_draft(index, author, slug, title, article)
            except Exception as exc:  # a page write must not stop the run
                failed.append(slug)
                self.stderr.write(f"[ERROR] {slug}: could not save the draft: {exc}")
                continue
            created.append(slug)
            self.stdout.write(
                f"drafted {slug}"
                + (f" ({dropped} flagged paragraph(s) dropped)" if dropped else "")
            )

        self.stdout.write(
            f"care drafts: {len(created)} created, {len(existing)} already "
            f"existed, {len(failed)} failed, {len(screened)} screened out, "
            f"{dropped_total} paragraph(s) dropped by the guardrail. Nothing "
            "was published."
        )
        if failed or screened:
            self.stdout.write("not drafted: " + ", ".join(failed + screened))

    def _resolve_index(self, slug: str | None) -> BlogIndexPage:
        indexes = BlogIndexPage.objects.all()
        if slug:
            lookup = {"pk": int(slug)} if slug.isdigit() else {"slug": slug}
            matches = list(indexes.filter(**lookup)[:2])
            if not matches:
                raise CommandError(f"No BlogIndexPage matches {slug!r}.")
            if len(matches) > 1:
                raise CommandError(
                    f"Several BlogIndexPages have the slug {slug!r}; pass the "
                    "page id instead: "
                    + ", ".join(str(p.pk) for p in indexes.filter(**lookup))
                )
            return matches[0]
        found = list(indexes[:2])
        if not found:
            raise CommandError("No BlogIndexPage exists to hold the drafts.")
        if len(found) > 1:
            raise CommandError(
                "More than one BlogIndexPage exists; pick one with --index "
                "(slug or id): " + ", ".join(f"{p.slug} (id {p.pk})" for p in indexes)
            )
        return found[0]

    def _create_draft(self, index, author, slug, title, article):
        with transaction.atomic():
            page = index.add_child(
                instance=BlogPostPage(
                    title=title,
                    slug=slug,
                    author=author,
                    publish_date=timezone.now().date(),
                    introduction=f"<p>{escape(article['introduction'])}</p>",
                    content_blocks=to_blocks(article),
                    difficulty_level="beginner",
                    live=False,
                    # Owner = author, so the drafts show under the author's
                    # "My pages" in the CMS for the spot-check.
                    owner=author,
                )
            )
            page.tags.add(CARE_GUIDE_TAG)
            page.save()
            # A revision, so the draft opens in the CMS editor like any other
            # (docs/rules/wagtail.md). Never .publish(): the owner does that.
            page.save_revision(user=author)
