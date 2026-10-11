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
    problems = sorted({*GENERATOR_STATS._warn_cache, *GENERATOR_STATS._error_cache})
    reset_generator_stats()
    assert not problems, "drf-spectacular reported:\n" + "\n".join(problems)
