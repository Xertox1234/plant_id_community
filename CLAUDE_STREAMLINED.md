# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Last Major Update**: November 12, 2025 - P2 Issues Complete (#017, #018, #019)
- **Automatic JWT Token Refresh**: OWASP-compliant 15-minute tokens with 10-minute refresh
- **CSRF Protection**: Enforced on all auth endpoints including registration
- **TypeScript Migration**: 100% complete - 74 files, zero `any` types in StreamField

## Quick Reference

- **Port 8000** - Django backend + Wagtail CMS (`/cms/` admin)
- **Port 5174** - React web frontend
- **Port 6379** - Redis cache

## Essential Commands

### Backend (`/backend`)

```bash
source venv/bin/activate

# Development
python manage.py runserver
python manage.py migrate
python manage.py createsuperuser

# Testing
python manage.py test apps.{app_name} --keepdb
python manage.py test apps.{app_name}.tests.test_{module} --keepdb -v 2

# Cache & Redis
redis-cli ping
python manage.py warm_moderation_cache
```

### Web Frontend (`/web`)

```bash
# Development
npm run dev          # http://localhost:5174
npm run build        # Production build with type-check
npm run test         # Vitest (492 tests)
npm run test:e2e     # Playwright (107 tests)
```

### Flutter Mobile (`/plant_community_mobile`)

```bash
flutter run -d {ios|android|macos}
flutter test --coverage
flutter pub run build_runner build --delete-conflicting-outputs
```

## Architecture

**Multi-Platform Stack**:
- Backend: Django 5.2 + DRF + Wagtail 7.1.2 + PostgreSQL + Redis
- Web: React 19 + TypeScript + Vite + Tailwind CSS 4
- Mobile: Flutter 3.27 + Firebase (primary platform)

**Critical Paths**:
- `/backend/` - Active development (NOT `/existing_implementation/`)
- `/backend/apps/plant_identification/services/` - Business logic layer
- `/backend/apps/blog/` - Wagtail CMS + AI integration
- `/backend/apps/forum/` - Community forum with trust levels + spam detection
- `/web/src/` - React TypeScript frontend
- `/plant_community_mobile/lib/` - Flutter mobile app

## Critical Patterns

### 1. Constants Over Magic Numbers
ALL configuration in app-specific `constants.py` files:
```python
# ✅ CORRECT
from ..constants import MAX_ATTACHMENTS_PER_POST, CACHE_TIMEOUT_SPAM_CHECK

# ❌ WRONG
MAX_ATTACHMENTS = 6  # Never hardcode
```

Each app has its own constants file - NEVER hardcode values.

### 2. ViewSet Permission Pattern (CRITICAL - Issue #131)
```python
class MyViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_permissions(self):
        # Let custom actions use their own permission_classes
        if self.action in ['custom_action']:
            return super().get_permissions()  # ✅ Uses @action permissions

        if self.action in ['update', 'destroy']:
            return [IsAuthorOrModerator()]
        return [IsAuthenticatedOrReadOnly()]

    @action(detail=True, methods=['POST'], permission_classes=[CustomPermission])
    def custom_action(self, request, pk=None):
        pass  # CustomPermission is properly enforced
```

**Why**: `get_permissions()` is called for EVERY action. If not handled correctly, `@action` decorators are silently ignored.

### 3. File Upload Security (Phase 6 Pattern)
**REQUIRED validations** (defense in depth):
```python
from ..constants import ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMAGE_MIME_TYPES, MAX_ATTACHMENT_SIZE_BYTES

# 1. Extension check (prevents .php.jpg)
file_extension = image_file.name.split('.')[-1].lower()
if file_extension not in ALLOWED_IMAGE_EXTENSIONS:
    return Response({"error": "Invalid file type"}, status=400)

# 2. MIME type check (prevents content-type spoofing)
if image_file.content_type not in ALLOWED_IMAGE_MIME_TYPES:
    return Response({"error": "Invalid MIME type"}, status=400)

# 3. Size check
if image_file.size > MAX_ATTACHMENT_SIZE_BYTES:
    return Response({"error": "File too large"}, status=400)
```

