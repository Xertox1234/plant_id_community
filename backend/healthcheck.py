#!/usr/bin/env python3
import os
import sys

# Ensure Django is set up
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "plant_community_backend.settings")

try:
    import django
    django.setup()
except Exception as e:
    print(f"Django setup failed: {e}")
    sys.exit(1)

# DB check
try:
    from django.db import connections
    with connections["default"].cursor() as cursor:
        cursor.execute("SELECT 1;")
        cursor.fetchone()
except Exception as e:
    print(f"Database check failed: {e}")
    sys.exit(1)

# Redis check (optional but recommended)
try:
    import redis  # type: ignore
    redis_url = os.environ.get("REDIS_URL")
    if redis_url:
        r = redis.from_url(redis_url, socket_connect_timeout=3, socket_timeout=3)
        r.ping()
except Exception as e:
    print(f"Redis check failed: {e}")
    sys.exit(1)

print("OK")
sys.exit(0)
