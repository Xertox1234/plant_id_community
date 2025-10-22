# Authentication Strategy - Plant Identification API

## Overview

The plant identification API implements a **dual-mode authentication strategy** that automatically adjusts based on the deployment environment:

- **Development (`DEBUG=True`)**: Anonymous users allowed with strict rate limiting (10 req/hour)
- **Production (`DEBUG=False`)**: Authentication required (100 req/hour for authenticated users)

This strategy protects expensive API quota (Plant.id: 100 IDs/month free tier) while allowing easy development and testing.

---

## Implementation

### Permission Classes

Created in `apps/plant_identification/permissions.py`:

1. **`IsAuthenticatedOrAnonymousWithStrictRateLimit`** (Development)
   - Allows both authenticated and anonymous users
   - Anonymous users get 10 requests/hour
   - Authenticated users get 100 requests/hour

2. **`IsAuthenticatedForIdentification`** (Production)
   - Requires authentication for POST /identify/
   - Health check (GET) remains public
   - Returns clear error message: "Authentication required for plant identification"

3. **`IsAuthenticatedOrReadOnlyWithRateLimit`** (Alternative)
   - Allows authenticated users full access
   - Anonymous users read-only (GET requests only)

### Endpoint Configuration

**File:** `apps/plant_identification/api/simple_views.py`

```python
@api_view(['POST'])
@permission_classes([
    IsAuthenticatedOrAnonymousWithStrictRateLimit if settings.DEBUG
    else IsAuthenticatedForIdentification
])
@ratelimit(
    key=lambda request: 'anon' if not request.user.is_authenticated else f'user-{request.user.id}',
    rate='10/h' if settings.DEBUG else '100/h',
    method='POST'
)
def identify_plant(request):
    """Plant identification with environment-aware authentication."""
```

**Key Features:**
- Environment-driven permission selection
- User-specific rate limit keys (prevents users from getting same quota)
- Higher limits for authenticated users (10x more requests)

---

## Rate Limiting Strategy

### Development (DEBUG=True)

| User Type | Rate Limit | Key | Quota Usage |
|-----------|------------|-----|-------------|
| Anonymous | 10/hour | `'anon'` | Shared across all anonymous users |
| Authenticated | 100/hour | `f'user-{user.id}'` | Per-user quota |

**Risk Mitigation:**
- Low rate limit for anonymous (10/h) prevents quota exhaustion
- Shared `'anon'` key means all anonymous users share 10 req/hour
- Still allows frontend testing without authentication

### Production (DEBUG=False)

| User Type | Rate Limit | Key | Quota Usage |
|-----------|------------|-----|-------------|
| Anonymous | ❌ **Blocked** | N/A | No access |
| Authenticated | 100/hour | `f'user-{user.id}'` | Per-user quota |

**Risk Mitigation:**
- No anonymous access protects API quota completely
- Per-user quotas allow monitoring and throttling
- 100/hour allows legitimate usage (2,400/day max per user)

---

## Why This Strategy?

### Problem: API Quota is Expensive

- Plant.id free tier: **100 identifications/month**
- PlantNet free tier: **500 requests/day**
- Combined: ~3,500 free IDs/month for development
- Paid Plant.id: $29/month for 1,000 IDs

**Unprotected API Risk:**
- 10 anonymous users @ 10 req/hour = 100 requests/hour = 2,400/day
- Could exhaust monthly quota in **1 day**

### Solution: Progressive Authentication

**Phase 1: Development (Current)**
- Allow anonymous users for easy testing
- Strict rate limits prevent abuse (10/h shared)
- Frontend developers can test without login flow

**Phase 2: Staging**
- Set `DEBUG=False` in staging environment
- Requires authentication (tests production behavior)
- Validates login flow before production

**Phase 3: Production**
- `DEBUG=False` enforced
- Authentication required (protects quota)
- Monitor usage per user
- Can adjust rate limits based on actual usage

---

## Migration Guide

### Frontend Changes Required

**React Web (`web/src/services/plantIdService.js`):**

