"""The forum test suite must exercise the PostgreSQL/pgvector contract."""

import pytest
from django.db import connection


@pytest.mark.django_db
def test_forum_tests_use_postgresql_with_pgvector():
    assert connection.vendor == "postgresql"

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')"
        )
        has_vector = cursor.fetchone()[0]

    assert has_vector is True
