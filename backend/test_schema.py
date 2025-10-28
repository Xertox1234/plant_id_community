#!/usr/bin/env python
"""Test schema generation."""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'plant_community_backend.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from drf_spectacular.generators import SchemaGenerator

try:
    generator = SchemaGenerator()
    schema = generator.get_schema()

    paths = schema.get('paths', {})
    print(f"✓ Schema generated successfully!")
    print(f"✓ Total endpoints: {len(paths)}")
    print(f"\nSample endpoints:")
    for i, path in enumerate(list(paths.keys())[:10]):
        print(f"  {i+1}. {path}")

    print(f"\n✓ API Documentation is ready!")
    print(f"  - Swagger UI: http://localhost:8000/api/docs/")
    print(f"  - ReDoc UI: http://localhost:8000/api/redoc/")
    print(f"  - Schema download: http://localhost:8000/api/schema/")

except Exception as e:
    print(f"✗ Error generating schema: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