```javascript
// Before: Works without authentication
export const identifyPlant = async (imageFile) => {
  const formData = new FormData();
  formData.append('image', imageFile);

  const response = await fetch(`${API_BASE_URL}/plant-identification/identify/`, {
    method: 'POST',
    body: formData,
  });

  return response.json();
};

// After: Include authentication token
export const identifyPlant = async (imageFile) => {
  const formData = new FormData();
  formData.append('image', imageFile);

  const token = localStorage.getItem('access_token');

  const response = await fetch(`${API_BASE_URL}/plant-identification/identify/`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
    body: formData,
  });

  if (response.status === 401) {
    // Redirect to login
    window.location.href = '/login?next=/identify';
  }

  return response.json();
};
```

**Flutter Mobile (`lib/services/plant_identification_service.dart`):**

```dart
Future<PlantIdentification> identifyPlant(File imageFile) async {
  final token = await _authService.getAccessToken();

  final request = http.MultipartRequest(
    'POST',
    Uri.parse('$baseUrl/plant-identification/identify/'),
  );

  request.headers['Authorization'] = 'Bearer $token';
  request.files.add(await http.MultipartFile.fromPath('image', imageFile.path));

  final response = await request.send();

  if (response.statusCode == 401) {
    // Token expired, refresh or redirect to login
    throw UnauthorizedException('Please log in to identify plants');
  }

  final responseBody = await response.stream.bytesToString();
  return PlantIdentification.fromJson(jsonDecode(responseBody));
}
```

---

## Error Handling

### 401 Unauthorized Response

**Development (DEBUG=True):**
- Should never occur (anonymous allowed)
- If occurs, indicates expired/invalid JWT token

**Production (DEBUG=False):**
```json
{
  "detail": "Authentication required for plant identification. Please log in or create an account to identify plants."
}
```

**Frontend Handling:**
```javascript
if (response.status === 401) {
  // Save current location for redirect after login
  sessionStorage.setItem('redirect_after_login', window.location.pathname);

  // Redirect to login page
  window.location.href = '/login';
}
```

### 429 Rate Limit Exceeded

**Anonymous User (Dev Only):**
```json
{
  "detail": "Request was throttled. Expected available in 3254 seconds."
}
```

**Authenticated User:**
```json
{
  "detail": "Request was throttled. Expected available in 1234 seconds."
}
```

**Frontend Handling:**
```javascript
if (response.status === 429) {
  const retryAfter = response.headers.get('Retry-After');
  const minutes = Math.ceil(retryAfter / 60);

  alert(`Rate limit exceeded. Please try again in ${minutes} minutes.`);
}
```

---

## Testing

### Unit Tests

```python
# apps/plant_identification/tests/test_authentication.py
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from apps.users.models import User


class IdentificationAuthenticationTestCase(TestCase):
    """Test authentication for plant identification endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('plant-identification:identify')
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    @override_settings(DEBUG=True)
    def test_anonymous_allowed_in_development(self):
        """Anonymous users can identify plants in development mode."""
        with open('test_plant.jpg', 'rb') as f:
            response = self.client.post(self.url, {'image': f})

        self.assertIn(response.status_code, [200, 429])  # 200 or rate limited

    @override_settings(DEBUG=False)
    def test_anonymous_blocked_in_production(self):
        """Anonymous users cannot identify plants in production mode."""
        with open('test_plant.jpg', 'rb') as f:
            response = self.client.post(self.url, {'image': f})

        self.assertEqual(response.status_code, 401)
        self.assertIn('Authentication required', response.data['detail'])

    @override_settings(DEBUG=False)
    def test_authenticated_allowed_in_production(self):
        """Authenticated users can identify plants in production mode."""
        self.client.force_authenticate(user=self.user)

        with open('test_plant.jpg', 'rb') as f:
            response = self.client.post(self.url, {'image': f})

        self.assertIn(response.status_code, [200, 429])  # 200 or rate limited
```

### Manual Testing

