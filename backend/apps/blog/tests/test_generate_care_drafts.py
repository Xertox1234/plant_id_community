"""Tests for ``manage.py generate_care_drafts`` (todo 445).

The command must never publish, must keep todo 330's hard-blocked classes out,
and must be safe to re-run. Page-creating: run with --create-db after a
migration change.
"""

import json
from io import StringIO
from unittest.mock import patch

import pytest
from apps.blog.care_topics import CARE_GUIDE_TAG, CARE_TOPICS
from apps.blog.management.commands.generate_care_drafts import (
    is_blocked,
    parse_article,
    screen_article,
)
from apps.blog.models import BlogIndexPage, BlogPostPage
from apps.forum_host.rag_guardrails import classify_blocked_question
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from wagtail.models import Site
from wagtail.signals import page_published

User = get_user_model()

AI = "apps.blog.wagtail_ai_v3_integration.generate_ai_text"


def _reply(paragraphs=None, introduction="Water when the top inch is dry."):
    paragraphs = paragraphs or [
        "Check the soil with a finger before watering.",
        "Water thoroughly until it drains from the bottom.",
        "Empty the saucer so roots do not sit in water.",
        "Water less in winter, when growth slows.",
        "Bright indirect light keeps growth steady.",
    ]
    return json.dumps(
        {
            "introduction": introduction,
            "sections": [
                {"heading": "Watering", "paragraphs": paragraphs[:3]},
                {"heading": "Light and season", "paragraphs": paragraphs[3:]},
            ],
        }
    )


@pytest.fixture
def index(db):
    root = Site.objects.get(is_default_site=True).root_page
    page = root.add_child(instance=BlogIndexPage(title="Blog", slug="blog"))
    page.save_revision().publish()
    return page


@pytest.fixture
def author(db):
    return User.objects.create_user(username="editor", email="editor@example.com")


def _run(*args):
    out, err = StringIO(), StringIO()
    call_command("generate_care_drafts", *args, stdout=out, stderr=err)
    return out.getvalue(), err.getvalue()


def test_the_topic_list_is_clean_and_about_fifty():
    slugs = [slug for slug, _, _ in CARE_TOPICS]
    assert 45 <= len(CARE_TOPICS) <= 60
    assert len(set(slugs)) == len(slugs)
    for slug, title, focus in CARE_TOPICS:
        assert classify_blocked_question(f"{title}. {focus}") is None, slug


@pytest.mark.django_db
def test_dry_run_calls_nothing_and_writes_nothing(index):
    with patch(AI) as ai:
        out, _ = _run("--dry-run")

    ai.assert_not_called()
    assert not BlogPostPage.objects.exists()
    assert f"{len(CARE_TOPICS)} to draft" in out


@pytest.mark.django_db
def test_drafts_are_unpublished_tagged_and_revisioned(index, author):
    published = []

    def on_publish(sender, **kwargs):
        published.append(kwargs["instance"].pk)

    page_published.connect(on_publish)
    try:
        with patch(AI, return_value=_reply()) as ai:
            out, _ = _run("--author", "editor", "--limit", "2")
    finally:
        page_published.disconnect(on_publish)

    assert ai.call_count == 2
    pages = list(BlogPostPage.objects.order_by("pk"))
    assert [p.slug for p in pages] == [slug for slug, _, _ in CARE_TOPICS[:2]]
    for page in pages:
        assert page.live is False
        assert page.first_published_at is None
        assert page.latest_revision is not None
        assert page.author == author
        assert list(page.tags.names()) == [CARE_GUIDE_TAG]
        assert page.get_parent().specific == index
        kinds = [b.block_type for b in page.content_blocks]
        assert kinds.count("heading") == 2 and kinds.count("paragraph") == 5
    assert published == []
    assert "Nothing was published" in out


@pytest.mark.django_db
def test_a_rerun_skips_existing_topics(index, author):
    first = CARE_TOPICS[0][0]
    with patch(AI, return_value=_reply()):
        _run("--author", "editor", "--only", first)
    with patch(AI, return_value=_reply()) as ai:
        out, _ = _run("--author", "editor", "--only", first)

    ai.assert_not_called()
    assert BlogPostPage.objects.filter(slug=first).count() == 1
    assert "1 already existed" in out


@pytest.mark.django_db
def test_blocked_paragraphs_are_dropped(index, author):
    reply = _reply(
        paragraphs=[
            "Check the soil with a finger before watering.",
            "Pothos is toxic to cats, so keep it out of reach.",
            "Empty the saucer so roots do not sit in water.",
            "Water less in winter, when growth slows.",
            "Bright indirect light keeps growth steady.",
        ]
    )
    with patch(AI, return_value=reply):
        out, _ = _run("--author", "editor", "--only", "pothos-care-guide")

    page = BlogPostPage.objects.get(slug="pothos-care-guide")
    body = " ".join(str(b.value) for b in page.content_blocks)
    assert "toxic" not in body
    assert "1 flagged paragraph(s) dropped" in out


