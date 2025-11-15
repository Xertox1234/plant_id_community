"""
Django settings for plant_community_backend project.

Plant Community Web App - A comprehensive platform for plant enthusiasts
Built with Django 5.2 LTS, Wagtail 7.0 LTS, and modern web technologies.
"""

import os
import sys
from pathlib import Path
from decouple import config
import dj_database_url
from datetime import timedelta
import sentry_sdk
from django.core.exceptions import ImproperlyConfigured

# Optional JSON logging availability check for tests/local
try:
    from pythonjsonlogger import jsonlogger  # noqa: F401
    _HAS_JSON_LOGGER = True
except Exception:
    _HAS_JSON_LOGGER = False

# Optional request_id dependency
try:
    import request_id  # noqa: F401
    _HAS_REQUEST_ID = True
except Exception:
    _HAS_REQUEST_ID = False

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
# Environment-aware SECRET_KEY configuration with production validation
if config('DEBUG', default=False, cast=bool):
    # Development: Allow insecure default for local testing
    SECRET_KEY = config(
        'SECRET_KEY',
        default='django-insecure-dev-only-DO-NOT-USE-IN-PRODUCTION-abc123xyz'
    )
else:
    # Production: MUST have SECRET_KEY set - fail loudly if missing
    try:
        SECRET_KEY = config('SECRET_KEY')  # Raises Exception if not set
    except Exception:
        raise ImproperlyConfigured(
            "\n"
            "=" * 70 + "\n"
            "CRITICAL: SECRET_KEY environment variable is not set!\n"
            "=" * 70 + "\n"
            "Django requires a unique SECRET_KEY for production security.\n"
            "This key is used for cryptographic signing of:\n"
            "  - Session cookies (authentication)\n"
            "  - CSRF tokens (security)\n"
            "  - Password reset tokens\n"
            "  - Signed cookies\n"
            "\n"
            "Generate a secure key with:\n"
            "  python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'\n"
            "\n"
            "Then set in environment:\n"
            "  export SECRET_KEY='your-generated-key-here'\n"
            "\n"
            "Or add to .env file (do NOT commit):\n"
            "  SECRET_KEY=your-generated-key-here\n"
            "=" * 70 + "\n"
        )

    # Validate it's not a default/example value
    INSECURE_PATTERNS = [
        'django-insecure',
        'change-me',
        'your-secret-key-here',
        'secret',
        'password',
        'abc123',
    ]

    for pattern in INSECURE_PATTERNS:
        if pattern in SECRET_KEY.lower():
            raise ImproperlyConfigured(
                f"Production SECRET_KEY contains insecure pattern: '{pattern}'\n"
                f"Generate a new key with:\n"
                f"  python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'"
            )

    # Validate minimum length
    if len(SECRET_KEY) < 50:
        raise ImproperlyConfigured(
            f"Production SECRET_KEY is too short ({len(SECRET_KEY)} characters).\n"
            f"Django recommends at least 50 characters for security.\n"
            f"Generate a new key with:\n"
            f"  python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'"
        )

# SECURITY WARNING: don't run with debug turned on in production!
# Default to False for security - explicitly set DEBUG=True in development
DEBUG = config('DEBUG', default=False, cast=bool)
ENABLE_FILE_LOGGING = config('ENABLE_FILE_LOGGING', default=True, cast=bool)
# Default to disabling file logging inside Celery processes (can be overridden)
if any('celery' in arg for arg in sys.argv):
    ENABLE_FILE_LOGGING = config('ENABLE_FILE_LOGGING_CELERY', default=False, cast=bool)
print(f"[settings] ENABLE_FILE_LOGGING={ENABLE_FILE_LOGGING} (argv={sys.argv})")

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=lambda v: [s.strip() for s in v.split(',')])

# Application definition
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
]

WAGTAIL_APPS = [
    'wagtail.contrib.forms',
    'wagtail.contrib.redirects',
    'wagtail.contrib.settings',  # Required for Wagtail AI 3.0 admin UI
    'wagtail.embeds',
    'wagtail.sites',
    'wagtail.users',
    'wagtail.snippets',
    'wagtail.documents',
    'wagtail.images',
    'wagtail.search',
    'wagtail.admin',
    'wagtail',
    'wagtail.api.v2',
    'wagtail_ai',  # AI-powered content generation (Phase 1: Issue #157)
    'wagtail_headless_preview',  # Phase 3: Headless preview for React/Flutter
    'modelcluster',
    'taggit',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'drf_spectacular',  # OpenAPI 3.0 schema generation
    'corsheaders',
    'django_filters',
    'imagekit',
    'mptt',
    'widget_tweaks',
    'csp',  # Content Security Policy
    'django_celery_beat',
    'auditlog',  # Audit trail for data access tracking (GDPR compliance)
    # OAuth Authentication
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.github',
]

# Feature flags
ENABLE_FORUM = config('ENABLE_FORUM', default=False, cast=bool)

# Django Machina Apps (optional)
MACHINA_APPS = []
if ENABLE_FORUM:
    MACHINA_APPS = [
        'machina',
        'machina.apps.forum',
        'machina.apps.forum_conversation',
        'machina.apps.forum_conversation.forum_attachments',
        'machina.apps.forum_conversation.forum_polls',
        'machina.apps.forum_feeds',
        'machina.apps.forum_moderation',
        'machina.apps.forum_search',
        'machina.apps.forum_tracking',
        'machina.apps.forum_member',
        'machina.apps.forum_permission',
        'haystack',
    ]

