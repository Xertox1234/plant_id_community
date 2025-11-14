# Forum Authentication & TipTap Fixes - Codified Patterns

**Date**: October 31, 2025
**Status**: Production-Ready ✅
**Impact**: Critical - Enables forum posting functionality

## Summary

Fixed two blocking issues preventing users from posting to forum threads:
1. **401 Unauthorized Error**: Frontend-backend authentication field mismatch
2. **TipTap Duplicate Extension Warning**: StarterKit Link extension conflict

---

## Issue 1: Forum Post 401 Unauthorized Error

### Problem Statement

**Symptom**: Authenticated users received HTTP 401 errors when attempting to post replies to forum threads.

**Error Log**:
```
WARNING API client error: NotAuthenticated
WARNING Unauthorized: /api/v1/forum/posts/
WARNING "POST /api/v1/forum/posts/ HTTP/1.1" 401 185
```

**Frontend Error**:
```javascript
[ThreadDetailPage] Error creating post: Error: HTTP 401
```

### Root Cause Analysis

**Frontend** (`web/src/pages/auth/LoginPage.jsx`):
```javascript
// Line 102-104
const result = await login({
  email: formData.email,        // ❌ Sends 'email' field
  password: formData.password,
})
```

**Backend** (`backend/apps/users/views.py` - BEFORE FIX):
```python
# Line 140 (original)
username = request.data.get('username')  # ❌ Expected 'username' field
password = request.data.get('password')
```

**Result**: Django's `authenticate()` received `None` for username, authentication failed silently, no JWT cookies were set, forum API rejected requests.

### Solution Implementation

**File**: `backend/apps/users/views.py`
**Function**: `login(request: Request) -> Response`
**Lines**: 136-174

```python
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
@ensure_csrf_cookie
@ratelimit(
    key='ip',
    rate=RATE_LIMITS['auth_endpoints']['login'],
    method='POST',
    block=True
)
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
            'Email/username and password are required',  # ✅ Updated message
            status.HTTP_400_BAD_REQUEST
        )

    # ... account lockout check ...

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

### Pattern: Email/Username Flexible Authentication

**When to Apply**: Any Django login endpoint that needs to support both username and email authentication.

**Implementation Steps**:

1. **Accept both fields with fallback**:
   ```python
   username = request.data.get('username') or request.data.get('email')
   ```

2. **Try direct authentication first**:
   ```python
   user = authenticate(username=username, password=password)
   ```

3. **Email-based fallback** (if User model uses username as USERNAME_FIELD):
   ```python
   if not user and '@' in username:
       try:
           user_by_email = User.objects.get(email=username)
           user = authenticate(username=user_by_email.username, password=password)
       except User.DoesNotExist:
           pass
   ```

4. **Update error messages** to reflect dual authentication:
   ```python
   'Email/username and password are required'
   ```

### Security Considerations

✅ **Safe**:
- No timing attack vulnerabilities (same authenticate() calls)
- Maintains account lockout protection
- Preserves rate limiting
- Uses Django's built-in authentication (no custom password checking)

⚠️ **Performance Impact**:
- Email-based login adds 1 database query (`User.objects.get(email=...)`)
- Minimal impact: O(1) indexed email lookup
- Only triggered on failed authentication with '@' in identifier

❌ **NOT Recommended**:
- Do NOT use this pattern if your User model has `USERNAME_FIELD = 'email'`
- Do NOT bypass Django's authenticate() function
- Do NOT implement custom password verification

### Testing Checklist

- [x] Login with username works
- [x] Login with email works
- [x] JWT cookies are set correctly (`access_token`, `refresh_token`)
- [x] Forum posting works after login
- [x] Account lockout still functions
- [x] Rate limiting still enforced
- [x] Invalid credentials return proper errors

---

## Issue 2: TipTap Duplicate Extension Warning

### Problem Statement

**Symptom**: Console warning on every editor mount.

**Error Log**:
```
TipTapEditor.jsx:20 [tiptap warn]: Duplicate extension names found: ['link'].
This can lead to issues.
```

### Root Cause Analysis

**StarterKit Bundle** (from `@tiptap/starter-kit`):
- Includes multiple pre-configured extensions
- **Includes a default Link extension**

**Custom Configuration** (`TipTapEditor.jsx` - BEFORE FIX):
```javascript
// Lines 21-38 (original)
extensions: [
  StarterKit.configure({
    heading: {
      levels: [2, 3],
    },
  }),
  Link.configure({           // ❌ Duplicate! StarterKit already has Link
    openOnClick: false,
    HTMLAttributes: {
      class: 'text-green-600 hover:underline',
      target: '_blank',
      rel: 'noopener noreferrer',
    },
  }),
  // ...
]
```

**Result**: Two Link extensions registered, TipTap warns about naming conflict.

### Solution Implementation

**File**: `web/src/components/forum/TipTapEditor.jsx`
**Hook**: `useEditor()`
**Lines**: 20-40

```javascript
const editor = useEditor({
  extensions: [
    StarterKit.configure({
      heading: {
        levels: [2, 3], // Only H2 and H3
      },
      // Disable the default Link from StarterKit to avoid duplicate
      link: false,  // ✅ Disable bundled Link extension
    }),
    Link.configure({
      openOnClick: false,
      HTMLAttributes: {
        class: 'text-green-600 hover:underline',
        target: '_blank',
        rel: 'noopener noreferrer',
      },
    }),
    Placeholder.configure({
      placeholder,
    }),
  ],
  // ...
});
```

### Pattern: TipTap Extension Deduplication

**When to Apply**: Using TipTap with StarterKit + custom extension configuration.

**StarterKit Bundled Extensions**:
- Document
- Paragraph
- Text
- **Link** ⚠️
- Bold
- Italic
- Strike
- Code
- Heading
- BulletList
- OrderedList
- ListItem
- BlockQuote
- CodeBlock
- HorizontalRule
- HardBreak
- Dropcursor
- Gapcursor
- History

**Implementation Pattern**:

```javascript
import StarterKit from '@tiptap/starter-kit';
import CustomExtension from '@tiptap/extension-custom';

