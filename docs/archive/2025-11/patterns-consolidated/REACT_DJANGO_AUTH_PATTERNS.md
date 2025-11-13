# React + Django Authentication Integration Patterns

**Date**: October 31, 2025
**Context**: Lessons learned from fixing registration flow between React 19 frontend and Django 5.2 + DRF backend

## Critical Issues and Fixes

### 1. API Endpoint Path Mismatches

**Problem**: Frontend was calling `/api/v1/users/*` but backend routes were at `/api/v1/auth/*`

**Root Cause**:
- Main URL config at `backend/plant_community_backend/urls.py` includes users app as:
  ```python
  path('api/v1/', include([
      path('auth/', include('apps.users.urls')),  # NOT path('users/', ...)
  ]))
  ```

**Solution**:
1. Always verify backend routes with Django's `show_urls` command:
   ```bash
   cd backend
   source venv/bin/activate
   python manage.py show_urls | grep auth
   ```

2. Update frontend to match exact backend paths:
   ```javascript
   // web/src/services/authService.js
   const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

   // ✅ Correct - matches backend URL configuration
   await fetch(`${API_URL}/api/v1/auth/register/`, { ... })
   await fetch(`${API_URL}/api/v1/auth/login/`, { ... })
   await fetch(`${API_URL}/api/v1/auth/user/`, { ... })

   // ❌ Wrong - assumes app name matches URL prefix
   await fetch(`${API_URL}/api/v1/users/register/`, { ... })
   ```

**Files Changed**:
- `web/src/services/authService.js` - All endpoint URLs

---

### 2. Form Field Name Mismatches

**Problem**: Frontend sent `name` field, backend expected `username`

**Root Cause**:
- Backend serializer (`apps/users/serializers.py`) expects:
  ```python
  fields = [
      'username', 'email', 'password', 'password_confirm', 'confirmPassword',
      'first_name', 'last_name', 'bio', 'location', 'gardening_experience'
  ]
  ```
- Frontend form collected "Full name" in single field

**Solution**:
1. Match frontend form fields to backend serializer exactly:
   ```jsx
   // ✅ Correct - separate fields matching backend
   const [formData, setFormData] = useState({
     username: '',      // Django expects this
     firstName: '',     // Maps to first_name
     lastName: '',      // Maps to last_name
     email: '',
     password: '',
     confirmPassword: '',
   })
   ```

2. Map camelCase (React) to snake_case (Django) on submission:
   ```jsx
   const result = await signup({
     username: formData.username,
     first_name: formData.firstName,  // camelCase → snake_case
     last_name: formData.lastName,    // camelCase → snake_case
     email: formData.email,
     password: formData.password,
     confirmPassword: formData.confirmPassword,
   })
   ```

**Files Changed**:
- `web/src/pages/auth/SignupPage.jsx` - Added username, firstName, lastName fields
- `web/src/pages/auth/SignupPage.jsx` - Form submission mapping

---

### 3. Password Validation Mismatches

**Problem**: Frontend validated min 8 chars, backend required min 14 chars

**Backend Error Response**:
```json
{
  "password": ["This password is too short. It must contain at least 14 characters."]
}
```

**Root Cause**:
- Django's `AUTH_PASSWORD_VALIDATORS` in settings.py configured for 14 character minimum
- Frontend validation used generic 8 character minimum

**Solution**:
1. Check Django password validators in settings.py:
   ```python
   AUTH_PASSWORD_VALIDATORS = [
       {
           'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
           'OPTIONS': {'min_length': 14}  # ← This is the requirement
       },
       # ... other validators
   ]
   ```

2. Update frontend validation to match:
   ```javascript
   // web/src/utils/validation.js
   export function validatePassword(password) {
     if (!password || typeof password !== 'string') {
       return false
     }
     // Minimum 14 characters (Django backend requirement)
     return password.length >= 14  // ← Must match backend
   }

   export function getPasswordError(password) {
     if (!validateRequired(password)) {
       return 'Password is required'
     }
     if (!validatePassword(password)) {
       return 'Password must be at least 14 characters long'  // ← Match backend message
     }
     return null
   }
   ```

3. Update UI placeholder text:
   ```jsx
   <Input
     type="password"
     label="Password"
     placeholder="At least 14 characters"  // ← Inform user of requirement
     // ...
   />
   ```

**Files Changed**:
- `web/src/utils/validation.js` - Updated `validatePassword()` and `getPasswordError()`
- `web/src/pages/auth/SignupPage.jsx` - Updated placeholder text

---

### 4. CSRF Token Configuration

**Problem**: 403 Forbidden errors despite CSRF token being sent

**Root Cause**:
- DRF's `SessionAuthentication` requires CSRF protection by default
- Public registration endpoints don't need CSRF when using token-based auth (JWT)
- CSRF adds unnecessary complexity for unauthenticated endpoints

**Solution**:
Use `@csrf_exempt` decorator for public authentication endpoints:

```python
# backend/apps/users/views.py
from django.views.decorators.csrf import csrf_exempt

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
@csrf_exempt  # ← Acceptable for public endpoints
@ratelimit(
    key='ip',
    rate=RATE_LIMITS['auth_endpoints']['register'],
    method='POST',
    block=True
)
def register(request: Request) -> Response:
    """Register a new user account."""
    # ...
```