@pytest.mark.django_db
def test_a_draft_with_too_little_clean_text_is_skipped(index, author):
    reply = _reply(introduction="Is pothos safe for cats and dogs?")
    with patch(AI, return_value=reply):
        out, err = _run("--author", "editor", "--only", "pothos-care-guide")

    assert not BlogPostPage.objects.exists()
    assert "guardrail screen" in err
    assert "1 screened out" in out


@pytest.mark.django_db
def test_a_bad_reply_or_a_failed_call_skips_only_that_topic(index, author):
    two = [slug for slug, _, _ in CARE_TOPICS[:3]]
    with patch(AI, side_effect=["not json at all", RuntimeError("503"), _reply()]):
        out, err = _run("--author", "editor", "--only", *two)

    assert list(BlogPostPage.objects.values_list("slug", flat=True)) == [two[2]]
    assert "2 failed" in out
    assert "not valid JSON" in err and "AI call failed" in err


@pytest.mark.django_db
def test_author_is_required_to_write(index):
    with pytest.raises(CommandError, match="--author"):
        _run("--limit", "1")


def test_parse_article_rejects_malformed_shapes():
    assert parse_article("") is None
    assert parse_article('{"introduction": "x"}') is None
    assert parse_article('{"introduction": "x", "sections": [{"heading": 1}]}') is None
    assert parse_article("[1, 2]") is None
    assert parse_article(_reply()) is not None


def test_screen_drops_a_whole_blocked_section():
    article = parse_article(
        json.dumps(
            {
                "introduction": "Caring for a snake plant.",
                "sections": [
                    {"heading": "Is it pet-friendly?", "paragraphs": ["Yes."]},
                    {
                        "heading": "Watering",
                        "paragraphs": [
                            "Let it dry.",
                            "Water less.",
                            "Use a gritty mix.",
                            "Repot rarely.",
                        ],
                    },
                ],
            }
        )
    )
    screened, dropped = screen_article(article)
    assert dropped == 1
    assert [s["heading"] for s in screened["sections"]] == ["Watering"]


@pytest.mark.parametrize(
    "text",
    [
        "Spray the plant with neem oil once a week.",
        "Dab each mealybug with a cotton swab dipped in rubbing alcohol.",
        "Mix a little dish soap into water and wipe the leaves.",
        "A hydrogen peroxide drench kills the larvae.",
    ],
)
def test_the_screen_flags_any_named_treatment(text):
    """PR #855 review: the question classifier needs a dose word next to a
    chemical, so these passed it. The content screen flags the name alone."""
    assert classify_blocked_question(text) is None
    assert is_blocked(text)


def test_the_screen_keeps_plain_care_advice():
    for text in (
        "Rinse the leaves with plain water in the shower.",
        "Wipe the leaves with a damp cloth.",
        "Let the top inch of soil dry before watering.",
    ):
        assert not is_blocked(text), text


@pytest.mark.django_db
def test_a_failed_page_write_skips_only_that_topic(index, author):
    three = [slug for slug, _, _ in CARE_TOPICS[:3]]
    from apps.blog.management.commands import generate_care_drafts as module

    real = module.Command._create_draft
    calls = []

    def flaky(self, *args):
        calls.append(args[2])
        if len(calls) == 1:
            raise RuntimeError("slug clash")
        return real(self, *args)

    with patch(AI, return_value=_reply()), patch.object(
        module.Command, "_create_draft", flaky
    ):
        out, err = _run("--author", "editor", "--only", *three)

    assert sorted(BlogPostPage.objects.values_list("slug", flat=True)) == sorted(
        three[1:]
    )
    assert "could not save the draft" in err
    assert "1 failed" in out


@pytest.mark.django_db
def test_existing_means_a_child_of_this_index(index, author):
    """A same-slug post under ANOTHER index does not count; any child of this
    index with the slug (any page type) does."""
    root = Site.objects.get(is_default_site=True).root_page
    other = root.add_child(instance=BlogIndexPage(title="Old", slug="old-blog"))
    slug = CARE_TOPICS[0][0]
    with patch(AI, return_value=_reply()):
        out, err = _run("--author", "editor", "--index", "old-blog", "--only", slug)
    other.refresh_from_db()  # treebeard trusts a stale numchild
    assert other.get_children().filter(slug=slug).exists(), (out, err)

    with patch(AI, return_value=_reply()) as ai:
        _run("--author", "editor", "--index", "blog", "--only", slug)

    assert ai.call_count == 1
    index.refresh_from_db()
    assert index.get_children().filter(slug=slug).exists()


@pytest.mark.django_db
def test_several_indexes_need_an_explicit_one(index, author):
    root = Site.objects.get(is_default_site=True).root_page
    root.add_child(instance=BlogIndexPage(title="Old", slug="old-blog"))
    with pytest.raises(CommandError, match="--index"):
        _run("--dry-run")


@pytest.mark.django_db
def test_drafts_are_owned_by_the_author(index, author):
    with patch(AI, return_value=_reply()):
        _run("--author", "editor", "--limit", "1")
    assert BlogPostPage.objects.get().owner == author
