"""
Run migrations for simple server
"""
import os
import sys
import django

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'simple_settings')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

from django.conf import settings

if not settings.configured:
    settings.configure(
        DEBUG=True,
        SECRET_KEY='dev-key',
        ALLOWED_HOSTS=['*'],
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
        ],
        
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': os.path.join(BASE_DIR, 'plant_id.db'),
            }
        },
    )

django.setup()

from django.core.management import call_command

print("Running migrations...")
call_command('migrate', verbosity=1)
print("\n✅ Migrations complete! Database ready.")
print(f"Database file: {os.path.join(BASE_DIR, 'plant_id.db')}")
