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
        validate_forum_body(
            [{"type": "raw_html", "value": "<script>x</script>"}], set()
        )


@pytest.mark.django_db
def test_image_block_with_nonexistent_id_is_rejected():
    # The to_python dry-run never resolves chooser PKs, so a nonexistent id
    # would break rendering — the membership check rejects it (audit L5 guard).
    from rest_framework.serializers import ValidationError
    from wagtail_forum.api.sanitize import validate_forum_body

    with pytest.raises(ValidationError):
        validate_forum_body([{"type": "image", "value": 12345}], {1})


@pytest.mark.django_db
def test_image_block_in_forum_collection_uploaded_by_allowed_user_is_accepted():
    # PR-3 relaxes the blanket chooser rejection: an image that lives in the
    # forum collection AND was uploaded by an allowed user (audit L21) round-
    # trips through body validation unchanged.
    from django.contrib.auth import get_user_model
    from wagtail.images import get_image_model
    from wagtail.images.tests.utils import get_test_image_file
    from wagtail_forum.api.sanitize import validate_forum_body
    from wagtail_forum.collections import get_forum_image_collection

    uploader = get_user_model().objects.create_user(username="uploader")
    image = get_image_model().objects.create(
        title="seedling",
        file=get_test_image_file(),
        collection=get_forum_image_collection(),
        uploaded_by_user=uploader,
    )
    cleaned = validate_forum_body([{"type": "image", "value": image.id}], {uploader.pk})
    # ImageBlock shape (0037): the bare PK is normalised on write, and a
    # blank alt becomes decorative=True — the combination ImageBlock.clean()
    # accepts. These images have no description, hence alt_text "".
    assert cleaned == [
        {
            "type": "image",
            "value": {"image": image.id, "alt_text": "", "decorative": True},
        }
    ]


@pytest.mark.django_db
def test_image_block_uploaded_by_a_different_member_is_rejected():
    # audit L21: collection membership alone is not enough — an image another
    # member uploaded (not in allowed_uploader_ids) must not be referenceable
    # even though it lives in the shared forum collection.
    from django.contrib.auth import get_user_model
    from rest_framework.serializers import ValidationError
    from wagtail.images import get_image_model
    from wagtail.images.tests.utils import get_test_image_file
    from wagtail_forum.api.sanitize import validate_forum_body
    from wagtail_forum.collections import get_forum_image_collection

    uploader = get_user_model().objects.create_user(username="uploader")
    other = get_user_model().objects.create_user(username="other")
    image = get_image_model().objects.create(
        title="seedling",
        file=get_test_image_file(),
        collection=get_forum_image_collection(),
        uploaded_by_user=uploader,
    )
    with pytest.raises(ValidationError):
        validate_forum_body([{"type": "image", "value": image.id}], {other.pk})


@pytest.mark.django_db
def test_image_block_with_null_uploader_matches_none_in_allowed_ids():
    # Grandfathers an account-deleted author's pre-existing images: Wagtail's
    # Image.uploaded_by_user and Post.author both go SET_NULL together on
    # account deletion, so None is a legitimate member of allowed_uploader_ids
    # (wired by the edit call site's existing_author_id).
    from wagtail.images import get_image_model
    from wagtail.images.tests.utils import get_test_image_file
    from wagtail_forum.api.sanitize import validate_forum_body
    from wagtail_forum.collections import get_forum_image_collection

    image = get_image_model().objects.create(
        title="seedling",
        file=get_test_image_file(),
        collection=get_forum_image_collection(),
        uploaded_by_user=None,
    )
    cleaned = validate_forum_body([{"type": "image", "value": image.id}], {None})
    # ImageBlock shape (0037): the bare PK is normalised on write, and a
    # blank alt becomes decorative=True — the combination ImageBlock.clean()
    # accepts. These images have no description, hence alt_text "".
    assert cleaned == [
        {
            "type": "image",
            "value": {"image": image.id, "alt_text": "", "decorative": True},
        }
    ]


@pytest.mark.django_db
def test_image_block_outside_forum_collection_is_rejected():
    # Guessing a restricted asset's id is the exact IDOR the membership check
    # closes: an image in any other collection must not be referenceable, even
    # when its uploader is in allowed_uploader_ids.
    from django.contrib.auth import get_user_model
    from rest_framework.serializers import ValidationError
    from wagtail.images import get_image_model
    from wagtail.images.tests.utils import get_test_image_file
    from wagtail.models import Collection
    from wagtail_forum.api.sanitize import validate_forum_body

    uploader = get_user_model().objects.create_user(username="uploader")
    other = Collection.get_first_root_node().add_child(name="Private")
    image = get_image_model().objects.create(
        title="secret",
        file=get_test_image_file(),
        collection=other,
        uploaded_by_user=uploader,
    )
    with pytest.raises(ValidationError):
        validate_forum_body([{"type": "image", "value": image.id}], {uploader.pk})


