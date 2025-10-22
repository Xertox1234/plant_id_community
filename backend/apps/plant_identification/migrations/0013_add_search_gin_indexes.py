# Generated manually for PostgreSQL GIN indexes
# Performance optimization for text search queries (ICONTAINS)

from django.db import migrations
from django.contrib.postgres.operations import TrigramExtension


class Migration(migrations.Migration):

    dependencies = [
        ('plant_identification', '0012_add_performance_indexes'),
    ]

    operations = [
        # Enable PostgreSQL trigram extension for similarity searches
        TrigramExtension(),

        # GIN indexes for full-text search on PlantSpecies
        # These dramatically improve ICONTAINS query performance
        migrations.RunSQL(
            sql="""
            -- GIN index for scientific_name full-text search
            CREATE INDEX IF NOT EXISTS idx_species_scientific_gin
            ON plant_identification_plantspecies
            USING gin(to_tsvector('english', scientific_name));

            -- GIN index for common_names full-text search
            CREATE INDEX IF NOT EXISTS idx_species_common_gin
            ON plant_identification_plantspecies
            USING gin(to_tsvector('english', common_names));

            -- GIN index for family full-text search
            CREATE INDEX IF NOT EXISTS idx_species_family_gin
            ON plant_identification_plantspecies
            USING gin(to_tsvector('english', family));

            -- Trigram index for fuzzy matching on scientific_name
            CREATE INDEX IF NOT EXISTS idx_species_scientific_trgm
            ON plant_identification_plantspecies
            USING gin(scientific_name gin_trgm_ops);

            -- Trigram index for fuzzy matching on common_names
            CREATE INDEX IF NOT EXISTS idx_species_common_trgm
            ON plant_identification_plantspecies
            USING gin(common_names gin_trgm_ops);
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS idx_species_scientific_gin;
            DROP INDEX IF EXISTS idx_species_common_gin;
            DROP INDEX IF EXISTS idx_species_family_gin;
            DROP INDEX IF EXISTS idx_species_scientific_trgm;
            DROP INDEX IF EXISTS idx_species_common_trgm;
            """
        ),

        # Additional composite index for common query patterns
        migrations.RunSQL(
            sql="""
            -- Composite index for user + status + date (common filtering pattern)
            CREATE INDEX IF NOT EXISTS idx_request_user_status_date
            ON plant_identification_plantidentificationrequest(user_id, status, created_at DESC);

            -- Index for result lookups by request (FK optimization)
            CREATE INDEX IF NOT EXISTS idx_result_request_fk
            ON plant_identification_plantidentificationresult(request_id);
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS idx_request_user_status_date;
            DROP INDEX IF EXISTS idx_result_request_fk;
            """
        ),
    ]