# Local Apps
LOCAL_APPS = [
    'apps.users',
    'apps.plant_identification',
    'apps.blog',
    'apps.forum',  # New headless forum implementation
    'apps.core',
    # 'apps.search',  # Temporarily disabled (depends on Machina)
    'apps.garden_calendar',
    'apps.garden',  # Garden planner feature (Phase 1 - Backend)
]
# Temporarily disable forum_integration (depends on Machina)
# if ENABLE_FORUM:
#     LOCAL_APPS.insert(2, 'apps.forum_integration')

# Temporarily disable MACHINA_APPS while building new headless forum
# MACHINA_APPS will be removed entirely once new forum is production-ready
INSTALLED_APPS = DJANGO_APPS + WAGTAIL_APPS + THIRD_PARTY_APPS + LOCAL_APPS  # + MACHINA_APPS

# WebSockets via Django Channels
INSTALLED_APPS += [
    'channels',
]

if DEBUG:
    INSTALLED_APPS += [
        'debug_toolbar',
        'django_extensions',
    ]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Static file serving
    'apps.core.security.SecurityMiddleware',  # Security monitoring
    'apps.core.middleware.RateLimitMonitoringMiddleware',  # Rate limit monitoring
    'apps.core.middleware.SecurityMetricsMiddleware',  # Security metrics collection
    'apps.core.middleware.PermissionsPolicyMiddleware',  # Permissions-Policy header (Issue #145)
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',  # OAuth middleware
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'wagtail.contrib.redirects.middleware.RedirectMiddleware',
    'apps.blog.middleware.BlogViewTrackingMiddleware',  # Blog analytics (Phase 6.2)
]

# Add CSP middleware only in production (disabled in dev to allow Wagtail admin widgets)
if not DEBUG:
    MIDDLEWARE.insert(
        MIDDLEWARE.index('django.middleware.clickjacking.XFrameOptionsMiddleware') + 1,
        'csp.middleware.CSPMiddleware'
    )

if _HAS_REQUEST_ID:
    MIDDLEWARE.append('request_id.middleware.RequestIdMiddleware')  # Request ID tracking

if DEBUG:
    MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']

# Include forum permission middleware only when forum is enabled
# Temporarily disabled (depends on Machina)
# if ENABLE_FORUM:
#     MIDDLEWARE.append('machina.apps.forum_permission.middleware.ForumPermissionMiddleware')

ROOT_URLCONF = 'plant_community_backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates',
            BASE_DIR / 'apps' / 'forum_integration' / 'templates',
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'machina.core.context_processors.metadata',
                'apps.forum_integration.context_processors.forum_globals',
            ],
        },
    },
]

WSGI_APPLICATION = 'plant_community_backend.wsgi.application'
# ASGI application for Channels
ASGI_APPLICATION = 'plant_community_backend.asgi.application'

# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases
DATABASES = {
    'default': dj_database_url.config(
        default=config('DATABASE_URL', default='sqlite:///db.sqlite3'),
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# Use PostgreSQL for tests to match production environment
# This ensures PostgreSQL-specific features (GIN indexes, trigrams, etc.) work correctly
if 'test' in sys.argv:
    import getpass
    DATABASES['default'] = {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('TEST_DB_NAME', default='plant_community_test'),
        'USER': config('TEST_DB_USER', default=getpass.getuser()),
        'PASSWORD': config('TEST_DB_PASSWORD', default=''),
        'HOST': config('TEST_DB_HOST', default='localhost'),
        'PORT': config('TEST_DB_PORT', default='5432'),
        'TEST': {
            'NAME': 'test_plant_community',
        }
    }


# Cache configuration with Redis fallback to dummy cache
try:
    # Try Redis configuration if available
    import redis
    redis_url = config('REDIS_URL', default='redis://127.0.0.1:6379/1')
    redis_client = redis.from_url(redis_url)
    redis_client.ping()  # Test connection
    
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': redis_url,
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'CONNECTION_POOL_KWARGS': {
                    'retry_on_timeout': True,
                    'socket_keepalive': True,
                    'socket_keepalive_options': {},
                },
                'IGNORE_EXCEPTIONS': True,
            },
            'KEY_PREFIX': 'plant_community',
            'TIMEOUT': 300,
        },
        'machina_attachments': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': config('REDIS_URL', default='redis://127.0.0.1:6379/2'),
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'IGNORE_EXCEPTIONS': True,
            },
            'KEY_PREFIX': 'machina_attachments',
        },
        'renditions': {
            # Phase 2.5: Wagtail image rendition cache
            # Long TTL (1 year) because renditions are immutable
            # Significantly reduces database queries for image generation
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': config('REDIS_URL', default='redis://127.0.0.1:6379/3'),
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'IGNORE_EXCEPTIONS': True,
            },
            'KEY_PREFIX': 'wagtail_renditions',
            'TIMEOUT': 31536000,  # 1 year (images rarely change)
        }
    }
except (ImportError, redis.ConnectionError, redis.TimeoutError):
    # Fallback to local memory cache if Redis is not available
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-snowflake',
            'TIMEOUT': 300,
            'OPTIONS': {
                'MAX_ENTRIES': 1000,
            }
        },
        'machina_attachments': {
            'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
            'LOCATION': BASE_DIR / 'machina_attachments_cache',
            'TIMEOUT': 3600,
            'OPTIONS': {
                'MAX_ENTRIES': 500,
            }
        },
        'renditions': {
            # Phase 2.5: Fallback rendition cache (file-based)
            'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
            'LOCATION': BASE_DIR / 'wagtail_renditions_cache',
            'TIMEOUT': 31536000,  # 1 year
            'OPTIONS': {
                'MAX_ENTRIES': 5000,
            }
        }
    }

