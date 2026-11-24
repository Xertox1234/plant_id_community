"""Removed forum words must not come back through the AI features (audit
2026-11-24 F64): retrieval reads the current opening post, and the stored
copies (``SimilarTopics`` rows, ``EmbeddingCache`` text, ``RagAnswer.sources``)
go when the words go, whatever the feature flags say.
"""

from unittest.mock import patch

import pytest
from apps.forum_host import constants
from apps.forum_host import vector_indexes as vi
from apps.forum_host.models import RagAnswer
from apps.users.constants import DELETED_ACCOUNT_REASON_SELF, DELETED_TOPIC_TITLE
from apps.users.deletion import email_hash, erase_django_data
from apps.users.models import DeletedAccount
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django_ai_core.contrib.index.models import EmbeddingCache
from django_ai_core.contrib.index.storage.pgvector.models import PgVectorEmbedding
from django_ai_core.llm import LLMService
from wagtail_forum.models import Post, Report, Topic

from .test_rag_retrieval import CORE, _core_returning, _retrieve, _topic_doc
from .test_similar import _FAKE_OPENAI_KEY, _fake_embedding, _topic

pytestmark = pytest.mark.django_db

User = get_user_model()

SECRET = "zqphone5550199"  # pragma: allowlist secret


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def _build():
    """Index everything with the fake embedder, then drop back to flags off."""
    with (
        override_settings(
            FORUM_VECTOR_SEARCH_ENABLED=True, OPENAI_API_KEY=_FAKE_OPENAI_KEY
        ),
        patch.object(LLMService, "embedding", _fake_embedding),
    ):
        vi.SimilarTopics().build()


def _rows(topic):
    return PgVectorEmbedding.objects.filter(
        document_key__startswith=f"wagtail_forum.Topic:{topic.pk}:"
    )


def _opening(topic):
    return Post.objects.get(topic=topic, is_opening_post=True)


def _cached(text=SECRET):
    return EmbeddingCache.objects.filter(content__contains=text)


# --- retrieval reads the current post ------------------------------------------


def _passages(topic):
    with patch(CORE, side_effect=_core_returning(topic_docs=[_topic_doc(topic, 0.9)])):
        return _retrieve()


def test_passage_and_snippet_are_the_current_opening_post():
    topic = _topic("Tomato blight", "the corrected words", suffix="cur")

    (passage,) = _passages(topic)

    # The stored document says "content of wagtail_forum.Topic:…".
    assert passage.text == "Tomato blight\nthe corrected words"
    assert passage.snippet == "Tomato blight the corrected words"


def test_the_matched_chunk_of_a_long_post_is_the_one_shown():
    topic = _topic("Tomato blight", "word " * 300 + "the end", suffix="lng")
    doc = _topic_doc(topic, 0.9, chunk=1)
    with patch(CORE, side_effect=_core_returning(topic_docs=[doc])):
        (passage,) = _retrieve()
    assert passage.text.endswith("the end")

    # The post has since been cut short: its remaining text is used.
    gone = _topic_doc(topic, 0.9, chunk=9)
    with patch(CORE, side_effect=_core_returning(topic_docs=[gone])):
        (passage,) = _retrieve()
    assert passage.text.startswith("Tomato blight")


@pytest.mark.parametrize("how", ["unpublished", "deleted", "blank"])
def test_a_topic_with_no_readable_opening_post_is_dropped(how):
    topic = _topic("Tomato blight", "gone words", suffix=how[:3])
    posts = Post.objects.filter(topic=topic)
    if how == "unpublished":
        posts.update(live=False)
    elif how == "deleted":
        posts.delete()
    else:
        post = posts.get()
        post.body = []
        post.save()

    assert _passages(topic) == []


def test_opening_posts_are_read_in_one_query(django_assert_num_queries):
    from apps.forum_host.rag_retrieval import _refetch_topics

    one = [_topic("Tomato 0", "tomato", suffix="q0")]
    three = [_topic(f"Tomato {i}", "tomato", suffix=f"q{i}") for i in (1, 2, 3)]
    for topics in (one, three):
        docs = [_topic_doc(t, 0.9) for t in topics]
        with django_assert_num_queries(2):
            assert len(_refetch_topics(docs, None)) == len(topics)


# --- stored copies go with the words -------------------------------------------


def _edit(topic):
    post = _opening(topic)
    post.body = [{"type": "paragraph", "value": "<p>redacted</p>"}]
    post.save_revision().publish()


def _unpublish_post(topic):
    _opening(topic).unpublish()


def _delete_post(topic):
    _opening(topic).delete()


def _retitle(topic):
    topic = Topic.objects.get(pk=topic.pk)
    topic.title = "Another title"
    topic.save()


def _unpublish_topic(topic):
    Topic.objects.get(pk=topic.pk).unpublish()