def test_oversized_body_chars_rejected():
    import pytest
    from rest_framework.serializers import ValidationError
    from wagtail_forum.api.sanitize import MAX_BODY_CHARS, validate_forum_body

    huge = [{"type": "paragraph", "value": "<p>" + "x" * MAX_BODY_CHARS + "</p>"}]
    with pytest.raises(ValidationError):
        validate_forum_body(huge, set())


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
            validate_forum_body(bad, set())


# --- ImageBlock migration (0037/0038) -------------------------------------
#
# The block moved from ImageChooserBlock (bare PK, alt on Image.description) to
# ImageBlock ({image, alt_text, decorative}, alt per usage). Both shapes must be
# readable forever: revisions predate the migration, and a web build deployed
# before the frontend switch still POSTs the bare PK.


def _forum_image(username, description=""):
    from django.contrib.auth import get_user_model
    from wagtail.images import get_image_model
    from wagtail.images.tests.utils import get_test_image_file
    from wagtail_forum.collections import get_forum_image_collection

    uploader = get_user_model().objects.create_user(username=username)
    image = get_image_model().objects.create(
        title="IMG_2481.jpg",
        description=description,
        file=get_test_image_file(),
        collection=get_forum_image_collection(),
        uploaded_by_user=uploader,
    )
    return uploader, image


@pytest.mark.django_db
def test_image_block_accepts_the_imageblock_dict_with_alt_and_decorative():
    from wagtail_forum.api.sanitize import validate_forum_body

    uploader, image = _forum_image("ib-dict")
    cleaned = validate_forum_body(
        [
            {
                "type": "image",
                "value": {
                    "image": image.id,
                    "alt_text": "  A monstera leaf  ",
                    "decorative": False,
                },
            }
        ],
        {uploader.pk},
    )
    # Alt is stripped, and an authored alt keeps decorative False.
    assert cleaned[0]["value"] == {
        "image": image.id,
        "alt_text": "A monstera leaf",
        "decorative": False,
    }


@pytest.mark.django_db
def test_legacy_bare_pk_keeps_its_description_as_the_usage_alt():
    """A pre-0037 client still POSTs the bare PK; its alt lived on the Image.

    Normalising it to a blank alt_text would silently discard what the author
    typed at upload time — the regression this guards is invisible in the
    response (the read path would just fall back), but permanent in storage.
    """
    from wagtail_forum.api.sanitize import validate_forum_body

    uploader, image = _forum_image("ib-legacy", description="Author's own words")
    cleaned = validate_forum_body([{"type": "image", "value": image.id}], {uploader.pk})
    assert cleaned[0]["value"] == {
        "image": image.id,
        "alt_text": "Author's own words",
        "decorative": False,
    }


@pytest.mark.django_db
def test_blank_alt_normalises_to_decorative_so_the_cms_can_still_edit_it():
    """ImageBlock.clean() rejects "no alt text and not decorative".

    That clean() runs only through the admin form's BlockField, never through
    model full_clean(), so the API can happily store the combination it refuses
    — minting posts a moderator cannot open in /cms/. Normalising blank alt to
    decorative=True is what keeps the two paths consistent.
    """
    from wagtail_forum.api.sanitize import validate_forum_body

    uploader, image = _forum_image("ib-blank")
    cleaned = validate_forum_body(
        [
            {
                "type": "image",
                "value": {"image": image.id, "alt_text": "   ", "decorative": False},
            }
        ],
        {uploader.pk},
    )
    assert cleaned[0]["value"]["decorative"] is True
    assert cleaned[0]["value"]["alt_text"] == ""


@pytest.mark.django_db
def test_decorative_true_blanks_any_supplied_alt():
    from wagtail_forum.api.sanitize import validate_forum_body

    uploader, image = _forum_image("ib-dec")
    cleaned = validate_forum_body(
        [
            {
                "type": "image",
                "value": {
                    "image": image.id,
                    "alt_text": "ignored",
                    "decorative": True,
                },
            }
        ],
        {uploader.pk},
    )
    assert cleaned[0]["value"] == {
        "image": image.id,
        "alt_text": "",
        "decorative": True,
    }


