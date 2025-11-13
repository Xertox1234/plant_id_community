# CSRF Protection Patterns

**Last Updated**: November 13, 2025
**Consolidated From**: `PLANT_SAVE_PATTERNS_CODIFIED.md` (CSRF sections)
**Status**: ✅ Production-Tested

---

## Table of Contents

1. [Django CSRF Configuration](#django-csrf-configuration)
2. [Fetch API CSRF Handling](#fetch-api-csrf-handling)
3. [React Frontend Integration](#react-frontend-integration)
4. [Testing CSRF Protection](#testing-csrf-protection)
5. [Common Pitfalls](#common-pitfalls)

---

## Django CSRF Configuration

### Pattern: Secure CSRF Cookie Settings

**Correct Configuration**:
```python
# backend/settings.py

# CSRF Cookie Configuration
CSRF_COOKIE_SECURE = not DEBUG          # HTTPS only in production
CSRF_COOKIE_HTTPONLY = True             # Prevent JavaScript access (XSS protection)
CSRF_COOKIE_SAMESITE = 'Lax'           # CSRF protection while allowing normal navigation
CSRF_COOKIE_AGE = 60 * 60 * 24 * 7     # 7 days
CSRF_COOKIE_NAME = 'csrftoken'         # Default name

# Trusted origins for cross-origin requests
CSRF_TRUSTED_ORIGINS = [
    'https://yourdomain.com',
    'https://www.yourdomain.com',
]

# CORS settings (must allow credentials)
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [
    'http://localhost:5174',           # Development frontend
    'https://yourdomain.com',          # Production frontend
]
```

**Why Each Setting Matters**:
- `CSRF_COOKIE_SECURE = True`: HTTPS-only prevents token interception
- `CSRF_COOKIE_HTTPONLY = True`: Prevents XSS attacks from stealing tokens
- `CSRF_COOKIE_SAMESITE = 'Lax'`: CSRF protection while allowing normal navigation
- `CORS_ALLOW_CREDENTIALS = True`: Required for `credentials: 'include'` in fetch

---

### Pattern: CSRF Endpoint for Token Fetching

**Backend Implementation**:
```python
# apps/users/views.py
from django.views.decorators.csrf import ensure_csrf_cookie
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

@api_view(['GET'])
@permission_classes([AllowAny])
@ensure_csrf_cookie
def csrf_token_view(request):
    """
    Get CSRF token endpoint.

    Sets csrftoken cookie that frontend must send as X-CSRFToken header.
    This is necessary because HttpOnly cookies can't be read by JavaScript.
    """
    return JsonResponse({'detail': 'CSRF cookie set'})

# urls.py
urlpatterns = [
    path('api/v1/users/csrf/', csrf_token_view, name='csrf-token'),
]
```

**Why This Is Needed**: HttpOnly cookies cannot be read by JavaScript. This endpoint sets the cookie, allowing the frontend to know a CSRF token exists (even though it can't read the value).

---

## Fetch API CSRF Handling

### Pattern: Complete CSRF Token Lifecycle

**Location**: `web/src/services/plantIdService.ts`

**Step 1: Cookie Extraction**
```typescript
/**
 * Get CSRF token from Django cookies
 * Django sets csrftoken cookie that must be sent as X-CSRFToken header
 */
function getCsrfToken(): string | null {
  const match = document.cookie.match(/csrftoken=([^;]+)/)
  return match ? match[1] : null
}
```

**Step 2: Token Fetching**
```typescript
/**
 * Fetch CSRF token from Django backend
 * This endpoint sets the csrftoken cookie
 */
async function fetchCsrfToken(): Promise<void> {
  try {
    await fetch(`${API_BASE_URL}/api/v1/users/csrf/`, {
      credentials: 'include',  // Required to receive Set-Cookie header
    })
  } catch (error) {
    console.error('[CSRF] Failed to fetch token:', error)
  }
}
```

**Step 3: Ensure Token Exists**
```typescript
/**
 * Ensure CSRF token exists before making authenticated requests
 */
async function ensureCsrfToken(): Promise<void> {
  if (!getCsrfToken()) {
    await fetchCsrfToken()
  }
}
```

**Step 4: Use Token in Requests**
```typescript
export const plantIdService = {
  saveToCollection: async (plantData: PlantData) => {
    // ✅ Step 1: Ensure token exists
    await ensureCsrfToken()
    const csrfToken = getCsrfToken()

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/plant-identification/plants/`,
        {
          method: 'POST',
          credentials: 'include',  // ✅ Send HttpOnly cookies
          headers: {
            'Content-Type': 'application/json',
            // ✅ Step 2: Inject CSRF token header
            ...(csrfToken && { 'X-CSRFToken': csrfToken }),
          },
          body: JSON.stringify(plantData),
        }
      )

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.error || 'Failed to save plant')
      }

      return response.json()
    } catch (error) {
      throw new Error('Failed to save plant to collection')
    }
  },
}
```

---

### Pattern: Why `credentials: 'include'` Is Required

**Anti-Pattern** ❌:
```javascript
// ❌ BAD - Cookies not sent, authentication fails
fetch('/api/v1/endpoint/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-CSRFToken': csrfToken,
  },
  // Missing credentials option - sessionid cookie not sent!
})
```

**Correct Pattern** ✅:
```javascript
// ✅ GOOD - HttpOnly cookies sent automatically
fetch('/api/v1/endpoint/', {
  method: 'POST',
  credentials: 'include',  // Sends sessionid, csrftoken cookies
  headers: {
    'Content-Type': 'application/json',
    'X-CSRFToken': csrfToken,
  },
})
```

**Why This Matters**:
1. **Session Authentication**: Django needs `sessionid` cookie to identify user
2. **CSRF Protection**: Django needs `csrftoken` cookie to validate against header
3. **HttpOnly Security**: Cookies marked HttpOnly cannot be accessed via JavaScript (XSS protection)

**The Flow**:
```
1. Django sets HttpOnly cookies: sessionid, csrftoken
2. fetch() with credentials: 'include' sends cookies automatically
3. Django middleware validates:
   - sessionid cookie → authenticates user
   - csrftoken cookie matches X-CSRFToken header → CSRF check passes