def _delete_topic(topic):
    Topic.objects.get(pk=topic.pk).delete()


@override_settings(FORUM_VECTOR_SEARCH_ENABLED=False, FORUM_RAG_ENABLED=False)
@pytest.mark.parametrize(
    "change",
    [
        _edit,
        _unpublish_post,
        _delete_post,
        _retitle,
        _unpublish_topic,
        _delete_topic,
    ],
)
def test_a_change_drops_the_topics_rows_and_cached_text(change):
    topic = _topic("Tomato blight", f"call {SECRET}", suffix="chg")
    other = _topic("Rose care", "prune a rose", suffix="oth")
    _build()
    assert _rows(topic).exists() and _cached().exists()

    with patch.object(LLMService, "embedding", side_effect=AssertionError):
        change(topic)

    assert not _rows(topic).exists()
    assert not _cached().exists()
    assert _rows(other).exists()
    assert _cached("prune a rose").exists()


def test_a_save_that_changes_no_indexed_text_keeps_the_rows():
    topic = _topic("Tomato blight", "tomato", suffix="kep")
    _build()

    fresh = Topic.objects.get(pk=topic.pk)
    fresh.is_closed = True
    fresh.save()
    _opening(topic).save()

    assert _rows(topic).exists()


# --- account erasure -----------------------------------------------------------


def _erase(user):
    record = DeletedAccount.objects.create(
        user_id=user.pk,
        email=user.email,
        email_hash=email_hash(user.email),
        reason=DELETED_ACCOUNT_REASON_SELF,
    )
    erase_django_data(record)


def _answer(topic, asker):
    return RagAnswer.objects.create(
        user=asker,
        question="q",
        answer="a [1]",
        sources=[
            {
                "n": 1,
                "kind": "topic",
                "title": topic.title,
                "date": "2026-01-01",
                "snippet": f"{topic.title} call {SECRET}",
                "topic_id": topic.pk,
                "topic_slug": f"slug-{SECRET}",
                "board_id": topic.board_id,
                "board_slug": "general",
            },
            {"n": 2, "kind": "blog", "title": "Blog", "snippet": "kept", "slug": "b"},
        ],
        prompt_version=constants.RAG_PROMPT_VERSION,
    )


def test_erasure_purges_every_stored_copy():
    topic = _topic(f"Tomato {SECRET}", f"call {SECRET}", suffix="era")
    other = _topic("Rose care", "prune a rose", suffix="ot2")
    asker = User.objects.create_user(username="asker", email="asker@example.org")
    _build()
    answer = _answer(topic, asker)
    other_answer = _answer(other, asker)

    _erase(topic.author)

    assert not _rows(topic).exists()
    assert _rows(other).exists()
    assert not _cached().exists()
    assert _cached("prune a rose").exists()
    answer.refresh_from_db()
    topic_source, blog_source = answer.sources
    assert SECRET not in str(answer.sources)
    assert topic_source["title"] == DELETED_TOPIC_TITLE
    assert topic_source["snippet"] == ""
    assert topic_source["topic_id"] == topic.pk
    assert blog_source["snippet"] == "kept"
    other_answer.refresh_from_db()
    assert other_answer.sources[0]["snippet"] != ""


def test_erasure_purges_cached_text_of_earlier_versions():
    """The vector row holds one version; the cache keeps one per version ever
    embedded. The post's revisions are the exact-match key to the rest."""
    topic = _topic("Tomato blight", f"call {SECRET}", suffix="ver")
    post = _opening(topic)
    post.save_revision()
    _build()
    content = _cached().get()
    post.body = [{"type": "paragraph", "value": "<p>later words</p>"}]
    post.save_revision().publish()
    # As an index rebuilt before this fix would have left it.
    EmbeddingCache.objects.create(
        content=content.content,
        content_hash=content.content_hash,
        embedding_transformer_id=content.embedding_transformer_id,
        embedding_vector=content.embedding_vector,
        embedding_dimensions=content.embedding_dimensions,
    )

    _erase(topic.author)

    assert not _cached().exists()


def test_a_held_opening_post_loses_its_copies_again_when_released():
    from apps.users.retention import release_held_posts

    topic = _topic("Tomato blight", f"call {SECRET}", suffix="hld")
    reporter = User.objects.create_user(username="rep", email="rep@example.org")
    report = Report.objects.create(
        post=_opening(topic), reporter=reporter, reason=Report.ABUSE
    )
    _build()
    _erase(topic.author)
    assert not _rows(topic).exists()
    # The held post is still up, so a rebuild indexes it again.
    _build()
    answer = _answer(topic, reporter)
    assert _rows(topic).exists()

    report.status = Report.DISMISSED
    report.save()
    assert release_held_posts() == 1

    assert not _rows(topic).exists()
    assert not _cached().exists()
    answer.refresh_from_db()
    assert SECRET not in str(answer.sources)
