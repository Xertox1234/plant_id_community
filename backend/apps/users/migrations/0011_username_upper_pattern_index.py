"""Functional B-tree on UPPER(username) for @mention autocomplete (audit 2026-09-04 L11).

``wagtail_forum/api/user_search.py`` runs ``username__istartswith=query``,
which Django's PostgreSQL backend compiles as
``UPPER("auth_user"."username"::text) LIKE UPPER(%s)`` — a prefix LIKE on an
expression. The default unique B-tree on ``username`` serves neither half of
that: it is on the bare column, and under a non-C locale a plain B-tree
cannot serve LIKE at all (PostgreSQL §11.10, operator classes). The shape
that does is a B-tree on the SAME expression with ``text_pattern_ops`` (the
expression is ``text`` once cast). NOT a trigram GIN — that is the fix for
``icontains``' leading wildcard (blog migration 0014), which a prefix lacks.

Hand-written with a vendor guard like blog 0014 (``DATABASE_URL`` defaults
to SQLite in settings.py, where the opclass does not exist), so it is not in
``User.Meta.indexes`` and ``makemigrations --check`` stays clean. Built
``CONCURRENTLY`` with ``atomic = False`` (blog 0012/0014 precedent): a plain
``CREATE INDEX`` takes an ACCESS EXCLUSIVE lock on ``auth_user`` — the table
every authenticated request touches — for the whole build. Same accepted
tradeoff as 0014: a build that fails mid-way leaves an INVALID index that
``IF NOT EXISTS`` then skips on retry; drop it by hand and re-run.
``apps/users/tests/test_indexes.py`` pins the indexdef AND proves the planner
can serve the real ORM query from it (``enable_seqscan = off`` + EXPLAIN); at
today's row count Postgres still picks a seq scan, correctly, for a tiny table.
"""

from django.db import connection, migrations

INDEX_NAME = "users_username_upper_pat_idx"


def create_index(apps, schema_editor):
    if connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS users_username_upper_pat_idx "
            "ON auth_user (UPPER(username) text_pattern_ops)"
        )


def drop_index(apps, schema_editor):
    if connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("DROP INDEX CONCURRENTLY IF EXISTS users_username_upper_pat_idx")


class Migration(migrations.Migration):
    # CONCURRENTLY cannot run inside a transaction block.
    atomic = False

    dependencies = [
        ("users", "0010_user_is_premium"),
    ]

    operations = [
        migrations.RunPython(create_index, drop_index),
    ]