### 4. Search Query Sanitization
```python
def escape_search_query(query: str) -> str:
    """Escape SQL wildcard characters in search queries."""
    return query.replace('%', r'\%').replace('_', r'\_')

# Usage
query = request.query_params.get('q', '').strip()
safe_query = escape_search_query(query)
qs = qs.filter(Q(title__icontains=safe_query))
```

### 5. React Performance - Timer Pattern
```javascript
// ✅ CORRECT - Use ref for timers (no memory leak, stable reference)
const debounceTimerRef = useRef(null);

const handleInput = useCallback((e) => {
  if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
  debounceTimerRef.current = setTimeout(() => { /* search */ }, 500);
}, []); // Stable - no dependencies

useEffect(() => {
  return () => {
    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
  };
}, []);

// ❌ WRONG - useState triggers re-render, causes memory leak
const [debounceTimer, setDebounceTimer] = useState(null);
```

### 6. Migration SQL Injection Prevention
```python
from psycopg2 import sql

ALLOWED_TABLES = {'machina_forum_conversation_topic', 'blog_blogpostpage'}

def add_columns(apps, schema_editor):
    with connection.cursor() as cursor:
        for table in tables_to_modify:
            # Defense in depth: validate against whitelist
            if table not in ALLOWED_TABLES:
                raise ValueError(f"[SECURITY] Table not in whitelist: {table}")

            # Use sql.Identifier for proper SQL escaping
            cursor.execute(
                sql.SQL("ALTER TABLE {} ADD COLUMN ...").format(
                    sql.Identifier(table)
                )
            )
```

### 7. Type Hints (Required)
```python
from typing import Optional, Dict, Any
from rest_framework.request import Request
from rest_framework.response import Response

def view_name(request: Request) -> Response:
    """Type hints REQUIRED for all views and service methods."""
    pass
```

### 8. Logging Standards
```python
logger.info("[CACHE] HIT for key {key} (instant response)")
logger.info("[PERF] Query completed in {duration:.2f}s")
logger.error("[ERROR] API failed: {error}")
logger.info("[CIRCUIT] Circuit breaker opened")
```

### 9. Performance Test Assertions (Issue #117)
```python
# ✅ CORRECT - Strict equality for known query counts
with self.assertNumQueries(1):
    response = self.client.get(url)
self.assertEqual(len(connection.queries), 1)  # Specific count

# ❌ WRONG - Lenient assertions allow regressions
self.assertLess(len(connection.queries), 10)  # Too vague
```

### 10. JWT Token Refresh (Issue #018 - OWASP Compliant)
```typescript
// Frontend: Automatic refresh every 10 minutes (before 15-minute expiry)
const TOKEN_REFRESH_INTERVAL = 10 * 60 * 1000;

useEffect(() => {
  if (!user) return;

  const timerId = window.setInterval(async () => {
    const success = await authService.refreshAccessToken();
    if (!success) {
      setUser(null); // Logout on failure
    }
  }, TOKEN_REFRESH_INTERVAL);

  return () => clearInterval(timerId);
}, [user]);
```

Backend: 15-minute tokens already configured in `settings.py`.

## Key Systems

### Trust Level System (Forum)
5-tier system managing permissions and rate limits:
- **NEW** (0): 10 posts/day, 3 threads/day, no images
- **BASIC** (1): 50 posts/day, 10 threads/day, images allowed
- **TRUSTED** (2): 100 posts/day, 25 threads/day
- **VETERAN** (3): Unlimited
- **EXPERT** (4): Unlimited + moderation powers

```python
from apps.forum.services.trust_level_service import TrustLevelService

TrustLevelService.check_daily_limit(user, 'posts')  # True/False
TrustLevelService.can_perform_action(user, 'can_upload_images')
info = TrustLevelService.get_trust_level_info(user)
```

### Spam Detection System
Multi-heuristic detection with weighted keyword scoring (≥50 points = spam):
- Duplicate Content (60 pts) - 85% similarity threshold
- Rapid Posting (55 pts) - <10s between posts
- Link Spam (50 pts) - Trust-based URL limits
- Keyword Spam (50 pts) - Weighted by risk (phishing: 30pts, financial: 20pts, commercial: 10pts)
- Pattern Detection (45 pts) - Caps ratio, punctuation abuse

