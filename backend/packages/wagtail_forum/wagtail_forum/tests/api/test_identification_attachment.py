"""Topic identification attachment — the plant-ID snapshot card (audit M6).

Covers the compose-time write contract (bounds, IDOR-safe photo, the
present-or-absent nesting), the detail-only read shape, and the two paths that
are easy to get wrong: a topic with NO attachment (a reverse OneToOne raises
rather than returning None) and an attachment whose photo was deleted.

The snapshot is caller-supplied by design — there is no server-side
identification record to resolve (see models/identifications.py) — so the write
bounds ARE the defence, and each one is pinned here.
"""

import io
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from PIL import Image as PILImage
from rest_framework.test import APIClient
from wagtail.images import get_image_model
from wagtail.models import Collection, Page
from wagtail_forum.api.serializers import TopicIdentificationSerializer
from wagtail_forum.collections import get_forum_image_collection
from wagtail_forum.models import (
    ForumBoard,
    ForumIdentificationAttachment,
    ForumIndex,
    ForumProfile,
    Topic,
    TrustLevel,
)
from wagtail_forum.workflow import ensure_default_workflow

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")

CANDIDATES = [
    {
        "name": "Swiss cheese plant",
        "scientific_name": "Monstera deliciosa",
        "confidence": 0.82,
    },
    {
        "name": "Heartleaf philodendron",
        "scientific_name": "Philodendron hederaceum",
        "confidence": 0.11,
    },
]


@pytest.fixture(autouse=True)
def clear_idempotency_cache():
    cache.clear()
    yield
    cache.clear()


def _board():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    return index.add_child(instance=ForumBoard(title="General", slug="general"))


def _trusted_client(username="asker"):
    """A MEMBER-trust user, so topic create publishes instead of going pending."""
    user = User.objects.create_user(username=username)
    profile = ForumProfile.for_user(user)
    profile.trust_level = TrustLevel.MEMBER
    profile.save()
    client = APIClient()
    client.force_authenticate(user)
    return client, user


def _jpeg_bytes():
    buf = io.BytesIO()
    PILImage.new("RGB", (10, 10), color="green").save(buf, format="JPEG")
    buf.seek(0)
    return buf.read()


def _forum_image(uploader, collection=None):
    """An image row as the forum upload endpoint would have created it."""
    return get_image_model().objects.create(
        title="plant.jpg",
        file=SimpleUploadedFile("plant.jpg", _jpeg_bytes(), content_type="image/jpeg"),
        collection=collection or get_forum_image_collection(),
        uploaded_by_user=uploader,
    )


def _create_topic(client, board, identification=None, slug="what-is-this"):
    payload = {
        "title": "What is this?",
        "slug": slug,
        "body": [{"type": "paragraph", "value": "<p>Found it in the yard.</p>"}],
    }
    if identification is not None:
        payload["identification"] = identification
    return client.post(f"/forum/boards/{board.slug}/topics/", payload, format="json")


# ---------------------------------------------------------------------------
# Write contract — happy paths
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_topic_with_an_identification_persists_the_snapshot():
    ensure_default_workflow()
    board = _board()
    client, user = _trusted_client()
    image = _forum_image(user)

    resp = _create_topic(
        client,
        board,
        {"image_id": image.id, "provider": "plant_id", "candidates": CANDIDATES},
    )

    assert resp.status_code == 201
    attachment = ForumIdentificationAttachment.objects.get(topic_id=resp.data["id"])
    assert attachment.image_id == image.id
    assert attachment.provider == "plant_id"
    assert attachment.candidates == CANDIDATES
    # No producer exists for this yet — it must default to empty, not null.
    assert attachment.identification_result_id == ""


@pytest.mark.django_db
def test_create_topic_without_an_identification_is_not_an_error():
    ensure_default_workflow()
    board = _board()
    client, _ = _trusted_client()

    resp = _create_topic(client, board)

    assert resp.status_code == 201
    assert not ForumIdentificationAttachment.objects.filter(
        topic_id=resp.data["id"]
    ).exists()