# Session configuration - use database sessions for development
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
# Session timeout after 24 hours of inactivity
SESSION_COOKIE_AGE = 86400  # 24 hours
SESSION_SAVE_EVERY_REQUEST = True  # Reset timeout on activity

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 14,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# WhiteNoise configuration for optimized static file serving
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
WHITENOISE_AUTOREFRESH = DEBUG  # Auto-refresh in development
WHITENOISE_USE_FINDERS = DEBUG  # Use finders in development
WHITENOISE_COMPRESS_OFFLINE = not DEBUG  # Pre-compress files in production
WHITENOISE_KEEP_ONLY_HASHED_FILES = not DEBUG  # Keep only hashed files in production
WHITENOISE_MANIFEST_STRICT = not DEBUG  # Strict manifest in production

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Sites framework
SITE_ID = 1

# Wagtail settings
WAGTAIL_SITE_NAME = 'Plant Community'
WAGTAIL_FRONTEND_LOGIN_URL = '/accounts/login/'
# WAGTAILIMAGES_IMAGE_MODEL = 'core.CustomImage'  # Uncomment after creating core app

# Base URL to use when referring to full URLs within the Wagtail admin backend
WAGTAILADMIN_BASE_URL = 'http://localhost:8000'
 # Frontend base URL (used for OAuth redirect targets)
FRONTEND_BASE_URL = config('FRONTEND_BASE_URL', default='http://localhost:3000')

# Wagtail Headless Preview (Phase 3)
# Configuration for React/Flutter preview of unpublished content
HEADLESS_PREVIEW_CLIENT_URLS = {
    'default': config(
        'HEADLESS_PREVIEW_CLIENT_URL',
        default='http://localhost:5173/blog/preview/{content_type}/{token}/'
    ),
}
HEADLESS_PREVIEW_LIVE = config('HEADLESS_PREVIEW_LIVE', default=True, cast=bool)

# Use custom user model
AUTH_USER_MODEL = 'users.User'

# Django REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'apps.users.authentication.CookieJWTAuthentication',
        'rest_framework_simplejwt.authentication.JWTAuthentication',  # Fallback
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'EXCEPTION_HANDLER': 'apps.core.exceptions.custom_exception_handler',
    # API Versioning
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.NamespaceVersioning',
    'DEFAULT_VERSION': 'v1',
    'ALLOWED_VERSIONS': ['v1', 'v2'],  # v2 is for Wagtail API endpoints
    'VERSION_PARAM': 'version',
    # API Schema Generation
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# drf-spectacular OpenAPI Schema Settings
SPECTACULAR_SETTINGS = {
    'TITLE': 'Plant ID Community API',
    'DESCRIPTION': 'Plant identification and community platform API with dual provider support (Plant.id + PlantNet)',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'CONTACT': {
        'name': 'Plant ID Community',
        'url': 'https://github.com/Xertox1234/plant_id_community',
    },
    'LICENSE': {
        'name': 'MIT License',
    },
    'COMPONENT_SPLIT_REQUEST': True,
    'SORT_OPERATIONS': False,
    'SCHEMA_PATH_PREFIX': r'/api/v[0-9]',
    'SCHEMA_PATH_PREFIX_TRIM': True,
    'SERVERS': [
        {'url': 'http://localhost:8000', 'description': 'Development server'},
    ],
    'TAGS': [
        {'name': 'authentication', 'description': 'User authentication and JWT token management'},
        {'name': 'plant-identification', 'description': 'Plant identification using AI (Plant.id + PlantNet)'},
        {'name': 'blog', 'description': 'Blog posts and content management'},
        {'name': 'users', 'description': 'User profile and account management'},
        {'name': 'search', 'description': 'Search functionality across the platform'},
    ],
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'persistAuthorization': True,
        'displayOperationId': True,
        'filter': True,
    },
    # Exclude Wagtail API endpoints that don't use DRF versioning
    'PREPROCESSING_HOOKS': ['plant_community_backend.api_schema.preprocess_exclude_wagtail'],
}

# JWT Settings
# SECURITY: Access token lifetime should be short (15 minutes) per OWASP recommendations
# Changed: 15 minutes (OWASP compliant - Issue #018)
# Previous: 60 minutes (too long for security best practices)
# See: https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html
#
# Environment variables:
#   JWT_ACCESS_TOKEN_LIFETIME - Access token lifetime in MINUTES (default: 15 minutes)
#   JWT_REFRESH_TOKEN_LIFETIME - Refresh token lifetime in DAYS (default: 7 days)
#   JWT_ACCESS_TOKEN_LIFETIME_DEBUG - Debug mode access token lifetime in MINUTES (default: 120 = 2 hours)
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=config('JWT_ACCESS_TOKEN_LIFETIME', default=15, cast=int)),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=config('JWT_REFRESH_TOKEN_LIFETIME', default=7, cast=int)),
    'ACCESS_TOKEN_LIFETIME_DEBUG': timedelta(minutes=config('JWT_ACCESS_TOKEN_LIFETIME_DEBUG', default=120, cast=int)) if DEBUG else None,
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': None,  # Will be set below after validation
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,
    'JWK_URL': None,
    'LEEWAY': 0,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'USER_AUTHENTICATION_RULE': 'rest_framework_simplejwt.authentication.default_user_authentication_rule',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
    'JTI_CLAIM': 'jti',
    'SLIDING_TOKEN_REFRESH_EXP_CLAIM': 'refresh_exp',
    'SLIDING_TOKEN_LIFETIME': timedelta(minutes=5),
    'SLIDING_TOKEN_REFRESH_LIFETIME': timedelta(days=1),
}

