# Generated manually for PostgreSQL GIN indexes
# Performance optimization for text search queries (ICONTAINS)

from django.db import connection, migrations
from django.contrib.postgres.operations import TrigramExtension


def is_postgresql():
    """Check if the current database is PostgreSQL."""
    return connection.vendor == 'postgresql'


def create_gin_indexes(apps, schema_editor):
    """Create GIN indexes only on PostgreSQL."""
    if not is_postgresql():
        return  # Skip on SQLite/other databases

    with schema_editor.connection.cursor() as cursor:
        # GIN indexes for full-text search
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_species_scientific_gin
            ON plant_identification_plantspecies
            USING gin(to_tsvector('english', scientific_name));
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_species_common_gin
            ON plant_identification_plantspecies
            USING gin(to_tsvector('english', common_names));
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_species_family_gin
            ON plant_identification_plantspecies
            USING gin(to_tsvector('english', family));
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_species_scientific_trgm
            ON plant_identification_plantspecies
            USING gin(scientific_name gin_trgm_ops);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_species_common_trgm
            ON plant_identification_plantspecies
            USING gin(common_names gin_trgm_ops);
        """)


def drop_gin_indexes(apps, schema_editor):
    """Drop GIN indexes only on PostgreSQL."""
    if not is_postgresql():
        return  # Skip on SQLite/other databases

    with schema_editor.connection.cursor() as cursor:
        cursor.execute("DROP INDEX IF EXISTS idx_species_scientific_gin;")
        cursor.execute("DROP INDEX IF EXISTS idx_species_common_gin;")
        cursor.execute("DROP INDEX IF EXISTS idx_species_family_gin;")
        cursor.execute("DROP INDEX IF EXISTS idx_species_scientific_trgm;")
        cursor.execute("DROP INDEX IF EXISTS idx_species_common_trgm;")


def create_composite_indexes(apps, schema_editor):
    """Create composite indexes (works on both PostgreSQL and SQLite)."""
    with schema_editor.connection.cursor() as cursor:
        # Composite index for user + status + date
        if is_postgresql():
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_request_user_status_date
                ON plant_identification_plantidentificationrequest(user_id, status, created_at DESC);
            """)
        else:
            # SQLite syntax (doesn't support DESC in index)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_request_user_status_date
                ON plant_identification_plantidentificationrequest(user_id, status, created_at);
            """)

        # FK optimization index
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_result_request_fk
            ON plant_identification_plantidentificationresult(request_id);
        """)


def drop_composite_indexes(apps, schema_editor):
    """Drop composite indexes."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("DROP INDEX IF EXISTS idx_request_user_status_date;")
        cursor.execute("DROP INDEX IF EXISTS idx_result_request_fk;")


class Migration(migrations.Migration):

    dependencies = [
        ('plant_identification', '0012_add_performance_indexes'),
    ]

    operations = [
        # Enable PostgreSQL trigram extension (no-op on SQLite)
        migrations.RunPython(
            lambda apps, schema_editor: (
                schema_editor.connection.cursor().execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
                if is_postgresql() else None
            ),
            lambda apps, schema_editor: None,  # No reverse
        ),

        # GIN indexes for full-text search (PostgreSQL only)
        migrations.RunPython(create_gin_indexes, drop_gin_indexes),

        # Composite indexes (works on both databases)
        migrations.RunPython(create_composite_indexes, drop_composite_indexes),
    ]
