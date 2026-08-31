"""
Test for the blog title GIN trigram index (todo 323).

search_suggestions (routed in todo 307) does title__icontains=query
against BlogPostPage with no supporting index. Migration
0014_add_blog_title_trigram_index adds a GIN trigram index on
UPPER(title) directly on wagtailcore_page via RunPython — title can't go
in BlogPostPage.Meta.indexes (Django system check models.E016: it's
inherited from wagtail.Page, not a local field), and UPPER(title) (not
bare title) is required because Django's PostgreSQL backend compiles
title__icontains as `UPPER(title::text) LIKE UPPER(%s)`, confirmed via
EXPLAIN during review — a bare-column trigram index cannot serve that
expression.

Asserts on indexdef, not just indexname: a name-only check would stay
green even if a future migration silently swapped the index for a plain
B-tree, or for one on the wrong (bare-title) expression — either change
would silently regress the exact performance problem this index exists
to fix.
"""

from unittest import skipUnless

from django.db import connection
from django.test import TestCase


class BlogTitleTrigramIndexTestCase(TestCase):
    @skipUnless(
        connection.vendor == "postgresql",
        "GIN trigram index is Postgres-only — migration 0014 no-ops elsewhere",
    )
    def test_title_trigram_index_is_gin_on_upper_title(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT indexdef FROM pg_indexes "
                "WHERE tablename = 'wagtailcore_page' "
                "AND indexname = 'wagtailcore_page_title_upper_trgm_idx'"
            )
            row = cursor.fetchone()
        self.assertIsNotNone(
            row,
            "wagtailcore_page_title_upper_trgm_idx is missing — "
            "search_suggestions' title__icontains query has no supporting "
            "GIN index (todo 323).",
        )
        indexdef = row[0].lower()
        self.assertIn("using gin", indexdef)
        self.assertIn("gin_trgm_ops", indexdef)
        self.assertIn("upper(", indexdef)
