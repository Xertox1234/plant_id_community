import pytest
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


@pytest.mark.django_db
def test_image_block_with_nonexistent_id_is_rejected():
    # The to_python dry-run never resolves chooser PKs, so a nonexistent id
    # would break rendering — the membership check rejects it (audit L5 guard).
    from rest_framework.serializers import ValidationError
    from wagtail_forum.api.sanitize import validate_forum_body

    with pytest.raises(ValidationError):
        validate_forum_body([{"type": "image", "value": 12345}])


@pytest.mark.django_db
def test_image_block_in_forum_collection_is_accepted():
    # PR-3 relaxes the blanket chooser rejection: an image that lives in the
    # forum collection round-trips through body validation unchanged.
    from wagtail.images import get_image_model
    from wagtail.images.tests.utils import get_test_image_file
    from wagtail_forum.api.sanitize import validate_forum_body
    from wagtail_forum.collections import get_forum_image_collection

    image = get_image_model().objects.create(
        title="seedling",
        file=get_test_image_file(),
        collection=get_forum_image_collection(),
    )
    cleaned = validate_forum_body([{"type": "image", "value": image.id}])
    assert cleaned == [{"type": "image", "value": image.id}]


@pytest.mark.django_db
def test_image_block_outside_forum_collection_is_rejected():
    # Guessing a restricted asset's id is the exact IDOR the membership check
    # closes: an image in any other collection must not be referenceable.
    from rest_framework.serializers import ValidationError
    from wagtail.images import get_image_model
    from wagtail.images.tests.utils import get_test_image_file
    from wagtail.models import Collection
    from wagtail_forum.api.sanitize import validate_forum_body

    other = Collection.get_first_root_node().add_child(name="Private")
    image = get_image_model().objects.create(
        title="secret", file=get_test_image_file(), collection=other
    )
    with pytest.raises(ValidationError):
        validate_forum_body([{"type": "image", "value": image.id}])


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
        # An image value must be the referenced PK (int); a string or a bool
        # (int subclass) is rejected by the type guard before the DB lookup.
        [{"type": "image", "value": "12"}],
        [{"type": "image", "value": True}],
    ):
        with pytest.raises(ValidationError):
            validate_forum_body(bad)
