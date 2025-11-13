# Generated manually for PostgreSQL GIN indexes on Post.content_raw
# Performance optimization for full-text search queries (ICONTAINS)
# Issue #151: Missing GIN Index on Post.content_raw for Full-Text Search

from django.db import connection, migrations
from psycopg2 import sql


def is_postgresql():
    """Check if the current database is PostgreSQL."""
    return connection.vendor == 'postgresql'


def create_gin_indexes(apps, schema_editor):
    """
    Create GIN indexes on Post.content_raw for full-text search.

    Two index types:
    1. tsvector GIN: Full-text search with ranking (to_tsvector)
    2. trigram GIN: Pattern matching for partial searches (ICONTAINS)

    Only runs on PostgreSQL (gracefully skips on SQLite for dev).
    Uses psycopg2.sql.Identifier to prevent SQL injection (Issue #143 pattern).
    """
    if not is_postgresql():
        return  # Skip on SQLite/other databases

    with schema_editor.connection.cursor() as cursor:
        # Enable pg_trgm extension (idempotent)
        cursor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

        # Get the actual table name from the Post model
        Post = apps.get_model('forum', 'Post')
        table_name = Post._meta.db_table

        # GIN index for full-text search (tsvector)
        # Used for ranked full-text queries with @@ operator
        cursor.execute(
            sql.SQL("""
                CREATE INDEX IF NOT EXISTS idx_post_content_raw_gin_tsvector
                ON {table}
                USING gin(to_tsvector('english', content_raw));
            """).format(table=sql.Identifier(table_name))
        )

        # GIN index for trigram pattern matching (ICONTAINS)
        # Used for partial text search with ICONTAINS/LIKE operators
        # 100x faster than sequential scan at 100k+ posts
        cursor.execute(
            sql.SQL("""
                CREATE INDEX IF NOT EXISTS idx_post_content_raw_gin_trgm
                ON {table}
                USING gin(content_raw gin_trgm_ops);
            """).format(table=sql.Identifier(table_name))
        )


def drop_gin_indexes(apps, schema_editor):
    """Drop GIN indexes on Post.content_raw (rollback operation)."""
    if not is_postgresql():
        return  # Skip on SQLite/other databases

    with schema_editor.connection.cursor() as cursor:
        # Use DROP INDEX IF EXISTS for idempotent rollback
        cursor.execute("DROP INDEX IF EXISTS idx_post_content_raw_gin_tsvector;")
        cursor.execute("DROP INDEX IF EXISTS idx_post_content_raw_gin_trgm;")


class Migration(migrations.Migration):

    dependencies = [
        ('forum', '0007_attachment_active_index'),
    ]

    operations = [
        # GIN indexes for full-text search on Post.content_raw (PostgreSQL only)
        migrations.RunPython(create_gin_indexes, drop_gin_indexes),
    ]