@pytest.mark.django_db
def test_an_identification_without_a_photo_is_allowed():
    """A user who ran an ID without keeping the photo still has useful
    candidates — the card falls back to text-only rather than the whole
    attachment being refused."""
    ensure_default_workflow()
    board = _board()
    client, _ = _trusted_client()

    resp = _create_topic(
        client, board, {"provider": "plantnet", "candidates": CANDIDATES}
    )

    assert resp.status_code == 201
    attachment = ForumIdentificationAttachment.objects.get(topic_id=resp.data["id"])
    assert attachment.image_id is None

    detail = client.get(f"/forum/topics/{resp.data['id']}/")
    assert detail.data["identification"]["image"] is None
    assert len(detail.data["identification"]["candidates"]) == 2


@pytest.mark.django_db
def test_the_snapshot_is_created_in_the_same_transaction_as_the_topic():
    """A topic whose attachment failed to write would render as an ordinary
    question, silently losing the thing it was asked about. Proven by the
    absence of a topic when the attachment insert blows up."""
    ensure_default_workflow()
    board = _board()
    client, user = _trusted_client()
    image = _forum_image(user)

    with patch(
        "wagtail_forum.api.views.ForumIdentificationAttachment.objects.create",
        side_effect=RuntimeError("boom"),
    ):
        resp = _create_topic(
            client, board, {"image_id": image.id, "candidates": CANDIDATES}
        )

    assert resp.status_code == 500
    # The whole create rolled back — no half-made topic, and no orphan opening
    # post pointing at one.
    assert not Topic.objects.filter(slug="what-is-this").exists()
    assert ForumIdentificationAttachment.objects.count() == 0


# ---------------------------------------------------------------------------
# Write contract — IDOR
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_photo_must_be_an_image_the_caller_uploaded():
    """Same rule as the avatar and inline-image paths: collection membership
    alone is not enough — otherwise any member could point the card at any
    other member's upload."""
    ensure_default_workflow()
    board = _board()
    client, _ = _trusted_client()
    someone_else = User.objects.create_user(username="stranger")
    their_image = _forum_image(someone_else)

    resp = _create_topic(
        client, board, {"image_id": their_image.id, "candidates": CANDIDATES}
    )

    assert resp.status_code == 400
    assert not Topic.objects.filter(slug="what-is-this").exists()


@pytest.mark.django_db
def test_a_photo_outside_the_forum_collection_is_rejected():
    ensure_default_workflow()
    board = _board()
    client, user = _trusted_client()
    other_collection = Collection.get_first_root_node().add_child(name="Blog Images")
    outside_image = _forum_image(user, collection=other_collection)

    resp = _create_topic(
        client, board, {"image_id": outside_image.id, "candidates": CANDIDATES}
    )

    assert resp.status_code == 400


@pytest.mark.django_db
def test_a_nonexistent_photo_id_is_rejected():
    ensure_default_workflow()
    board = _board()
    client, _ = _trusted_client()

    resp = _create_topic(client, board, {"image_id": 999999, "candidates": CANDIDATES})

    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Write contract — bounds
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_an_empty_candidate_list_is_rejected():
    ensure_default_workflow()
    board = _board()
    client, _ = _trusted_client()

    resp = _create_topic(client, board, {"candidates": []})

    assert resp.status_code == 400


@pytest.mark.django_db
def test_too_many_candidates_are_rejected():
    ensure_default_workflow()
    board = _board()
    client, _ = _trusted_client()
    four = [
        {"name": f"Plant {i}", "scientific_name": "", "confidence": 0.5}
        for i in range(4)
    ]

    resp = _create_topic(client, board, {"candidates": four})

    assert resp.status_code == 400


@pytest.mark.django_db
@override_settings(WAGTAILFORUM_TOPIC_IDENTIFICATION_MAX_CANDIDATES=4)
def test_the_candidate_bound_is_read_at_request_time():
    """Bounds come from get_setting at CALL time, so a host override (and
    @override_settings) actually applies — same rule as the tag bounds."""
    ensure_default_workflow()
    board = _board()
    client, _ = _trusted_client()
    four = [
        {"name": f"Plant {i}", "scientific_name": "", "confidence": 0.5}
        for i in range(4)
    ]

    resp = _create_topic(client, board, {"candidates": four})

    assert resp.status_code == 201