# JWT_SECRET_KEY Validation (CRITICAL SECURITY)
# JWT tokens MUST use a separate signing key from Django's SECRET_KEY
# This prevents SECRET_KEY compromise from affecting JWT authentication
#
# SECURITY REQUIREMENTS (TODO #007):
# 1. JWT_SECRET_KEY MUST be set in ALL environments (no fallbacks allowed)
# 2. JWT_SECRET_KEY MUST be different from SECRET_KEY (no key reuse)
# 3. JWT_SECRET_KEY MUST be at least 50 characters (cryptographic strength)
# 4. NO default values allowed (fail loudly if missing)
#
# IMPORTANT: Do NOT add default=None or any fallback behavior
# Settings should fail immediately if JWT_SECRET_KEY is not configured
try:
    JWT_SECRET_KEY = config('JWT_SECRET_KEY')  # No default - fail if not set
except Exception as e:
    raise ImproperlyConfigured(
        "\n"
        "=" * 70 + "\n"
        "CRITICAL: JWT_SECRET_KEY environment variable is not set!\n"
        "=" * 70 + "\n"
        "JWT authentication requires a separate signing key from SECRET_KEY.\n"
        "This is REQUIRED in ALL environments (development and production).\n"
        "\n"
        "Why this is critical:\n"
        "  - Prevents cascade compromise if SECRET_KEY is leaked\n"
        "  - Isolates JWT authentication from Django session security\n"
        "  - Enables independent key rotation without affecting sessions\n"
        "\n"
        "Generate a secure JWT_SECRET_KEY with:\n"
        "  python -c 'import secrets; print(secrets.token_urlsafe(64))'\n"
        "\n"
        "Then add to your .env file (do NOT commit):\n"
        "  JWT_SECRET_KEY=your-generated-key-here\n"
        "\n"
        "See: backend/.env.example for complete configuration\n"
        "=" * 70 + "\n"
    ) from e

# Validate JWT_SECRET_KEY is different from SECRET_KEY
if JWT_SECRET_KEY == SECRET_KEY:
    raise ImproperlyConfigured(
        "\n"
        "=" * 70 + "\n"
        "CRITICAL: JWT_SECRET_KEY cannot be the same as SECRET_KEY!\n"
        "=" * 70 + "\n"
        "Using the same key for both JWT and Django session/CSRF tokens\n"
        "creates a single point of failure and security vulnerability.\n"
        "\n"
        "If one key is compromised, ALL authentication mechanisms are broken.\n"
        "\n"
        "Generate a DIFFERENT JWT_SECRET_KEY with:\n"
        "  python -c 'import secrets; print(secrets.token_urlsafe(64))'\n"
        "\n"
        "Your .env should have TWO separate keys:\n"
        "  SECRET_KEY=<django-secret-key>\n"
        "  JWT_SECRET_KEY=<different-jwt-secret-key>\n"
        "=" * 70 + "\n"
    )

# Validate minimum length for cryptographic strength
if len(JWT_SECRET_KEY) < 50:
    raise ImproperlyConfigured(
        "\n"
        "=" * 70 + "\n"
        f"CRITICAL: JWT_SECRET_KEY is too short ({len(JWT_SECRET_KEY)} characters)!\n"
        "=" * 70 + "\n"
        "JWT secret keys must be at least 50 characters for cryptographic security.\n"
        "\n"
        "Generate a secure key with:\n"
        "  python -c 'import secrets; print(secrets.token_urlsafe(64))'\n"
        "\n"
        "This will generate an 86-character URL-safe key.\n"
        "=" * 70 + "\n"
    )

# Set JWT signing key (validation passed)
SIMPLE_JWT['SIGNING_KEY'] = JWT_SECRET_KEY

# CORS settings - Secure configuration
# SECURITY FIX: Never use CORS_ALLOW_ALL_ORIGINS, even in DEBUG mode
# Whitelist specific dev origins to prevent CSRF attacks (CVSS 7.5)
if DEBUG:
    CORS_ALLOWED_ORIGINS = [
        'http://localhost:3000',
        'http://127.0.0.1:3000',
        'http://localhost:3001',
        'http://127.0.0.1:3001',
        'http://localhost:5173',
        'http://127.0.0.1:5173',
        'http://localhost:5174',  # React blog dev server
        'http://127.0.0.1:5174',
        'https://localhost:5174',
        'https://127.0.0.1:5174',
    ]
else:
    # Production: Use environment variable for allowed origins
    CORS_ALLOWED_ORIGINS = config(
        'CORS_ALLOWED_ORIGINS',
        default='https://plantcommunity.com',
        cast=lambda v: [s.strip() for s in v.split(',')]
    )

CORS_ALLOW_CREDENTIALS = True
# SECURITY: NEVER set to True, even in DEBUG mode (prevents CSRF attacks)
CORS_ALLOW_ALL_ORIGINS = False

# Additional CORS settings for proper API access
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-request-id',  # For distributed tracing (httpClient)
    'x-requested-with',
]

# CSRF trusted origins - environment-driven for production security
# In production, set CSRF_TRUSTED_ORIGINS env var with https URLs
if DEBUG:
    # Development origins - localhost only
    CSRF_TRUSTED_ORIGINS = [
        'http://localhost:3000',
        'http://127.0.0.1:3000',
        'http://localhost:3001',
        'http://127.0.0.1:3001',
        'http://localhost:5173',
        'http://127.0.0.1:5173',
        'http://localhost:5174',
        'http://127.0.0.1:5174',
        'http://localhost:8000',
        'http://127.0.0.1:8000',
    ]