@pytest.mark.django_db
def test_image_block_ownership_is_still_enforced_through_the_dict_shape():
    """audit L21 must not be bypassable by switching to the new shape."""
    from rest_framework.serializers import ValidationError
    from wagtail_forum.api.sanitize import validate_forum_body

    _uploader, image = _forum_image("ib-owner")
    intruder_ids = {-1}
    with pytest.raises(ValidationError):
        validate_forum_body(
            [
                {
                    "type": "image",
                    "value": {"image": image.id, "alt_text": "x", "decorative": False},
                }
            ],
            intruder_ids,
        )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "bad_value",
    [
        {"image": True, "alt_text": "", "decorative": False},  # bool is an int
        {"image": 1, "alt_text": 5, "decorative": False},  # alt not a string
        {"image": 1, "alt_text": "", "decorative": "yes"},  # decorative not bool
        {"image": 1, "unexpected": "key"},  # unknown sub-key
        {"alt_text": "no image key"},
        "not-a-dict-or-int",
    ],
)
def test_malformed_image_block_values_are_rejected(bad_value):
    from rest_framework.serializers import ValidationError
    from wagtail_forum.api.sanitize import validate_forum_body

    with pytest.raises(ValidationError):
        validate_forum_body([{"type": "image", "value": bad_value}], {1})


@pytest.mark.django_db
def test_none_alt_and_decorative_are_tolerated():
    """Wagtail itself writes None for both.

    ImageBlock._image_to_struct_value stores
    `{"alt_text": image and image.contextual_alt_text, "decorative": ...}`,
    which is None whenever an Image INSTANCE is assigned to the block instead of
    a raw dict — the CMS admin, fixtures, and `Post(body=[("image", img)])` all
    take that path. Treating None as malformed made those images resolve to None
    and vanish from the post with no error anywhere.
    """
    from wagtail_forum.api.sanitize import validate_forum_body

    uploader, image = _forum_image("ib-none", description="from the image row")
    cleaned = validate_forum_body(
        [
            {
                "type": "image",
                "value": {"image": image.id, "alt_text": None, "decorative": None},
            }
        ],
        {uploader.pk},
    )
    assert cleaned[0]["value"]["image"] == image.id


@pytest.mark.django_db  # instantiating an Image resolves Collection's default
def test_image_block_searchable_content_now_includes_alt_text():
    """Behaviour change, pinned deliberately.

    Post.search_fields declares SearchField("body") AND AutocompleteField("body").
    ImageChooserBlock.get_searchable_content returned nothing; ImageBlock's
    returns the usage's alt text — so an image's description is now findable in
    forum search. That is desirable (it is real authored content), but it is a
    change in what update_index writes, so it gets an explicit test rather than
    being discovered later.
    """
    from wagtail.images import get_image_model

    block = ForumBodyBlock().child_blocks["image"]
    image = get_image_model()(id=1, title="IMG_2481.jpg")
    image.contextual_alt_text = "A monstera leaf with brown edges"
    image.decorative = False
    assert block.get_searchable_content(image) == ["A monstera leaf with brown edges"]


@pytest.mark.django_db
def test_over_long_alt_is_truncated_not_rejected():
    """Matches the upload endpoint's idiom for the same value.

    Rejecting would also be unenforceable: ImageBlock.alt_text is a bare
    CharBlock with no max_length, so a moderator can save a longer one in /cms/
    and the API still has to serve that post.
    """
    from wagtail_forum.api.sanitize import MAX_ALT_TEXT_LENGTH, validate_forum_body

    uploader, image = _forum_image("ib-long")
    cleaned = validate_forum_body(
        [
            {
                "type": "image",
                "value": {
                    "image": image.id,
                    "alt_text": "x" * 400,
                    "decorative": False,
                },
            }
        ],
        {uploader.pk},
    )
    assert cleaned[0]["value"]["alt_text"] == "x" * MAX_ALT_TEXT_LENGTH


@pytest.mark.django_db
def test_read_accessor_still_resolves_a_block_the_writer_would_reject():
    """The read path must NEVER be stricter than storage.

    image_block_pk is used by build_forum_image_map, serialize_forum_body and
    the recent-topics thumbnail extractor. A rejection there does not become a
    400 — it makes the block serialise as null and the image vanish from the
    post with no error anywhere. So values a moderator could put in the column
    via /cms/ (a longer alt, or a key this package does not know) must still
    resolve to their PK.
    """
    from wagtail_forum.api.sanitize import _valid_image_block_value, image_block_pk

    long_alt = {"image": 7, "alt_text": "x" * 400, "decorative": False}
    unknown_key = {"image": 7, "alt_text": "a", "decorative": False, "caption": "?"}
    for value in (long_alt, unknown_key):
        assert image_block_pk(value) == 7, value

    # ...while the writer still refuses the unknown key outright.
    assert _valid_image_block_value(unknown_key) is False
    assert _valid_image_block_value(long_alt) is True  # truncated, not rejected
