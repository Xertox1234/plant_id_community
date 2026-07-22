"""The forum OpenAPI schema documents a 429 on every rate-limited operation,
keeps unthrottled operations clean, and marks read-only fields (todo 254)."""

import pytest
from drf_spectacular.generators import SchemaGenerator

# (schema path, HTTP method) for every host-throttled forum operation — mirrors
# the @_throttled wrappers in apps/forum_host/api.py. Paths are post-trim
# (SCHEMA_PATH_PREFIX_TRIM strips /api/v1).
THROTTLED_OPERATIONS = [
    ("/forum/boards/{slug}/topics/", "post"),
    ("/forum/topics/{topic_id}/posts/", "post"),
    ("/forum/images/", "post"),
    ("/forum/posts/{post_id}/", "patch"),
    ("/forum/posts/{post_id}/", "delete"),
    ("/forum/posts/{post_id}/reactions/", "post"),
    ("/forum/me/profile/", "patch"),
    ("/forum/search/", "get"),
    ("/forum/sync/", "get"),
    ("/forum/notifications/unread-count/", "get"),
    ("/forum/notifications/mark-read/", "post"),
    ("/forum/topics/{topic_id}/subscription/", "post"),
    ("/forum/topics/{topic_id}/subscription/", "delete"),
    ("/forum/topics/{topic_id}/summary/", "get"),  # H14 premium AI summary
]


@pytest.fixture(scope="module")
def schema():
    # Generation is DB-free (view/serializer introspection) and applies the
    # PRE/POST-processing hooks from SPECTACULAR_SETTINGS, so the 429 hook runs.
    return SchemaGenerator().get_schema(request=None, public=True)


@pytest.mark.parametrize("path,method", THROTTLED_OPERATIONS)
def test_throttled_forum_operation_documents_429(schema, path, method):
    responses = schema["paths"][path][method]["responses"]
    assert "429" in responses, f"{method.upper()} {path} is throttled but has no 429"


def test_unthrottled_forum_get_has_no_429(schema):
    # The board's topic list GET is public + unthrottled (only its POST is rated);
    # the hook must document 429 ONLY on throttled operations, never blanket-add.
    get_op = schema["paths"]["/forum/boards/{slug}/topics/"]["get"]
    assert "429" not in get_op.get("responses", {})


def test_me_profile_operations_have_response_shapes(schema):
    # AC2 (auto-satisfied by drf-spectacular from the serializer, but pin it): the
    # profile GET + PATCH appear with a 200 response shape.
    profile = schema["paths"]["/forum/me/profile/"]
    assert "200" in profile["get"]["responses"]
    assert "200" in profile["patch"]["responses"]


def test_post_topic_id_is_read_only_in_schema(schema):
    topic_id = schema["components"]["schemas"]["Post"]["properties"]["topic_id"]
    assert topic_id.get("readOnly") is True
