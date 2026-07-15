# Input Validation & Sanitization Patterns

**Last Updated**: 2026-07-14 (SQL wildcard-escaping correction — see top of
"SQL Wildcard Escaping (Backend)")
**Consolidated From**:

- `apps/core/utils/query_sanitization.py` (SQL wildcard escaping)
- `apps/search/migrations/0003_simple_search_vectors.py` (SQL injection prevention)
- `web/src/utils/sanitize.ts` (XSS prevention)
- `web/src/utils/validation.ts` (form validation)
- `SECURITY_PATTERNS_CODIFIED.md` (SQL wildcard patterns)
- `todos/completed/012-completed-p0-sql-injection-migration.md` (migration security)

**Status**: ✅ Production-Tested

---

## Table of Contents

1. [SQL Wildcard Escaping (Backend)](#sql-wildcard-escaping-backend)
2. [SQL Injection Prevention in Migrations](#sql-injection-prevention-in-migrations)
3. [XSS Prevention (Frontend)](#xss-prevention-frontend)
4. [Form Input Validation (Frontend)](#form-input-validation-frontend)
5. [Search Query Sanitization (Full-Stack)](#search-query-sanitization-full-stack)
6. [Testing Input Validation](#testing-input-validation)
7. [Common Pitfalls](#common-pitfalls)

---

## SQL Wildcard Escaping (Backend)

> **⚠️ Correction (2026-07-14, todo 253 slice 4 review)**: Django's ORM
> **already auto-escapes** `%`, `_`, and `\` for `contains`/`icontains`/
> `startswith`/`istartswith`/`endswith`/`iendswith` — verified by reading
> `PatternLookup.process_rhs()` and `BaseDatabaseOperations.
> prep_for_like_query()` directly (confirmed PostgreSQL does not override
> it). Calling `escape_search_query()` and THEN passing the result into one
> of these six lookups **double-escapes and breaks real matches** — e.g.
> `escape_search_query("dave_")` → `"dave\_"`; the ORM auto-escapes that
> AGAIN into a pattern that requires a literal backslash in the matched
> text, so `username__istartswith="dave\_"` no longer matches the real
> username `"dave_1"`. This is not theoretical — it reproduces via a direct
> `.query` introspection test and was caught by a failing test this
> session. `escape_search_query()` is only correct for lookups that DON'T
> go through `PatternLookup` (raw SQL, `.extra()`, a custom `Lookup`
> subclass) — **verify which case you're in before calling it**; do not
> assume every `__icontains`/`__istartswith` call site needs it. See
> `docs/rules/security.md` and `docs/rules/database.md`.
>
> **Every `escape_search_query()` call site in this codebase as of
> 2026-07-14 pairs it with `__icontains` and is therefore suspected
> double-escaped** (`apps/blog/admin_views.py`, `apps/blog/api_views.py`,
> `apps/blog/views.py`, `apps/blog/api/viewsets.py`,
> `apps/plant_identification/views.py`,
> `apps/plant_identification/api/endpoints.py`) — not verified/fixed as
> part of this correction; each site needs its own audit, since this is a
> silent-failure bug (empty result set, not an error) that a smoke test
> without a `%`/`_`-containing fixture would never catch.

### Pattern: Escape SQL Wildcards in Django ORM

**Problem**: Django ORM's `icontains`, `istartswith`, and `iendswith` use PostgreSQL's `ILIKE` operator, which treats `%` and `_` as wildcards. User input like `"test%"` would match `"test"`, `"testing"`, `"test123"`, etc., causing unintended data access.

**Location**: `backend/apps/core/utils/query_sanitization.py`

**SQL Wildcards**:

- `%` - Matches zero or more characters
- `_` - Matches exactly one character

**Correct Implementation**:

```python
from apps.core.utils.query_sanitization import escape_search_query

# User search input
query = request.query_params.get('q', '').strip()

# Sanitize before using in Django ORM
safe_query = escape_search_query(query)

# Now safe to use in icontains queries
results = Thread.objects.filter(title__icontains=safe_query)
```

**Utility Function Implementation**:

```python
def escape_search_query(query: str) -> str:
    """
    Escape SQL wildcard characters in search queries.

    Prevents unintended pattern matching from user input containing SQL wildcard
    characters that are interpreted by Django ORM's icontains, istartswith, and
    iendswith operations when using PostgreSQL's ILIKE operator.

    SQL Wildcards:
        % - Matches zero or more characters
        _ - Matches exactly one character

    Without escaping, user input like "test%" would match "test", "testing",
    "test123", etc., which may not be the intended behavior.

    Args:
        query: User-provided search query string

    Returns:
        Sanitized query with escaped wildcards

    Examples:
        >>> escape_search_query("test%data")
        'test\\%data'
        >>> escape_search_query("user_name")
        'user\\_name'
        >>> escape_search_query("normal text")
        'normal text'
        >>> escape_search_query("test%_both")
        'test\\%\\_both'

    Note:
        This function only escapes SQL wildcards. It does not protect against
        SQL injection (Django ORM handles that). This is specifically for
        preventing unintended pattern matching in ILIKE queries.
    """
    if not query:
        return query

    # Escape % (matches any characters)
    sanitized = query.replace('%', r'\%')

    # Escape _ (matches single character)
    sanitized = sanitized.replace('_', r'\_')

    return sanitized


def escape_search_query_optional(query: Optional[str]) -> Optional[str]:
    """
    Escape SQL wildcard characters with None-safe handling.

    Convenience wrapper around escape_search_query() that handles None values.

    Args:
        query: User-provided search query string or None

    Returns:
        Sanitized query with escaped wildcards, or None if input was None

    Examples:
        >>> escape_search_query_optional("test%")
        'test\\%'
        >>> escape_search_query_optional(None)
        None
        >>> escape_search_query_optional("")
        ''
    """
    if query is None:
        return None

    return escape_search_query(query)
```

---

### Pattern: Forum Thread Search with Multiple Fields

**Location**: historical example — the machina-based `apps/forum/` this path
referenced was retired (PR #362); current forum search lives in
`backend/packages/wagtail_forum/wagtail_forum/api/views.py::SearchView`.

**Implementation** (escaping removed — `icontains` already auto-escapes,
see the correction at the top of this document):

```python
from django.db.models import Q

class ThreadViewSet(viewsets.ModelViewSet):
    @action(detail=False, methods=['GET'])
    def search(self, request):
        """
        Search threads by title and author.

        Query Parameters:
            - q: Search query (searches title)
            - author: Author username filter
            - category: Category slug filter
        """
        queryset = self.get_queryset()

        # Search by title
        query = request.query_params.get('q', '').strip()
        if query:
            queryset = queryset.filter(Q(title__icontains=query))

        # Filter by author username
        author_username = request.query_params.get('author', '').strip()
        if author_username:
            queryset = queryset.filter(Q(author__username__icontains=author_username))

        # Filter by category
        category_slug = request.query_params.get('category', '').strip()
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)

        # Paginate results
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)
```

**Why This Matters**:

- User searches for `"50% off"` → Should match exactly `"50% off"`, NOT `"50 off"`, `"50x off"`, etc.
- User searches for `"C++"` → Should match exactly `"C++"`, NOT any string containing `"C"`
- User searches for `"test_file.txt"` → Should match exactly `"test_file.txt"`, NOT `"test-file.txt"` or `"testXfile.txt"`

---

## SQL Injection Prevention in Migrations

### Pattern: psycopg2.sql.Identifier for Dynamic Table Names

**Problem**: F-strings in raw SQL queries bypass Django ORM's SQL injection protection. Even in migrations where table names are hardcoded, using string interpolation is a vulnerability if the code is ever modified to accept dynamic input.

**Issue**: Issue #012 (November 11, 2025)

**Location**: `backend/apps/search/migrations/0003_simple_search_vectors.py`

**❌ VULNERABLE - Never use f-strings for table/column names:**

```python
def add_search_vectors(apps, schema_editor):
    with connection.cursor() as cursor:
        for table in tables_to_modify:
            # ❌ SQL injection risk - f-string bypasses ORM protection
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN ...")
```

**✅ SECURE - Use psycopg2.sql.Identifier + Whitelist Validation:**

```python
from psycopg2 import sql
from django.db import migrations, connection

# Whitelist of allowed tables (defense in depth)
ALLOWED_TABLES = {
    'machina_forum_conversation_topic',
    'machina_forum_conversation_post',
    'plant_identification_plantspecies',
    'plant_identification_plantdiseasedatabase',
    'blog_blogpostpage'
}


def add_simple_search_vectors(apps, schema_editor):
    """Add search vector fields only, without initial data."""
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
            # Defense in depth: validate against whitelist
            if table not in ALLOWED_TABLES:
                raise ValueError(f"[SECURITY] Table not in whitelist: {table}")

            # Check if table exists
            cursor.execute(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %s)",
                [table]
            )
            if cursor.fetchone()[0]:
                try:
                    # ✅ SAFE - Use sql.Identifier for proper SQL escaping
                    cursor.execute(
                        sql.SQL("ALTER TABLE {} ADD COLUMN IF NOT EXISTS search_vector tsvector;").format(
                            sql.Identifier(table)
                        )
                    )

                    # Create GIN index for full-text search
                    index_name = f"idx_{table.split('_')[-1]}_search_vector"
                    cursor.execute(
                        sql.SQL("CREATE INDEX IF NOT EXISTS {} ON {} USING gin(search_vector);").format(
                            sql.Identifier(index_name),
                            sql.Identifier(table)
                        )
                    )
                except Exception as e:
                    print(f"Skipping {table}: {e}")
```

---

### Pattern: Defense in Depth - Both sql.Identifier AND Whitelist

**Why Both?**:

1. **`sql.Identifier()`** - Prevents SQL injection by properly quoting and escaping identifiers
2. **Whitelist Validation** - Fails loudly if table list is modified incorrectly, defense against logic errors

**Anti-Pattern** ❌:

```python
# Only using sql.Identifier without whitelist
cursor.execute(
    sql.SQL("ALTER TABLE {} ADD COLUMN ...").format(
        sql.Identifier(table)  # Safe from injection, but no validation
    )
)
```

**Correct Pattern** ✅:

```python
# Both sql.Identifier AND whitelist validation
if table not in ALLOWED_TABLES:
    raise ValueError(f"[SECURITY] Table not in whitelist: {table}")

cursor.execute(
    sql.SQL("ALTER TABLE {} ADD COLUMN ...").format(
        sql.Identifier(table)  # Proper escaping
    )
)
```

---

### Pattern: Rollback Migration Security

**Location**: `apps/search/migrations/0003_simple_search_vectors.py:62-95`

**Rollback functions must use the SAME security patterns:**

```python
def remove_simple_search_vectors(apps, schema_editor):
    """Remove search vector fields."""
    if connection.vendor != 'postgresql':
        return

    with connection.cursor() as cursor:
        tables_to_modify = [
            'machina_forum_conversation_topic',
            'machina_forum_conversation_post',
            'plant_identification_plantspecies',
            'plant_identification_plantdiseasedatabase',
            'blog_blogpostpage'
        ]

        for table in tables_to_modify:
            # ✅ REQUIRED: Whitelist validation in rollback too
            if table not in ALLOWED_TABLES:
                raise ValueError(f"[SECURITY] Table not in whitelist: {table}")

            try:
                # ✅ SAFE - sql.Identifier in DROP operations
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
```

---

## XSS Prevention (Frontend)

### Pattern: DOMPurify Sanitization Presets

**Problem**: User-generated content or untrusted HTML can execute malicious JavaScript, steal cookies, redirect users, or modify the DOM.

**Location**: `web/src/utils/sanitize.ts`

**Sanitization Strategy**:

- **Client-side**: Defense-in-depth using DOMPurify (prevents XSS if backend fails)
- **Server-side**: Primary defense (validate and sanitize all user input)

---

### Pattern: Preset-Based Sanitization

**Why Presets?**

- **Consistency**: Same security policies across all components
- **Maintainability**: Update one preset, all usages benefit
- **Least Privilege**: Use most restrictive preset that meets needs

**Available Presets**:

```typescript
export const SANITIZE_PRESETS = {
  // MINIMAL: Only basic inline formatting
  // Use for: Simple text excerpts, user comments
  MINIMAL: {
    ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'u'],
    ALLOWED_ATTR: [],
  },

  // BASIC: Basic formatting + links
  // Use for: Blog card excerpts, short descriptions
  BASIC: {
    ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'u', 'a'],
    ALLOWED_ATTR: ['href', 'target', 'rel'],
  },

  // STANDARD: Rich text formatting
  // Use for: Blog introductions, user-generated content
  STANDARD: {
    ALLOWED_TAGS: [
      'p', 'br', 'strong', 'em', 'u', 'a',
      'ul', 'ol', 'li', 'h2', 'h3', 'h4', 'blockquote',
    ],
    ALLOWED_ATTR: ['href', 'target', 'rel', 'class'],
  },

  // FULL: All safe content blocks
  // Use for: Full blog posts, documentation
  FULL: {
    ALLOWED_TAGS: [
      'p', 'br', 'strong', 'em', 'u', 'a',
      'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4',
      'blockquote', 'code', 'pre', 'img',
    ],
    ALLOWED_ATTR: ['href', 'target', 'rel', 'class', 'src', 'alt', 'title'],
  },

  // FORUM: Rich forum posts with mentions, code blocks
  // Use for: Forum posts, thread content
  FORUM: {
    ALLOWED_TAGS: [
      'p', 'br', 'strong', 'em', 'u', 'a',
      'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
      'blockquote', 'code', 'pre', 'img', 'span', 'div',
    ],
    ALLOWED_ATTR: [
      'href', 'target', 'rel', 'class', 'src', 'alt', 'title',
      'data-mention', 'data-mention-id',
    ],
    ALLOWED_CLASSES: {
      span: ['mention'],
      code: ['language-*'],
      div: ['code-block'],
    },
    ALLOW_DATA_ATTR: false,
  },
};
```

---

### Pattern: Sanitize HTML Content

**Function**: `sanitizeHtml(html, options?)`

**Usage Examples**:

```typescript
import { sanitizeHtml, SANITIZE_PRESETS } from '../utils/sanitize';

// Using preset (recommended)
const safeExcerpt = sanitizeHtml(post.excerpt, SANITIZE_PRESETS.BASIC);

// Using default (STANDARD preset)
const safeIntro = sanitizeHtml(post.introduction);

// Custom config (rare)
const safeContent = sanitizeHtml(content, {
  ALLOWED_TAGS: ['p', 'br', 'strong'],
  ALLOWED_ATTR: []
});
```

**React Integration**:

```typescript
import { createSafeMarkup, SANITIZE_PRESETS } from '../utils/sanitize';

// For dangerouslySetInnerHTML
function BlogCard({ post }) {
  return (
    <div
      dangerouslySetInnerHTML={createSafeMarkup(
        post.introduction,
        SANITIZE_PRESETS.BASIC
      )}
    />
  );
}
```

---

### Pattern: Strip All HTML

**Function**: `stripHtml(html)`

**Use Cases**:

- Search indexing (plain text only)
- Meta descriptions (no HTML in SEO tags)
- Form inputs (email, username, etc.)
- Excerpts where HTML is not needed

**Implementation**:

```typescript
import { stripHtml } from '../utils/sanitize';

// Extract plain text from rich content
const plainText = stripHtml('<p>Hello <strong>world</strong>!</p>');
// Returns: "Hello world!"

// Meta description (no HTML)
const metaDescription = stripHtml(post.introduction).substring(0, 160);

// Search indexing
const searchableText = stripHtml(post.content);
```

---

### Pattern: Sanitize Form Inputs

**Function**: `sanitizeInput(input)`

**Use Cases**:

- Email fields
- Username/name fields
- Any text input where HTML is not expected

**Implementation**:

```typescript
import { sanitizeInput } from '../utils/sanitize';

function handleSubmit(formData) {
  const cleanedData = {
    email: sanitizeInput(formData.email),
    username: sanitizeInput(formData.username),
    bio: sanitizeInput(formData.bio),
  };

  // Send to API
  await api.updateProfile(cleanedData);
}
```

**Why Strip HTML from Form Inputs?**

- Prevents XSS if backend doesn't validate
- Users should not enter HTML in email/username fields
- Better UX (no accidental HTML tags in display names)

---

### Pattern: Check for XSS Attempts

**Function**: `isSafeHtml(html)`

**Use Cases**:

- Pre-validation before sanitization
- Logging suspicious content
- Security monitoring

**Implementation**:

```typescript
import { isSafeHtml, sanitizeHtml } from '../utils/sanitize';

function processUserContent(content) {
  // Check for dangerous patterns
  if (!isSafeHtml(content)) {
    logger.warn('Suspicious content detected', {
      contentLength: content.length,
      userId: currentUser.id,
    });
    // Still sanitize (defense in depth)
  }

  return sanitizeHtml(content, SANITIZE_PRESETS.FORUM);
}
```

**Detected Patterns**:

- `<script>` tags
- `javascript:` URLs
- `vbscript:` URLs
- `data:text/html` URLs
- Event handlers (`onclick`, `onerror`, etc.)
- `<iframe>` tags
- `eval()` calls

---

## Form Input Validation (Frontend)

### Pattern: Validate Slugs (Path Traversal Prevention)

**Location**: `web/src/utils/validation.ts`

**Security Checks**:

1. Type and length validation
2. Path traversal prevention (`..`, `/`, `\`)
3. Suspicious pattern detection (`---`, `___`)
4. Format validation (alphanumeric, hyphens, underscores only)

**Implementation**:

```typescript
export function validateSlug(slug: unknown): string {
  // Null/undefined/empty check
  if (!slug || typeof slug !== 'string' || slug.trim() === '') {
    throw new Error('Slug is required and must be a string');
  }

  // Length check
  if (slug.length > 200) {
    throw new Error('Slug is too long (maximum 200 characters)');
  }

  // Path traversal check
  if (slug.includes('..') || slug.includes('/') || slug.includes('\\')) {
    throw new Error('Invalid slug: path traversal patterns are not allowed');
  }

  // Suspicious pattern check (repeated delimiters)
  if (/---/.test(slug) || /___/.test(slug)) {
    throw new Error('Invalid slug: suspicious pattern detected');
  }

  // Format check (only alphanumeric, hyphens, underscores)
  if (!/^[a-zA-Z0-9_-]+$/.test(slug)) {
    throw new Error('Invalid slug format');
  }

  return slug;
}
```

**Usage**:

```typescript
import { validateSlug } from '../utils/validation';

function BlogDetailPage() {
  const { slug } = useParams();

  try {
    const safeSlug = validateSlug(slug);
    // Use safeSlug in API call
    const post = await api.getPost(safeSlug);
  } catch (error) {
    // Handle validation error
    navigate('/404');
  }
}
```

---

### Pattern: Validate UUID Tokens

**Security Checks**:

1. Type and empty validation
2. UUID v4 format validation (strict regex)

**Implementation**:

```typescript
export function validateToken(token: unknown): string {
  // Null/undefined/empty check
  if (!token || typeof token !== 'string' || token.trim() === '') {
    throw new Error('Token is required and must be a string');
  }

  // UUID v4 format check
  const uuidV4Regex = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
  if (!uuidV4Regex.test(token)) {
    throw new Error('Invalid token format: must be a valid UUID v4');
  }

  return token;
}
```

**Usage**:

```typescript
import { validateToken } from '../utils/validation';

function usePasswordReset() {
  const { token } = useParams();

  try {
    const safeToken = validateToken(token);
    // Safe to use in API
    await api.resetPassword(safeToken, newPassword);
  } catch (error) {
    setError('Invalid or expired reset link');
  }
}
```

---

### Pattern: Validate Content Types (Wagtail)

**Security Checks**:

1. Type and length validation
2. Path traversal prevention
3. Format validation (`app.Model` pattern)

**Implementation**:

```typescript
export function validateContentType(contentType: unknown): string {
  // Null/undefined/empty check
  if (!contentType || typeof contentType !== 'string' || contentType.trim() === '') {
    throw new Error('Content type is required and must be a string');
  }

  // Length check
  if (contentType.length > 100) {
    throw new Error('Content type is too long (maximum 100 characters)');
  }

  // Path traversal check
  if (contentType.includes('..') || contentType.includes('/') || contentType.includes('\\')) {
    throw new Error('Invalid content type: path traversal patterns are not allowed');
  }

  // Format check (app.Model format - alphanumeric, underscores, and dot)
  if (!/^[a-zA-Z0-9_]+\.[a-zA-Z0-9_]+$/.test(contentType)) {
    if (!contentType.includes('.')) {
      throw new Error('Invalid content type format: must be in app.model format');
    }
    throw new Error('Invalid content type format');
  }

  return contentType;
}
```

---

## Search Query Sanitization (Full-Stack)

### Pattern: Frontend Search Query Sanitization

**Location**: `web/src/utils/validation.ts`

**Function**: `sanitizeSearchQuery(query)`

**Sanitization Steps**:

1. Type validation (must be string)
2. Trim whitespace
3. Remove null bytes (`\x00`) and control characters
4. Enforce max length (200 characters)

**Implementation**:

```typescript
export function sanitizeSearchQuery(query: unknown): string {
  // Type check
  if (!query || typeof query !== 'string') {
    return '';
  }

  // Trim whitespace
  let sanitized = query.trim();

  // Remove null bytes and control characters (ASCII 0-31, 127)
  sanitized = sanitized.replace(/[\x00-\x1F\x7F]/g, '');

  // Enforce max length
  if (sanitized.length > 200) {
    sanitized = sanitized.substring(0, 200);
  }

  return sanitized;
}
```

**Why Not Strip Special Characters?**

- Users may search for `"50% off"`, `"C++"`, `"test@example.com"` legitimately
- Backend handles SQL wildcard escaping separately
- Frontend sanitization focuses on: null bytes, control characters, length

**Usage**:

```typescript
import { sanitizeSearchQuery } from '../utils/validation';

function SearchBar() {
  const [query, setQuery] = useState('');

  const handleSearch = async () => {
    // Sanitize before sending to backend
    const safeQuery = sanitizeSearchQuery(query);

    if (!safeQuery) {
      return; // Don't search empty queries
    }

    const results = await api.search(safeQuery);
    setResults(results);
  };

  return (
    <input
      type="text"
      value={query}
      onChange={(e) => setQuery(e.target.value)}
      onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
    />
  );
}
```

---

### Pattern: Backend Search Query Sanitization

**Location**: `backend/apps/core/utils/query_sanitization.py` (escaping
utility — see the top-of-document correction for when it's actually needed)

**Backend receives the frontend's sanitized query; `icontains` handles
wildcard-escaping itself:**

```python
def search_threads(request):
    # Frontend already sanitized (removed null bytes, trimmed, limited length)
    query = request.query_params.get('q', '').strip()

    # No escape_search_query() call — Django's icontains already
    # auto-escapes %/_/\ (PatternLookup.process_rhs); calling it here would
    # double-escape and silently drop real matches.
    threads = Thread.objects.filter(title__icontains=query)

    return Response(ThreadSerializer(threads, many=True).data)
```

---

## Testing Input Validation

### Pattern: Backend SQL Wildcard Escaping Tests

**Location**: `backend/apps/core/tests/test_query_sanitization.py`

**Test Cases**:

```python
from apps.core.utils.query_sanitization import escape_search_query

class QuerySanitizationTestCase(TestCase):
    def test_escape_percent_wildcard(self):
        """% should be escaped to prevent matching any characters."""
        result = escape_search_query("test%")
        self.assertEqual(result, r"test\%")

    def test_escape_underscore_wildcard(self):
        """_ should be escaped to prevent matching single character."""
        result = escape_search_query("test_name")
        self.assertEqual(result, r"test\_name")

    def test_escape_both_wildcards(self):
        """Both % and _ should be escaped."""
        result = escape_search_query("test%_data")
        self.assertEqual(result, r"test\%\_data")

    def test_no_escape_normal_text(self):
        """Normal text should pass through unchanged."""
        result = escape_search_query("normal text")
        self.assertEqual(result, "normal text")

    def test_empty_string(self):
        """Empty string should remain empty."""
        result = escape_search_query("")
        self.assertEqual(result, "")

    def test_special_characters_preserved(self):
        """Other special characters (not wildcards) should be preserved."""
        result = escape_search_query("test@email.com")
        self.assertEqual(result, "test@email.com")

        result = escape_search_query("test-value")
        self.assertEqual(result, "test-value")

        result = escape_search_query("test's value")
        self.assertEqual(result, "test's value")

    def test_unicode_characters(self):
        """Unicode characters should be preserved."""
        result = escape_search_query("café%")
        self.assertEqual(result, r"café\%")

        result = escape_search_query("测试_data")
        self.assertEqual(result, r"测试\_data")
```

---

### Pattern: Frontend XSS Prevention Tests

**Location**: `web/src/utils/sanitize.test.ts`

**Test Cases**:

```typescript
import { sanitizeHtml, stripHtml, isSafeHtml, SANITIZE_PRESETS } from './sanitize';

describe('XSS attack vectors', () => {
  it('should prevent XSS via img onerror', () => {
    const html = '<img src="x" onerror="alert(1)" />';
    const result = sanitizeHtml(html);

    // onerror handler should be removed
    expect(result).not.toContain('onerror');
    expect(result).not.toContain('alert');
  });

  it('should prevent XSS via SVG', () => {
    const html = '<svg onload="alert(1)"></svg>';
    const result = sanitizeHtml(html);

    // SVG not in ALLOWED_TAGS, entire tag removed
    expect(result).not.toContain('svg');
    expect(result).not.toContain('alert');
  });

  it('should prevent XSS via form action', () => {
    const html = '<form action="javascript:alert(1)"><input type="submit" /></form>';
    const result = sanitizeHtml(html);

    // Form tag not allowed
    expect(result).not.toContain('form');
    expect(result).not.toContain('javascript:');
  });

  it('should prevent XSS via meta refresh', () => {
    const html = '<meta http-equiv="refresh" content="0;url=javascript:alert(1)" />';
    const result = sanitizeHtml(html);

    // Meta tag not allowed
    expect(result).not.toContain('meta');
    expect(result).not.toContain('javascript:');
  });

  it('should prevent XSS via object/embed', () => {
    const html = '<object data="javascript:alert(1)"></object>';
    const result = sanitizeHtml(html);

    // Object tag not allowed
    expect(result).not.toContain('object');
    expect(result).not.toContain('javascript:');
  });
});
```

---

### Pattern: Frontend Form Validation Tests

**Location**: `web/src/utils/validation.test.ts`

**Test Cases**:

```typescript
import { validateSlug, validateToken, sanitizeSearchQuery } from './validation';

describe('validateSlug', () => {
  it('should reject XSS attempts', () => {
    expect(() => validateSlug('<script>alert(1)</script>')).toThrow('Invalid slug format');
    expect(() => validateSlug('test<img src=x>')).toThrow('Invalid slug format');
  });

  it('should reject path traversal attempts', () => {
    expect(() => validateSlug('../../../etc/passwd')).toThrow('path traversal');
    expect(() => validateSlug('test/../admin')).toThrow('path traversal');
    expect(() => validateSlug('test/../../secret')).toThrow('path traversal');
  });

  it('should accept valid slugs', () => {
    expect(validateSlug('my-blog-post')).toBe('my-blog-post');
    expect(validateSlug('category_name')).toBe('category_name');
    expect(validateSlug('post-123')).toBe('post-123');
  });
});

describe('validateToken', () => {
  it('should accept valid UUID v4', () => {
    const validToken = '123e4567-e89b-42d3-a456-426614174000';
    expect(validateToken(validToken)).toBe(validToken);
  });

  it('should reject invalid UUID formats', () => {
    expect(() => validateToken('not-a-uuid')).toThrow('Invalid token format');
    expect(() => validateToken('123e4567-e89b-12d3-a456-426614174000')).toThrow('Invalid token format'); // Not v4 (wrong version digit)
  });
});

describe('sanitizeSearchQuery', () => {
  it('should remove null bytes', () => {
    expect(sanitizeSearchQuery('hello\x00world')).toBe('helloworld');
    expect(sanitizeSearchQuery('test\x01query')).toBe('testquery');
  });

  it('should trim whitespace', () => {
    expect(sanitizeSearchQuery('  hello world  ')).toBe('hello world');
    expect(sanitizeSearchQuery('\thello\t')).toBe('hello');
  });

  it('should enforce max length', () => {
    const longQuery = 'a'.repeat(300);
    const result = sanitizeSearchQuery(longQuery);
    expect(result.length).toBe(200);
  });

  it('should preserve special characters', () => {
    expect(sanitizeSearchQuery('50%')).toBe('50%');
    expect(sanitizeSearchQuery('C++')).toBe('C++');
    expect(sanitizeSearchQuery('test@example.com')).toBe('test@example.com');
  });
});
```

---

## Common Pitfalls

### Pitfall 1: Forgetting to Escape SQL Wildcards

> **Superseded (2026-07-14)** — see the correction at the top of "SQL
> Wildcard Escaping (Backend)" above. `Thread.objects.filter(title__icontains=…)`
> is one of the six `PatternLookup` lookups Django's ORM already
> auto-escapes; `escape_search_query()` ahead of it double-escapes and
> breaks matches containing a literal `%`/`_`. This pitfall's "BAD" example
> is still bad (unescaped wildcards act as wildcards), but its "GOOD"
> example below is now itself a pitfall — kept for historical context, not
> as guidance to copy.

**Problem**:

```python
# ❌ BAD - User input "test%" matches unintended results
query = request.query_params.get('q')
threads = Thread.objects.filter(title__icontains=query)
# User searches "50%" → matches "50 off", "50x discount", etc.
```

**Solution**:

```python
# ⚠️ Was "✅ GOOD" — now known to double-escape, see the correction above.
# Django's own icontains auto-escaping already does this; DON'T also call
# escape_search_query() here.
threads = Thread.objects.filter(title__icontains=query.strip())
# User searches "50%" → matches ONLY "50%"; searches "dave_" → matches
# ONLY "dave_", not "daveX" (Django's ILIKE-escaping handles both).
```

---

### Pitfall 2: Using F-Strings in Raw SQL

**Problem**:

```python
# ❌ VULNERABLE - SQL injection risk
table_name = get_table_name()
cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN ...")
```

**Solution**:

```python
# ✅ SECURE - Use sql.Identifier
from psycopg2 import sql

table_name = get_table_name()
cursor.execute(
    sql.SQL("ALTER TABLE {} ADD COLUMN ...").format(
        sql.Identifier(table_name)
    )
)
```

---

### Pitfall 3: Client-Side Sanitization Only

**Problem**:

```typescript
// ❌ INSECURE - Client-side only (can be bypassed)
const safeContent = sanitizeHtml(userInput);
await api.createPost(safeContent);
```

**Solution**:

```typescript
// ✅ DEFENSE IN DEPTH - Sanitize on both client and server
// Client-side (UX + defense-in-depth)
const safeContent = sanitizeHtml(userInput);

// Server-side (PRIMARY DEFENSE)
// Backend MUST also validate and sanitize!
await api.createPost(safeContent);
```

**Backend Must Validate**:

```python
from django.utils.html import strip_tags

def create_post(request):
    content = request.data.get('content')

    # Server-side sanitization (PRIMARY)
    safe_content = strip_tags(content)

    # Additional validation
    if len(safe_content) > 10000:
        return Response({'error': 'Content too long'}, status=400)

    post = Post.objects.create(content=safe_content)
    return Response(PostSerializer(post).data)
```

---

### Pitfall 4: Wrong DOMPurify Preset

**Problem**:

```typescript
// ❌ BAD - Using FULL preset for user comments (too permissive)
const safeComment = sanitizeHtml(userComment, SANITIZE_PRESETS.FULL);
// Allows images, code blocks, headers - overkill for comments
```

**Solution**:

```typescript
// ✅ GOOD - Use most restrictive preset that meets needs
const safeComment = sanitizeHtml(userComment, SANITIZE_PRESETS.MINIMAL);
// Only allows: p, br, strong, em, u (sufficient for comments)
```

**Preset Selection Guide**:

- User comments → `MINIMAL`
- Blog excerpts → `BASIC`
- Blog introductions → `STANDARD`
- Full blog posts → `FULL`
- Forum posts → `FORUM`

---

### Pitfall 5: Not Validating URL Parameters

**Problem**:

```typescript
// ❌ INSECURE - Using URL params directly
function BlogDetailPage() {
  const { slug } = useParams();

  // Direct use without validation - XSS/path traversal risk
  const post = await api.getPost(slug);
}
```

**Solution**:

```typescript
// ✅ SECURE - Validate before use
import { validateSlug } from '../utils/validation';

function BlogDetailPage() {
  const { slug } = useParams();

  try {
    const safeSlug = validateSlug(slug);
    const post = await api.getPost(safeSlug);
  } catch (error) {
    navigate('/404');
  }
}
```

---

### Pitfall 6: Assuming Django ORM Doesn't Escape SQL Wildcards

> **Rewritten (2026-07-14)** — this pitfall previously asserted the
> opposite of what's actually true; see the correction at the top of "SQL
> Wildcard Escaping (Backend)". Kept at this heading so old links/searches
> still land somewhere accurate.

**Problem**:

```python
# ❌ INCORRECT ASSUMPTION
# "Django ORM doesn't escape wildcards, I must call escape_search_query()
# myself before every icontains/istartswith/iendswith"
query = request.query_params.get('q')
safe_query = escape_search_query(query)
results = Model.objects.filter(field__icontains=safe_query)
# User searches "dave_1" (a literal username) → matches NOTHING, because
# escape_search_query() already escaped the "_", then Django's OWN
# icontains auto-escaping escaped it AGAIN — the resulting LIKE pattern
# now requires a literal backslash in the matched text that isn't there.
```

**Clarification** (verified 2026-07-14 by reading Django 6.0.7's
`django.db.models.lookups.PatternLookup.process_rhs()` and
`django.db.backends.base.operations.BaseDatabaseOperations.
prep_for_like_query()` directly — PostgreSQL does not override it):

- ✅ Django ORM **DOES** prevent SQL injection (parameterized queries)
- ✅ Django ORM **DOES** auto-escape `%`, `_`, and `\` for all six
  `contains`/`icontains`/`startswith`/`istartswith`/`endswith`/`iendswith`
  lookups — unconditionally, for any literal filter value
- ❌ Calling `escape_search_query()` before one of those six lookups does
  **NOT** add safety — it double-escapes and breaks matches on any query
  containing a literal `%`, `_`, or `\`

**Solution**:

```python
# ✅ CORRECT — no manual escaping needed for these six lookup types
query = request.query_params.get('q', '').strip()
results = Model.objects.filter(field__icontains=query)
# User searches "dave_1" → matches "dave_1" correctly; "test%" matches
# ONLY a literal "test%", not "testing"/"test123" — both handled by
# Django's own auto-escaping, no library call needed.
```

`escape_search_query()` is still correct for a lookup that bypasses
`PatternLookup` entirely — raw SQL, `.extra()`, a custom `Lookup`
subclass. Verify which case you're in before reaching for it.

---

### Pitfall 7: Reusing a Rendering-Oriented HTML Walker for a Second, Security-Sensitive Parser

**Problem** (todo 253 slice 4 review — @mention parsing): a sanitizer that
allows a tag's attributes (e.g. `nh3` allowing `href`/`title` on `<a>`,
`api/sanitize.py`) is safe FOR RENDERING — the browser only shows attribute
values if something explicitly reads and displays them. But a second
consumer that walks the same stored content for a DIFFERENT purpose (a
regex scanner, a keyword extractor, a mention resolver) can accidentally
treat attribute text as if it were reader-visible prose:

```python
# ❌ BAD — a walker built for spam heuristics (wants to see links/code
# as-is) reused for mention scanning (wants only what a reader sees)
text = " ".join(str(block.value) for block in post.body)
mentions = MENTION_RE.findall(text)
# A post containing <a href="https://x.com/@victim">click</a> resolves
# "victim" as a mention — invisible to any reader, since only "click" is
# ever displayed. Likewise a code block's raw source text, or any other
# block value not meant to be read as prose.
```

**Solution**: build the SECOND parser's own text extraction, scoped to
what its purpose actually needs — don't assume an existing walker's
scope generalizes:

```python
# ✅ GOOD — strip_tags() drops attribute VALUES along with the tag markup
# that carries them (they're part of the tag syntax, not a text node), so
# an href/title never survives; skip block types with no prose meaning
# (code, image) entirely.
from django.utils.html import strip_tags

parts = []
for raw in post.body.raw_data:
    value = raw.get("value")
    if isinstance(value, str):
        text = strip_tags(value).strip()
        if text:
            parts.append(text)
    # code (dict) / image (int) blocks: deliberately skipped — not prose.
mentions = MENTION_RE.findall(" ".join(parts))
```

Verified: `strip_tags('<a href="x/@victim" title="@evil">click</a>')` ==
`'click'` (both attributes gone), while a real link *label* like
`'<a href="…">@alice</a>'` still yields `'@alice'` — no false negative.

---

## Security Checklist

### Backend Input Validation

- [ ] `escape_search_query()` is called ONLY for lookups that bypass Django's
      `PatternLookup` (raw SQL, `.extra()`, a custom `Lookup`) — never stacked
      in front of `icontains`/`istartswith`/`iendswith`/their non-`i` variants,
      which already auto-escape and would double-escape (2026-07-14 correction)
- [ ] Raw SQL migrations use `psycopg2.sql.Identifier()` for dynamic identifiers
- [ ] Whitelist validation added for all raw SQL table/column names
- [ ] No f-strings or string concatenation in raw SQL
- [ ] Django ORM used for all user input queries (not raw SQL)

### Frontend Input Validation

- [ ] All HTML content sanitized with DOMPurify before rendering
- [ ] Most restrictive DOMPurify preset used for each use case
- [ ] URL parameters validated before use (slugs, tokens, content types)
- [ ] Form inputs stripped of HTML tags (email, username, etc.)
- [ ] Search queries sanitized (null bytes removed, length limited)
- [ ] Error messages from API sanitized before display

### Defense in Depth

- [ ] Client-side validation for UX (immediate feedback)
- [ ] Server-side validation as PRIMARY defense (never trust client)
- [ ] Input validation at multiple layers (frontend → API → database)
- [ ] Logging of suspicious input patterns for monitoring

### Testing Coverage

- [ ] SQL wildcard escaping tests (%, _, combinations)
- [ ] XSS prevention tests (script tags, event handlers, javascript: URLs)
- [ ] Path traversal tests (../, ..\, //, \\)
- [ ] Form validation tests (slugs, tokens, content types)
- [ ] Search query sanitization tests (null bytes, length, special chars)

---

## Related Patterns

- **File Upload Security**: See `file-upload.md` (4-layer validation)
- **CSRF Protection**: See `csrf-protection.md` (token handling)
- **Authentication**: See `authentication.md` (JWT validation)
- **Secret Management**: See `secret-management.md` (API keys, env vars)

---

**Last Reviewed**: 2026-05-06
**Pattern Count**: 17 input validation patterns
**Status**: ✅ Production-validated
**OWASP**: A03:2021 – Injection

---

## ICS Calendar Export — CRLF Injection Prevention

### Pattern: Sanitize User Strings Before Embedding in ICS f-strings

**Problem**: ICS (iCalendar) files use CRLF (`\r\n`) as a record separator. Embedding user-supplied strings (plant names, reminder types, descriptions) directly into an ICS f-string allows an attacker to inject arbitrary ICS fields or terminate the current field early, leading to calendar spoofing or data exfiltration via crafted calendar events.

**Vulnerable Code** ❌:

```python
def build_ics_event(plant_name, reminder_type, description):
    return (
        f"BEGIN:VEVENT\r\n"
        f"SUMMARY:{plant_name} — {reminder_type}\r\n"
        f"DESCRIPTION:{description}\r\n"
        f"END:VEVENT\r\n"
    )
```

An attacker can set `plant_name = "Cactus\r\nBEGIN:VEVENT\r\nSUMMARY:Injected event"` to insert a second synthetic calendar event.

**Correct Pattern** ✅:

```python
_ics_safe = lambda s: str(s).replace('\r', '').replace('\n', ' ')

def build_ics_event(plant_name, reminder_type, description):
    return (
        f"BEGIN:VEVENT\r\n"
        f"SUMMARY:{_ics_safe(plant_name)} — {_ics_safe(reminder_type)}\r\n"
        f"DESCRIPTION:{_ics_safe(description)}\r\n"
        f"END:VEVENT\r\n"
    )
```

**Rules**:

1. EVERY user-supplied value embedded in an ICS f-string MUST pass through `_ics_safe()`.
2. Strip both `\r` and `\n` — a lone `\r` is enough to break field boundaries on some parsers.
3. Apply to: SUMMARY, DESCRIPTION, LOCATION, COMMENT, and any custom properties.

---

## Integer Input Bounds Validation

### Pattern: Validate Integer Range for User-Supplied Numeric Parameters

**Problem**: User-supplied integers passed directly to service methods without type conversion and range checking can cause logic errors, excessive resource consumption, or DoS (e.g., snoozing a reminder for 100,000 hours).

**Vulnerable Code** ❌:

```python
snooze_hours = request.data.get('snooze_hours')  # Could be a string, float, negative, or huge
reminder.mark_snoozed(snooze_hours)  # ❌ No conversion or range check
```

**Correct Pattern** ✅:

```python
# constants.py
SNOOZE_HOURS_MIN = 1
SNOOZE_HOURS_MAX = 8760  # 365 days

# view
raw = request.data.get('snooze_hours')
try:
    snooze_hours = int(raw)
except (TypeError, ValueError):
    return Response({"error": "snooze_hours must be an integer"}, status=400)
if not (SNOOZE_HOURS_MIN <= snooze_hours <= SNOOZE_HOURS_MAX):
    return Response(
        {"error": f"snooze_hours must be between {SNOOZE_HOURS_MIN} and {SNOOZE_HOURS_MAX}"},
        status=400
    )
reminder.mark_snoozed(snooze_hours)
```

**Rules**:

1. Always call `int()` inside a `try/except` before using a user-supplied numeric value.
2. Define min/max bounds as named constants in `constants.py`.
3. Return HTTP 400 with a message naming both the field and the allowed range.
4. Apply to ALL numeric parameters: hours, counts, page sizes, limits, offsets.
