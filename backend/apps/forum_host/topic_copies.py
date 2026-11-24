"""The stored copies of a topic's words, and dropping them (audit 2026-11-24 F64).

Three tables hold a copy of what an author wrote in a topic's opening post:
the ``SimilarTopics`` vector rows, django-ai-core's ``EmbeddingCache`` (the
embedded text in full), and ``RagAnswer.sources`` (title and snippet).

Nothing here calls the embedding provider or reads the feature flags: copies
made while a feature was on must go even when it is off. A topic whose rows
are dropped is out of semantic search until the next ``rebuild_indexes``.

Not covered, because nothing ties the text to a topic: the answer prose in
``RagAnswer.answer``, and cache rows of earlier versions whose revisions are
gone.
"""

from collections.abc import Iterable
from typing import Any

from django_ai_core.contrib.index.models import EmbeddingCache
from django_ai_core.contrib.index.storage.pgvector.models import PgVectorEmbedding
from wagtail_forum.models import Post, Topic

from .models import RagAnswer
from .vector_indexes import SimilarTopics, _index_name, topic_chunks


def _vector_rows(topic_id: int) -> Any:
    return PgVectorEmbedding.objects.filter(
        index_name=_index_name(SimilarTopics),
        document_key__startswith=f"{Topic._meta.label}:{topic_id}:",
    )


def _delete_cached_text(contents: Iterable[str]) -> None:
    """Delete the cache rows holding exactly one of ``contents``. A row is
    shared by every document with the same text; losing it costs a re-embed."""
    hashes = {EmbeddingCache.get_content_hash(text) for text in contents}
    EmbeddingCache.objects.filter(content_hash__in=hashes).delete()


def drop_topic_vectors(topic_id: int) -> None:
    """Delete a topic's vector rows and the cached text they were made from."""
    rows = _vector_rows(topic_id)
    contents = list(rows.values_list("content", flat=True))
    if contents:
        _delete_cached_text(contents)
        rows.delete()


def drop_stale_topic_vectors(topic_id: int) -> None:
    """``drop_topic_vectors`` unless the rows still hold what the live topic
    says. One query when the topic was never indexed."""
    stored = set(_vector_rows(topic_id).values_list("content", flat=True))
    if not stored:
        return
    topic = Topic.objects.filter(pk=topic_id, live=True).first()
    if topic is not None:
        opening = topic.posts.filter(live=True, is_opening_post=True).first()
        body = opening.body if opening is not None else None
        if stored == set(topic_chunks(topic.title, body)):
            return
    drop_topic_vectors(topic_id)


def forget_post_copies(topic: Topic, post: Post | None) -> None:
    """Drop every stored copy of ``topic`` with opening post ``post``, which is
    about to be erased. Call it BEFORE the revisions go: they are the exact
    text of the earlier versions the cache may still hold."""
    titles = {topic.title}
    titles.update(
        revision.content.get("title", "") for revision in topic.revisions.all()
    )
    bodies: list[Any] = [None]
    if post is not None:
        bodies.append(post.body)
        bodies.extend(revision.as_object().body for revision in post.revisions.all())
    _delete_cached_text(
        chunk
        for title in titles
        for body in bodies
        for chunk in topic_chunks(title, body)
    )
    drop_topic_vectors(topic.pk)
    _redact_sources(topic.pk, {"snippet": ""})


def redact_topic_sources(topic_id: int, *, title: str, slug: str) -> None:
    """Replace an erased topic's title, slug and snippet in stored answers."""
    _redact_sources(topic_id, {"snippet": "", "title": title, "topic_slug": slug})


def _redact_sources(topic_id: int, values: dict[str, str]) -> None:
    answers = RagAnswer.objects.filter(
        sources__contains=[{"kind": "topic", "topic_id": topic_id}]
    )
    for answer in answers.iterator():
        answer.sources = [
            (
                {**source, **values}
                if source.get("kind") == "topic" and source.get("topic_id") == topic_id
                else source
            )
            for source in answer.sources
        ]
        answer.save(update_fields=["sources"])
