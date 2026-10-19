"""The single-post read's OpenAPI entry. No ``urls`` mark: like
test_schema.py, the schema is generated from the project URLconf."""

import pytest


@pytest.mark.django_db
def test_get_post_schema_declares_its_codes():
    from drf_spectacular.generators import SchemaGenerator

    paths = SchemaGenerator().get_schema(request=None, public=True)["paths"]
    get = paths["/forum/posts/{post_id}/"]["get"]
    assert get["operationId"] == "forum_posts_retrieve"
    # 429 is the host throttle hook's (pinned in apps/forum_host).
    assert set(get["responses"]) - {"429"} == {"200", "401", "404"}