@pytest.mark.django_db
def test_a_huge_raw_candidate_list_is_rejected_before_child_validation():
    ensure_default_workflow()
    board = _board()
    client, _ = _trusted_client()
    flood = [{"name": "x", "confidence": 0.1}] * 101

    resp = _create_topic(client, board, {"candidates": flood})

    assert resp.status_code == 400


@pytest.mark.django_db
@pytest.mark.parametrize("confidence", [-0.01, 1.01, 42])
def test_confidence_outside_zero_to_one_is_rejected(confidence):
    ensure_default_workflow()
    board = _board()
    client, _ = _trusted_client()

    resp = _create_topic(
        client, board, {"candidates": [{"name": "Fern", "confidence": confidence}]}
    )

    assert resp.status_code == 400


def test_a_nan_confidence_is_rejected():
    """Every comparison with NaN is False, so FloatField's min/max bounds pass
    it through. Asserted at the serializer, not over HTTP: DRF's own STRICT_JSON
    parser rejects the `NaN` literal first, which would hide whether OUR guard
    works — and this package must not assume a host left that default on."""
    serializer = TopicIdentificationSerializer(
        data={"candidates": [{"name": "Fern", "confidence": float("nan")}]}
    )

    assert not serializer.is_valid()
    assert "candidates" in serializer.errors


def test_an_infinite_confidence_is_rejected():
    serializer = TopicIdentificationSerializer(
        data={"candidates": [{"name": "Fern", "confidence": float("inf")}]}
    )

    assert not serializer.is_valid()


@pytest.mark.django_db
def test_a_blank_candidate_name_is_rejected():
    ensure_default_workflow()
    board = _board()
    client, _ = _trusted_client()

    resp = _create_topic(
        client, board, {"candidates": [{"name": "", "confidence": 0.5}]}
    )

    assert resp.status_code == 400


@pytest.mark.django_db
def test_an_overlong_candidate_name_is_rejected():
    ensure_default_workflow()
    board = _board()
    client, _ = _trusted_client()

    resp = _create_topic(
        client, board, {"candidates": [{"name": "x" * 201, "confidence": 0.5}]}
    )

    assert resp.status_code == 400


@pytest.mark.django_db
def test_candidate_names_have_their_inner_whitespace_collapsed():
    """Without this, a "name" of 200 newlines passes the length check and
    renders as a wall in the card."""
    ensure_default_workflow()
    board = _board()
    client, _ = _trusted_client()

    resp = _create_topic(
        client,
        board,
        {"candidates": [{"name": "  Monstera \n\n\n  deliciosa  ", "confidence": 0.5}]},
    )

    assert resp.status_code == 201
    attachment = ForumIdentificationAttachment.objects.get(topic_id=resp.data["id"])
    assert attachment.candidates[0]["name"] == "Monstera deliciosa"


@pytest.mark.django_db
def test_an_overlong_provider_is_rejected():
    ensure_default_workflow()
    board = _board()
    client, _ = _trusted_client()

    resp = _create_topic(
        client, board, {"provider": "p" * 51, "candidates": CANDIDATES}
    )

    assert resp.status_code == 400


@pytest.mark.django_db
def test_an_overlong_identification_result_id_is_rejected():
    ensure_default_workflow()
    board = _board()
    client, _ = _trusted_client()

    resp = _create_topic(
        client,
        board,
        {"candidates": CANDIDATES, "identification_result_id": "r" * 65},
    )

    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Read shape
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_topic_detail_serializes_the_identification_card():
    ensure_default_workflow()
    board = _board()
    client, user = _trusted_client()
    image = _forum_image(user)
    created = _create_topic(
        client,
        board,
        {"image_id": image.id, "provider": "plant_id", "candidates": CANDIDATES},
    )

    detail = client.get(f"/forum/topics/{created.data['id']}/")

    assert detail.status_code == 200
    card = detail.data["identification"]
    assert set(card) == {"image", "provider", "candidates", "created_at"}
    assert card["provider"] == "plant_id"
    assert card["candidates"] == CANDIDATES
    assert set(card["image"]) == {"id", "url", "alt", "width", "height"}
    assert card["image"]["url"].startswith("http://testserver")


