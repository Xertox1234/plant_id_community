"""Grounding-passage retrieval for RAG plant-care answers (todo 289 / M13).

The RAG wrapper over ``vector_indexes._scored_search`` (the single embedding
entry point — flag, query cap, ``EMBED_BUDGET`` peek-then-consume). Where
``find_similar_topics`` reduces hits to Topic pks and throws the scores away,
this keeps them: the similarity floor is the primary guardrail (design doc,
guardrail 1) and it can only be applied to a scored hit.

Pipeline per question:
1. ``_scored_search`` each index (``RAG_OVERFETCH_PER_INDEX`` hits each).
2. Discard everything under ``RAG_SIMILARITY_FLOOR``.
3. Refetch survivors through EACH corpus's own visibility predicate — never
   trust the index: a page may have been unpublished or a board restricted
   after indexing (and a topic author blocked by the asker).
4. Dedupe per source object, keeping its best chunk.
5. Merge across corpora by score, cap by count and total characters, renumber
   from 1 so ``[n]`` citations line up with the ``sources`` array.

Adding a corpus = a new index class + a refetcher keyed by its
``ModelSource.source_id`` + a ``kind`` for the client to style.
"""

import logging
from dataclasses import dataclass, replace

from apps.blog.models import BlogPostPage
from wagtail_forum.api.views import _exclude_blocked_authors, _visible_boards
from wagtail_forum.models import Topic

from . import constants
from .vector_indexes import BlogChunks, SimilarTopics, _scored_search

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Passage:
    n: int  # 1-based citation number after the merge
    kind: str  # "blog" | "topic" — the client styles provenance by this
    pk: int
    score: float
    title: str
    date: str  # ISO 8601, so a 2019 thread and a fresh article look different
    text: str  # what the prompt sees (≤ RAG_PASSAGE_MAX_CHARS)
    snippet: str  # what the client shows under the source (≤ RAG_SNIPPET_CHARS)
    # blog
    slug: str | None = None
    anchor: str | None = None  # "block-<index>", None once the index drifted
    # topic — enough for the client's threadPath(); no server URL building
    # (the todo-308 Site landmine) is needed.
    topic_id: int | None = None
    topic_slug: str | None = None
    board_id: int | None = None
    board_slug: str | None = None

    def as_source(self) -> dict:
        """The API's ``sources[]`` item — only the keys this kind carries."""
        base = {
            "n": self.n,
            "kind": self.kind,
            "title": self.title,
            "date": self.date,
            "snippet": self.snippet,
        }
        if self.kind == "blog":
            return {**base, "slug": self.slug, "anchor": self.anchor}
        return {
            **base,
            "topic_id": self.topic_id,
            "topic_slug": self.topic_slug,
            "board_id": self.board_id,
            "board_slug": self.board_slug,
        }


def _best_per_pk(docs) -> dict:
    best: dict = {}
    for doc in docs:
        pk = (doc.metadata or {}).get("pk")
        if pk is None:
            continue
        if pk not in best or doc.score > best[pk].score:
            best[pk] = doc
    return best


def _text(doc) -> str:
    return (doc.content or "")[: constants.RAG_PASSAGE_MAX_CHARS]


def _snippet(doc) -> str:
    return " ".join((doc.content or "").split())[: constants.RAG_SNIPPET_CHARS]


def _refetch_topics(docs, user) -> list[Passage]:
    best = _best_per_pk(docs)
    qs = Topic.objects.filter(
        pk__in=best, live=True, board__in=_visible_boards()
    ).select_related("board")
    qs = _exclude_blocked_authors(qs, user)
    return [
        Passage(
            n=0,
            kind="topic",
            pk=topic.pk,
            score=best[topic.pk].score,
            title=topic.title,
            date=topic.created_at.isoformat(),
            text=_text(best[topic.pk]),
            snippet=_snippet(best[topic.pk]),
            topic_id=topic.pk,
            topic_slug=topic.slug,
            board_id=topic.board_id,
            board_slug=topic.board.slug,
        )
        for topic in qs
    ]