**Why this is acceptable**:
- ✅ Registration and login are public endpoints
- ✅ JWT tokens provide authentication for subsequent requests
- ✅ Rate limiting provides protection against abuse
- ✅ CSRF is primarily for session-based auth (cookies)

**When to use CSRF**:
- ✅ Use for authenticated endpoints with session cookies
- ❌ Not needed for public registration/login with JWT
- ❌ Not needed for token-based API endpoints

**Files Changed**:
- `backend/apps/users/views.py` - Added `@csrf_exempt` to register view

---

### 5. Enhanced Error Logging

**Problem**: Generic "Signup failed" error didn't show backend validation details

**Solution**:
Always parse and log detailed backend error responses:

```javascript
// web/src/services/authService.js
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

**Files Changed**:
- `web/src/services/authService.js` - Enhanced error handling in `signup()` function

---

## Patterns to Follow

### For React Frontend

1. **Verify API endpoints match backend routes**
   ```bash
   # Always check backend routes first
   cd backend && python manage.py show_urls | grep auth
   ```

2. **Map form fields to backend serializer**
   - Check serializer's `Meta.fields` list
   - Use snake_case for Django (first_name) vs camelCase for React (firstName)
   - Create explicit mapping on submission

3. **Match password validation rules**
   - Check Django's `AUTH_PASSWORD_VALIDATORS` in settings.py
   - Frontend validation should match or exceed backend requirements
   - Display same error messages as backend

4. **Log detailed backend errors in development**
   ```javascript
   logger.error('[authService] Failed:', {
     status: response.status,
     error: errorData
   })
   ```

### For Django Backend

1. **Use `@csrf_exempt` for public auth endpoints**
   ```python
   @csrf_exempt  # For register, login
   def register(request):
       ...
   ```

2. **Document serializer fields clearly**
   ```python
   class UserRegistrationSerializer(serializers.ModelSerializer):
       """
       Serializer for user registration.

       Required fields: username, email, password
       Optional fields: first_name, last_name, bio
       """
       class Meta:
           fields = ['username', 'email', 'password', ...]
   ```

3. **Return detailed validation errors**
   ```python
   if serializer.is_valid():
       # ...
   else:
       # Return specific field errors, not generic 400
       return Response(serializer.errors, status=400)
   ```

### For Integration Testing

1. **Test registration flow end-to-end first**
   - Verify all required fields are sent
   - Check password meets backend requirements
   - Confirm user creation and response format
   - Test error cases (duplicate email, weak password)

2. **Use curl to test API directly**
   ```bash
   # Test CSRF token fetch
   curl -v http://localhost:8000/api/v1/auth/csrf/

   # Test registration
   curl -X POST http://localhost:8000/api/v1/auth/register/ \
     -H "Content-Type: application/json" \
     -d '{
       "username": "testuser",
       "email": "test@example.com",
       "password": "MySecurePassword2024!",
       "confirmPassword": "MySecurePassword2024!"
     }'
   ```

---

## Common Mistakes to Avoid

❌ **Don't assume app name matches URL prefix**
```python
# urls.py might have:
path('auth/', include('apps.users.urls'))  # NOT 'users/'
```

❌ **Don't use single "name" field when backend expects username + first_name + last_name**

❌ **Don't hardcode password validation length** - always check Django settings

❌ **Don't use CSRF for public JWT-based auth endpoints** - adds unnecessary complexity

❌ **Don't show generic error messages** - parse and display backend validation errors

---

## Quick Reference

### Backend Routes
```bash
python manage.py show_urls | grep "v1/auth"
```

### Required Fields (from serializer)
- `username` (required)
- `email` (required)
- `password` (required)
- `confirmPassword` or `password_confirm` (required)
- `first_name` (optional)
- `last_name` (optional)

### Password Requirements
- Minimum 14 characters
- Cannot be too similar to username/email
- Cannot be entirely numeric
- Cannot be a common password

### Error Response Formats
```json
{
  "password": ["This password is too short. It must contain at least 14 characters."]
}
```

```json
{
  "username": ["A user with that username already exists."]
}
```

---

## Related Files

### Backend
- `backend/plant_community_backend/urls.py` - Main URL configuration
- `backend/apps/users/urls.py` - User app URLs
- `backend/apps/users/views.py` - Authentication views
- `backend/apps/users/serializers.py` - User serializers
- `backend/plant_community_backend/settings.py` - Password validators

### Frontend
- `web/src/services/authService.js` - API service layer
- `web/src/pages/auth/SignupPage.jsx` - Registration form
- `web/src/pages/auth/LoginPage.jsx` - Login form
- `web/src/utils/validation.js` - Form validation
- `web/src/contexts/AuthContext.jsx` - Auth state management

---

## Testing Checklist

- [ ] Backend routes verified with `show_urls`
- [ ] Form fields match serializer fields exactly
- [ ] Password validation matches backend requirements
- [ ] CSRF configuration appropriate for endpoint type
- [ ] Error messages are detailed and helpful
- [ ] camelCase/snake_case mapping is correct
- [ ] Test with real registration attempt
- [ ] Verify user created in database
- [ ] Check JWT tokens returned correctly
- [ ] Test error cases (duplicate email, weak password)

---

**Status**: ✅ Registration working as of October 31, 2025
**Next Steps**: Apply same patterns to login, password reset, profile update
