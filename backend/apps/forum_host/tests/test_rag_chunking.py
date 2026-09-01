"""Tests for the RAG blog chunker (todo 289 / M13).

Pure functions over ``BlogPostPage.content_blocks.raw_data`` — no DB, no
provider. The chunker exists because a whole-article embedding both dilutes
the vector and gives a useless citation ("somewhere in this 2000-word
article"); every chunk here must anchor on a real block index.
"""

from apps.forum_host import constants
from apps.forum_host.rag_chunking import block_plain_text, chunk_blocks

TITLE = "Killed by kindness"


def _p(text: str, *, html: bool = True) -> dict:
    return {"type": "paragraph", "value": f"<p>{text}</p>" if html else text}


def _h(text: str) -> dict:
    return {"type": "heading", "value": text}


def _text_of(n: int, marker: str) -> str:
    """A distinctive ~n-char body of UNIQUE words so packing assertions can find
    whole blocks and a truncated tail is never a substring of its head.
    Right-stripped because ``flatten_html`` strips each line."""
    words = " ".join(f"{marker}{i}" for i in range(n))
    return words[:n].rstrip()


# --------------------------------------------------------------------------- #
# block_plain_text — per-block extraction                                      #
# --------------------------------------------------------------------------- #


def test_paragraph_boundaries_are_not_fused():
    """strip_tags substitutes NOTHING for a tag, so "<p>a</p><p>b</p>" flattens
    to "ab" — the todo 275 review's high finding, and for a chunker the worst
    input possible (fused words inside a cited passage)."""
    text = block_plain_text(
        {"type": "paragraph", "value": "<p>Water weekly.</p><p>Feed monthly.</p>"}
    )
    assert "weekly.Feed" not in text
    assert "Water weekly." in text and "Feed monthly." in text


def test_entities_are_unescaped():
    assert block_plain_text(_p("Tom &amp; Jerry")) == "Tom & Jerry"
    # A pasted non-breaking space is an EMPTY block, not the truthy "&nbsp;".
    assert block_plain_text(_p("&nbsp;")) is None


def test_code_and_call_to_action_blocks_are_skipped():
    code = {"type": "code", "value": {"language": "python", "code": "print(1)"}}
    cta = {
        "type": "call_to_action",
        "value": {
            "cta_title": "Join us",
            "cta_description": "<p>Sign up today</p>",
            "button_text": "Go",
            "button_url": "https://example.com",
            "button_style": "primary",
        },
    }
    assert block_plain_text(code) is None
    assert block_plain_text(cta) is None
    assert block_plain_text({"type": "unknown", "value": "x"}) is None


def test_plant_spotlight_struct_string_fields_are_joined():
    block = {
        "type": "plant_spotlight",
        "value": {
            "plant_name": "Pothos",
            "scientific_name": "Epipremnum aureum",
            "description": "<p>Tolerates low light.</p>",
            "care_difficulty": "easy",
            "image": 5,
        },
    }
    text = block_plain_text(block)
    assert "Pothos" in text
    assert "Epipremnum aureum" in text
    assert "Tolerates low light." in text
    assert "5" not in text  # the image PK is not text


def test_quote_block_keeps_text_and_attribution():
    block = {
        "type": "quote",
        "value": {"quote_text": "<p>Less is more.</p>", "attribution": "A gardener"},
    }
    text = block_plain_text(block)
    assert "Less is more." in text
    assert "A gardener" in text


# --------------------------------------------------------------------------- #
# chunk_blocks — packing, anchors, heading paths                               #
# --------------------------------------------------------------------------- #


def test_empty_page_yields_no_chunks():
    assert chunk_blocks([], title=TITLE) == []
    assert chunk_blocks([_p("")], title=TITLE) == []
    assert chunk_blocks([_h("Watering")], title=TITLE) == []


def test_blocks_pack_to_max_chars_without_splitting_a_block():
    size = constants.RAG_CHUNK_MAX_CHARS // 2 - 50  # two fit, three don't
    a, b, c = (_text_of(size, m) for m in ("alpha", "bravo", "charlie"))
    chunks = chunk_blocks([_p(a), _p(b), _p(c)], title=TITLE)
    assert len(chunks) == 2
    assert a in chunks[0].text and b in chunks[0].text
    assert c in chunks[1].text
    # Never split mid-block: every block appears whole in exactly the chunk
    # that owns it (b is too long to be carried over as overlap).
    assert c not in chunks[0].text
    assert b not in chunks[1].text
    assert chunks[0].block_index == 0
    assert chunks[1].block_index == 2


def test_chunk_text_is_prefixed_with_title_and_heading_path():
    chunks = chunk_blocks(
        [_h("Watering"), _p("Less often than you think.")], title=TITLE
    )
    assert len(chunks) == 1
    assert chunks[0].heading_path == "Watering"
    assert chunks[0].text.startswith(f"{TITLE} — Watering\n")
    assert "Less often than you think." in chunks[0].text


def test_heading_path_resets_on_a_new_heading_and_anchors_on_it():
    chunks = chunk_blocks(
        [_h("Watering"), _p("Water less."), _h("Light"), _p("Bright, indirect.")],
        title=TITLE,
    )
    assert [c.heading_path for c in chunks] == ["Watering", "Light"]
    # A heading starts a new chunk whose anchor is the HEADING block, so a
    # citation lands on the section title, not a paragraph beneath it.
    assert [c.block_index for c in chunks] == [0, 2]
    assert "Water less." not in chunks[1].text  # no overlap across sections


def test_overlap_carries_trailing_blocks_but_does_not_move_the_anchor():
    big = constants.RAG_CHUNK_MAX_CHARS // 2
    small = constants.RAG_CHUNK_OVERLAP_CHARS - 20  # fits the overlap budget
    a = _text_of(big, "alpha")
    b = _text_of(small, "bravo")
    c = _text_of(big, "charlie")
    chunks = chunk_blocks([_p(a), _p(b), _p(c)], title=TITLE)
    assert len(chunks) == 2
    # b is carried into the second chunk as context…
    assert b in chunks[1].text and c in chunks[1].text
    # …but the anchor is the first NON-carried block.
    assert chunks[1].block_index == 2


def test_oversized_block_is_truncated_and_becomes_its_own_chunk():
    huge = _text_of(constants.RAG_BLOCK_MAX_CHARS + 500, "huge")
    chunks = chunk_blocks(
        [_p("Short intro."), _p(huge), _p("Short outro.")], title=TITLE
    )
    owner = next(c for c in chunks if c.block_index == 1)
    assert huge[: constants.RAG_BLOCK_MAX_CHARS] in owner.text
    assert huge[constants.RAG_BLOCK_MAX_CHARS :] not in owner.text
    assert "Short outro." not in owner.text