def _refetch_blog(docs, user) -> list[Passage]:
    best = _best_per_pk(docs)
    passages = []
    for page in BlogPostPage.objects.live().public().filter(pk__in=best):
        doc = best[page.pk]
        block_index = (doc.metadata or {}).get("block_index")
        # An edit after indexing can leave the chunk pointing past the end of
        # raw_data; degrade the citation to the article rather than a dead anchor.
        in_range = isinstance(block_index, int) and 0 <= block_index < len(
            page.content_blocks.raw_data
        )
        passages.append(
            Passage(
                n=0,
                kind="blog",
                pk=page.pk,
                score=doc.score,
                title=page.title,
                date=page.publish_date.isoformat(),
                text=_text(doc),
                snippet=_snippet(doc),
                slug=page.slug,
                anchor=f"block-{block_index}" if in_range else None,
            )
        )
    return passages


# Keyed by ModelSource.source_id (the model label), which every document's
# metadata carries. A corpus with no refetcher is ignored — the index must
# never be the visibility authority.
_REFETCHERS = {
    "wagtail_forum.Topic": _refetch_topics,
    "blog.BlogPostPage": _refetch_blog,
}

_DEFAULT_INDEXES = (SimilarTopics, BlogChunks)


def retrieve_grounding_passages(
    question: str, *, user=None, indexes=_DEFAULT_INDEXES
) -> list[Passage] | None:
    """Scored, floored, visibility-checked, merged passages for ``question``.

    TRI-STATE, like the core it wraps: ``None`` when NO index searched at all
    (embedding budget exhausted, provider down) — the caller must answer
    "unavailable", not "no information", because the corpus was never checked;
    ``[]`` when at least one index searched and nothing clears the floor — the
    caller answers "no information" WITHOUT an LLM call. Never raises (the core
    never does, and the refetches are plain ORM reads).

    ``user`` — pass only from a caller whose OWN response is never cross-user
    cached (the same rule as ``find_similar_topics``); the RAG answer is
    per-asker and uncached, so the ask view passes it.
    """
    floor = constants.RAG_SIMILARITY_FLOOR
    by_source: dict[str, list] = {}
    top_scores: dict[str, float | None] = {}
    searched = False
    for index_cls in indexes:
        docs = _scored_search(index_cls, question, constants.RAG_OVERFETCH_PER_INDEX)
        label = getattr(index_cls, "__name__", "index")
        top_scores[label] = max((d.score for d in docs), default=None) if docs else None
        if docs is None:
            continue
        searched = True
        for doc in docs:
            if doc.score < floor:
                continue
            source_id = (doc.metadata or {}).get("source_id")
            by_source.setdefault(source_id, []).append(doc)
    if not searched:
        logger.warning("[RAG] retrieval unavailable: no index could search")
        return None

    # The calibration signal for RAG_SIMILARITY_FLOOR (todo 330): top score per
    # index on every question, never the question text itself.
    logger.info(
        "[RAG] retrieval top scores %s (floor %s); %d candidates above floor",
        top_scores,
        floor,
        sum(len(v) for v in by_source.values()),
    )

    passages: list[Passage] = []
    for source_id, docs in by_source.items():
        refetch = _REFETCHERS.get(source_id)
        if refetch is not None:
            passages.extend(refetch(docs, user))

    passages.sort(key=lambda p: p.score, reverse=True)
    merged: list[Passage] = []
    used = 0
    for passage in passages:
        if len(merged) >= constants.RAG_MAX_PASSAGES:
            break
        if used + len(passage.text) > constants.RAG_MAX_CONTEXT_CHARS:
            continue
        used += len(passage.text)
        merged.append(replace(passage, n=len(merged) + 1))
    return merged
