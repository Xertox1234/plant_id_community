"""GIN trigram index for BlogPostPage title search (todo 323).

search_suggestions (routed in todo 307) does title__icontains=query
against BlogPostPage — a substring lookup with no supporting index.
docs/rules/database.md: "Add GIN indexes for __icontains / full-text
search columns; plain B-tree indexes do not accelerate substring search."

Index must be on UPPER(title), not bare title (empirically verified via
EXPLAIN, code review finding): Django's PostgreSQL backend compiles
`__icontains` as `UPPER("wagtailcore_page"."title"::text) LIKE UPPER(%s)`
(confirmed via `BlogPostPage.objects.filter(title__icontains=...).query`),
not a direct ILIKE. A GIN trigram index on the bare column doesn't match
that expression — Postgres only uses an expression index when the WHERE
clause's expression matches structurally. `EXPLAIN` with
`enable_seqscan = off` against a bare-title index showed a forced Seq
Scan ("Disabled: true"); against `UPPER(title) gin_trgm_ops`, the same
query correctly used a Bitmap Index Scan.

title cannot be added to BlogPostPage.Meta.indexes: it's declared on
wagtail.models.Page and lives in wagtailcore_page (multi-table
inheritance), not in blog_blogpostpage. Django's system check models.E016
rejects a Meta.indexes entry for a non-local field — the same constraint
BlogPostPage.Meta already documents for first_published_at. So this is a
hand-written migration against wagtailcore_page, same as the categories
junction-table index in migration 0007.

Uses CONCURRENTLY + a connection.vendor guard, mirroring migration
0012_recreate_trending_index_concurrently.py: wagtailcore_page is shared
by every Page subclass in the installation (not blog-scoped), so a plain
CREATE INDEX would lock writes across the whole site for the build's
duration — worse here than 0012's case, since wagtailcore_page is hotter
and larger than blog_blogpostview. The vendor guard also matters because
DATABASE_URL defaults to sqlite:///db.sqlite3 in this project's own
settings.py when unset.

pg_trgm is enabled via a plain RunPython pair with a true no-op reverse,
matching plant_identification/migrations/0013_add_search_gin_indexes.py's
established handling — NOT Django's built-in TrigramExtension() operation.
TrigramExtension()'s reverse (database_backwards) unconditionally runs
DROP EXTENSION IF EXISTS pg_trgm with no dependent-object check; since
migration 0013 already created GIN trigram indexes on
plant_identification_plantspecies using this same shared,
database-scoped extension, that DROP fails once those indexes exist
("cannot drop extension pg_trgm because other objects depend on it"),
breaking any rollback of this migration. A genuine no-op reverse avoids
that entirely — pg_trgm is a shared resource other migrations also rely
on, so this migration shouldn't try to tear it down on its own reverse.

Full-table (not blog-post-scoped): Postgres forbids subqueries in index
predicates, and a content type's numeric id isn't stable across
environments — a partial index scoped to content_type_id isn't viable
here. This also incidentally speeds up Wagtail admin's own title search
across all page types (which uses the same icontains-shaped lookup).
"""

from django.db import connection, migrations


def enable_pg_trgm(apps, schema_editor):
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")


def create_title_trigram_index(apps, schema_editor):
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        # CONCURRENTLY cannot run inside a transaction block — the
        # Migration class below sets atomic = False for this reason.
        cursor.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
            "wagtailcore_page_title_upper_trgm_idx "
            "ON wagtailcore_page USING gin (UPPER(title) gin_trgm_ops);"
        )


def drop_title_trigram_index(apps, schema_editor):
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS wagtailcore_page_title_upper_trgm_idx;"
        )


class Migration(migrations.Migration):
    # CONCURRENTLY requires running outside a transaction block.
    atomic = False

    dependencies = [
        ("blog", "0013_alter_blogpostpage_content_blocks"),
    ]

    operations = [
        # pg_trgm is a shared, database-scoped extension other migrations
        # also depend on (plant_identification/0013) — true no-op reverse,
        # not a DROP EXTENSION, so this migration's rollback can't break
        # another app's still-live indexes.
        migrations.RunPython(enable_pg_trgm, reverse_code=migrations.RunPython.noop),
        migrations.RunPython(
            create_title_trigram_index,
            reverse_code=drop_title_trigram_index,
        ),
    ]