```

---

## React Frontend Integration

### Pattern: Centralized CSRF Service

**File**: `web/src/services/csrfService.ts`
```typescript
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

/**
 * Get CSRF token from Django cookies
 */
export function getCsrfToken(): string | null {
  const match = document.cookie.match(/csrftoken=([^;]+)/)
  return match ? match[1] : null
}

/**
 * Fetch CSRF token from Django backend
 */
export async function fetchCsrfToken(): Promise<void> {
  try {
    await fetch(`${API_BASE_URL}/api/v1/users/csrf/`, {
      credentials: 'include',
    })
  } catch (error) {
    console.error('[CSRF] Failed to fetch token:', error)
  }
}

/**
 * Ensure CSRF token exists before making authenticated requests
 */
export async function ensureCsrfToken(): Promise<void> {
  if (!getCsrfToken()) {
    await fetchCsrfToken()
  }
}

/**
 * Create fetch options with CSRF token and credentials
 */
export async function createAuthenticatedFetchOptions(
  method: string = 'GET',
  body?: any
): Promise<RequestInit> {
  await ensureCsrfToken()
  const csrfToken = getCsrfToken()

  return {
    method,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(csrfToken && { 'X-CSRFToken': csrfToken }),
    },
    ...(body && { body: JSON.stringify(body) }),
  }
}
```

**Usage in Services**:
```typescript
import { createAuthenticatedFetchOptions } from './csrfService'

