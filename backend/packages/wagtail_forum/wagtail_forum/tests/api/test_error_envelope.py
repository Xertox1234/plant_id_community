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