else:
    # Production origins - from environment variable with https
    CSRF_TRUSTED_ORIGINS = config(
        'CSRF_TRUSTED_ORIGINS',
        default='',
        cast=lambda v: [s.strip() for s in v.split(',') if s.strip()]
    )

# Django Machina settings
MACHINA_DEFAULT_AUTHENTICATED_USER_FORUM_PERMISSIONS = [
    'can_see_forum',
    'can_read_forum',
    'can_start_new_topics',
    'can_reply_to_topics',
    'can_edit_own_posts',
    'can_post_without_approval',
    'can_create_polls',
    'can_vote_in_polls',
    'can_download_file',
]

MACHINA_PROFILE_AVATARS_PATH = 'machina/avatars'
MACHINA_USER_DISPLAY = lambda u: u.get_full_name() if u.get_full_name() else u.username

# Search configuration
HAYSTACK_CONNECTIONS = {
    'default': {
        'ENGINE': 'haystack.backends.simple_backend.SimpleEngine',
    },
}

# Ensure 'file' handler is not configured when disabled
if not ENABLE_FILE_LOGGING:
    try:
        LOGGING['handlers'].pop('file', None)
        if 'handlers' in LOGGING.get('root', {}):
            LOGGING['root']['handlers'] = [h for h in LOGGING['root']['handlers'] if h != 'file']
        for _name, _logger in LOGGING.get('loggers', {}).items():
            if isinstance(_logger, dict) and 'handlers' in _logger:
                _logger['handlers'] = [h for h in _logger['handlers'] if h != 'file']
    except Exception:
        pass

# Channels configuration
# Try Redis channel layer; fall back to in-memory for local smoke tests
try:
    _redis_url = config('REDIS_URL', default='redis://127.0.0.1:6379/1')
    import redis as _redis
    _client = _redis.from_url(_redis_url)
    _client.ping()
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {
                'hosts': [_redis_url],
            },
        },
    }
except Exception:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        }
    }

# External API settings
TREFLE_API_KEY = config('TREFLE_API_KEY', default='')
TREFLE_API_BASE_URL = 'https://trefle.io/api/v1'

# Plant.id API (Kindwise) - Primary identification service
PLANT_ID_API_KEY = config('PLANT_ID_API_KEY', default='')
PLANT_ID_API_BASE_URL = 'https://api.plant.id/v3'  # Correct URL per official docs

PLANTNET_API_KEY = config('PLANTNET_API_KEY', default='')
PLANTNET_API_BASE_URL = 'https://my-api.plantnet.org/v2'

# Plant.health API (for disease diagnosis)
PLANT_HEALTH_API_KEY = config('PLANT_HEALTH_API_KEY', default='')
PLANT_HEALTH_API_BASE_URL = 'https://api.plant.id'

# OpenAI API key for Wagtail AI
OPENAI_API_KEY = config('OPENAI_API_KEY', default='')

# Image API settings
UNSPLASH_ACCESS_KEY = config('UNSPLASH_ACCESS_KEY', default='')
PEXELS_API_KEY = config('PEXELS_API_KEY', default='')

# Email settings
EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_USE_SSL = config('EMAIL_USE_SSL', default=False, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='Plant Community <noreply@plantcommunity.com>')
SERVER_EMAIL = config('SERVER_EMAIL', default='Plant Community <server@plantcommunity.com>')

# Email timeout and connection settings
EMAIL_TIMEOUT = config('EMAIL_TIMEOUT', default=30, cast=int)
EMAIL_USE_LOCALTIME = config('EMAIL_USE_LOCALTIME', default=False, cast=bool)

# Site configuration for email templates
SITE_NAME = config('SITE_NAME', default='Plant Community')
SITE_URL = config('SITE_URL', default='https://plantcommunity.com')

# Logging configuration
# Request ID configuration
REQUEST_ID_HEADER = 'X-Request-ID'
GENERATE_REQUEST_ID_IF_NOT_FOUND = True

# Choose production console formatter based on availability
_PROD_CONSOLE_FORMATTER = 'json' if _HAS_JSON_LOGGER else 'simple'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': (
        {
            'verbose': {
                'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
                'style': '{',
            },
            'simple': {
                'format': '{levelname} {message}',
                'style': '{',
            },
        }
        if not _HAS_JSON_LOGGER
        else {
            'verbose': {
                'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
                'style': '{',
            },
            'simple': {
                'format': '{levelname} {message}',
                'style': '{',
            },
            'json': {
                '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
                'format': '%(asctime)s %(name)s %(levelname)s %(message)s %(pathname)s %(lineno)d %(request_id)s',
            },
        }
    ),
    'filters': {
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        **(
            {'request_id': {'()': 'request_id.logging.RequestIdFilter'}}
            if _HAS_REQUEST_ID
            else {}
        ),
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'filters': ['require_debug_true'] + (['request_id'] if _HAS_REQUEST_ID else []),
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        },
        'console_prod': {
            'level': 'INFO',
            'filters': ['require_debug_false'] + (['request_id'] if _HAS_REQUEST_ID else []),
            'class': 'logging.StreamHandler',
            'formatter': _PROD_CONSOLE_FORMATTER,
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'formatter': 'verbose',
            'filters': (['request_id'] if _HAS_REQUEST_ID else []),
        },
    },
    'root': {
        'handlers': ['console', 'console_prod'] + (['file'] if ENABLE_FILE_LOGGING else []),
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'console_prod'] + (['file'] if ENABLE_FILE_LOGGING else []),
            'level': 'INFO',
        },
        'plant_community_backend': {
            'handlers': ['console', 'console_prod'] + (['file'] if ENABLE_FILE_LOGGING else []),
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
        'apps': {
            'handlers': ['console', 'console_prod'] + (['file'] if ENABLE_FILE_LOGGING else []),
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
    },
}