export const apiService = {
  async createPost(postData) {
    const options = await createAuthenticatedFetchOptions('POST', postData)
    const response = await fetch(`${API_BASE_URL}/api/v1/forum/posts/`, options)
    return response.json()
  },

  async updatePost(postId, postData) {
    const options = await createAuthenticatedFetchOptions('PATCH', postData)
    const response = await fetch(`${API_BASE_URL}/api/v1/forum/posts/${postId}/`, options)
    return response.json()
  },

  async deletePost(postId) {
    const options = await createAuthenticatedFetchOptions('DELETE')
    const response = await fetch(`${API_BASE_URL}/api/v1/forum/posts/${postId}/`, options)
    return response.ok
  },
}
```

---

## Testing CSRF Protection

### Pattern: CSRF Token Handling in Tests

**Backend Test**:
```python
# apps/users/tests/test_csrf_protection.py
from django.test import TestCase
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

User = get_user_model()

class CSRFProtectionTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

    def get_csrf_token(self):
        """Get CSRF token from Django."""
        response = self.client.get('/api/v1/users/csrf/')
        csrf_cookie = response.cookies.get('csrftoken')
        return csrf_cookie.value if csrf_cookie else None

    def test_post_without_csrf_fails(self):
        """POST without CSRF token should return 403."""
        self.client.login(username='testuser', password='testpass123')

        response = self.client.post('/api/v1/forum/posts/', {
            'content': 'Test post'
        })

        self.assertEqual(response.status_code, 403)
        self.assertIn('CSRF', response.data['detail'])

    def test_post_with_csrf_succeeds(self):
        """POST with CSRF token should succeed."""
        # Login and get CSRF token
        self.client.login(username='testuser', password='testpass123')
        csrf_token = self.get_csrf_token()

        response = self.client.post(
            '/api/v1/forum/posts/',
            {'content': 'Test post'},
            HTTP_X_CSRFTOKEN=csrf_token
        )

        self.assertEqual(response.status_code, 201)

    def test_csrf_token_endpoint_sets_cookie(self):
        """CSRF endpoint should set csrftoken cookie."""
        response = self.client.get('/api/v1/users/csrf/')

        self.assertEqual(response.status_code, 200)
        self.assertIn('csrftoken', response.cookies)

    def test_csrf_cookie_properties(self):
        """CSRF cookie should have secure properties."""
        response = self.client.get('/api/v1/users/csrf/')
        csrf_cookie = response.cookies.get('csrftoken')

        # Check HttpOnly (XSS protection)
        self.assertTrue(csrf_cookie.get('httponly'))

        # Check SameSite (CSRF protection)
        self.assertEqual(csrf_cookie.get('samesite'), 'Lax')
```

**Frontend Test (Vitest)**:
```typescript
// web/src/services/__tests__/csrfService.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { getCsrfToken, fetchCsrfToken, ensureCsrfToken } from '../csrfService'

describe('CSRF Service', () => {
  beforeEach(() => {
    // Clear cookies
    document.cookie = 'csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 UTC'
  })

  it('should extract CSRF token from cookie', () => {
    document.cookie = 'csrftoken=test-token-value'
    expect(getCsrfToken()).toBe('test-token-value')
  })

  it('should return null if no CSRF cookie', () => {
    expect(getCsrfToken()).toBeNull()
  })

  it('should fetch CSRF token from backend', async () => {
    const mockFetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ detail: 'CSRF cookie set' }),
      })
    )
    global.fetch = mockFetch

    await fetchCsrfToken()

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/users/csrf/'),
      expect.objectContaining({
        credentials: 'include',
      })
    )
  })

  it('should fetch token only if missing', async () => {
    const mockFetch = vi.fn()
    global.fetch = mockFetch

    // Token already exists
    document.cookie = 'csrftoken=existing-token'
    await ensureCsrfToken()

    // Should not fetch
    expect(mockFetch).not.toHaveBeenCalled()

    // Clear token
    document.cookie = 'csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 UTC'

    // Now should fetch
    await ensureCsrfToken()
    expect(mockFetch).toHaveBeenCalled()
  })
})
```

---

## Common Pitfalls

### Pitfall 1: Missing `credentials: 'include'`

**Problem**:
```javascript
// ❌ Cookies not sent
fetch('/api/v1/endpoint/', {
  method: 'POST',
  headers: {
    'X-CSRFToken': csrfToken,
  },
})
```

**Solution**:
```javascript
// ✅ Cookies sent automatically
fetch('/api/v1/endpoint/', {
  method: 'POST',
  credentials: 'include',  // Required!
  headers: {
    'X-CSRFToken': csrfToken,
  },
})
```

---

### Pitfall 2: Hardcoded CSRF Token

**Problem**:
```javascript
// ❌ Stale token, security risk
const CSRF_TOKEN = 'hardcoded-token-value'