```python
from apps.forum.services.spam_detection_service import SpamDetectionService

result = SpamDetectionService.is_spam(user, content, content_type='post')
# Returns: {'is_spam': bool, 'spam_score': int, 'reasons': [...], 'details': {...}}
```

### Wagtail AI Integration
AI-powered content generation for blog posts:
```python
# Backend: Generate with AI
from apps.blog.ai_integration import BlogAIIntegration

result = BlogAIIntegration.generate_blog_field(
    user=user,
    field_name='introduction',
    context={'title': 'Plant Care Guide'}
)
```

Admin UI: Access at `/cms/` with "Generate with AI" buttons.

## Security

### Environment-Aware Authentication
- **DEBUG=True**: Anonymous allowed, 10 req/hour
- **DEBUG=False**: Authentication required, 100 req/hour

### API Versioning
- URL: `/api/v1/plant-identification/identify/`
- Pattern: DRF NamespaceVersioning
- Legacy `/api/` maintained for backward compatibility

### Secret Key Validation (Production)
```python
# Must be 50+ characters, no insecure patterns
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

## TypeScript Standards

### Migration Status ✅ COMPLETE (Issue #134)
- 74 TypeScript files (46 `.tsx`, 28 `.ts`)
- Zero compilation errors
- Zero `any` types in production code

### Type Safety Patterns
```typescript
// Discriminated unions for Wagtail StreamField
export type StreamFieldBlock =
  | { type: 'heading'; value: string; id: string }
  | { type: 'quote'; value: { quote_text: string; attribution?: string }; id: string }
  | { type: 'plant_spotlight'; value: PlantSpotlightBlockValue; id: string };

// Type-safe narrowing
function renderBlock(block: StreamFieldBlock) {
  switch (block.type) {
    case 'heading':
      return <h2>{block.value}</h2>; // TypeScript knows value is string
    case 'quote':
      return <blockquote>{block.value.quote_text}</blockquote>; // TypeScript knows structure
  }
}
```

### React Router v7 Import Fix
```typescript
// ✅ CORRECT
import { useNavigate, useParams } from 'react-router-dom';

// ❌ WRONG - Will fail at runtime
import { useNavigate } from 'react-router';
```

## Documentation

**Pattern Documentation** (codified best practices):
- `AUTHENTICATION_PATTERNS.md` - React+Django auth (7 patterns)
- `PLANT_ID_PATTERNS_CODIFIED.md` - Plant ID API patterns
- `TRUST_LEVEL_PATTERNS_CODIFIED.md` - Trust level implementation (10 patterns)
- `SPAM_DETECTION_PATTERNS_CODIFIED.md` - Spam detection (7 patterns, A+ grade)
- `PERFORMANCE_TESTING_PATTERNS_CODIFIED.md` - Strict test assertions (Issue #117)
- `TYPESCRIPT_MIGRATION_PATTERNS_CODIFIED.md` - TypeScript patterns (7 comprehensive guides)

**Code Review Agents**:
- `.claude/agents/comprehensive-code-reviewer.md` - Full repo review (all 17 patterns)
- `.claude/agents/django-performance-reviewer.md` - N+1 query specialist
- `.claude/agents/wagtail-cms-orchestrator.md` - CMS content & API integration

## Common Issues

### Redis not running
```bash
brew install redis
brew services start redis
redis-cli ping  # Should return "PONG"
```

### PostgreSQL setup for tests
```bash
brew install postgresql@18
brew services start postgresql@18
createdb plant_community_test
psql plant_community_test -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"
```

### Migration Testing
If test database exists from before migration changes:
```bash
python manage.py test apps.forum --noinput  # Force fresh DB rebuild
```

## Deployment Checklist

**CRITICAL - Verify before production**:
1. `DEBUG=False` in environment variables
2. `SECRET_KEY` is production-grade (50+ chars)
3. `ALLOWED_HOSTS` configured with production domains
4. Plant.id API key is valid (50 chars)
5. Redis is running: `redis-cli ping`
6. Run cache warming: `python manage.py warm_moderation_cache`

**Plant.id API v3** (migrated Nov 6, 2025):
- Request format: Details in query parameters (not JSON body)
- Health assessment: Separate `/health_assessment` endpoint
- Response: Nested under `result.classification.suggestions`

**Security**: NEVER commit API keys. All keys in `backend/.env` (gitignored).
