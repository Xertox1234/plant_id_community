# Secret Management & API Key Patterns

**Last Updated**: November 13, 2025
**Consolidated From**:
- `plant_community_backend/settings.py` (SECRET_KEY validation)
- `docs/development/SECURITY_PATTERNS_CODIFIED.md` (secret detection)
- `todos/completed/005-completed-p1-api-key-rotation-verification.md` (key rotation)
- `.gitignore` (file exclusions)
- Issue #1 Security Incident (API keys exposed)

**Status**: ✅ Production-Tested

---

## Table of Contents

1. [Django SECRET_KEY Patterns](#django-secret_key-patterns)
2. [API Key Management](#api-key-management)
3. [Environment Variable Patterns](#environment-variable-patterns)
4. [GitIgnore Patterns](#gitignore-patterns)
5. [Secret Detection Regex](#secret-detection-regex)
6. [Key Rotation Procedures](#key-rotation-procedures)
7. [Pre-Commit Hooks](#pre-commit-hooks)
8. [Testing Secret Validation](#testing-secret-validation)

---

## Django SECRET_KEY Patterns

### Pattern: Environment-Aware SECRET_KEY with Production Validation

**Problem**: Django applications often ship with insecure default SECRET_KEY values, allowing production deployment with predictable keys. This enables session hijacking, CSRF bypass, and authentication bypass attacks.

**Security Impact**:
- Session cookie forgery → User impersonation
- CSRF token prediction → State-changing attacks
- Password reset token forgery → Account takeover
- Signed cookie tampering → Data integrity loss

**Location**: `backend/plant_community_backend/settings.py:34-95`

---

### Pattern: Fail-Fast Production Validation

**Correct Implementation**:
```python
import os
from pathlib import Path
from decouple import config
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# Environment-aware SECRET_KEY configuration
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
        'test',
        'dev',
        'local',
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
```

---

### Pattern: Why Development Defaults Are Allowed

**Development vs Production**:
```python
# ✅ DEVELOPMENT (DEBUG=True)
# - Insecure default allowed for quick setup
# - Clearly marked: "DO-NOT-USE-IN-PRODUCTION"
# - No validation warnings
if DEBUG:
    SECRET_KEY = config(
        'SECRET_KEY',
        default='django-insecure-dev-only-DO-NOT-USE-IN-PRODUCTION-abc123xyz'
    )

# ✅ PRODUCTION (DEBUG=False)
# - No defaults - MUST be set
# - Fails loudly with helpful error message
# - Validates against insecure patterns
# - Enforces minimum length (50 chars)
else:
    SECRET_KEY = config('SECRET_KEY')  # Raises if missing
```

**Why This Works**:
1. **Developer Experience**: Local setup "just works" without manual key generation
2. **Production Safety**: Impossible to deploy with insecure defaults
3. **Clear Errors**: Helpful messages guide correct setup
4. **Fail-Fast**: Application won't start with bad configuration

---

### Pattern: Generate Secure SECRET_KEY

**Command**:
```bash
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

**Output Example**:
```
django-insecure-r3a!5$x^w8%y*z#k@m+n=p&q~s[t]u{v}w|x,y.z/a<b>c?d
```

**Why Django's Generator?**:
- Uses `secrets` module (cryptographically secure)
- 50 characters by default
- Includes special characters for entropy
- Tested and maintained by Django team

---

## API Key Management

### Pattern: External Service API Keys

**Problem**: API keys for external services (Plant.id, PlantNet, OpenAI, etc.) should NEVER be committed to repositories. Even "development" or "test" keys can be abused if exposed.

**Types of API Keys**:
1. **Plant.id API Key** - 50 characters, 100 requests/month free tier
2. **PlantNet API Key** - 24 characters, 500 requests/day limit
3. **OpenAI API Key** - Starts with `sk-`, charged per token
4. **Firebase Keys** - Multiple types (Web API key, service account JSON)
5. **OAuth Credentials** - Client ID + Client Secret pairs

---

### Pattern: API Key Storage (.env files)

**Correct Storage**:
```bash
# backend/.env (NEVER commit this file)

# Django Core
SECRET_KEY=django-insecure-r3a!5$x^w8%y*z#k@m+n=p&q~s[t]u{v}w|x,y.z/a<b>c?d
DEBUG=True

# External APIs
PLANT_ID_API_KEY=your-plant-id-api-key-50-characters-long-example
PLANTNET_API_KEY=your-plantnet-api-key-24chars
OPENAI_API_KEY=sk-your-openai-api-key-here

# JWT Authentication
JWT_SECRET_KEY=your-jwt-secret-key-here-at-least-50-characters-long

# OAuth (if using)
GOOGLE_OAUTH2_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_OAUTH2_CLIENT_SECRET=your-google-client-secret
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret

# Database
DATABASE_URL=postgres://user:password@localhost:5432/plant_community

# Redis
REDIS_URL=redis://localhost:6379/1

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:5174
```

---

### Pattern: .env.example Template

**Purpose**: Provide template without real secrets

**Location**: `backend/.env.example`

**Content**:
```bash
# Django Core
# Generate with: python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# External APIs
# Plant.id: Sign up at https://web.plant.id/
PLANT_ID_API_KEY=your-plant-id-api-key-here

# PlantNet: Sign up at https://my.plantnet.org/
PLANTNET_API_KEY=your-plantnet-api-key-here

# OpenAI: Get from https://platform.openai.com/api-keys
OPENAI_API_KEY=sk-your-openai-api-key-here

# JWT Authentication
# Generate with: python -c 'import secrets; print(secrets.token_urlsafe(50))'
JWT_SECRET_KEY=your-jwt-secret-key-here

# Database (use SQLite for dev, PostgreSQL for prod)
DATABASE_URL=sqlite:///db.sqlite3

# Redis (required for caching + distributed locks)
REDIS_URL=redis://localhost:6379/1

# CORS (frontend URL)
CORS_ALLOWED_ORIGINS=http://localhost:5174
```

**Key Differences**:
- ✅ `.env.example` - Committed to repository, contains placeholders
- ❌ `.env` - NEVER committed, contains real secrets
- ✅ `.env.local` - Local overrides, also never committed

---

### Pattern: Loading Environment Variables

**Using python-decouple**:
```python
from decouple import config

# Required API keys (fail if missing)
PLANT_ID_API_KEY = config('PLANT_ID_API_KEY')
PLANTNET_API_KEY = config('PLANTNET_API_KEY')

# Optional API keys (default to None)
OPENAI_API_KEY = config('OPENAI_API_KEY', default=None)

# Type casting
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost', cast=lambda v: [s.strip() for s in v.split(',')])
```

**Using os.environ (alternative)**:
```python
import os

# Required (raises KeyError if missing)
PLANT_ID_API_KEY = os.environ['PLANT_ID_API_KEY']

# Optional with default
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', None)

# With validation
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    raise ImproperlyConfigured('SECRET_KEY environment variable required')
```

---

## Environment Variable Patterns

### Pattern: Environment Variable Naming

**Conventions**:
```bash
# Django settings - SCREAMING_SNAKE_CASE
SECRET_KEY=...
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# API keys - SERVICE_API_KEY pattern
PLANT_ID_API_KEY=...
PLANTNET_API_KEY=...
OPENAI_API_KEY=...

# Database URLs - *_URL pattern
DATABASE_URL=postgres://...
REDIS_URL=redis://...

# Feature flags - ENABLE_* pattern
ENABLE_FILE_LOGGING=True
ENABLE_CACHE_WARMING=True

# OAuth - SERVICE_OAUTH*_* pattern
GOOGLE_OAUTH2_CLIENT_ID=...
GOOGLE_OAUTH2_CLIENT_SECRET=...
```

---

### Pattern: Environment-Specific Configuration

**Development (.env.dev)**:
```bash
DEBUG=True
SECRET_KEY=django-insecure-dev-only-DO-NOT-USE-IN-PRODUCTION-abc123xyz
DATABASE_URL=sqlite:///db.sqlite3
REDIS_URL=redis://localhost:6379/1
ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:5174
```

**Production (.env.prod)**:
```bash
DEBUG=False
SECRET_KEY=<50+ character secure key>
DATABASE_URL=postgres://user:password@db.example.com:5432/plant_community
REDIS_URL=redis://cache.example.com:6379/1
ALLOWED_HOSTS=example.com,www.example.com
CORS_ALLOWED_ORIGINS=https://example.com,https://www.example.com
```

**Testing (.env.test)**:
```bash
DEBUG=True
SECRET_KEY=test-secret-key-for-testing-only
DATABASE_URL=sqlite:///test_db.sqlite3
REDIS_URL=redis://localhost:6379/2
```

---

## GitIgnore Patterns

### Pattern: Comprehensive Secret Exclusion

**Location**: `/.gitignore`

**Environment & Secrets Section**:
```gitignore
# ===================================
# Environment & Secrets
# ===================================
.env
.env.local
.env.*.local
.env.development.local
.env.test.local
.env.production.local
*.key
*.pem
*.p12
*.jks
secrets/
credentials/

# Specific secret files
google-credentials.json
firebase-adminsdk.json
service-account.json
```

**Development / Reference Materials**:
```gitignore
# ===================================
# Development / Reference Materials
# ===================================
# Claude Code configuration and tools
.claude/

# CLAUDE.md contains project-specific context and may include sensitive info
# Use CLAUDE.md.example as template
CLAUDE.md

# Local configuration
*.local
config.local.*
settings.local.py
```

**Why Each Pattern**:
- `.env*` - Catches all environment variable files
- `*.key`, `*.pem` - SSL/TLS certificates and private keys
- `secrets/` - Common directory for storing secrets
- `CLAUDE.md` - Local development context (Issue #1 incident)

---

### Pattern: What TO Commit vs NEVER Commit

**✅ SAFE TO COMMIT**:
```bash
.env.example           # Template with placeholders
.env.template          # Alternative template name
README.md              # Documentation with placeholder examples
requirements.txt       # Dependencies (no secrets)
docker-compose.yml     # Config with env var references (${SECRET_KEY})
settings.py            # Code that LOADS secrets, not secrets themselves
```

**❌ NEVER COMMIT**:
```bash
.env                   # Real secrets
.env.local             # Local overrides
.env.production        # Production secrets
config.json            # If contains secrets
google-credentials.json # Service account keys
firebase-adminsdk-*.json # Firebase keys
*.key, *.pem           # Private keys
CLAUDE.md              # May contain real credentials in examples
```

---

## Secret Detection Regex

### Pattern: API Key Detection Patterns

**Location**: Extracted from Issue #1 Security Incident

**Plant.id API Key**:
```regex
PLANT_ID_API_KEY\s*=\s*[A-Za-z0-9]{40,60}
```

**PlantNet API Key**:
```regex
PLANTNET_API_KEY\s*=\s*[A-Za-z0-9]{20,30}
```

**Generic API Key**:
```regex
[A-Z_]+_API_KEY\s*=\s*['"][A-Za-z0-9_\-]{20,}['"]
```

**Django SECRET_KEY**:
```regex
SECRET_KEY\s*=\s*['"][A-Za-z0-9!@#$%^&*()_+\-=\[\]{}|;:,.<>?]{40,}['"]
```

**Insecure Development Keys**:
```regex
SECRET_KEY\s*=\s*['"].*\b(dev|test|insecure|change|sample|example)\b.*['"]
```

**JWT Secret**:
```regex
JWT_SECRET_KEY\s*=\s*['"][A-Za-z0-9_\-]{20,}['"]
JWT_SECRET\s*=\s*['"][A-Za-z0-9_\-]{20,}['"]
```

**OAuth Credentials**:
```regex
[A-Z_]*CLIENT_SECRET\s*=\s*['"][A-Za-z0-9_\-]{20,}['"]
[A-Z_]*OAUTH.*SECRET\s*=\s*['"][A-Za-z0-9_\-]{20,}['"]
```

**OpenAI API Key**:
```regex
sk-[A-Za-z0-9]{48}
```

---

### Pattern: Pre-Commit Secret Detection

**Using grep**:
```bash
#!/bin/bash
# Check staged files for secrets

PATTERNS=(
    "PLANT_ID_API_KEY\s*=\s*[A-Za-z0-9]{40,60}"
    "PLANTNET_API_KEY\s*=\s*[A-Za-z0-9]{20,30}"
    "SECRET_KEY\s*=\s*['\"][A-Za-z0-9!@#$%^&*()_+\-=\[\]{}|;:,.<>?]{40,}['\"]"
    "sk-[A-Za-z0-9]{48}"
)

for pattern in "${PATTERNS[@]}"; do
    if git diff --cached | grep -E "$pattern"; then
        echo "❌ BLOCKED: Potential secret detected in staged changes"
        echo "Pattern: $pattern"
        exit 1
    fi
done

echo "✅ No secrets detected"
exit 0
```

---

## Key Rotation Procedures

### Pattern: API Key Rotation Workflow

**When to Rotate**:
1. **Immediately**: If key is exposed in public repository
2. **Quarterly**: Routine security hygiene (recommended)
3. **After Breach**: If any system compromise is suspected
4. **Team Changes**: When team member with access leaves

---

### Pattern: Plant.id API Key Rotation

**Steps**:
```bash
# 1. Generate new key at https://web.plant.id/
# 2. Update .env file (do NOT commit)
echo "PLANT_ID_API_KEY=new-key-here" >> backend/.env

# 3. Update production environment
# Kubernetes:
kubectl create secret generic plant-id-api-key --from-literal=key=new-key-here --dry-run=client -o yaml | kubectl apply -f -

# Heroku:
heroku config:set PLANT_ID_API_KEY=new-key-here

# AWS Systems Manager:
aws ssm put-parameter --name /plant-community/prod/plant-id-api-key --value new-key-here --overwrite

# 4. Restart application
kubectl rollout restart deployment/plant-community  # Kubernetes
heroku ps:restart  # Heroku
```

---

### Pattern: Django SECRET_KEY Rotation

**CRITICAL**: SECRET_KEY rotation invalidates all sessions and CSRF tokens

**Steps**:
```bash
# 1. Generate new key
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'

# 2. Update .env file
echo "SECRET_KEY=new-secret-key-here" >> backend/.env

# 3. Update production (with downtime warning)
# WARNING: All users will be logged out
heroku config:set SECRET_KEY=new-secret-key-here

# 4. Restart application
heroku ps:restart

# 5. Notify users
# - Send email: "Security update - please log in again"
# - Display message: "Session expired, please log in"
```

**Zero-Downtime Rotation** (Advanced):
```python
# settings.py - Multiple SECRET_KEY support
SECRET_KEY = config('SECRET_KEY')
OLD_SECRET_KEYS = [
    config('OLD_SECRET_KEY_1', default=None),
    config('OLD_SECRET_KEY_2', default=None),
]
# Django will try each key for validation
# Deploy new key as OLD_SECRET_KEY_1, keep original
# After 24 hours, promote new key to SECRET_KEY
```

---

### Pattern: JWT Secret Rotation

**Location**: `backend/docs/deployment/UPGRADE_JWT_SECRET_KEY.md`

**Steps**:
```bash
# 1. Generate new JWT secret
python -c 'import secrets; print(secrets.token_urlsafe(50))'

# 2. Update .env
echo "JWT_SECRET_KEY=new-jwt-secret-here" >> backend/.env

# 3. Update production
heroku config:set JWT_SECRET_KEY=new-jwt-secret-here

# 4. Restart application
# All JWT tokens will be invalidated
# Users must log in again

# 5. Clear Redis cache (if caching JWTs)
redis-cli FLUSHDB
```

---

## Pre-Commit Hooks

### Pattern: Git Pre-Commit Hook Setup

**Location**: `.git/hooks/pre-commit`

**Implementation**:
```bash
#!/bin/bash
# Pre-commit hook to prevent secret leaks

echo "🔍 Checking for secrets..."

# Patterns to detect
PATTERNS=(
    # API keys
    "PLANT_ID_API_KEY\s*=\s*[A-Za-z0-9]{40,60}"
    "PLANTNET_API_KEY\s*=\s*[A-Za-z0-9]{20,30}"
    "[A-Z_]+_API_KEY\s*=\s*['\"][A-Za-z0-9_\-]{20,}['\"]"

    # Django secrets
    "SECRET_KEY\s*=\s*['\"][A-Za-z0-9!@#$%^&*()_+\-=\[\]{}|;:,.<>?]{40,}['\"]"
    "JWT_SECRET_KEY\s*=\s*['\"][A-Za-z0-9_\-]{20,}['\"]"

    # OAuth
    "[A-Z_]*CLIENT_SECRET\s*=\s*['\"][A-Za-z0-9_\-]{20,}['\"]"

    # OpenAI
    "sk-[A-Za-z0-9]{48}"

    # Generic patterns
    "password\s*=\s*['\"][^'\"]{8,}['\"]"
    "token\s*=\s*['\"][A-Za-z0-9_\-]{20,}['\"]"
)

# Check staged files
FAILED=0
for pattern in "${PATTERNS[@]}"; do
    if git diff --cached --diff-filter=ACM | grep -E "$pattern"; then
        echo "❌ BLOCKED: Potential secret detected"
        echo "   Pattern: $pattern"
        FAILED=1
    fi
done

if [ $FAILED -eq 1 ]; then
    echo ""
    echo "🚨 COMMIT BLOCKED - Secrets detected in staged changes"
    echo ""
    echo "If this is a false positive:"
    echo "  git commit --no-verify"
    echo ""
    echo "If you accidentally staged secrets:"
    echo "  git reset HEAD <file>  # Unstage file"
    echo "  # Edit file to remove secrets"
    echo "  git add <file>         # Re-stage cleaned file"
    exit 1
fi

echo "✅ No secrets detected"
exit 0
```

**Installation**:
```bash
# Make hook executable
chmod +x .git/hooks/pre-commit

# Or use pre-commit framework
pip install pre-commit
pre-commit install
```

---

### Pattern: Using detect-secrets Tool

**Installation**:
```bash
pip install detect-secrets
```

**Initialize Baseline**:
```bash
# Create baseline of current secrets (for exceptions)
detect-secrets scan > .secrets.baseline
```

**Pre-Commit Configuration** (`.pre-commit-config.yaml`):
```yaml
repos:
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
        exclude: package.lock.json
```

**Run Manually**:
```bash
# Scan all files
detect-secrets scan

# Audit baseline
detect-secrets audit .secrets.baseline
```

---

## Testing Secret Validation

### Pattern: Test SECRET_KEY Validation

**Location**: Create in `backend/plant_community_backend/tests/test_settings.py`

**Test Cases**:
```python
import os
import pytest
from django.core.exceptions import ImproperlyConfigured
from django.conf import settings

class TestSecretKeyValidation:
    """Test SECRET_KEY validation in production mode."""

    def test_production_requires_secret_key(self, monkeypatch):
        """Production mode must have SECRET_KEY set."""
        monkeypatch.setenv('DEBUG', 'False')
        monkeypatch.delenv('SECRET_KEY', raising=False)

        with pytest.raises(ImproperlyConfigured, match="SECRET_KEY environment variable is not set"):
            # Reload settings to trigger validation
            import plant_community_backend.settings
            reload(plant_community_backend.settings)

    def test_production_rejects_insecure_patterns(self, monkeypatch):
        """Production mode rejects SECRET_KEY with insecure patterns."""
        monkeypatch.setenv('DEBUG', 'False')

        insecure_keys = [
            'django-insecure-test-key',
            'change-me-in-production',
            'your-secret-key-here',
            'test-secret-key',
            'dev-key',
        ]

        for key in insecure_keys:
            monkeypatch.setenv('SECRET_KEY', key)

            with pytest.raises(ImproperlyConfigured, match="insecure pattern"):
                import plant_community_backend.settings
                reload(plant_community_backend.settings)

    def test_production_enforces_minimum_length(self, monkeypatch):
        """SECRET_KEY must be at least 50 characters."""
        monkeypatch.setenv('DEBUG', 'False')
        monkeypatch.setenv('SECRET_KEY', 'short-key')

        with pytest.raises(ImproperlyConfigured, match="too short"):
            import plant_community_backend.settings
            reload(plant_community_backend.settings)

    def test_development_allows_insecure_default(self, monkeypatch):
        """Development mode allows insecure default."""
        monkeypatch.setenv('DEBUG', 'True')
        monkeypatch.delenv('SECRET_KEY', raising=False)

        # Should not raise
        import plant_community_backend.settings
        reload(plant_community_backend.settings)

        assert 'django-insecure' in settings.SECRET_KEY.lower()

    def test_valid_production_key_accepted(self, monkeypatch):
        """Valid production key should be accepted."""
        monkeypatch.setenv('DEBUG', 'False')
        secure_key = 'r3a!5$x^w8%y*z#k@m+n=p&q~s[t]u{v}w|x,y.z/a<b>c?d'
        monkeypatch.setenv('SECRET_KEY', secure_key)

        # Should not raise
        import plant_community_backend.settings
        reload(plant_community_backend.settings)

        assert settings.SECRET_KEY == secure_key
```

---

### Pattern: Test Environment Variable Loading

**Test Cases**:
```python
import os
import pytest
from decouple import config

class TestEnvironmentVariables:
    """Test environment variable loading."""

    def test_required_api_keys_loaded(self, monkeypatch):
        """Required API keys must be present."""
        monkeypatch.setenv('PLANT_ID_API_KEY', 'test-key-50-characters-long-example-placeholder')
        monkeypatch.setenv('PLANTNET_API_KEY', 'test-key-24chars-example')

        from plant_community_backend import settings
        reload(settings)

        assert settings.PLANT_ID_API_KEY
        assert settings.PLANTNET_API_KEY

    def test_optional_api_keys_default_none(self, monkeypatch):
        """Optional API keys default to None if not set."""
        monkeypatch.delenv('OPENAI_API_KEY', raising=False)

        from plant_community_backend import settings
        reload(settings)

        assert settings.OPENAI_API_KEY is None

    def test_bool_casting_works(self, monkeypatch):
        """Boolean environment variables cast correctly."""
        monkeypatch.setenv('DEBUG', 'True')
        assert config('DEBUG', cast=bool) is True

        monkeypatch.setenv('DEBUG', 'False')
        assert config('DEBUG', cast=bool) is False

        monkeypatch.setenv('DEBUG', '1')
        assert config('DEBUG', cast=bool) is True

        monkeypatch.setenv('DEBUG', '0')
        assert config('DEBUG', cast=bool) is False
```

---

## Common Pitfalls

### Pitfall 1: Committing .env Files

**Problem**:
```bash
# ❌ DANGER - Accidentally staging .env file
git add .
git commit -m "Update configuration"
# .env file with real secrets now in git history!
```

**Solution**:
```bash
# ✅ ALWAYS check what you're staging
git status
git diff --cached

# ✅ Add .env to .gitignore
echo ".env" >> .gitignore
git add .gitignore
git commit -m "Add .env to gitignore"

# ✅ If already committed, remove from history
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch .env" \
  --prune-empty --tag-name-filter cat -- --all
```

---

### Pitfall 2: Hardcoding Secrets in Code

**Problem**:
```python
# ❌ DANGER - Hardcoded secret in code
SECRET_KEY = 'django-insecure-hardcoded-key-123'
PLANT_ID_API_KEY = 'W3YvEk2rx8g7Ko3fa8hKrlPJVqQeT2muIfikhKqvSBnaIUkXd4'
```

**Solution**:
```python
# ✅ CORRECT - Load from environment
from decouple import config

SECRET_KEY = config('SECRET_KEY')
PLANT_ID_API_KEY = config('PLANT_ID_API_KEY')
```

---

### Pitfall 3: Putting Secrets in Documentation

**Problem**:
```markdown
# ❌ DANGER - Real secrets in documentation
## Quick Start

Set up your environment:
\`\`\`bash
export PLANT_ID_API_KEY=W3YvEk2rx8g7Ko3fa8hKrlPJVqQeT2muIfikhKqvSBnaIUkXd4
export SECRET_KEY=django-insecure-real-production-key-abc123
\`\`\`
```

**Solution**:
```markdown
# ✅ CORRECT - Placeholders in documentation
## Quick Start

Set up your environment:
\`\`\`bash
export PLANT_ID_API_KEY=your-plant-id-api-key-here
export SECRET_KEY=$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')
\`\`\`

Get API keys from:
- Plant.id: https://web.plant.id/
- PlantNet: https://my.plantnet.org/
```

---

### Pitfall 4: Sharing .env Files via Slack/Email

**Problem**:
```
❌ DANGER - "Hey, here's my .env file for reference"
[Attaches .env with real production secrets]
```

**Solution**:
```
✅ CORRECT - Share .env.example instead
"Use .env.example as a template. I'll share secrets via 1Password/LastPass"
```

**Use Secret Management Tools**:
- 1Password (Teams)
- LastPass (Teams)
- AWS Secrets Manager
- HashiCorp Vault
- Azure Key Vault

---

### Pitfall 5: Not Rotating Compromised Keys

**Problem**:
```
❌ DANGER - "Key was exposed but it's fine, I deleted the commit"
# Git history still contains the key!
# Anyone with a clone has the old history
```

**Solution**:
```
✅ CORRECT - Immediate rotation workflow
1. Generate new key
2. Update production IMMEDIATELY
3. Update .env files
4. Restart services
5. Notify team
6. Document incident
```

---

## Security Checklist

### Development Setup
- [ ] `.env` file created (not committed)
- [ ] `.env.example` template committed (placeholders only)
- [ ] All API keys loaded from environment variables
- [ ] No secrets hardcoded in code
- [ ] Pre-commit hooks installed for secret detection

### Production Deployment
- [ ] `DEBUG=False` in production environment
- [ ] `SECRET_KEY` set to unique 50+ character value
- [ ] All API keys set in environment (not in code)
- [ ] `.gitignore` excludes all secret files
- [ ] Secret rotation schedule established (quarterly)

### GitIgnore Configuration
- [ ] `.env` and `.env.local` in .gitignore
- [ ] `*.key`, `*.pem` in .gitignore
- [ ] `secrets/` directory in .gitignore
- [ ] `CLAUDE.md` in .gitignore (local dev context)
- [ ] Service account JSONs in .gitignore

### SECRET_KEY Validation
- [ ] Production fails loudly if SECRET_KEY missing
- [ ] Insecure patterns rejected (django-insecure, change-me, etc.)
- [ ] Minimum length enforced (50 characters)
- [ ] Development default clearly marked as insecure

### API Key Management
- [ ] All external API keys in environment variables
- [ ] Rate limits documented for each service
- [ ] Fallback providers configured (Plant.id + PlantNet)
- [ ] Key rotation procedures documented

### Secret Detection
- [ ] Pre-commit hooks configured
- [ ] detect-secrets baseline created
- [ ] Regex patterns for all API keys documented
- [ ] Regular secret scanning scheduled

---

## Related Patterns

- **Authentication**: See `authentication.md` (JWT secret usage)
- **CSRF Protection**: See `csrf-protection.md` (CSRF_COOKIE_SECURE settings)
- **Input Validation**: See `input-validation.md` (validate env var inputs)
- **File Upload**: See `file-upload.md` (upload path security)

---

**Last Reviewed**: November 13, 2025
**Pattern Count**: 20 secret management patterns
**Status**: ✅ Production-validated
**OWASP**: A07:2021 – Identification and Authentication Failures

