"""OpenAPI generation is warning-free (todo 581).

CI runs ``manage.py spectacular --validate --fail-on-warn``, which fails on any
drf-spectacular warning or error. This test is the same gate inside pytest, so
a view added without a serializer or an ``@extend_schema`` fails here with the
list of offending views, not only in the backend-checks job.
"""

from drf_spectacular.drainage import GENERATOR_STATS, reset_generator_stats
from drf_spectacular.generators import SchemaGenerator


def test_schema_generation_emits_no_warnings_or_errors():
    reset_generator_stats()
    with GENERATOR_STATS.silence():
        SchemaGenerator().get_schema(request=None, public=True)
    # These caches are drf-spectacular internals. If an upgrade renames them,
    # fail here rather than read an empty set and pass with nothing checked.
    for cache in ("_warn_cache", "_error_cache"):
        assert hasattr(
            GENERATOR_STATS, cache
        ), f"drf-spectacular no longer has GENERATOR_STATS.{cache}; update this test"
    problems = sorted({*GENERATOR_STATS._warn_cache, *GENERATOR_STATS._error_cache})
    reset_generator_stats()
    assert not problems, "drf-spectacular reported:\n" + "\n".join(problems)


def test_gate_catches_a_view_without_a_serializer():
    """Canary: the caches above still fill, so an empty result means clean.

    The path sits under ``api/v1/``: SPECTACULAR_SETTINGS only enumerates
    paths matching ``SCHEMA_PATH_PREFIX``, so a bare path is never inspected.
    """
    from django.urls import path
    from rest_framework.decorators import api_view
    from rest_framework.response import Response

    @api_view(["POST"])
    def bare_view(request):
        return Response({})

    reset_generator_stats()
    with GENERATOR_STATS.silence():
        SchemaGenerator(patterns=[path("api/v1/canary/", bare_view)]).get_schema(
            request=None, public=True
        )
    problems = {*GENERATOR_STATS._warn_cache, *GENERATOR_STATS._error_cache}
    reset_generator_stats()
    assert problems, "a serializer-less view produced no drf-spectacular diagnostic"


def test_paginated_image_list_is_wrapped_once():
    """/forum/images/mine/ is one cursor page of images, not a page of pages."""
    schema = SchemaGenerator().get_schema(request=None, public=True)
    (op,) = [
        ops["get"]
        for p, ops in schema["paths"].items()
        if p.endswith("/forum/images/mine/")
    ]
    page = op["responses"]["200"]["content"]["application/json"]["schema"]
    assert set(page["properties"]) == {"next", "previous", "results"}
    item = page["properties"]["results"]["items"]
    assert "results" not in item.get("properties", {}), item
    assert {"id", "url", "alt"} <= set(item["properties"])
