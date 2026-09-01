"""Block-boundary chunker for blog articles (todo 289 / M13).

Turns a ``BlogPostPage.content_blocks.raw_data`` list into ``BlogChunk``s for
the ``BlogChunks`` vector index (``vector_indexes.py``). Pure functions — no DB,
no provider — so the index source and the tests can call them directly.

Why not django-ai-core's default ``SimpleChunkTransformer``: it windows blind
character ranges, which splits sentences mid-word and, worse, has no notion of
WHICH block a window came from — so a citation could only ever point at the
article, never at the passage (design doc §2). Here every chunk carries the
``raw_data`` index of its first (non-carried) block; the client turns that into
a ``#block-<index>`` anchor.

Rules:
- Pack whole blocks up to ``RAG_CHUNK_MAX_CHARS``; never split a block.
- Carry the trailing blocks of the previous chunk (up to
  ``RAG_CHUNK_OVERLAP_CHARS``) into the next one as context. Carried blocks do
  not move the anchor.
- A heading starts a new chunk (no overlap across sections), anchors it, and
  becomes the chunk's ``heading_path``; the title + heading path prefix every
  chunk's text so a passage still reads in context on its own.
- A single block over ``RAG_BLOCK_MAX_CHARS`` is truncated, not split.
- ``code`` and ``call_to_action`` blocks are skipped (not prose).
"""

from dataclasses import dataclass
from typing import Sequence

from . import constants
from .html_text import flatten_html


@dataclass(frozen=True)
class BlogChunk:
    block_index: int  # index into content_blocks.raw_data → "#block-<n>"
    heading_path: str  # nearest preceding heading, "" before the first one
    text: str  # what gets embedded: "<title> — <heading>\n<block>\n<block>…"


# Struct-block string fields worth embedding, in reading order. ``image`` (an
# int PK), choice fields and URLs are deliberately absent.
_STRUCT_TEXT_FIELDS = {
    "quote": ("quote_text", "attribution"),
    "plant_spotlight": ("plant_name", "scientific_name", "description"),
}


def block_plain_text(raw_block: dict) -> str | None:
    """Plain text of one raw StreamField block, or ``None`` if it carries none.

    Allowlisted by type: ``heading`` and ``paragraph`` (string values, the
    latter rich-text HTML), and the ``quote`` / ``plant_spotlight`` structs.
    Everything else — ``code``, ``call_to_action``, unknown types — is ``None``.
    """
    kind = raw_block.get("type")
    value = raw_block.get("value")
    if kind in ("heading", "paragraph"):
        text = flatten_html(value) if isinstance(value, str) else ""
    elif kind in _STRUCT_TEXT_FIELDS and isinstance(value, dict):
        parts = (value.get(field) for field in _STRUCT_TEXT_FIELDS[kind])
        text = "\n".join(
            flat for p in parts if isinstance(p, str) and (flat := flatten_html(p))
        )
    else:
        return None
    return text or None


def chunk_blocks(raw_blocks: Sequence[dict], *, title: str) -> list[BlogChunk]:
    """Chunk ``raw_blocks`` (``StreamValue.raw_data``) per the module rules."""
    chunks: list[BlogChunk] = []
    heading = ""
    # (block_index, text, carried) — the blocks packed into the chunk being built.
    items: list[tuple[int, str, bool]] = []

    def flush(*, carry: bool) -> None:
        nonlocal items
        real = [it for it in items if not it[2]]
        body = "\n".join(text for _, text, _ in items if text)
        if real and body:
            prefix = f"{title} — {heading}\n" if heading else f"{title}\n"
            chunks.append(
                BlogChunk(
                    block_index=real[0][0], heading_path=heading, text=prefix + body
                )
            )
        if not carry:
            items = []
            return
        # Overlap: keep the trailing real blocks that fit the overlap budget,
        # flagged as carried so they can never become the next anchor.
        kept: list[tuple[int, str, bool]] = []
        total = 0
        for index, text, _ in reversed(real):
            if not text or total + len(text) > constants.RAG_CHUNK_OVERLAP_CHARS:
                break
            kept.insert(0, (index, text, True))
            total += len(text)
        items = kept

    for index, raw in enumerate(raw_blocks):
        text = block_plain_text(raw)
        if raw.get("type") == "heading":
            # New section: no overlap across a heading; the heading itself is
            # the anchor and the path, not body text.
            flush(carry=False)
            heading = text or ""
            items = [(index, "", False)]
            continue
        if not text:
            continue
        text = text[: constants.RAG_BLOCK_MAX_CHARS]
        packed = sum(len(t) for _, t, _ in items)
        has_body = any(t and not carried for _, t, carried in items)
        if has_body and packed + len(text) > constants.RAG_CHUNK_MAX_CHARS:
            flush(carry=True)
        items.append((index, text, False))

    flush(carry=False)
    return chunks