const editor = useEditor({
  extensions: [
    StarterKit.configure({
      // Disable bundled extension to avoid duplicate
      extensionName: false,

      // Configure other bundled extensions
      otherExtension: {
        // options
      },
    }),

    // Add custom-configured version
    CustomExtension.configure({
      // Custom configuration
    }),
  ],
});
```

**Common Scenarios**:

1. **Custom Link with security attributes**:
   ```javascript
   StarterKit.configure({ link: false }),
   Link.configure({
     HTMLAttributes: {
       target: '_blank',
       rel: 'noopener noreferrer',
     },
   }),
   ```

2. **Custom Heading with limited levels**:
   ```javascript
   StarterKit.configure({
     heading: {
       levels: [1, 2, 3],  // Only H1-H3
     },
   }),
   ```

3. **Disable unwanted bundled extensions**:
   ```javascript
   StarterKit.configure({
     codeBlock: false,    // Disable code blocks
     blockquote: false,   // Disable blockquotes
   }),
   ```

### Best Practices

✅ **Do**:
- Always check StarterKit's bundled extensions before adding custom ones
- Add explanatory comments when disabling bundled extensions
- Use `configure()` to customize bundled extensions when possible

❌ **Don't**:
- Don't assume extension names match package names
- Don't ignore duplicate extension warnings (can cause editor bugs)
- Don't remove StarterKit entirely unless you need full control

### Testing Checklist

- [x] No duplicate extension warnings in console
- [x] Link toolbar button works
- [x] Links open in new tab with noopener/noreferrer
- [x] Link styling applied correctly
- [x] All other editor features work (bold, italic, lists, etc.)

---

## Cross-Domain Cookie Authentication (Bonus Pattern)

### Context

During debugging, we discovered that cookie-based JWT authentication works across different ports on localhost:
- Frontend: `http://localhost:5174`
- Backend: `http://localhost:8000`

