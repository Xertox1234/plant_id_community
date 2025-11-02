# React + Django Authentication Integration Patterns

**Complete documentation for integrating React 19 frontend with Django 5.2 + DRF backend authentication**

**Last Updated**: November 2, 2025

---

## Essential Debugging Commands

```bash
# Backend - Verify API endpoints
cd backend
source venv/bin/activate
python manage.py show_urls | grep auth

# Expected output:
# /api/v1/auth/csrf/
# /api/v1/auth/register/
# /api/v1/auth/login/
# /api/v1/auth/logout/
# /api/v1/auth/user/
```

---

## Critical Pattern #1: URL Path Discovery

**Problem**: Frontend calling wrong endpoint paths (`/api/v1/users/*` instead of `/api/v1/auth/*`)

**Root cause**: Django URL config doesn't always match app name
```python
# backend/plant_community_backend/urls.py
path('api/v1/', include([
    path('auth/', include('apps.users.urls')),  # NOT path('users/', ...)
]))
```

**Solution**: Always verify backend routes first
```bash
python manage.py show_urls | grep auth  # Find actual paths
```

---

## Critical Pattern #2: Field Name Mapping

**Problem**: Backend expects `username`, `first_name`, `last_name` but frontend sent `name`

**Backend serializer** (`apps/users/serializers.py`):
```python
class UserRegistrationSerializer(serializers.ModelSerializer):
    class Meta:
        fields = [
            'username',       # Required
            'email',          # Required
            'password',       # Required
            'confirmPassword',# Required
            'first_name',     # Optional (snake_case)
            'last_name',      # Optional (snake_case)
        ]
```

**Frontend form** (`web/src/pages/auth/SignupPage.jsx`):
```jsx
const [formData, setFormData] = useState({
  username: '',      // Maps to username
  firstName: '',     // Maps to first_name (camelCase)
  lastName: '',      // Maps to last_name (camelCase)
  email: '',
  password: '',
  confirmPassword: '',
})

// Form submission with explicit mapping
const result = await signup({
  username: formData.username,
  first_name: formData.firstName,  // camelCase → snake_case
  last_name: formData.lastName,    // camelCase → snake_case
  email: formData.email,
  password: formData.password,
  confirmPassword: formData.confirmPassword,
})
```

---

## Critical Pattern #3: Password Validation Sync

**Problem**: Frontend validated 8 chars, backend required 14 chars

**Backend configuration** (`plant_community_backend/settings.py`):
```python
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 14}  # ← Frontend must match this
    },
]
```

**Frontend validation** (`web/src/utils/validation.js`):
```javascript
export function validatePassword(password) {
  if (!password || typeof password !== 'string') {
    return false
  }
  // Minimum 14 characters (Django backend requirement)
  return password.length >= 14  // Must match backend exactly
}

export function getPasswordError(password) {
  if (!validatePassword(password)) {
    return 'Password must be at least 14 characters long'  // Match backend message
  }
  return null
}
```

---

## Critical Pattern #4: CSRF for Public Endpoints

**Problem**: 403 Forbidden on registration despite CSRF token being sent

**When to use CSRF exempt**:
```python
# backend/apps/users/views.py
from django.views.decorators.csrf import csrf_exempt

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
@csrf_exempt  # ✅ Acceptable for public JWT endpoints
@ratelimit(key='ip', rate='3/h', method='POST', block=True)
def register(request: Request) -> Response:
    """Register a new user account."""
    # ...
```

**Rationale**:
- ✅ Public registration/login endpoints with JWT auth don't need CSRF
- ✅ Rate limiting provides protection against abuse
- ✅ CSRF is primarily for session-based authentication
- ❌ Use CSRF for authenticated endpoints with session cookies

---

## Critical Pattern #5: Enhanced Error Logging

**Problem**: Generic "Signup failed" error didn't show backend validation details

**Frontend error handling** (`web/src/services/authService.js`):
```javascript
if (!response.ok) {
  let errorData
  try {
    errorData = await response.json()
  } catch (e) {
    throw new Error(`Signup failed with status ${response.status}`)
  }

  // Log detailed error for debugging
  logger.error('[authService] Signup failed:', {
    status: response.status,
    error: errorData
  })

  // Extract error message from various backend formats
  const errorMessage = errorData.error?.message ||
                      errorData.message ||
                      JSON.stringify(errorData)
  throw new Error(errorMessage)
}
```

---

## Critical Pattern #6: Email/Username Flexible Login (Forum Fix)

**Problem**: Frontend sends `email` field, backend expected `username` field, causing 401 errors on authenticated requests.

**Root cause**: Django User model uses `username` as USERNAME_FIELD, but LoginPage sends email.

