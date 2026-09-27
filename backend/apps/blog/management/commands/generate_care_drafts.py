"""Draft about 50 AI care articles for the owner to spot-check (todo 445).

Each topic in ``apps.blog.care_topics.CARE_TOPICS`` becomes an UNPUBLISHED
``BlogPostPage`` tagged ``care-guide`` under the blog index. The command never
publishes: the owner reviews each draft in the CMS and publishes it (todo 445
AC 3). Mobile care guides (todo 386) list published posts with that tag.

Todo 330's hard-blocked classes (ingestion, toxicity, pesticide or chemical
dosing) are kept out twice: the topic list is screened before any call, and
every generated paragraph is screened afterwards with the RAG guardrail's
``classify_blocked_question``. A flagged paragraph is dropped. A draft left
with too little text is skipped and reported. It is not retried, because the
AI layer caches identical prompts.

Idempotent: a topic whose slug already exists is skipped, so a re-run after a
partial failure only fills the gaps.
"""

import json
from typing import Any

from apps.blog.care_topics import CARE_GUIDE_TAG, CARE_TOPICS
from apps.blog.constants import (
    CARE_DRAFT_AI_TIMEOUT_SECONDS,
    CARE_DRAFT_MAX_PARAGRAPHS_PER_SECTION,
    CARE_DRAFT_MAX_SECTIONS,
    CARE_DRAFT_MAX_TEXT_CHARS,
    CARE_DRAFT_MIN_PARAGRAPHS,
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
amounts or dilutions for any product. For fertilizer, say to follow the label.
- No links, no HTML, no markdown.

Reply with ONLY a JSON object of this shape:
{{"introduction": "two or three sentences", "sections": [{{"heading": \
"short heading", "paragraphs": ["paragraph", "paragraph"]}}]}}
Use 4 to 6 sections."""


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
    """Drop every paragraph the RAG guardrail blocks (todo 330's classes).

    Returns ``(article, dropped)``. The article is None when the introduction
    is blocked or fewer than ``CARE_DRAFT_MIN_PARAGRAPHS`` paragraphs survive.
    """
    if classify_blocked_question(article["introduction"]):
        return None, 0
    dropped = 0
    sections = []
    for section in article["sections"]:
        if classify_blocked_question(section["heading"]):
            dropped += len(section["paragraphs"])
            continue
        kept = [p for p in section["paragraphs"] if not classify_blocked_question(p)]
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
            slug
            for slug, title, focus in topics
            if classify_blocked_question(f"{title}. {focus}")
        ]
        if blocked:
            raise CommandError(
                "Topic(s) fall in todo 330's hard-blocked classes: "
                + ", ".join(blocked)
            )

        existing = set(
            BlogPostPage.objects.filter(
                slug__in=[slug for slug, _, _ in topics]
            ).values_list("slug", flat=True)
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
        index = BlogIndexPage.objects.first()
        if index is None:
            raise CommandError("No BlogIndexPage exists to hold the drafts.")

        created, failed, screened, dropped_total = [], [], [], 0
        for slug, title, focus in todo:
            try:
                raw = generate_ai_text(
                    PROMPT.format(title=title, focus=focus),
                    timeout=CARE_DRAFT_AI_TIMEOUT_SECONDS,
                )
            except Exception as exc:  # one topic's failure must not stop the run
                failed.append(slug)
                self.stderr.write(f"[BLOG] {slug}: AI call failed: {exc}")
                continue
            article = parse_article(raw)
            if article is None:
                failed.append(slug)
                self.stderr.write(f"[BLOG] {slug}: the reply was not valid JSON")
                continue
            article, dropped = screen_article(article)
            dropped_total += dropped
            if article is None:
                screened.append(slug)
                self.stderr.write(
                    f"[BLOG] {slug}: too little text passed the guardrail screen"
                )
                continue
            self._create_draft(index, author, slug, title, article)
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
                )
            )
            page.tags.add(CARE_GUIDE_TAG)
            page.save()
            # A revision, so the draft opens in the CMS editor like any other
            # (docs/rules/wagtail.md). Never .publish(): the owner does that.
            page.save_revision(user=author)