# Cleanup: when file logging is disabled, ensure the 'file' handler and any
# references are removed before Django applies logging config.
if not ENABLE_FILE_LOGGING:
    try:
        LOGGING['handlers'].pop('file', None)
        if 'handlers' in LOGGING.get('root', {}):
            LOGGING['root']['handlers'] = [h for h in LOGGING['root']['handlers'] if h != 'file']
        for _name, _logger in LOGGING.get('loggers', {}).items():
            if isinstance(_logger, dict) and 'handlers' in _logger:
                _logger['handlers'] = [h for h in _logger['handlers'] if h != 'file']
    except Exception:
        pass

# Sentry Error Tracking
SENTRY_DSN = config('SENTRY_DSN', default='')
if SENTRY_DSN and not DEBUG:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            # Auto-configured integrations for Django and Celery
        ],
        traces_sample_rate=config('SENTRY_TRACES_SAMPLE_RATE', default=0.1, cast=float),
        send_default_pii=False,  # Don't send personally identifiable information
        environment=config('ENVIRONMENT', default='production'),
        release=config('RELEASE_VERSION', default='1.0.0'),
        attach_stacktrace=True,
        request_bodies='medium',  # Log request bodies for POST/PUT
        profiles_sample_rate=config('SENTRY_PROFILES_SAMPLE_RATE', default=0.1, cast=float),
    )

# Celery configuration
# Use Redis (same REDIS_URL as cache by default)
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default=config('REDIS_URL', default='redis://127.0.0.1:6379/1'))
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default=CELERY_BROKER_URL)
CELERY_TASK_TIME_LIMIT = config('CELERY_TASK_TIME_LIMIT', default=120, cast=int)
CELERY_TASK_SOFT_TIME_LIMIT = config('CELERY_TASK_SOFT_TIME_LIMIT', default=90, cast=int)
CELERY_TASK_ALWAYS_EAGER = config('CELERY_TASK_ALWAYS_EAGER', default=False, cast=bool)

# Security settings - Apply to both development and production (Issue #014)
SECURE_BROWSER_XSS_FILTER = True  # Enable XSS filtering in IE/Edge (legacy browsers)
SECURE_CONTENT_TYPE_NOSNIFF = True  # Prevent MIME type sniffing
X_FRAME_OPTIONS = 'DENY'  # Anti-clickjacking - prevent embedding in iframes

# Permissions-Policy (Issue #145 fix) - Restrict browser features to prevent abuse
# See: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Permissions-Policy
# Format: 'feature': [] (deny all) or ['self'] (allow same origin only)
PERMISSIONS_POLICY = {
    'accelerometer': [],  # Deny accelerometer access (not needed)
    'camera': ['self'],  # Camera only from same origin (plant photo uploads)
    'geolocation': ['self'],  # Geolocation only from same origin (plant location tracking)
    'gyroscope': [],  # Deny gyroscope access (not needed)
    'magnetometer': [],  # Deny magnetometer access (not needed)
    'microphone': [],  # Deny microphone access (not needed)
    'payment': [],  # Deny payment API (no e-commerce)
    'usb': [],  # Deny USB access (not needed)
}
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'  # Privacy-preserving referrer policy

# Additional security headers
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True  # ✅ Secure - prevents XSS attacks from stealing CSRF tokens (JavaScript reads from meta tag instead)
# SameSite policy - stricter in production if workflows allow
SESSION_COOKIE_SAMESITE = 'Strict' if not DEBUG else 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'  # Keep Lax for CSRF to handle standard POST flows

# Content Security Policy using django-csp 4.0+ format (Issue #014)
# CSP provides defense-in-depth against XSS by restricting resource origins
# Report violations to /api/v1/security/csp-report/ for monitoring and refinement
if DEBUG:
    # More permissive in development for hot reload
    # REPORT_ONLY mode doesn't block resources, just logs violations
    CONTENT_SECURITY_POLICY_REPORT_ONLY = {
        'DIRECTIVES': {
            'base-uri': ("'self'",),
            'connect-src': ("'self'", "http://localhost:*", "ws://localhost:*"),
            'default-src': ("'self'",),
            'font-src': ("'self'", "data:", "https://fonts.gstatic.com"),
            'form-action': ("'self'",),
            'frame-ancestors': ("'none'",),  # Anti-clickjacking (also enforced by X-Frame-Options)
            'img-src': ("'self'", "data:", "https:", "blob:"),
            'media-src': ("'self'",),
            'object-src': ("'none'",),  # Block Flash, Java applets, etc.
            'script-src': ("'self'", "'unsafe-inline'", "'unsafe-eval'", "http://localhost:*", "ws://localhost:*"),
            'style-src': ("'self'", "'unsafe-inline'"),
            'worker-src': ("'self'", "blob:"),
        },
        'REPORT_URI': '/api/v1/security/csp-report/',  # Log violations for refinement
    }
