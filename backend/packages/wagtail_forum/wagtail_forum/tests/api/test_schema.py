"""AC1: the read endpoints are OpenAPI-annotated (todo 231).

Generated against the REAL project urlconf — the bare test urlconf mounts the
forum at /forum/, but the project's `preprocess_exclude_wagtail` hook keeps only
/api/v1/* paths, so a /forum/-mounted schema is filtered to empty. Under the real
urlconf the forum sits at /api/v1/forum/, survives the hook, and SCHEMA_PATH_
PREFIX_TRIM strips /api/v1 → final keys are /forum/... .

Generating the schema also exercises the swagger_fake_view guards — without
them, PostListView.get_queryset's get_object_or_404 raises during generation.
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
