"""The host envelope handler's ``message`` is human-readable for dict/list
details (todo 320).

``str(exc)`` on a DRF ``ValidationError`` with a dict/list ``detail`` is the
Python repr of ``ErrorDetail`` objects — ``{'poll': {'options': [ErrorDetail(
string='...', code='invalid')]}}`` — and every web page renders ``message``
verbatim. The package twin (``wagtail_forum/api/exception_handler.py``) cannot
import the host, so the flattener is duplicated there; the drift guard below
fails CI if one side is edited alone (same shape as
``docs/patterns/domain/forum.md`` "Cross-boundary drift guard", audit L16).
"""

import pytest
from apps.core.exceptions import custom_exception_handler
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from wagtail_forum.api.exception_handler import forum_exception_handler

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

SCALAR_MESSAGES = [
    (PermissionDenied, (), "You do not have permission to perform this action."),
    (
        NotFound,
        ("No Topic matches the given query.",),
        "No Topic matches the given query.",
    ),
    # DRF wraps a scalar ValidationError detail in a list; it flattens to the
    # bare sentence.
    (
        ValidationError,
        ("Poll close time must be in the future.",),
        "Poll close time must be in the future.",
    ),
]


def _handle(exc):
    return custom_exception_handler(exc, {})


@pytest.mark.django_db
@pytest.mark.parametrize("detail,expected", READABLE_CASES)
def test_validation_error_message_is_readable(detail, expected):
    resp = _handle(ValidationError(detail))

    assert resp.status_code == 400
    assert resp.data["message"] == expected
    assert "ErrorDetail" not in resp.data["message"]
    assert "{'" not in resp.data["message"] and resp.data["message"] != "{}"


@pytest.mark.django_db
def test_flattening_leaves_errors_structured():
    detail = {"poll": {"options": ["Poll options must be unique."]}}

    resp = _handle(ValidationError(detail))

    assert resp.data["errors"] == detail
    assert resp.data["code"] == "invalid"
    assert set(resp.data) == {"error", "message", "code", "status_code", "errors"}


@pytest.mark.django_db
@pytest.mark.parametrize("exc_class,args,expected", SCALAR_MESSAGES)
def test_scalar_detail_message_is_unchanged(exc_class, args, expected):
    # 401/403/404-style exceptions carry one string detail; str(exc) was
    # already readable there, and web clients (AuthContext, httpClient's CSRF
    # retry) match on that exact text.
    assert _handle(exc_class(*args)).data["message"] == expected


@pytest.mark.django_db
@pytest.mark.parametrize(
    "detail",
    [detail for detail, _ in READABLE_CASES]
    + ["Poll close time must be in the future."],
)
def test_package_handler_agrees_with_host_handler(detail):
    """Drift guard: the package duplicates the flattener because it cannot
    import the host. Editing one side alone must fail here, not in prod."""
    host = custom_exception_handler(ValidationError(detail), {})
    package = forum_exception_handler(ValidationError(detail), {})

    assert host.data["message"] == package.data["message"]
    assert host.data["errors"] == package.data["errors"]