else:
    # Strict CSP in production with nonces (Issue #145 fix)
    # Enforcing mode - blocks resources that violate policy
    CONTENT_SECURITY_POLICY = {
        'DIRECTIVES': {
            'base-uri': ("'self'",),
            'connect-src': (
                "'self'",
                "https://api.plant.id",  # Plant.id API
                "https://my-api.plantnet.org",  # PlantNet API
            ),
            'default-src': ("'self'",),
            'font-src': ("'self'", "data:", "https://fonts.gstatic.com"),
            'form-action': ("'self'",),
            'frame-ancestors': ("'none'",),  # Anti-clickjacking (redundant with X-Frame-Options but defense-in-depth)
            'img-src': ("'self'", "data:", "https:", "blob:"),  # Allow HTTPS images (plant photos from external sources)
            'media-src': ("'self'",),
            'object-src': ("'none'",),  # Block Flash, Java applets, etc.
            'script-src': ("'self'",),  # Will add nonces dynamically for inline scripts
            'style-src': ("'self'",),  # Will add nonces dynamically for inline styles
            'worker-src': ("'self'", "blob:"),
            'upgrade-insecure-requests': True,  # Force HTTPS for all resources
        },
        'INCLUDE_NONCE_IN': ['script-src', 'style-src'],  # Allow inline with nonces
        'REPORT_URI': '/api/v1/security/csp-report/',  # Monitor violations in production
    }

# Debug toolbar settings
if DEBUG:
    INTERNAL_IPS = [
        '127.0.0.1',
        'localhost',
    ]

# File upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1000

# Create logs directory if it doesn't exist
os.makedirs(BASE_DIR / 'logs', exist_ok=True)

# Django Allauth Configuration
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# Allauth settings (django-allauth 65.x+ API)
# Replaced ACCOUNT_AUTHENTICATION_METHOD with ACCOUNT_LOGIN_METHODS
ACCOUNT_LOGIN_METHODS = {'username', 'email'}  # Allow login with either username or email
# Replaced ACCOUNT_EMAIL_REQUIRED and ACCOUNT_USERNAME_REQUIRED with ACCOUNT_SIGNUP_FIELDS
ACCOUNT_SIGNUP_FIELDS = ['email*', 'username*', 'password1*', 'password2*']  # * = required
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'  # Require email verification for new accounts
ACCOUNT_USER_MODEL_USERNAME_FIELD = 'username'
ACCOUNT_USER_MODEL_EMAIL_FIELD = 'email'
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_SESSION_REMEMBER = True
ACCOUNT_LOGOUT_ON_GET = False  # Require POST for logout for security

# Social account settings
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_REQUIRED = True
SOCIALACCOUNT_QUERY_EMAIL = True
SOCIALACCOUNT_STORE_TOKENS = True  # Store OAuth tokens for API access

# OAuth Provider Configuration
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        },
        'OAUTH_PKCE_ENABLED': True,
        'APP': {
            'client_id': config('GOOGLE_OAUTH2_CLIENT_ID', default=''),
            'secret': config('GOOGLE_OAUTH2_CLIENT_SECRET', default=''),
            'key': ''
        }
    },
    'github': {
        'SCOPE': [
            'user:email',
        ],
        'APP': {
            'client_id': config('GITHUB_CLIENT_ID', default=''),
            'secret': config('GITHUB_CLIENT_SECRET', default=''),
            'key': ''
        }
    }
}

# Custom adapter for JWT integration
SOCIALACCOUNT_ADAPTER = 'apps.users.oauth_adapters.CustomSocialAccountAdapter'
ACCOUNT_ADAPTER = 'apps.users.oauth_adapters.CustomAccountAdapter'

# Wagtail AI Configuration (Phase 1: Issue #157)
# Provides AI-powered content generation for blog posts and CMS content
# Cost-effective configuration using GPT-4o-mini (~$0.003/request)
# Expected usage: ~500 requests/month = $1.50/month (before 80% caching)
WAGTAIL_AI = {
    # v3.0 Provider Configuration (replaces BACKENDS)
    # https://github.com/wagtail/wagtail-ai/blob/main/docs/configuration.md
    "PROVIDERS": {
        "default": {
            "provider": "openai",  # LLM provider (openai, anthropic, etc.)
            "model": "gpt-4o-mini",  # Cost-effective model for text generation
            "api_key": config('OPENAI_API_KEY', default=''),
        },
        # Future: Add vision provider for image alt text generation (Phase 3)
        # "vision": {
        #     "provider": "openai",
        #     "model": "gpt-4o-vision-preview",
        #     "api_key": config('OPENAI_API_KEY', default=''),
        # },
    },

    # Legacy BACKENDS configuration (deprecated but kept for backward compatibility)
    # Will be removed when all code migrates to PROVIDERS
    "BACKENDS": {
        "default": {
            "CLASS": "wagtail_ai.ai.openai.OpenAIBackend",
            "CONFIG": {
                "MODEL_ID": "gpt-4o-mini",  # Cost-effective model for text generation
                "TOKEN_LIMIT": 16384,  # GPT-4o-mini supports up to 16K tokens
                "OPENAI_API_KEY": config('OPENAI_API_KEY', default=''),
            },
        },
    },

    # Custom prompts for plant-specific content (Wagtail AI 3.0)
    # These override the default prompts with plant care and gardening context
    "AGENT_SETTINGS": {
        "wai_basic_prompt": {
            # Title generation - Optimized for plant blog posts
            "page_title_prompt": (
                "Generate an SEO-optimized blog post title about plants, gardening, or plant care. "
                "Make it compelling, informative, and under 60 characters for optimal SEO. "
                "Focus on actionable benefits and specific plant topics. "
                "Context: {context}"
            ),

            # Meta description - Optimized for search engines and plant content
            "page_description_prompt": (
                "Write a compelling meta description (150-160 characters) for this plant care or "
                "gardening blog post. Focus on specific benefits, care tips, or plant characteristics "
                "that would attract readers. Include relevant keywords naturally. "
                "Make it actionable and engaging. "
                "Context: {context}"
            ),
        }
    },
}

