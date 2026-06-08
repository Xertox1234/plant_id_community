from wagtail_forum.blocks import ForumBodyBlock


def test_body_block_accepts_safe_blocks():
    block = ForumBodyBlock()
    value = block.to_python(
        [
            {"type": "heading", "value": "Hello"},
            {"type": "paragraph", "value": "<p>Hi there</p>"},
        ]
    )
    assert [child.block_type for child in value] == ["heading", "paragraph"]


def test_body_block_rejects_unknown_block_type():
    block = ForumBodyBlock()
    child_names = set(block.child_blocks.keys())
    assert "raw_html" not in child_names
    assert {"heading", "paragraph", "quote", "code", "image"} <= child_names
