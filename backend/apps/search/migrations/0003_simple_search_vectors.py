"""
Simple migration to add search vectors without complex queries.
"""

from django.db import migrations, connection
from psycopg2 import sql


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
                    # Use sql.Identifier to safely escape table names (prevents SQL injection)
                    cursor.execute(
                        sql.SQL("ALTER TABLE {} ADD COLUMN IF NOT EXISTS search_vector tsvector;").format(
                            sql.Identifier(table)
                        )
                    )
                    index_name = f"idx_{table.split('_')[-1]}_search_vector"
                    cursor.execute(
                        sql.SQL("CREATE INDEX IF NOT EXISTS {} ON {} USING gin(search_vector);").format(
                            sql.Identifier(index_name),
                            sql.Identifier(table)
                        )
                    )
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
                # Use sql.Identifier to safely escape table/index names (prevents SQL injection)
                index_name = f"idx_{table.split('_')[-1]}_search_vector"
                cursor.execute(
                    sql.SQL("DROP INDEX IF EXISTS {};").format(
                        sql.Identifier(index_name)
                    )
                )
                cursor.execute(
                    sql.SQL("ALTER TABLE {} DROP COLUMN IF EXISTS search_vector;").format(
                        sql.Identifier(table)
                    )
                )
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