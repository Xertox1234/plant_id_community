"""M39 (todo 258): the package's reference exception handler pins exactly ONE
error-envelope shape, so a host mounting wagtail_forum gets a consistent error
contract instead of bare DRF ``{"detail": ...}`` responses — WITHOUT depending on
the host's own handler. The integration side (host handler active) is pinned in
test_topic_create.py::test_oversized_body_is_rejected; this pins the shipped
package handler directly."""

import pytest
from rest_framework.exceptions import ValidationError
from wagtail_forum.api.exception_handler import forum_exception_handler
from wagtail_forum.api.exceptions import Conflict, UnprocessableEntity


def _handle(exc):
    return forum_exception_handler(exc, {})


@pytest.mark.django_db
def test_conflict_maps_to_the_core_envelope():
    msg = "A request with this Idempotency-Key is being processed."
    resp = _handle(Conflict(msg))
    assert resp.status_code == 409
    # A scalar detail nests under errors["detail"] — identical to the host
    # handler, so the two are interchangeable.
    assert resp.data == {
        "error": True,
        "message": msg,
        "code": "conflict",
        "status_code": 409,
        "errors": {"detail": msg},
    }


@pytest.mark.django_db
def test_unprocessable_entity_maps_to_422_envelope():
    resp = _handle(UnprocessableEntity("Key reused with a different payload."))
    assert resp.status_code == 422
    assert resp.data["error"] is True
    assert resp.data["code"] == "unprocessable"
    assert set(resp.data) == {"error", "message", "code", "status_code", "errors"}
    assert resp.data["errors"] == {"detail": "Key reused with a different payload."}


@pytest.mark.django_db
def test_validation_error_nests_field_errors_under_errors():
    resp = _handle(ValidationError({"body": ["This field is required."]}))
    assert resp.status_code == 400
    assert resp.data["error"] is True
    assert resp.data["code"] == "invalid"
    assert resp.data["errors"]["body"][0] == "This field is required."
    assert set(resp.data) == {"error", "message", "code", "status_code", "errors"}


READABLE_CASES = [
    ({"body": ["This field is required."]}, "body: This field is required."),
    (
        {"poll": {"options": ["Poll options must be unique."]}},
        "poll.options: Poll options must be unique.",
    ),
    # A many=True child: valid items are empty dicts, failures carry an index.
    ({"options": [{}, {"text": ["Too long."]}]}, "options[1].text: Too long."),
    ({"non_field_errors": ["Pick one."]}, "Pick one."),
    (["A.", "B."], "A. B."),
    (
        {"title": ["Required."], "poll": {"question": ["Too long."]}},
        "title: Required.; poll.question: Too long.",
    ),
    # A dict/list detail that flattens to nothing must not fall back to
    # str(exc) — '{}' is the repr the helper exists to avoid.
    ({}, "Invalid input."),
    ({"body": []}, "Invalid input."),
]


@pytest.mark.django_db
@pytest.mark.parametrize("detail,expected", READABLE_CASES)
def test_validation_error_message_is_readable(detail, expected):
    """``message`` is what a client renders verbatim, so a dict/list detail is
    flattened to ``field: text`` — never ``str(exc)``'s ``ErrorDetail`` repr
    (todo 320). Same table as the host's ``test_exception_envelope.py``, which
    also asserts the two handlers agree on it (drift guard)."""
    resp = _handle(ValidationError(detail))

    assert resp.status_code == 400
    assert resp.data["message"] == expected
    assert "ErrorDetail" not in resp.data["message"]
    assert "{'" not in resp.data["message"]


@pytest.mark.django_db
def test_scalar_detail_message_is_unchanged():
    resp = _handle(ValidationError("Poll close time must be in the future."))
    # DRF wraps a scalar ValidationError detail in a list; it flattens to the
    # bare sentence, and errors keeps DRF's non_field_errors shape.
    assert resp.data["message"] == "Poll close time must be in the future."
    assert resp.data["errors"] == {
        "non_field_errors": ["Poll close time must be in the future."]
    }


@pytest.mark.django_db
def test_unhandled_exception_falls_back_to_500_envelope():
    """A non-DRF exception (a bug) still returns the envelope, not an HTML page."""
    resp = _handle(RuntimeError("boom"))
    assert resp.status_code == 500
    assert resp.data == {
        "error": True,
        "message": "An unexpected error occurred",
        "code": "internal_error",
        "status_code": 500,
    }
