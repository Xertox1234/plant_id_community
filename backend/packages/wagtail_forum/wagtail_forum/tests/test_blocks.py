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
    # Exercise the actual rejection path (api/sanitize.py), not just the block
    # configuration — a config-only assertion can't fail if rejection regresses.
    import pytest
    from rest_framework.serializers import ValidationError
    from wagtail_forum.api.sanitize import validate_forum_body

    with pytest.raises(ValidationError):
        validate_forum_body([{"type": "raw_html", "value": "<script>x</script>"}])


def test_image_blocks_are_rejected_on_the_api_path():
    # ChooserBlock PKs are not resolved by the dry-run validation, so an API
    # caller could reference restricted-collection images by id (audit L5).
    import pytest
    from rest_framework.serializers import ValidationError
    from wagtail_forum.api.sanitize import validate_forum_body

    with pytest.raises(ValidationError):
        validate_forum_body([{"type": "image", "value": 12345}])


def test_oversized_body_chars_rejected():
    import pytest
    from rest_framework.serializers import ValidationError
    from wagtail_forum.api.sanitize import MAX_BODY_CHARS, validate_forum_body

    huge = [{"type": "paragraph", "value": "<p>" + "x" * MAX_BODY_CHARS + "</p>"}]
    with pytest.raises(ValidationError):
        validate_forum_body(huge)


def test_non_string_block_values_are_rejected_not_500():
    # An int paragraph value reaches nh3.clean() -> TypeError -> 500 without
    # this guard (review finding 3, execution-proven); int heading persists
    # silently (finding 4). Struct (code) blocks need dict-of-str.
    import pytest
    from rest_framework.serializers import ValidationError
    from wagtail_forum.api.sanitize import validate_forum_body

    for bad in (
        [{"type": "paragraph", "value": 123}],
        [{"type": "heading", "value": 123}],
        [{"type": "quote", "value": ["x"]}],
        [{"type": "code", "value": "not-a-dict"}],
        [{"type": "code", "value": {"language": "py", "code": 1}}],
    ):
        with pytest.raises(ValidationError):
            validate_forum_body(bad)