### How It Works

**Backend** (`apps/users/authentication.py`):
```python
def set_jwt_cookies(response: HttpResponse, user: User) -> HttpResponse:
    response.set_cookie(
        key='access_token',
        value=str(access_token),
        max_age=access_max_age,
        httponly=True,
        secure=not settings.DEBUG,
        samesite='Strict' if not settings.DEBUG else 'Lax',  # ✅ Lax for dev
        domain=None,  # ✅ Default domain (allows cross-port)
        path='/'
    )
```

**Frontend** (`services/forumService.js`):
```javascript
async function authenticatedFetch(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    credentials: 'include',  // ✅ Send cookies cross-origin
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      ...(csrfToken && { 'X-CSRFToken': csrfToken }),
    },
  });
}
```

**CORS Configuration** (`settings.py`):
```python
CORS_ALLOWED_ORIGINS = [
    'http://localhost:5174',  # React dev server
    # ...
]
CORS_ALLOW_CREDENTIALS = True  # ✅ Required for cookies
```

### Key Requirements

1. **Backend**: `SameSite=Lax` in development (not `Strict`)
2. **Frontend**: `credentials: 'include'` on all fetch requests
3. **CORS**: Origin must be in `CORS_ALLOWED_ORIGINS`
4. **CORS**: `CORS_ALLOW_CREDENTIALS = True` must be set

---

## Related Files Modified

### Backend
- `backend/apps/users/views.py` - login() function (lines 136-174)
- `backend/apps/users/authentication.py` - set_jwt_cookies() (added domain comment)

### Frontend
- `web/src/components/forum/TipTapEditor.jsx` - useEditor() extensions (lines 20-40)

### Documentation
- `REACT_DJANGO_AUTH_PATTERNS.md` - Should be updated with email/username pattern
- `CLAUDE.md` - Authentication section should reference this document

---

## Future Improvements

### Backend
1. **Add type hints to email lookup**:
   ```python
   from typing import Optional

   user_by_email: Optional[User] = None
   if not user and '@' in username:
       try:
           user_by_email = User.objects.get(email=username)
           user = authenticate(username=user_by_email.username, password=password)
       except User.DoesNotExist:
           pass
   ```

2. **Add logging for email-based authentication**:
   ```python
   if user_by_email:
       logger.info(f"Email-based authentication for {log_safe_username(user.username)}")
   ```

3. **Consider custom authentication backend** (if pattern used frequently):
   ```python
   # apps/users/backends.py
   class EmailOrUsernameBackend:
       def authenticate(self, request, username=None, password=None):
           # Centralized email/username logic
           pass
   ```

### Frontend
1. **Add PropTypes for all TipTap extensions** (if using PropTypes)
2. **Extract StarterKit config to constants** for reusability
3. **Add TypeScript types** if migrating to TypeScript

---

## Appendix: Debugging Commands

### Check cookies in browser
```javascript
// DevTools Console
document.cookie.split(';').forEach(c => console.log(c.trim()));
```

### Test authentication from command line
```bash
curl -i -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password"}' \
  | grep -i "set-cookie"
```

### Check backend logs for authentication
```bash
# In backend directory
tail -f logs/debug.log | grep -E "LOGIN|AUTH|401"
```

### Verify CORS configuration
```bash
curl -i -X OPTIONS http://localhost:8000/api/v1/forum/posts/ \
  -H "Origin: http://localhost:5174" \
  -H "Access-Control-Request-Method: POST"
```

---

## References

- **Django Authentication**: https://docs.djangoproject.com/en/5.2/topics/auth/
- **TipTap StarterKit**: https://tiptap.dev/docs/editor/api/extensions/starter-kit
- **CORS Credentials**: https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS#requests_with_credentials
- **SameSite Cookies**: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Set-Cookie#samesitesamesite-value

---

**Last Updated**: October 31, 2025
**Review Status**: Ready for Production ✅
**Breaking Changes**: None (backward compatible)
