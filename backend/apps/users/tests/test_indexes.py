"""UPPER(username) text_pattern_ops index for @mention autocomplete (audit 2026-09-04 L11).

Two assertions, both needed (todo 323's lesson, blog/tests/test_indexes.py):
the indexdef, because a name-only check stays green if a later migration
swaps in a plain B-tree or the wrong expression; and an EXPLAIN of the REAL
ORM query with ``enable_seqscan`` off, because an index whose expression or
opclass does not match what Django emits compiles fine and is simply never
chosen — the planner reports a forced ``Seq Scan`` instead of this index.
"""

from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase

INDEX_NAME = "users_username_upper_pat_idx"


class UsernamePrefixIndexTestCase(TestCase):
    @skipUnless(
        connection.vendor == "postgresql",
        "text_pattern_ops is Postgres-only — migration 0011 no-ops elsewhere",
    )
    def test_username_upper_pattern_index_exists_with_the_right_shape(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT indexdef FROM pg_indexes "
                "WHERE tablename = 'auth_user' AND indexname = %s",
                [INDEX_NAME],
            )
            row = cursor.fetchone()
        self.assertIsNotNone(
            row,
            f"{INDEX_NAME} is missing — user_search's username__istartswith "
            "has no supporting index (audit 2026-09-04 L11).",
        )
        indexdef = row[0].lower()
        self.assertIn("using btree", indexdef)
        self.assertIn("upper(", indexdef)
        self.assertIn("text_pattern_ops", indexdef)

    @skipUnless(connection.vendor == "postgresql", "EXPLAIN shape is Postgres-only")
    def test_planner_can_serve_the_mention_lookup_from_the_index(self):
        User = get_user_model()
        User.objects.create_user(username="adaline")
        # The exact query wagtail_forum/api/user_search.py issues.
        sql, params = (
            User.objects.filter(is_active=True, username__istartswith="ad")
            .values("pk")
            .query.sql_with_params()
        )
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL enable_seqscan = off")
            cursor.execute("EXPLAIN " + sql, params)
            plan = "\n".join(line[0] for line in cursor.fetchall())
        self.assertIn(INDEX_NAME, plan, plan)