headers: {
  'X-CSRFToken': CSRF_TOKEN,
}
```

**Solution**:
```javascript
// ✅ Always fetch fresh token
await ensureCsrfToken()
const csrfToken = getCsrfToken()

headers: {
  ...(csrfToken && { 'X-CSRFToken': csrfToken }),
}
```

---

### Pitfall 3: Reading from localStorage

**Problem**:
```javascript
// ❌ CSRF tokens are in cookies, not localStorage!
const token = localStorage.getItem('csrftoken')
```

**Solution**:
```javascript
// ✅ Read from cookies
const match = document.cookie.match(/csrftoken=([^;]+)/)
const token = match ? match[1] : null
```

---

### Pitfall 4: Missing `@ensure_csrf_cookie` Decorator

**Problem**:
```python
# ❌ Cookie not set
@api_view(['GET'])
def csrf_token_view(request):
    return JsonResponse({'detail': 'CSRF cookie set'})
```

**Solution**:
```python
# ✅ Cookie set automatically
from django.views.decorators.csrf import ensure_csrf_cookie

@api_view(['GET'])
@ensure_csrf_cookie
def csrf_token_view(request):
    return JsonResponse({'detail': 'CSRF cookie set'})
```

---

### Pitfall 5: Sending `undefined` as Header Value

**Problem**:
```javascript
// ❌ Sends 'X-CSRFToken: undefined'
headers: {
  'X-CSRFToken': csrfToken,  // undefined if token doesn't exist
}
```

**Solution**:
```javascript
// ✅ Only includes header if token exists
headers: {
  'Content-Type': 'application/json',
  ...(csrfToken && { 'X-CSRFToken': csrfToken }),
}
```

---

## Security Checklist

### Backend Configuration
- [ ] `CSRF_COOKIE_SECURE = True` in production
- [ ] `CSRF_COOKIE_HTTPONLY = True` (XSS protection)
- [ ] `CSRF_COOKIE_SAMESITE = 'Lax'` (CSRF protection)
- [ ] `CORS_ALLOW_CREDENTIALS = True`
- [ ] CSRF endpoint configured (`/api/v1/users/csrf/`)
- [ ] `@ensure_csrf_cookie` decorator on CSRF endpoint

### Frontend Implementation
- [ ] `getCsrfToken()` reads from cookies (not localStorage)
- [ ] `fetchCsrfToken()` calls backend CSRF endpoint
- [ ] `ensureCsrfToken()` called before authenticated requests
- [ ] `credentials: 'include'` on all authenticated fetches
- [ ] `X-CSRFToken` header injected with conditional spreading
- [ ] No hardcoded tokens
- [ ] Centralized CSRF service for reuse

### Testing
- [ ] Test POST without CSRF token (should fail with 403)
- [ ] Test POST with CSRF token (should succeed)
- [ ] Test CSRF endpoint sets cookie
- [ ] Test cookie properties (HttpOnly, SameSite)
- [ ] Test frontend token extraction
- [ ] Test frontend token fetching

---

## Related Patterns

- **Authentication**: See `authentication.md`
- **Cookie Security**: See Django `SESSION_COOKIE_*` settings
- **CORS Configuration**: See `backend/settings.py` CORS settings
- **Input Validation**: See `input-validation.md`

---

**Last Reviewed**: November 13, 2025
**Pattern Count**: 8 CSRF protection patterns
**Status**: ✅ Production-validated
**OWASP**: A01:2021 – Broken Access Control
