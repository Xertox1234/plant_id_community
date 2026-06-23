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
