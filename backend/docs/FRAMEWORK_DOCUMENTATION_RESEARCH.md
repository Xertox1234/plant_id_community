# Framework Documentation & Best Practices Research

**Purpose**: Official documentation references and best practices for frameworks used in Plant ID Community backend

**Date**: 2025-10-22
**Context**: Support for GitHub issue creation and technical implementation guidance

---

## Table of Contents

1. [Django 5.2 Security Best Practices](#1-django-52-security-best-practices)
2. [Django REST Framework Authentication & Permissions](#2-django-rest-framework-authentication--permissions)
3. [Redis & django-redis Best Practices](#3-redis--django-redis-best-practices)
4. [Python Type Hints & mypy](#4-python-type-hints--mypy)
5. [File Upload Security](#5-file-upload-security)
6. [Distributed Systems Patterns](#6-distributed-systems-patterns)

---

## 1. Django 5.2 Security Best Practices

### Official Documentation Links

- **Deployment Checklist**: https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/
- **Security in Django**: https://docs.djangoproject.com/en/5.2/topics/security/
- **OWASP Django Security**: https://cheatsheetseries.owasp.org/cheatsheets/Django_Security_Cheat_Sheet.html

### SECRET_KEY Management

#### Best Practices

1. **Generate Strong Keys** (50+ characters minimum):
```python
from django.core.management.utils import get_random_secret_key

# Generate a new secret key
secret_key = get_random_secret_key()
```

2. **Never Commit to Source Control**:
```python
# settings.py - WRONG
SECRET_KEY = 'django-insecure-hardcoded-key-123'

# settings.py - CORRECT
import os
SECRET_KEY = os.environ.get('SECRET_KEY')

# Or use python-decouple
from decouple import config
SECRET_KEY = config('SECRET_KEY')
```

3. **Use SECRET_KEY_FALLBACKS for Rotation**:
```python
SECRET_KEY = os.environ.get('SECRET_KEY')
SECRET_KEY_FALLBACKS = [
    os.environ.get('OLD_SECRET_KEY'),  # Keep temporarily during rotation
]
```

4. **Validate Production Settings**:
```bash
python manage.py check --deploy
```

#### Security Implications

- **Risk**: SECRET_KEY exposure allows session hijacking, CSRF token forgery, password reset token generation
- **Impact**: Complete application compromise
- **Mitigation**: Store in environment variables or secrets managers (AWS Secrets Manager, HashiCorp Vault)

### DEBUG Setting

#### Production Configuration

```python
# settings.py
DEBUG = os.environ.get('DEBUG', 'False') == 'True'  # Default to False

# Or more explicit
DEBUG = False  # Always False in production
```

#### Security Risks of DEBUG=True in Production

1. **Information Disclosure**: Exposes source code excerpts, local variables, settings
2. **Library Versions**: Reveals dependencies and their versions
3. **Database Queries**: Shows SQL queries with parameters
4. **File Paths**: Exposes server file structure
5. **Configuration**: Reveals middleware, installed apps, settings

### ALLOWED_HOSTS

#### Configuration

```python
# settings.py - Development
ALLOWED_HOSTS = ['localhost', '127.0.0.1']

# Production
ALLOWED_HOSTS = [
    'example.com',
    'www.example.com',
    'api.example.com',
]

# Environment-aware
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost').split(',')
```

#### Security Purpose

- **Protects Against**: HTTP Host header attacks, DNS rebinding attacks
- **Required When**: DEBUG = False (application won't start without it)

### File Upload Security

#### Django ImageField Limitations

**Official Security Advisory**: https://www.djangoproject.com/weblog/2013/dec/02/image-field-advisory/

**Key Points**:
1. ImageField only validates file headers, not entire file
2. Malicious content can be appended to valid images
3. Validation only runs when using forms (not direct model saves)
4. Content-Type header is user-controlled and untrustworthy

#### Secure File Upload Pattern

```python
from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError
from PIL import Image
import magic

def validate_image_file(file):
    """Comprehensive image validation"""

    # 1. Check file extension
    validator = FileExtensionValidator(
        allowed_extensions=['jpg', 'jpeg', 'png', 'gif', 'webp']
    )
    validator(file)

    # 2. Verify magic bytes (actual file type)
    file_type = magic.from_buffer(file.read(2048), mime=True)
    file.seek(0)  # Reset file pointer

    allowed_mime_types = [
        'image/jpeg',
        'image/png',
        'image/gif',
        'image/webp'
    ]

    if file_type not in allowed_mime_types:
        raise ValidationError(
            f'Invalid file type: {file_type}. Expected image.'
        )

    # 3. Verify with PIL (checks entire image)
    try:
        img = Image.open(file)
        img.verify()  # Verify it's actually an image
        file.seek(0)  # Reset for subsequent use

        # Optional: Check image dimensions
        if img.size[0] > 10000 or img.size[1] > 10000:
            raise ValidationError('Image dimensions too large')

    except Exception as e:
        raise ValidationError(f'Invalid image file: {str(e)}')

    # 4. Check file size
    if file.size > 10 * 1024 * 1024:  # 10MB
        raise ValidationError('File size exceeds 10MB limit')

    return True

# Usage in models
from django.db import models

class PlantIdentification(models.Model):
    image = models.ImageField(
        upload_to='plant_images/',
        validators=[validate_image_file]
    )
```

### Deployment Checklist Commands

```bash
# Run security checks
python manage.py check --deploy

# Common warnings to address:
# - SECURITY WARNING: SECRET_KEY not set
# - SECURITY WARNING: DEBUG=True in production
# - SECURITY WARNING: ALLOWED_HOSTS is empty
# - SECURITY WARNING: SECURE_SSL_REDIRECT not enabled
# - SECURITY WARNING: SESSION_COOKIE_SECURE not enabled
# - SECURITY WARNING: CSRF_COOKIE_SECURE not enabled
```

### Production Settings Template

```python
# settings_production.py
import os
from pathlib import Path

# Security
SECRET_KEY = os.environ['SECRET_KEY']
DEBUG = False
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',')

# HTTPS/SSL
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# HSTS (only after testing)
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# File uploads
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ['DB_NAME'],
        'USER': os.environ['DB_USER'],
        'PASSWORD': os.environ['DB_PASSWORD'],
        'HOST': os.environ['DB_HOST'],
        'PORT': os.environ.get('DB_PORT', '5432'),
        'CONN_MAX_AGE': 600,  # Connection pooling
    }
}
```

---

## 2. Django REST Framework Authentication & Permissions

### Official Documentation Links

- **Authentication**: https://www.django-rest-framework.org/api-guide/authentication/
- **Permissions**: https://www.django-rest-framework.org/api-guide/permissions/
- **Tutorial**: https://www.django-rest-framework.org/tutorial/4-authentication-and-permissions/

### Permission Classes

#### Built-in Permission Classes

```python
from rest_framework.permissions import (
    AllowAny,
    IsAuthenticated,
    IsAdminUser,
    IsAuthenticatedOrReadOnly,
)

# Usage in views
from rest_framework.views import APIView

class PlantIdentificationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Only authenticated users can identify plants
        pass
```

#### Permission Class Descriptions

1. **AllowAny**: Unrestricted access (public endpoints)
2. **IsAuthenticated**: Requires authenticated user (rejects anonymous)
3. **IsAdminUser**: Requires `user.is_staff == True` (admin only)
4. **IsAuthenticatedOrReadOnly**: Read-only for anonymous, full access for authenticated

#### Custom Permissions

```python
from rest_framework import permissions

class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners to edit objects.
    """

    def has_object_permission(self, request, view, obj):
        # Read permissions for any request (GET, HEAD, OPTIONS)
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions only for owner
        return obj.owner == request.user

# Usage
class PlantDetailView(APIView):
    permission_classes = [IsOwnerOrReadOnly]
```

### Authentication Schemes

#### Default Configuration

```python
# settings.py
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}
```

#### Token Authentication

```python
# settings.py
INSTALLED_APPS = [
    ...
    'rest_framework.authtoken',
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ],
}

# Generate tokens
from rest_framework.authtoken.models import Token

# For a user
token = Token.objects.create(user=user)

# Client usage
# Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b
```

#### Environment-Aware Permissions

```python
# settings.py
import os

# Development: Allow anonymous access
# Production: Require authentication
if os.environ.get('ENVIRONMENT') == 'production':
    DEFAULT_PERMISSION_CLASSES = [
        'rest_framework.permissions.IsAuthenticated',
    ]
else:
    DEFAULT_PERMISSION_CLASSES = [
        'rest_framework.permissions.AllowAny',
    ]

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': DEFAULT_PERMISSION_CLASSES,
}
```

### Best Practices

1. **Always specify permission classes explicitly** on sensitive views
2. **Use IsAuthenticated as default**, override with AllowAny for public endpoints
3. **Combine authentication and throttling** for rate limiting
4. **Validate request.user** in permission checks, not just request.auth
5. **Test permissions thoroughly** with authenticated, anonymous, and admin users

---

## 3. Redis & django-redis Best Practices

### Official Documentation Links

- **django-redis**: https://github.com/jazzband/django-redis
- **Redis Python**: https://redis.readthedocs.io/en/stable/
- **python-redis-lock**: https://pypi.org/project/python-redis-lock/
- **Redis Distributed Locks**: https://redis.io/docs/latest/develop/clients/patterns/distributed-locks/

### Connection Pooling

#### Configuration

```python
# settings.py
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_KWARGS": {
                "max_connections": 50,
                "retry_on_timeout": True,
            },
            # Custom pool class (optional)
            "CONNECTION_POOL_CLASS": "redis.BlockingConnectionPool",
            "CONNECTION_POOL_CLASS_KWARGS": {
                "max_connections": 50,
                "timeout": 20,
            },
        }
    }
}
```

#### Best Practices

1. **Use connection pooling** - Reuses connections instead of creating new ones
2. **Configure max_connections** - Based on expected concurrent requests
3. **Enable retry_on_timeout** - Automatic retry for transient failures
4. **Monitor pool usage** - `connection_pool._created_connections`

### Error Handling

#### Retry Mechanism with Exponential Backoff

```python
import redis
from redis.retry import Retry
from redis.backoff import ExponentialBackoff
from redis.exceptions import (
    ConnectionError,
    TimeoutError,
    ConnectionResetError
)

# Configure Redis client with automatic retries
r = redis.Redis(
    host='127.0.0.1',
    port=6379,
    retry=Retry(ExponentialBackoff(cap=10, base=1), 25),
    retry_on_error=[
        ConnectionError,
        TimeoutError,
        ConnectionResetError
    ],
    health_check_interval=1
)
```

#### Connection Health Check

```python
from redis import Redis
from redis.exceptions import ConnectionError
import logging

logger = logging.getLogger(__name__)

def check_redis_connection():
    """Verify Redis is available at startup"""
    try:
        r = Redis('127.0.0.1', socket_connect_timeout=1)
        r.ping()
        logger.info("Redis connection: OK")
        return True
    except ConnectionError as e:
        logger.error(f"Redis connection failed: {e}")
        return False

# Usage in Django
# apps.py or wsgi.py
check_redis_connection()
```

#### Graceful Degradation Pattern

```python
from django.core.cache import cache
from redis.exceptions import ConnectionError
import logging

logger = logging.getLogger(__name__)

def get_cached_data(key, fallback_func):
    """
    Try to get from cache, fallback to function if Redis unavailable
    """
    try:
        cached = cache.get(key)
        if cached is not None:
            return cached
    except ConnectionError as e:
        logger.warning(f"[CACHE] Redis unavailable: {e}")

    # Cache miss or Redis down - compute value
    value = fallback_func()

    # Try to cache (fail silently if Redis down)
    try:
        cache.set(key, value, timeout=3600)
    except ConnectionError:
        logger.warning(f"[CACHE] Could not cache key: {key}")

    return value
```

### Distributed Locks

#### python-redis-lock Usage

**Installation**:
```bash
pip install python-redis-lock
```

**Basic Usage**:
```python
from redis import StrictRedis
import redis_lock

conn = StrictRedis()

# Context manager (recommended)
with redis_lock.Lock(conn, "plant-id-lock"):
    print("Got the lock. Doing work...")
    # Only one process can execute this block at a time

# Manual acquire/release
lock = redis_lock.Lock(conn, "plant-id-lock")
if lock.acquire(blocking=False):
    try:
        print("Got the lock")
    finally:
        lock.release()
else:
    print("Someone else has the lock")
```

#### Auto-Renewal and Expiration

```python
import redis_lock
import time

conn = StrictRedis()

# Auto-renewal prevents lock from expiring during long operations
with redis_lock.Lock(
    conn,
    name='my-lock',
    expire=60,           # Lock expires in 60 seconds
    auto_renewal=True,   # Automatically renew before expiration
    id=None              # Unique lock ID (generated automatically)
):
    # Do long-running work
    time.sleep(120)  # Lock is auto-renewed, won't expire
```

#### Lock Reset on Application Start

```python
import redis_lock
from redis import StrictRedis

# In Django apps.py ready() method or wsgi.py
def clear_stale_locks():
    """
    Clear any locks that weren't properly released
    (e.g., from crashed processes)
    """
    import redis_lock
    redis_lock.reset_all()

# Usage
class MyAppConfig(AppConfig):
    def ready(self):
        clear_stale_locks()
```

#### Cache Stampede Prevention

```python
from django.core.cache import cache
from redis import StrictRedis
import redis_lock
import hashlib
import logging

logger = logging.getLogger(__name__)
redis_conn = StrictRedis()

def get_or_compute_with_lock(key, compute_func, timeout=3600):
    """
    Prevent cache stampede using distributed locks
    Only one process computes the value, others wait
    """
    # Try cache first
    cached = cache.get(key)
    if cached is not None:
        logger.info(f"[CACHE] HIT for {key}")
        return cached

    logger.info(f"[CACHE] MISS for {key}")

    # Use lock to prevent multiple processes computing same value
    lock_key = f"lock:{key}"

    with redis_lock.Lock(
        redis_conn,
        lock_key,
        expire=30,           # Lock expires in 30s
        auto_renewal=True,   # Renew if computation takes longer
        blocking=True,       # Wait for lock
        blocking_timeout=35  # Max wait time
    ):
        # Double-check cache (another process might have set it)
        cached = cache.get(key)
        if cached is not None:
            logger.info(f"[CACHE] HIT after lock for {key}")
            return cached

        # Compute value
        logger.info(f"[CACHE] COMPUTING {key}")
        value = compute_func()

        # Store in cache
        cache.set(key, value, timeout=timeout)

        return value

# Usage example
def expensive_plant_lookup(plant_id):
    key = f"plant:{plant_id}"
    return get_or_compute_with_lock(
        key,
        lambda: fetch_from_database(plant_id),
        timeout=3600
    )
```

### Redlock Algorithm (Multi-Master)

For high-availability scenarios with multiple Redis masters:

```python
from redlock import RedLock

# Configure multiple Redis nodes
connection_details = [
    {'host': 'redis1.example.com', 'port': 6379, 'db': 0},
    {'host': 'redis2.example.com', 'port': 6379, 'db': 0},
    {'host': 'redis3.example.com', 'port': 6379, 'db': 0},
]

# Context manager
with RedLock("distributed_lock", connection_details=connection_details):
    # Critical section - safe across multiple Redis instances
    do_something()
```

**Properties**:
- **Safety**: Mutual exclusion (only one client holds lock)
- **Liveness A**: Deadlock-free (can always acquire eventually)
- **Liveness B**: Fault-tolerant (works if majority of nodes up)

### Best Practices Summary

1. **Connection Pooling**: Always use connection pools to reduce overhead
2. **Error Handling**: Implement retry logic with exponential backoff
3. **Health Checks**: Verify Redis connection at startup
4. **Graceful Degradation**: Application should work without Redis
5. **Lock Expiration**: Always set expiration on locks to prevent deadlocks
6. **Auto-Renewal**: Use for long-running operations
7. **Lock Cleanup**: Reset stale locks on application start
8. **Monitoring**: Log connection errors and cache hit/miss rates

---

## 4. Python Type Hints & mypy

### Official Documentation Links

- **Python typing module**: https://docs.python.org/3/library/typing.html
- **PEP 484 (Type Hints)**: https://peps.python.org/pep-0484/
- **PEP 585 (Native Generics)**: https://peps.python.org/pep-0585/
- **mypy documentation**: https://mypy.readthedocs.io/en/stable/
- **mypy configuration**: https://mypy.readthedocs.io/en/stable/config_file.html

### Modern Type Hints (2025)

#### PEP 585: Native Generics (Python 3.9+)

**Old (Deprecated)** - Will be removed in Python 3.13+:
```python
from typing import List, Dict, Set, Tuple, Optional

def process_plants(plants: List[str]) -> Dict[str, int]:
    pass
```

**New (Recommended)** - Native syntax:
```python
def process_plants(plants: list[str]) -> dict[str, int]:
    pass

# Other native generics
def get_coords() -> tuple[float, float]:
    pass

def get_tags() -> set[str]:
    pass
```

#### Union Types (Python 3.10+)

**Old**:
```python
from typing import Union, Optional

def process(value: Union[str, int]) -> Optional[dict]:
    pass
```

**New**:
```python
def process(value: str | int) -> dict | None:
    pass

# Optional[X] is equivalent to X | None
def get_plant(id: int) -> Plant | None:
    pass
```

### Common Type Hints

#### Basic Types

```python
# Primitives
name: str = "Monstera"
count: int = 42
confidence: float = 0.95
is_valid: bool = True

# None
result: None = None

# Any (use sparingly)
from typing import Any
data: Any = get_unknown_data()
```

#### Collections

```python
# Lists
plants: list[str] = ["rose", "tulip"]
coordinates: list[tuple[float, float]] = [(1.0, 2.0)]

# Dictionaries
plant_data: dict[str, Any] = {"name": "Rose", "count": 5}
typed_dict: dict[str, int] = {"apples": 3, "oranges": 5}

# Sets
unique_ids: set[int] = {1, 2, 3}

# Tuples (fixed size)
point: tuple[float, float] = (1.0, 2.0)

# Tuples (variable size)
numbers: tuple[int, ...] = (1, 2, 3, 4, 5)
```

#### Optional and Union

```python
# Optional (value or None)
def find_plant(id: int) -> Plant | None:
    # Returns Plant or None
    pass

# Union (multiple types)
def process_input(value: str | int | float) -> str:
    return str(value)

# Multiple optional
def get_coordinates() -> tuple[float, float] | None:
    pass
```

#### TypedDict (Structured Dictionaries)

```python
from typing import TypedDict, NotRequired, Required

class PlantResponse(TypedDict):
    name: str                    # Required by default
    scientific_name: str
    confidence: float
    care_instructions: NotRequired[dict[str, str]]  # Optional

# Usage
def identify_plant(image: bytes) -> PlantResponse:
    return {
        "name": "Monstera",
        "scientific_name": "Monstera deliciosa",
        "confidence": 0.95,
        # care_instructions is optional
    }

# total=False makes all keys optional by default
class OptionalPlantData(TypedDict, total=False):
    name: str
    scientific_name: str
    confidence: float

# Mix required and optional
class MixedPlantData(TypedDict, total=False):
    name: Required[str]          # Required
    scientific_name: str         # Optional (total=False)
    confidence: float            # Optional
```

#### Callable Types

```python
from collections.abc import Callable

# Function type: takes int, returns str
converter: Callable[[int], str] = str

# Multiple parameters
adder: Callable[[int, int], int] = lambda x, y: x + y

# No parameters
getter: Callable[[], str] = lambda: "hello"

# In function signature
def process_data(
    data: list[int],
    callback: Callable[[int], str]
) -> list[str]:
    return [callback(item) for item in data]
```

### mypy Configuration

#### pyproject.toml Configuration

```toml
[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
disallow_untyped_decorators = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
warn_unreachable = true
strict_equality = true
strict_concatenate = true

# Strict mode (enables all the above and more)
# strict = true

# Module-specific overrides
[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false
disallow_incomplete_defs = false

[[tool.mypy.overrides]]
module = ["redis_lock", "pybreaker"]
ignore_missing_imports = true
```

#### Strict Mode Flags

**Enabling strict mode** sets these flags:
- `warn_unused_configs`
- `disallow_any_generics`
- `disallow_subclassing_any`
- `disallow_untyped_calls`
- `disallow_untyped_defs`
- `disallow_incomplete_defs`
- `check_untyped_defs`
- `disallow_untyped_decorators`
- `warn_redundant_casts`
- `warn_unused_ignores`
- `warn_return_any`
- `no_implicit_reexport`
- `strict_equality`

**Recommendation**: Start with semi-strict, gradually enable flags

### Django-Specific Type Hints

```python
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.db.models import QuerySet
from typing import Any

# Views
def plant_detail(request: HttpRequest, pk: int) -> JsonResponse:
    # ...
    return JsonResponse({"data": "..."})

# QuerySets
def get_plants() -> QuerySet['Plant']:
    from .models import Plant
    return Plant.objects.all()

# Model instance
def create_plant(name: str) -> 'Plant':
    from .models import Plant
    return Plant.objects.create(name=name)

# DRF Serializers
from rest_framework import serializers

class PlantSerializer(serializers.ModelSerializer):
    def validate_name(self, value: str) -> str:
        if not value:
            raise serializers.ValidationError("Name required")
        return value

    def create(self, validated_data: dict[str, Any]) -> 'Plant':
        # ...
        pass
```

### Service Layer Type Hints

```python
from typing import Any
import logging

logger = logging.getLogger(__name__)

class PlantIdentificationService:
    """Service for identifying plants from images"""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def identify_plant(
        self,
        image_file: bytes
    ) -> dict[str, Any] | None:
        """
        Identify plant from image.

        Returns:
            Dictionary with identification results, or None if failed
        """
        try:
            response = self._call_api(image_file)
            return self._parse_response(response)
        except Exception as e:
            logger.error(f"Identification failed: {e}")
            return None

    def _call_api(self, image: bytes) -> dict[str, Any]:
        """Internal API call"""
        # Implementation
        pass

    def _parse_response(
        self,
        response: dict[str, Any]
    ) -> dict[str, Any]:
        """Parse API response"""
        return {
            "name": response.get("plant_name"),
            "confidence": response.get("probability", 0.0),
            "suggestions": response.get("suggestions", []),
        }
```

### Best Practices

1. **Use native generics** (`list`, `dict`) instead of `typing.List`, `typing.Dict`
2. **Prefer `X | None`** over `Optional[X]` (Python 3.10+)
3. **Use TypedDict** for structured dictionary types
4. **Avoid `Any`** when possible - be specific about types
5. **Use `NotRequired`** for optional TypedDict keys
6. **Configure mypy** in `pyproject.toml`
7. **Enable strict mode gradually** - start with key modules
8. **Use forward references** for circular dependencies (`'ClassName'`)
9. **Type all public APIs** - internal functions can be less strict
10. **Run mypy in CI/CD** to enforce type checking

### Running mypy

```bash
# Basic check
mypy .

# Specific paths
mypy apps/plant_identification/

# With configuration
mypy --config-file pyproject.toml .

# Show error codes
mypy --show-error-codes .

# Generate HTML report
mypy --html-report ./mypy-report .
```

---

## 5. File Upload Security

### Official Documentation Links

- **Django File Uploads**: https://docs.djangoproject.com/en/5.2/topics/http/file-uploads/
- **Django ImageField Advisory**: https://www.djangoproject.com/weblog/2013/dec/02/image-field-advisory/
- **python-magic**: https://pypi.org/project/python-magic/
- **Pillow Documentation**: https://pillow.readthedocs.io/en/stable/
- **OWASP File Upload**: https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html

### Security Vulnerabilities

#### Common Attack Vectors

1. **Extension Spoofing**: `malicious.php.jpg`
2. **Null Byte Injection**: `file.php\x00.jpg`
3. **Double Extensions**: `.jpg.php`
4. **Content-Type Manipulation**: Sending `image/jpeg` for PHP file
5. **Magic Byte Spoofing**: Adding JPEG header to malicious file
6. **Path Traversal**: `../../etc/passwd`
7. **Decompression Bombs**: Tiny file that decompresses to gigabytes
8. **Embedded Scripts**: JavaScript in SVG, PHP in EXIF data

### OWASP Best Practices

#### 1. File Type Validation (Multi-Layer)

**Never trust**:
- File extension
- Content-Type header
- File name

**Always validate**:
- Magic bytes (file signature)
- File structure (using library parsing)
- File content

```python
import magic
from PIL import Image
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator

def validate_image_comprehensive(file):
    """
    Multi-layer image validation following OWASP guidelines
    """
    # Layer 1: Extension validation
    ext_validator = FileExtensionValidator(
        allowed_extensions=['jpg', 'jpeg', 'png', 'webp', 'gif']
    )
    ext_validator(file)

    # Layer 2: Magic byte validation (actual file type)
    file_type = magic.from_buffer(file.read(2048), mime=True)
    file.seek(0)

    allowed_types = [
        'image/jpeg',
        'image/png',
        'image/webp',
        'image/gif'
    ]

    if file_type not in allowed_types:
        raise ValidationError(
            f'File type mismatch. Expected image, got {file_type}'
        )

    # Layer 3: PIL structure validation (verifies entire file)
    try:
        img = Image.open(file)
        img.verify()  # Checks file structure
        file.seek(0)

        # Re-open after verify (verify() invalidates image)
        img = Image.open(file)
        img.load()  # Actually decode image data
        file.seek(0)

    except Exception as e:
        raise ValidationError(f'Invalid image structure: {str(e)}')

    # Layer 4: Size restrictions
    if file.size > 10 * 1024 * 1024:  # 10MB
        raise ValidationError('File size exceeds 10MB limit')

    # Layer 5: Dimension restrictions
    if img.width > 10000 or img.height > 10000:
        raise ValidationError('Image dimensions too large')

    # Layer 6: Decompression bomb check
    # PIL raises DecompressionBombWarning automatically
    # Default threshold: 178,956,970 pixels
    Image.MAX_IMAGE_PIXELS = 89_000_000  # Custom limit

    return True
```

#### 2. File Name Sanitization

```python
import os
import uuid
from django.utils.text import get_valid_filename

def sanitize_upload_filename(original_filename: str) -> str:
    """
    OWASP-compliant filename sanitization
    """
    # Get base name (removes path traversal)
    basename = os.path.basename(original_filename)

    # Django's built-in sanitization
    safe_name = get_valid_filename(basename)

    # Generate random filename (recommended)
    ext = os.path.splitext(safe_name)[1].lower()
    random_name = f"{uuid.uuid4()}{ext}"

    return random_name

# Usage in model
from django.db import models

def upload_path(instance, filename):
    """Generate secure upload path"""
    safe_filename = sanitize_upload_filename(filename)
    return f"uploads/{instance.user_id}/{safe_filename}"

class Upload(models.Model):
    file = models.ImageField(upload_to=upload_path)
```

#### 3. Storage Outside Web Root

```python
# settings.py
import os

# WRONG: Files accessible via direct URL
MEDIA_ROOT = os.path.join(BASE_DIR, 'static', 'uploads')
MEDIA_URL = '/static/uploads/'

# CORRECT: Files stored outside web-accessible directory
MEDIA_ROOT = '/var/www/secure-uploads/'  # Outside web root
MEDIA_URL = '/media/'  # Served through Django view with auth check

# Serve files through Django (with authentication)
# urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('media/<path:path>/', views.protected_media, name='media'),
]

# views.py
from django.http import FileResponse, Http404
from django.contrib.auth.decorators import login_required
import os

@login_required
def protected_media(request, path):
    """
    Serve media files with authentication check
    """
    # Verify user has permission to access file
    if not request.user.has_perm('view_media'):
        raise Http404

    # Prevent path traversal
    safe_path = os.path.normpath(path)
    if safe_path.startswith('..'):
        raise Http404

    file_path = os.path.join(settings.MEDIA_ROOT, safe_path)

    # Verify file exists and is within MEDIA_ROOT
    if not os.path.exists(file_path):
        raise Http404

    if not file_path.startswith(settings.MEDIA_ROOT):
        raise Http404

    return FileResponse(open(file_path, 'rb'))
```

#### 4. File Size Limits

```python
# settings.py

# Maximum upload size (10MB)
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB

# Per-field validation
from django.core.validators import MaxValueValidator

class PlantImage(models.Model):
    image = models.ImageField(
        upload_to='plants/',
        validators=[
            validate_image_comprehensive,
            # Custom size validator
        ]
    )

    def clean(self):
        if self.image.size > 10 * 1024 * 1024:
            raise ValidationError('Image size cannot exceed 10MB')
```

### python-magic Best Practices

#### Installation

```bash
# macOS
brew install libmagic
pip install python-magic

# Ubuntu/Debian
sudo apt-get install libmagic1
pip install python-magic

# Verify installation
python -c "import magic; print(magic.from_file('/etc/hosts'))"
```

#### Usage

```python
import magic

# MIME type detection
def get_mime_type(file_path: str) -> str:
    """Get MIME type from file content (not extension)"""
    return magic.from_file(file_path, mime=True)

# From bytes
def get_mime_type_from_bytes(data: bytes) -> str:
    """Get MIME type from byte content"""
    # Use at least 2048 bytes for accuracy
    return magic.from_buffer(data[:2048], mime=True)

# Detailed file type
def get_file_description(file_path: str) -> str:
    """Get human-readable file description"""
    return magic.from_file(file_path)

# Usage in validation
def validate_file_type(file, allowed_types: list[str]):
    """
    Validate file type using magic bytes

    Args:
        file: Django UploadedFile
        allowed_types: List of allowed MIME types
    """
    # Read first 2048 bytes
    chunk = file.read(2048)
    file.seek(0)  # Reset file pointer

    # Detect MIME type
    detected_type = magic.from_buffer(chunk, mime=True)

    if detected_type not in allowed_types:
        raise ValidationError(
            f'Invalid file type: {detected_type}. '
            f'Allowed types: {", ".join(allowed_types)}'
        )

    return detected_type
```

### Pillow Security Best Practices

#### Decompression Bomb Protection

```python
from PIL import Image
import logging

logger = logging.getLogger(__name__)

# Configure decompression bomb protection
Image.MAX_IMAGE_PIXELS = 89_000_000  # ~89 megapixels (50% of default)

def safe_image_open(file_path: str) -> Image.Image | None:
    """
    Safely open image with decompression bomb protection
    """
    try:
        img = Image.open(file_path)

        # Verify image (checks header)
        img.verify()

        # Re-open after verify
        img = Image.open(file_path)

        # Check dimensions
        width, height = img.size
        if width * height > Image.MAX_IMAGE_PIXELS:
            logger.warning(
                f"Image too large: {width}x{height} "
                f"({width * height} pixels)"
            )
            return None

        return img

    except Image.DecompressionBombWarning as e:
        logger.warning(f"Decompression bomb detected: {e}")
        return None
    except Exception as e:
        logger.error(f"Image open failed: {e}")
        return None
```

#### Image Re-encoding (Security)

```python
from PIL import Image
from io import BytesIO

def sanitize_image(image_file) -> BytesIO:
    """
    Re-encode image to strip any embedded malicious content
    """
    img = Image.open(image_file)

    # Convert to RGB (removes any extra channels/data)
    if img.mode not in ('RGB', 'L'):
        img = img.convert('RGB')

    # Re-encode to new BytesIO (strips EXIF, metadata)
    output = BytesIO()
    img.save(output, format='JPEG', quality=85)
    output.seek(0)

    return output

# Usage
def process_upload(uploaded_file):
    """Process uploaded image securely"""
    # Validate first
    validate_image_comprehensive(uploaded_file)

    # Re-encode to strip malicious content
    clean_image = sanitize_image(uploaded_file)

    # Save clean image
    # ...
```

### Complete Validation Example

```python
import magic
from PIL import Image
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
import logging

logger = logging.getLogger(__name__)

class SecureImageValidator:
    """OWASP-compliant image validator"""

    ALLOWED_EXTENSIONS = ['jpg', 'jpeg', 'png', 'webp', 'gif']
    ALLOWED_MIME_TYPES = [
        'image/jpeg',
        'image/png',
        'image/webp',
        'image/gif'
    ]
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_DIMENSION = 10000
    MAX_PIXELS = 89_000_000

    def __call__(self, file):
        """Validate uploaded file"""
        self.validate_extension(file)
        self.validate_magic_bytes(file)
        self.validate_structure(file)
        self.validate_size(file)
        return True

    def validate_extension(self, file):
        """Validate file extension"""
        validator = FileExtensionValidator(
            allowed_extensions=self.ALLOWED_EXTENSIONS
        )
        validator(file)

    def validate_magic_bytes(self, file):
        """Validate using magic bytes"""
        chunk = file.read(2048)
        file.seek(0)

        mime_type = magic.from_buffer(chunk, mime=True)

        if mime_type not in self.ALLOWED_MIME_TYPES:
            raise ValidationError(
                f'Invalid file type: {mime_type}'
            )

        logger.info(f"[UPLOAD] Magic bytes validation: {mime_type}")

    def validate_structure(self, file):
        """Validate image structure with PIL"""
        try:
            img = Image.open(file)
            img.verify()
            file.seek(0)

            img = Image.open(file)
            img.load()
            file.seek(0)

            # Check dimensions
            if img.width > self.MAX_DIMENSION:
                raise ValidationError(
                    f'Image width {img.width}px exceeds '
                    f'{self.MAX_DIMENSION}px'
                )

            if img.height > self.MAX_DIMENSION:
                raise ValidationError(
                    f'Image height {img.height}px exceeds '
                    f'{self.MAX_DIMENSION}px'
                )

            # Check total pixels (decompression bomb)
            total_pixels = img.width * img.height
            if total_pixels > self.MAX_PIXELS:
                raise ValidationError(
                    f'Image too large: {total_pixels} pixels '
                    f'(max {self.MAX_PIXELS})'
                )

        except Exception as e:
            raise ValidationError(f'Invalid image: {str(e)}')

    def validate_size(self, file):
        """Validate file size"""
        if file.size > self.MAX_FILE_SIZE:
            size_mb = file.size / (1024 * 1024)
            max_mb = self.MAX_FILE_SIZE / (1024 * 1024)
            raise ValidationError(
                f'File size {size_mb:.1f}MB exceeds {max_mb:.1f}MB'
            )

# Usage
from django.db import models

class PlantIdentification(models.Model):
    image = models.ImageField(
        upload_to='plants/',
        validators=[SecureImageValidator()]
    )
```

### Testing File Upload Security

```python
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError

def test_rejects_php_file():
    """Test that PHP files are rejected"""
    php_content = b'<?php echo "malicious"; ?>'
    file = SimpleUploadedFile(
        "malicious.php.jpg",
        php_content,
        content_type="image/jpeg"
    )

    validator = SecureImageValidator()
    with pytest.raises(ValidationError):
        validator(file)

def test_rejects_oversized_image():
    """Test that oversized images are rejected"""
    # Create 20MB file
    large_content = b'0' * (20 * 1024 * 1024)
    file = SimpleUploadedFile("large.jpg", large_content)

    validator = SecureImageValidator()
    with pytest.raises(ValidationError, match="File size.*exceeds"):
        validator(file)

def test_accepts_valid_jpeg():
    """Test that valid JPEG is accepted"""
    # Use actual JPEG bytes (minimal valid JPEG)
    jpeg_bytes = (
        b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00'
        b'\x00\x01\x00\x01\x00\x00\xff\xdb\x00C'
    )
    file = SimpleUploadedFile("valid.jpg", jpeg_bytes)

    validator = SecureImageValidator()
    # Should not raise
    validator(file)
```

---

## 6. Distributed Systems Patterns

### Official Documentation Links

- **pybreaker**: https://github.com/danielfm/pybreaker
- **Martin Fowler Circuit Breaker**: https://martinfowler.com/bliki/CircuitBreaker.html
- **Redis Distributed Locks**: https://redis.io/docs/latest/develop/clients/patterns/distributed-locks/
- **Cache Stampede (Wikipedia)**: https://en.wikipedia.org/wiki/Cache_stampede

### Circuit Breaker Pattern

#### Concept

**Problem**: Remote calls can hang or fail, causing cascading failures in distributed systems

**Solution**: Wrap calls in a circuit breaker that:
1. **Monitors failures** and trips when threshold exceeded
2. **Fails fast** when open (returns error immediately)
3. **Auto-recovers** by periodically allowing test requests

**Benefits**:
- Prevents cascading failures
- Fails fast (no waiting for timeouts)
- Self-healing (auto-recovery)
- Better error handling

#### Three States

```
[Closed] → failures exceed threshold → [Open]
   ↑                                       ↓
   └── success ← [Half-Open] ← timeout ← ┘
```

1. **Closed**: Normal operation, requests pass through
2. **Open**: Failing, all requests fail immediately (fast-fail)
3. **Half-Open**: Testing recovery, limited requests allowed

#### pybreaker Usage

**Installation**:
```bash
pip install pybreaker
```

**Basic Usage**:
```python
import pybreaker

# Create circuit breaker (should be global/singleton)
plant_api_breaker = pybreaker.CircuitBreaker(
    fail_max=5,           # Open after 5 consecutive failures
    reset_timeout=60,     # Try recovery after 60 seconds
    name="PlantAPI"       # For logging/monitoring
)

# Decorator usage
@plant_api_breaker
def call_plant_api(image_data: bytes) -> dict:
    """Call external plant identification API"""
    response = requests.post(
        "https://api.plant.id/v1/identify",
        files={"image": image_data},
        timeout=30
    )
    response.raise_for_status()
    return response.json()

# Manual usage
try:
    result = plant_api_breaker.call(call_plant_api, image_data)
except pybreaker.CircuitBreakerError:
    # Circuit is open - API is down
    logger.warning("Plant API circuit breaker is OPEN")
    return {"error": "Service temporarily unavailable"}
```

#### Advanced Configuration

```python
import pybreaker
from redis import StrictRedis
import requests

# Redis storage for distributed circuit breaker state
redis_store = pybreaker.CircuitRedisStorage(
    pybreaker.STATE_OPEN,
    StrictRedis(host='localhost', port=6379)
)

# Advanced circuit breaker
plant_api_breaker = pybreaker.CircuitBreaker(
    fail_max=5,                    # Open after 5 failures
    reset_timeout=60,              # Reset after 60s
    exclude=[requests.HTTPError],  # Don't count 404s as failures
    name="PlantAPI",
    state_storage=redis_store      # Share state across processes
)

# Custom listeners for monitoring
def on_open(breaker):
    """Called when circuit opens"""
    logger.error(f"[CIRCUIT] {breaker.name} is now OPEN")
    # Send alert to monitoring system

def on_close(breaker):
    """Called when circuit closes"""
    logger.info(f"[CIRCUIT] {breaker.name} is now CLOSED")

plant_api_breaker.add_listener(on_open)
plant_api_breaker.add_listener(on_close)
```

#### Django Integration

```python
# apps/plant_identification/circuit_breakers.py
import pybreaker
from redis import StrictRedis
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

# Shared Redis connection
redis_conn = StrictRedis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB
)

# Circuit breakers (module-level singletons)
PLANT_ID_BREAKER = pybreaker.CircuitBreaker(
    fail_max=5,
    reset_timeout=60,
    name="PlantID_API",
    state_storage=pybreaker.CircuitRedisStorage(
        pybreaker.STATE_CLOSED,
        redis_conn
    )
)

PLANTNET_BREAKER = pybreaker.CircuitBreaker(
    fail_max=5,
    reset_timeout=60,
    name="PlantNet_API",
    state_storage=pybreaker.CircuitRedisStorage(
        pybreaker.STATE_CLOSED,
        redis_conn
    )
)

# Add logging listeners
def log_state_change(breaker, old_state, new_state):
    logger.warning(
        f"[CIRCUIT] {breaker.name} changed: "
        f"{old_state} → {new_state}"
    )

PLANT_ID_BREAKER.add_listener(log_state_change)
PLANTNET_BREAKER.add_listener(log_state_change)
```

```python
# apps/plant_identification/services/plant_id_service.py
from .circuit_breakers import PLANT_ID_BREAKER
import pybreaker
import logging

logger = logging.getLogger(__name__)

class PlantIDService:

    def identify_plant(self, image: bytes) -> dict | None:
        """Identify plant with circuit breaker protection"""
        try:
            result = PLANT_ID_BREAKER.call(
                self._call_api,
                image
            )
            return result

        except pybreaker.CircuitBreakerError:
            logger.warning(
                "[CIRCUIT] PlantID API breaker is OPEN - "
                "failing fast (<10ms)"
            )
            return None
        except Exception as e:
            logger.error(f"PlantID API error: {e}")
            return None

    def _call_api(self, image: bytes) -> dict:
        """Actual API call (wrapped by circuit breaker)"""
        # This will be called only if circuit is closed/half-open
        response = requests.post(...)
        response.raise_for_status()
        return response.json()
```

#### Best Practices

1. **Use module-level singletons** - One breaker per integration point
2. **Configure Redis storage** - Share state across processes
3. **Set appropriate timeouts** - Balance recovery vs. downtime
4. **Add listeners** - Log state changes for monitoring
5. **Exclude expected errors** - Don't trip on 404s or validation errors
6. **Test recovery** - Verify half-open state works correctly

### Distributed Locking (Cache Stampede Prevention)

#### Problem: Cache Stampede

When a popular cache key expires:
1. Multiple requests simultaneously detect cache miss
2. All requests call expensive backend (database, API)
3. Duplicate work wastes resources
4. Backend gets overloaded

**Example**: 1000 requests for same plant hit expired cache key, all 1000 call Plant.id API

#### Solution: Distributed Locks

Only one request computes the value, others wait:

```python
from django.core.cache import cache
from redis import StrictRedis
import redis_lock
import logging

logger = logging.getLogger(__name__)
redis_conn = StrictRedis()

def get_plant_with_lock(plant_id: int) -> dict:
    """
    Get plant data with distributed lock to prevent stampede
    """
    cache_key = f"plant:{plant_id}"
    lock_key = f"lock:{cache_key}"

    # Try cache first (fast path)
    cached = cache.get(cache_key)
    if cached is not None:
        logger.info(f"[CACHE] HIT for plant {plant_id}")
        return cached

    logger.info(f"[CACHE] MISS for plant {plant_id}")

    # Acquire distributed lock
    with redis_lock.Lock(
        redis_conn,
        lock_key,
        expire=30,           # Lock expires in 30s
        auto_renewal=True,   # Renew if taking longer
        blocking=True,       # Wait for lock
        blocking_timeout=35  # Max wait time
    ):
        # Double-check cache (another process may have set it)
        cached = cache.get(cache_key)
        if cached is not None:
            logger.info(f"[CACHE] HIT after lock for plant {plant_id}")
            return cached

        # Compute value (only one process does this)
        logger.info(f"[CACHE] COMPUTING plant {plant_id}")
        plant_data = fetch_from_database(plant_id)

        # Cache result
        cache.set(cache_key, plant_data, timeout=3600)

        return plant_data
```

#### Probabilistic Early Recomputation

Alternative to locking - probabilistically refresh before expiration:

```python
import random
import time
import math
from django.core.cache import cache

def get_with_early_recompute(
    key: str,
    compute_func,
    ttl: int = 3600,
    beta: float = 1.0
) -> any:
    """
    Probabilistic early recomputation to prevent stampedes

    Based on optimal probabilistic cache stampede prevention:
    https://cseweb.ucsd.edu/~avattani/papers/cache_stampede.pdf
    """
    # Get cached value and timestamp
    cached = cache.get(f"{key}:data")
    cached_time = cache.get(f"{key}:time")

    if cached is None or cached_time is None:
        # Cache miss - compute and store
        value = compute_func()
        cache.set(f"{key}:data", value, timeout=ttl)
        cache.set(f"{key}:time", time.time(), timeout=ttl)
        return value

    # Calculate probability of early recomputation
    elapsed = time.time() - cached_time

    # Exponential distribution (optimal)
    delta = ttl * beta * math.log(random.random())

    if elapsed + delta >= ttl:
        # Probabilistically recompute early
        logger.info(f"[CACHE] Early recompute for {key}")
        value = compute_func()
        cache.set(f"{key}:data", value, timeout=ttl)
        cache.set(f"{key}:time", time.time(), timeout=ttl)
        return value

    return cached
```

#### Request Coalescing

Deduplicate simultaneous identical requests:

```python
from threading import Lock
from typing import Callable, Any
import hashlib

class RequestCoalescer:
    """
    Coalesce multiple identical concurrent requests into one
    """
    def __init__(self):
        self._pending: dict[str, Any] = {}
        self._locks: dict[str, Lock] = {}
        self._global_lock = Lock()

    def coalesce(
        self,
        key: str,
        compute_func: Callable[[], Any]
    ) -> Any:
        """
        Execute compute_func, but if another thread is already
        computing the same key, wait for that result instead
        """
        with self._global_lock:
            if key not in self._locks:
                self._locks[key] = Lock()
            lock = self._locks[key]

        # Try to acquire lock
        if lock.acquire(blocking=False):
            try:
                # We're the first - compute value
                result = compute_func()
                self._pending[key] = result
                return result
            finally:
                lock.release()
                # Clean up
                with self._global_lock:
                    if key in self._locks:
                        del self._locks[key]
        else:
            # Another thread is computing - wait
            with lock:
                # Lock released - result is ready
                return self._pending.get(key)

# Usage
coalescer = RequestCoalescer()

def get_plant_data(plant_id: int) -> dict:
    """Get plant data with request coalescing"""
    key = f"plant:{plant_id}"

    return coalescer.coalesce(
        key,
        lambda: expensive_database_query(plant_id)
    )
```

### Combined Pattern: Circuit Breaker + Distributed Lock

```python
from apps.plant_identification.circuit_breakers import PLANT_ID_BREAKER
from django.core.cache import cache
from redis import StrictRedis
import redis_lock
import pybreaker
import logging

logger = logging.getLogger(__name__)
redis_conn = StrictRedis()

class PlantIdentificationService:
    """
    Plant identification with circuit breaker + distributed lock
    """

    def identify_with_cache(self, image_hash: str, image_data: bytes) -> dict | None:
        """
        Identify plant with:
        - Redis caching
        - Distributed lock (stampede prevention)
        - Circuit breaker (fault tolerance)
        """
        cache_key = f"plant_id:{image_hash}"
        lock_key = f"lock:{cache_key}"

        # Try cache first
        cached = cache.get(cache_key)
        if cached is not None:
            logger.info(f"[CACHE] HIT for {image_hash[:8]}")
            return cached

        logger.info(f"[CACHE] MISS for {image_hash[:8]}")

        # Acquire lock to prevent stampede
        try:
            with redis_lock.Lock(
                redis_conn,
                lock_key,
                expire=30,
                auto_renewal=True,
                blocking=True,
                blocking_timeout=35
            ):
                # Double-check cache
                cached = cache.get(cache_key)
                if cached is not None:
                    logger.info(f"[CACHE] HIT after lock for {image_hash[:8]}")
                    return cached

                # Call API with circuit breaker protection
                try:
                    result = PLANT_ID_BREAKER.call(
                        self._call_plant_api,
                        image_data
                    )

                    # Cache successful result
                    if result:
                        cache.set(cache_key, result, timeout=1800)

                    return result

                except pybreaker.CircuitBreakerError:
                    logger.warning(
                        f"[CIRCUIT] PlantID breaker OPEN - "
                        f"fast-fail for {image_hash[:8]}"
                    )
                    return None

        except redis_lock.LockNotOwnedError:
            logger.warning(f"[LOCK] Lock timeout for {image_hash[:8]}")
            return None

    def _call_plant_api(self, image_data: bytes) -> dict:
        """Actual API call (protected by circuit breaker)"""
        # Implementation...
        pass
```

### Monitoring and Observability

```python
import logging
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class CircuitBreakerMetrics:
    """Metrics for circuit breaker monitoring"""
    name: str
    state: str
    failure_count: int
    last_failure_time: datetime | None
    open_time: datetime | None

    def log(self):
        logger.info(
            f"[METRICS] Circuit Breaker: {self.name} | "
            f"State: {self.state} | "
            f"Failures: {self.failure_count}"
        )

def collect_metrics(breaker: pybreaker.CircuitBreaker) -> CircuitBreakerMetrics:
    """Collect metrics from circuit breaker"""
    return CircuitBreakerMetrics(
        name=breaker.name,
        state=str(breaker.current_state),
        failure_count=breaker.fail_counter,
        last_failure_time=getattr(breaker, 'last_failure_time', None),
        open_time=getattr(breaker, 'opened_at', None)
    )

# Health check endpoint
from django.http import JsonResponse

def circuit_breaker_health(request):
    """Expose circuit breaker states for monitoring"""
    from .circuit_breakers import PLANT_ID_BREAKER, PLANTNET_BREAKER

    return JsonResponse({
        "plant_id": {
            "state": str(PLANT_ID_BREAKER.current_state),
            "failures": PLANT_ID_BREAKER.fail_counter,
        },
        "plantnet": {
            "state": str(PLANTNET_BREAKER.current_state),
            "failures": PLANTNET_BREAKER.fail_counter,
        }
    })
```

---

## Summary of Key References

### Django 5.2
- Deployment Checklist: https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/
- Security: https://docs.djangoproject.com/en/5.2/topics/security/

### Django REST Framework
- Authentication: https://www.django-rest-framework.org/api-guide/authentication/
- Permissions: https://www.django-rest-framework.org/api-guide/permissions/

### Redis & Caching
- django-redis: https://github.com/jazzband/django-redis
- python-redis-lock: https://pypi.org/project/python-redis-lock/
- Redis Distributed Locks: https://redis.io/docs/latest/develop/clients/patterns/distributed-locks/

### Python Typing
- PEP 484: https://peps.python.org/pep-0484/
- PEP 585: https://peps.python.org/pep-0585/
- mypy: https://mypy.readthedocs.io/en/stable/

### File Upload Security
- OWASP File Upload: https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html
- python-magic: https://pypi.org/project/python-magic/
- Pillow: https://pillow.readthedocs.io/en/stable/

### Distributed Systems
- Martin Fowler Circuit Breaker: https://martinfowler.com/bliki/CircuitBreaker.html
- pybreaker: https://github.com/danielfm/pybreaker
- Cache Stampede: https://en.wikipedia.org/wiki/Cache_stampede

---

**Last Updated**: 2025-10-22
**Maintained By**: Plant ID Community Backend Team
