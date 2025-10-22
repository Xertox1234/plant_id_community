"""
Simple migration to add search vectors without complex queries.
"""

from django.db import migrations, connection


def add_simple_search_vectors(apps, schema_editor):
    """Add search vector fields only, without initial data."""
    if connection.vendor != 'postgresql':
        return  # Skip for non-PostgreSQL databases
    
    with connection.cursor() as cursor:
        # Add search vector columns without populating them initially
        tables_to_modify = [
            'machina_forum_conversation_topic',
            'machina_forum_conversation_post', 
            'plant_identification_plantspecies',
            'plant_identification_plantdiseasedatabase',
            'blog_blogpostpage'
        ]
        
        for table in tables_to_modify:
            # Check if table exists
            cursor.execute(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %s)",
                [table]
            )
            if cursor.fetchone()[0]:
                try:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS search_vector tsvector;")
                    cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table.split('_')[-1]}_search_vector ON {table} USING gin(search_vector);")
                except Exception as e:
                    print(f"Skipping {table}: {e}")


def remove_simple_search_vectors(apps, schema_editor):
    """Remove search vector fields."""
    if connection.vendor != 'postgresql':
        return  # Skip for non-PostgreSQL databases
        
    with connection.cursor() as cursor:
        tables_to_modify = [
            'machina_forum_conversation_topic',
            'machina_forum_conversation_post', 
            'plant_identification_plantspecies',
            'plant_identification_plantdiseasedatabase',
            'blog_blogpostpage'
        ]
        
        for table in tables_to_modify:
            try:
                cursor.execute(f"DROP INDEX IF EXISTS idx_{table.split('_')[-1]}_search_vector;")
                cursor.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS search_vector;")
            except Exception as e:
                print(f"Error removing search vectors from {table}: {e}")


class Migration(migrations.Migration):
    
    dependencies = [
        ('search', '0001_initial'),
    ]
    
    operations = [
        migrations.RunPython(
            add_simple_search_vectors,
            remove_simple_search_vectors
        ),
    ]