@pytest.mark.django_db
def test_topic_detail_identification_is_null_when_absent():
    """`identification` is a REVERSE OneToOne: a bare attribute read raises
    RelatedObjectDoesNotExist rather than returning None, and MOST topics have
    no attachment — so this is the path that 500s if the serializer reads it
    naively."""
    ensure_default_workflow()
    board = _board()
    client, _ = _trusted_client()
    created = _create_topic(client, board)

    detail = client.get(f"/forum/topics/{created.data['id']}/")

    assert detail.status_code == 200
    assert detail.data["identification"] is None


@pytest.mark.django_db
def test_the_result_id_is_never_serialized_out():
    """An internal correlation handle pointing into private identification
    history; the card has no use for it."""
    ensure_default_workflow()
    board = _board()
    client, _ = _trusted_client()
    created = _create_topic(client, board, {"candidates": CANDIDATES})
    ForumIdentificationAttachment.objects.filter(topic_id=created.data["id"]).update(
        identification_result_id="secret-correlation-handle"
    )

    detail = client.get(f"/forum/topics/{created.data['id']}/")

    assert "identification_result_id" not in detail.data["identification"]
    assert "secret-correlation-handle" not in str(detail.data)


@pytest.mark.django_db
def test_deleting_the_photo_leaves_the_snapshot_readable():
    """SET_NULL, not CASCADE: losing the image must not take the candidates —
    or the topic — with it. The card falls back to text-only."""
    ensure_default_workflow()
    board = _board()
    client, user = _trusted_client()
    image = _forum_image(user)
    created = _create_topic(
        client, board, {"image_id": image.id, "candidates": CANDIDATES}
    )

    image.delete()

    detail = client.get(f"/forum/topics/{created.data['id']}/")
    assert detail.status_code == 200
    assert detail.data["identification"]["image"] is None
    assert detail.data["identification"]["candidates"] == CANDIDATES


@pytest.mark.django_db
def test_deleting_the_topic_deletes_its_attachment():
    ensure_default_workflow()
    board = _board()
    client, _ = _trusted_client()
    created = _create_topic(client, board, {"candidates": CANDIDATES})

    Topic.objects.get(id=created.data["id"]).delete()

    assert ForumIdentificationAttachment.objects.count() == 0


@pytest.mark.django_db
def test_the_identification_is_absent_from_the_topic_list_payload():
    """DETAIL-ONLY, deliberately (roadmap: "a card above the opening post").
    Keeping it off the list is what leaves SearchView and the host's semantic
    _serialize — the other two topic-hit builders — untouched by this slice."""
    ensure_default_workflow()
    board = _board()
    client, _ = _trusted_client()
    _create_topic(client, board, {"candidates": CANDIDATES})

    listing = client.get(f"/forum/boards/{board.slug}/topics/")

    assert listing.status_code == 200
    assert "identification" not in listing.data["results"][0]


@pytest.mark.django_db
def test_topic_detail_query_count_with_an_identification_is_pinned():
    """The attachment row and its image ride the detail select_related, so the
    only extra cost over a plain topic is the rendition lookup behind the photo
    — one query, independent of candidate count.

    6 = the 5-query anonymous-shaped baseline (this client is the topic's
    AUTHOR, so `can_mark_solution` short-circuits before the two permission
    reads that make a non-author detail cost 8) + 1 rendition lookup.
    """
    ensure_default_workflow()
    board = _board()
    client, user = _trusted_client()
    image = _forum_image(user)
    created = _create_topic(
        client, board, {"image_id": image.id, "candidates": CANDIDATES}
    )
    url = f"/forum/topics/{created.data['id']}/"
    client.get(url)  # warm the rendition + view-count dedup cache

    with CaptureQueriesContext(connection) as ctx:
        resp = client.get(url)

    assert resp.status_code == 200
    assert resp.data["identification"]["image"] is not None
    assert len(ctx.captured_queries) == 6, [q["sql"] for q in ctx.captured_queries]
