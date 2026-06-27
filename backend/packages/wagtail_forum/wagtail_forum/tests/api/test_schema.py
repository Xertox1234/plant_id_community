"""AC1: the read endpoints are OpenAPI-annotated (todo 231).

Generated against the REAL project urlconf — the bare test urlconf mounts the
forum at /forum/, but the project's `preprocess_exclude_wagtail` hook keeps only
/api/v1/* paths, so a /forum/-mounted schema is filtered to empty. Under the real
urlconf the forum sits at /api/v1/forum/, survives the hook, and SCHEMA_PATH_
PREFIX_TRIM strips /api/v1 → final keys are /forum/... .

This covers the operation-level `@extend_schema` (documented 200 + description).
The views' `get_queryset` also carry a `swagger_fake_view` guard whose job is to
suppress drf-spectacular's "Failed to obtain model through view's queryset"
warning during generation; that guard is NOT exercised by this test (the
generator resolves the model from `serializer_class`, not `get_queryset`), so do
not rely on this test to catch a guard regression.
"""

import pytest


@pytest.mark.django_db
def test_read_views_appear_in_openapi_schema_with_documented_200():
    from drf_spectacular.generators import SchemaGenerator

    schema = SchemaGenerator().get_schema(request=None, public=True)
    paths = schema["paths"]

    detail = paths["/forum/topics/{topic_id}/"]["get"]
    assert detail["responses"]["200"]["content"]["application/json"]["schema"]
    assert detail.get("description")

    post_list = paths["/forum/topics/{topic_id}/posts/"]["get"]
    assert post_list["responses"]["200"]["content"]["application/json"]["schema"]
    assert post_list.get("description")


@pytest.mark.django_db
def test_read_serializer_method_fields_are_typed_not_default_string():
    """@extend_schema_field gives the read serializers' SerializerMethodFields real
    types instead of drf-spectacular's `string` fallback (todo 231 review)."""
    from drf_spectacular.generators import SchemaGenerator

    schema = SchemaGenerator().get_schema(request=None, public=True)
    components = schema["components"]["schemas"]

    post = components["Post"]["properties"]
    assert post["author"]["type"] == "object"
    assert post["body"]["type"] == "array"
    assert post["edited_at"]["format"] == "date-time"
    assert post["status"]["type"] == "string"
    assert post["can_edit"]["type"] == "boolean"
    assert post["can_delete"]["type"] == "boolean"

    topic = components["TopicDetail"]["properties"]
    assert topic["board"]["type"] == "object"
    assert topic["opening_post_id"]["type"] == "integer"


@pytest.mark.django_db
def test_me_profile_capabilities_typed_as_object():
    """MeProfileSerializer.get_capabilities is typed via @extend_schema_field
    instead of drf-spectacular's `string` fallback (todo 238)."""
    from drf_spectacular.generators import SchemaGenerator

    schema = SchemaGenerator().get_schema(request=None, public=True)
    capabilities = schema["components"]["schemas"]["MeProfile"]["properties"][
        "capabilities"
    ]
    assert capabilities["type"] == "object"
    props = capabilities["properties"]
    assert set(props) == {"can_react", "can_reply", "can_create_topic"}
    assert props["can_react"]["type"] == "boolean"
    assert props["can_reply"]["type"] == "boolean"
    assert props["can_create_topic"]["type"] == "boolean"


@pytest.mark.django_db
def test_cookie_jwt_authenticator_documents_a_security_scheme():
    """CookieJWTAuthentication (the project default authenticator) is resolved to
    a cookie security scheme instead of an `could not resolve authenticator`
    warning + empty securitySchemes (todo 238). Project-wide: this makes Swagger's
    Authorize button work for every authenticated endpoint."""
    from drf_spectacular.generators import SchemaGenerator

    schema = SchemaGenerator().get_schema(request=None, public=True)
    schemes = schema["components"]["securitySchemes"]
    # Named jwtCookieAuth, not cookieAuth — the latter is drf-spectacular's
    # built-in SessionAuthentication scheme (sessionid); reusing it collides.
    assert schemes["jwtCookieAuth"] == {
        "type": "apiKey",
        "in": "cookie",
        "name": "access_token",
    }


@pytest.mark.django_db
def test_topic_list_view_guards_schema_generation():
    """TopicListView.get_queryset returns an empty queryset under
    `swagger_fake_view` (drf-spectacular's schema-generation flag) instead of
    raising KeyError on the absent `slug` kwarg. That guard is what suppresses the
    "Failed to obtain model" warning (todo 238) — the schema tests above resolve
    the model from `serializer_class`, so they would NOT catch the guard's removal.
    This pins it: drop the guard and `_get_board(self.kwargs["slug"])` raises
    KeyError here, failing loudly instead of silently regressing the warning."""
    from wagtail_forum.api.views import TopicListView

    view = TopicListView()
    view.swagger_fake_view = True
    view.kwargs = {}  # schema generation supplies no URL kwargs
    assert list(view.get_queryset()) == []