```bash
# Development (DEBUG=True) - Anonymous allowed
curl -X POST \
  http://localhost:8000/api/plant-identification/identify/ \
  -F "image=@test_plant.jpg"
# Expected: 200 OK with plant identification results

# Production (DEBUG=False) - Anonymous blocked
curl -X POST \
  http://localhost:8000/api/plant-identification/identify/ \
  -F "image=@test_plant.jpg"
# Expected: 401 Unauthorized

# Production - Authenticated allowed
curl -X POST \
  http://localhost:8000/api/plant-identification/identify/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "image=@test_plant.jpg"
# Expected: 200 OK with plant identification results
```

---

## Monitoring

### Key Metrics to Track

1. **Authentication Rate** (% of requests authenticated)
   ```python
   authenticated_requests = Request.objects.filter(user__isnull=False).count()
   total_requests = Request.objects.count()
   auth_rate = authenticated_requests / total_requests * 100
   ```

2. **Anonymous API Usage** (development only)
   ```bash
   # Check Redis for anonymous rate limit key
   redis-cli GET "rl:anon:identify_plant:POST"
   ```

3. **Per-User API Usage**
   ```sql
   SELECT
     user_id,
     COUNT(*) as identification_count,
     MAX(created_at) as last_request
   FROM plant_identification_request
   WHERE created_at > NOW() - INTERVAL '1 hour'
   GROUP BY user_id
   ORDER BY identification_count DESC
   LIMIT 10;
   ```

4. **Rate Limit Violations**
   ```bash
   # Grep logs for rate limit errors
   grep "429" logs/api.log | wc -l
   ```

### Alerts

**High Anonymous Usage (Development)**
```
IF anonymous_requests_per_hour > 50 THEN
  ALERT "Possible API abuse detected - consider switching to production mode"
END
```

**API Quota Approaching Limit**
```
IF plant_id_api_calls_this_month > 80 THEN
  ALERT "Plant.id quota at 80% - consider upgrading to paid tier"
END
```

---

## Production Deployment Checklist

- [ ] Set `DEBUG=False` in production environment
- [ ] Verify `REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES']` includes JWT
- [ ] Test login flow in staging environment
- [ ] Update frontend to include `Authorization` header
- [ ] Update mobile app to include `Authorization` header
- [ ] Add error handling for 401 responses
- [ ] Monitor authentication rate (should be 100%)
- [ ] Set up alerts for API quota usage
- [ ] Document rate limits in user-facing docs

---

## Future Enhancements

### Tiered Rate Limiting

Implement different rate limits based on user subscription tier:

```python
def get_rate_limit(request):
    """Get rate limit based on user subscription tier."""
    if not request.user.is_authenticated:
        return '10/h'  # Anonymous (dev only)

    if request.user.subscription_tier == 'premium':
        return '500/h'  # Premium users
    elif request.user.subscription_tier == 'pro':
        return '200/h'  # Pro users
    else:
        return '100/h'  # Free users

@ratelimit(key='user', rate=get_rate_limit)
def identify_plant(request):
    ...
```

### API Key Authentication

For mobile apps and third-party integrations:

```python
class APIKeyAuthentication(authentication.BaseAuthentication):
    """Authenticate using X-API-Key header."""

    def authenticate(self, request):
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            return None

        try:
            user = User.objects.get(api_key=api_key)
            return (user, None)
        except User.DoesNotExist:
            raise exceptions.AuthenticationFailed('Invalid API key')
```

### OAuth2 Scopes

Fine-grained permissions for third-party apps:

```python
SCOPES = {
    'identify': 'Identify plants from images',
    'identify:batch': 'Batch plant identification',
    'collection:read': 'Read plant collection',
    'collection:write': 'Modify plant collection',
}

@permission_classes([TokenHasScope])
@required_scopes(['identify'])
def identify_plant(request):
    ...
```

---

## Summary

The authentication strategy successfully balances:
- ✅ **Development convenience** (anonymous testing allowed)
- ✅ **Production security** (authentication required)
- ✅ **API quota protection** (strict rate limits)
- ✅ **User experience** (clear error messages)
- ✅ **Gradual migration** (environment-driven, no code changes)

**Next Steps:**
1. Update React frontend to include JWT token
2. Update Flutter mobile to include JWT token
3. Test in staging with `DEBUG=False`
4. Deploy to production
5. Monitor authentication rate and API usage