**Solution** (`backend/apps/users/views.py` login() - lines 136-174):
```python
def login(request: Request) -> Response:
    """
    Authenticate user and return tokens.
    Accepts either 'username' or 'email' as the identifier.
    """
    # Support both 'username' and 'email' fields for flexibility
    username = request.data.get('username') or request.data.get('email')
    password = request.data.get('password')

    if not username or not password:
        return create_error_response(
            'MISSING_CREDENTIALS',
            'Missing credentials',
            'Email/username and password are required',  # Updated message
            status.HTTP_400_BAD_REQUEST
        )

    # Try to authenticate with username first
    user = authenticate(username=username, password=password)

    # If authentication fails and the identifier looks like an email,
    # try to find the user by email and authenticate with their username
    if not user and '@' in username:
        try:
            from_email = User.objects.get(email=username)
            user = authenticate(username=from_email.username, password=password)
        except User.DoesNotExist:
            pass

    # ... rest of authentication flow ...
```

**Security considerations**:
- ✅ No timing attack vulnerabilities (same authenticate() calls)
- ✅ Maintains account lockout protection
- ✅ Preserves rate limiting
- ⚠️ Adds 1 database query for email-based login (minimal impact)

**When to use**: Any Django login endpoint that needs to support both username and email authentication.

**Complete documentation**: See `FORUM_AUTH_FIXES_CODIFIED.md` for full pattern details.

---

## Critical Pattern #7: TipTap Extension Deduplication

**Problem**: Console warning about duplicate 'link' extension names in TipTap editor.

**Root cause**: StarterKit bundle includes a default Link extension, and custom Link configuration was added without disabling the bundled one.

**Solution** (`web/src/components/forum/TipTapEditor.jsx` - lines 20-40):
```javascript
const editor = useEditor({
  extensions: [
    StarterKit.configure({
      heading: {
        levels: [2, 3], // Only H2 and H3
      },
      // Disable the default Link from StarterKit to avoid duplicate
      link: false,  // ✅ CRITICAL: Disable bundled Link
    }),
    Link.configure({
      openOnClick: false,
      HTMLAttributes: {
        class: 'text-green-600 hover:underline',
        target: '_blank',
        rel: 'noopener noreferrer',
      },
    }),
    // ... other extensions
  ],
  // ...
});
```

**StarterKit bundled extensions** (check before adding custom ones):
- Document, Paragraph, Text, **Link** ⚠️, Bold, Italic, Strike, Code
- Heading, BulletList, OrderedList, ListItem, BlockQuote, CodeBlock
- HorizontalRule, HardBreak, Dropcursor, Gapcursor, History

**Pattern**: Disable bundled extension with `extensionName: false` before adding custom configuration.

**Complete documentation**: See `FORUM_AUTH_FIXES_CODIFIED.md` for full pattern details.

---

## Authentication Integration Checklist

Before implementing authentication features:

- [ ] Verify backend routes with `python manage.py show_urls | grep auth`
- [ ] Check serializer's `Meta.fields` list for required/optional fields
- [ ] Match password validation rules (check `AUTH_PASSWORD_VALIDATORS`)
- [ ] Decide if CSRF needed (public JWT endpoints: no, session auth: yes)
- [ ] Implement camelCase → snake_case field mapping on submission
- [ ] Add detailed error logging that parses backend validation errors
- [ ] Test with real registration/login attempts
- [ ] Verify JWT tokens stored correctly (sessionStorage for security)

---

## Common Authentication Mistakes

❌ **Don't assume app name matches URL prefix**
```python
# urls.py might have:
path('auth/', include('apps.users.urls'))  # NOT 'users/'
```

❌ **Don't use single "name" field** when backend expects `username` + `first_name` + `last_name`

❌ **Don't hardcode password validation length** - always check Django `AUTH_PASSWORD_VALIDATORS`

❌ **Don't use CSRF for public JWT-based auth endpoints** - adds unnecessary complexity

❌ **Don't show generic error messages** - parse and display backend validation errors

---

## Related Files

**Backend**:
- `backend/plant_community_backend/urls.py` - Main URL configuration
- `backend/apps/users/urls.py` - User app URLs
- `backend/apps/users/views.py` - Authentication views (`@csrf_exempt` pattern, email/username login)
- `backend/apps/users/serializers.py` - Field requirements
- `backend/plant_community_backend/settings.py` - Password validators

**Frontend**:
- `web/src/services/authService.js` - API service layer (endpoint paths, error handling)
- `web/src/pages/auth/SignupPage.jsx` - Registration form (field mapping)
- `web/src/pages/auth/LoginPage.jsx` - Login form (sends email field)
- `web/src/utils/validation.js` - Password validation (14 char minimum)
- `web/src/contexts/AuthContext.jsx` - Auth state management
- `web/src/components/forum/TipTapEditor.jsx` - Rich text editor (link extension deduplication)

**Documentation**:
- `FORUM_AUTH_FIXES_CODIFIED.md` - Complete patterns and debugging guide (400+ lines)
- `REACT_DJANGO_AUTH_PATTERNS.md` - This file