# Additional Feature Flags
ENABLE_TREFLE_ENRICHMENT = config('ENABLE_TREFLE_ENRICHMENT', default=True, cast=bool)
ENABLE_AI_CONTENT_GENERATION = config('ENABLE_AI_CONTENT_GENERATION', default=True, cast=bool)
ENABLE_COMMUNITY_VOTING = config('ENABLE_COMMUNITY_VOTING', default=True, cast=bool)
ENABLE_DISEASE_DIAGNOSIS = config('ENABLE_DISEASE_DIAGNOSIS', default=True, cast=bool)

# Environment Validation and Warning System
import logging
logger = logging.getLogger(__name__)

def validate_environment():
    """
    Validate critical environment variables and warn about missing configurations.
    This prevents silent failures and provides clear guidance for setup.
    """
    warnings = []
    critical_errors = []
    
    # Critical settings that MUST be set in production
    # Note: SECRET_KEY is validated earlier in settings.py (lines 35-95)
    # with comprehensive checks for pattern matching, length, and production requirements
    if not DEBUG:
        if not ALLOWED_HOSTS or ALLOWED_HOSTS == ['localhost', '127.0.0.1']:
            critical_errors.append("ALLOWED_HOSTS must be configured for production domains")

        if not config('CSRF_TRUSTED_ORIGINS', default=''):
            critical_errors.append("CSRF_TRUSTED_ORIGINS must be set in production")
    
    # API Keys validation - warn if features are enabled but keys missing
    api_checks = [
        ('TREFLE_API_KEY', TREFLE_API_KEY, ENABLE_TREFLE_ENRICHMENT, 'Plant data enrichment'),
        ('PLANTNET_API_KEY', PLANTNET_API_KEY, True, 'Plant identification'),
        ('PLANT_HEALTH_API_KEY', PLANT_HEALTH_API_KEY, ENABLE_DISEASE_DIAGNOSIS, 'Disease diagnosis'),
        ('OPENAI_API_KEY', OPENAI_API_KEY, ENABLE_AI_CONTENT_GENERATION, 'AI content generation'),
    ]
    
    for key_name, key_value, feature_enabled, feature_description in api_checks:
        if feature_enabled and not key_value:
            warnings.append(f"{key_name} not set - {feature_description} will not work")
    
    # OAuth validation - warn if providers configured but keys missing
    oauth_checks = [
        ('GOOGLE_OAUTH2_CLIENT_ID', config('GOOGLE_OAUTH2_CLIENT_ID', default=''), 'Google OAuth'),
        ('GOOGLE_OAUTH2_CLIENT_SECRET', config('GOOGLE_OAUTH2_CLIENT_SECRET', default=''), 'Google OAuth'),
        ('GITHUB_CLIENT_ID', config('GITHUB_CLIENT_ID', default=''), 'GitHub OAuth'),
        ('GITHUB_CLIENT_SECRET', config('GITHUB_CLIENT_SECRET', default=''), 'GitHub OAuth'),
    ]
    
    google_configured = bool(config('GOOGLE_OAUTH2_CLIENT_ID', default='') and config('GOOGLE_OAUTH2_CLIENT_SECRET', default=''))
    github_configured = bool(config('GITHUB_CLIENT_ID', default='') and config('GITHUB_CLIENT_SECRET', default=''))
    
    if not google_configured and not github_configured:
        warnings.append("No OAuth providers configured - users can only register with username/password")
    
    # Database validation
    try:
        db_config = DATABASES['default']
        if 'sqlite' in db_config['ENGINE'] and not DEBUG:
            warnings.append("SQLite database detected in production - consider PostgreSQL for better performance")
    except Exception:
        critical_errors.append("Database configuration is invalid")
    
    # Redis validation
    if not config('REDIS_URL', default=''):
        warnings.append("Redis not configured - caching and session storage will use database")
    
    # Email configuration
    if EMAIL_BACKEND == 'django.core.mail.backends.console.EmailBackend' and not DEBUG:
        warnings.append("Email backend is set to console in production - emails will not be sent")
    
    # Security configuration warnings
    security_checks = [
        (not SECURE_SSL_REDIRECT and not DEBUG, "SECURE_SSL_REDIRECT should be True in production"),
        (not SESSION_COOKIE_SECURE and not DEBUG, "SESSION_COOKIE_SECURE should be True in production"),
        (not CSRF_COOKIE_SECURE and not DEBUG, "CSRF_COOKIE_SECURE should be True in production"),
        (not CSRF_COOKIE_HTTPONLY, "CSRF_COOKIE_HTTPONLY should be True (prevents XSS attacks from stealing CSRF tokens)"),
    ]
    
    for condition, message in security_checks:
        if condition:
            warnings.append(message)
    
    # Log results
    if critical_errors:
        for error in critical_errors:
            logger.error(f"CRITICAL CONFIGURATION ERROR: {error}")
        if not DEBUG:
            raise Exception(f"Critical configuration errors detected: {'; '.join(critical_errors)}")
    
    if warnings:
        logger.warning("Configuration warnings detected:")
        for warning in warnings:
            logger.warning(f"  - {warning}")
        
        if DEBUG:
            print("\n" + "="*60)
            print("🔧 CONFIGURATION WARNINGS")
            print("="*60)
            for warning in warnings:
                print(f"⚠️  {warning}")
            print("="*60 + "\n")
    
    # Success message
    if not warnings and not critical_errors:
        logger.info("✅ All critical environment variables are properly configured")
        if DEBUG:
            print("✅ Environment configuration validated successfully")

# Run validation on settings load
validate_environment()