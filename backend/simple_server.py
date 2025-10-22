"""
Minimal Django Server for Plant ID API
Run with: python simple_server.py

SECURITY WARNING: This is a simplified server for development only.
For production, use the main Django settings with proper security configuration.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'simple_settings')

import django
from django.conf import settings
from django.core.management import execute_from_command_line
from django.core.management.utils import get_random_secret_key
import sys

# Configure minimal Django settings
if not settings.configured:
    # Get SECRET_KEY from environment or generate one
    secret_key = os.getenv('SECRET_KEY')
    if not secret_key or secret_key.startswith('django-insecure'):
        secret_key = get_random_secret_key()
        print("WARNING: Using generated SECRET_KEY. Set SECRET_KEY in .env for persistence.")

    # Get API keys from environment
    plant_id_key = os.getenv('PLANT_ID_API_KEY')
    plantnet_key = os.getenv('PLANTNET_API_KEY')

    if not plant_id_key:
        raise ValueError("PLANT_ID_API_KEY not found in environment variables. Please set in .env file.")
    if not plantnet_key:
        raise ValueError("PLANTNET_API_KEY not found in environment variables. Please set in .env file.")

    # Parse CORS origins from environment
    cors_origins = os.getenv('CORS_ALLOWED_ORIGINS', 'http://localhost:5173').split(',')

    settings.configure(
        DEBUG=os.getenv('DEBUG', 'True').lower() == 'true',
        SECRET_KEY=secret_key,
        ALLOWED_HOSTS=os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(','),
        ROOT_URLCONF='simple_urls',

        INSTALLED_APPS=[
            'django.contrib.contenttypes',
            'django.contrib.auth',
            'rest_framework',
            'corsheaders',
        ],

        MIDDLEWARE=[
            'corsheaders.middleware.CorsMiddleware',
            'django.middleware.common.CommonMiddleware',
            'django.middleware.csrf.CsrfViewMiddleware',
            'django.middleware.security.SecurityMiddleware',
        ],

        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': os.path.join(os.path.dirname(__file__), 'plant_id.db'),
            }
        },

        # Redis Cache Configuration (Week 2 Performance Optimization)
        CACHES={
            'default': {
                'BACKEND': 'django_redis.cache.RedisCache',
                'LOCATION': os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/1'),
                'OPTIONS': {
                    'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                },
                'KEY_PREFIX': 'plant_id',
                'TIMEOUT': 86400,  # 24 hours default
            }
        },

        # CORS settings - SECURE (no ALLOW_ALL)
        CORS_ALLOWED_ORIGINS=cors_origins,
        CORS_ALLOW_CREDENTIALS=True,

        # Security headers
        SECURE_CONTENT_TYPE_NOSNIFF=True,
        SECURE_BROWSER_XSS_FILTER=True,
        X_FRAME_OPTIONS='DENY',

        # API Keys from environment variables
        PLANT_ID_API_KEY=plant_id_key,
        PLANTNET_API_KEY=plantnet_key,
        ENABLE_PLANT_ID=True,
        ENABLE_PLANTNET=True,
        PLANT_ID_API_TIMEOUT=int(os.getenv('PLANT_ID_API_TIMEOUT', '30')),
        PLANTNET_API_TIMEOUT=int(os.getenv('PLANTNET_API_TIMEOUT', '15')),

        REST_FRAMEWORK={
            'DEFAULT_PERMISSION_CLASSES': [
                'rest_framework.permissions.AllowAny',  # Will be secured in simple_views.py
            ],
        },
    )

django.setup()

if __name__ == '__main__':
    execute_from_command_line(['manage.py', 'runserver', '8000'])
