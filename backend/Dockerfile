# ===================================
# Backend Dockerfile - Plant Community
# Django 5.2 LTS + Wagtail 7.0 LTS
# Multi-stage build for optimization
# ===================================

# Base Python image with security updates
FROM python:3.12-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    postgresql-client \
    gettext \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r django && useradd -r -g django django

# ===================================
# Development/Dependencies Stage
# ===================================
FROM base as dependencies

# Copy requirements file
COPY requirements.txt /tmp/requirements.txt

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt

# ===================================
# Production Stage
# ===================================
FROM base as production

# Copy installed packages from dependencies stage
COPY --from=dependencies /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin

# Set work directory
WORKDIR /app

# Create necessary directories
RUN mkdir -p /app/static /app/media /app/logs /app/machina_attachments_cache && \
    chown -R django:django /app

# Copy application code
COPY --chown=django:django . /app/

# Create entrypoint script
RUN cat > /app/docker-entrypoint.sh << 'EOF'
#!/bin/bash
set -e

echo "=== Plant Community Backend Starting ==="

# Wait for database
echo "Waiting for database..."
until pg_isready -h $DB_HOST -p $DB_PORT -U $DB_USER; do
  echo "Database is unavailable - sleeping"
  sleep 2
done
echo "Database is up - continuing..."

# Run database migrations
echo "Running database migrations..."
python manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput --clear

# Create superuser if it doesn't exist
echo "Creating default superuser if needed..."
python manage.py shell << PYTHON_EOF
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser(
        username='admin',
        email='admin@plantcommunity.com',
        password='changeme123'
    )
    print("Default superuser created: admin/changeme123")
else:
    print("Superuser already exists")
PYTHON_EOF

# Execute the main command
echo "Starting application..."
exec "$@"
EOF

# Make entrypoint executable
RUN chmod +x /app/docker-entrypoint.sh

# Health check script
RUN cat > /app/healthcheck.py << 'EOF'
#!/usr/bin/env python
import os
import sys
import django
from django.conf import settings
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'plant_community_backend.settings')
django.setup()

try:
    from django.db import connections
    from django.core.cache import cache
    
    # Check database connection
    db_conn = connections['default']
    db_conn.cursor()
    
    # Check cache connection
    cache.get('health_check')
    
    print("Health check passed")
    sys.exit(0)
except Exception as e:
    print(f"Health check failed: {e}")
    sys.exit(1)
EOF

RUN chmod +x /app/healthcheck.py

# Switch to non-root user
USER django

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python /app/healthcheck.py

# Set entrypoint
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Default command for production using Daphne for WebSocket support
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "--access-log", "-", "plant_community_backend.asgi:application"]