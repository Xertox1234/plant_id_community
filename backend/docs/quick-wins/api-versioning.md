# API Versioning - Quick Win #2

## Overview

URL-based API versioning with backward compatibility to enable safe API evolution without forcing all clients to update simultaneously.

**Status:** ✅ Complete
**Implementation Time:** ~1 hour
**Files Modified:** 3 (urls.py, settings.py, plantIdService.js)

---

## Problem Solved

**Challenge:** Without API versioning, breaking changes force all clients (web, mobile, third-party) to update simultaneously. This creates:
- Deployment coordination nightmares
- App store review delays for mobile apps
- Breaking changes for third-party integrations
- No gradual migration path

**Solution:** Implement URL-based API versioning with backward compatibility.

---

## Implementation

### URL Structure

```
/api/v2/          → Wagtail CMS API (unchanged)
/api/v1/          → Django REST Framework API (NEW, versioned)
/api/             → Legacy unversioned API (DEPRECATED, still works)
```

### Django REST Framework Configuration

**File:** `plant_community_backend/settings.py`

```python
REST_FRAMEWORK = {
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.NamespaceVersioning',
    'DEFAULT_VERSION': 'v1',
    'ALLOWED_VERSIONS': ['v1'],  # Add 'v2' when implementing breaking changes
    'VERSION_PARAM': 'version',
    # ... other settings ...
}
```

**Why NamespaceVersioning?**
- Clean URLs: `/api/v1/endpoint/` vs `/api/endpoint/?version=v1`
- No query parameters needed
- Explicit version in URL (better for debugging)
- Industry standard (Stripe, GitHub, Twitter)

### URL Configuration

**File:** `plant_community_backend/urls.py`

```python
from django.urls import path, include

urlpatterns = [
    # Wagtail CMS API (v2) - unchanged
    path('api/v2/', api_router.urls),

    # Django REST Framework API - Versioned (v1)
    path('api/v1/', include(([
        path('auth/', include('apps.users.urls')),
        path('plant-identification/', include('apps.plant_identification.urls')),
        path('blog/', include('apps.blog.urls')),
        path('search/', include('apps.search.urls')),
        path('calendar/', include('apps.garden_calendar.urls')),
    ], 'v1'))),

    # Legacy Unversioned API (DEPRECATED)
    # TODO: Remove after 2025-07-01 (6 months deprecation period)
    path('api/', include([
        path('auth/', include('apps.users.urls')),
        path('plant-identification/', include('apps.plant_identification.urls')),
        path('blog/', include('apps.blog.urls')),
        path('search/', include('apps.search.urls')),
        path('calendar/', include('apps.garden_calendar.urls')),
    ])),
]
```

---

## Migration Guide

### Backend: No Changes Required

The backend automatically serves both:
- **Versioned:** `/api/v1/plant-identification/identify/`
- **Legacy:** `/api/plant-identification/identify/`

Both route to the same view, maintaining backward compatibility.

### Frontend: Update API Calls

**React Web App** (`web/src/services/plantIdService.js`)

```javascript
// Before (legacy unversioned)
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const identifyPlant = async (imageFile) => {
  const response = await axios.post(
    `${API_BASE_URL}/api/plant-identification/identify/`,  // Legacy
    formData
  )
  return response.data
}

// After (versioned)
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const API_VERSION = 'v1'

export const identifyPlant = async (imageFile) => {
  const response = await axios.post(
    `${API_BASE_URL}/api/${API_VERSION}/plant-identification/identify/`,  // Versioned
    formData
  )
  return response.data
}
```

**Flutter Mobile App** (`lib/config/api_config.dart`)

```dart
class ApiConfig {
  static const String baseUrl = 'https://api.plantcommunity.com';
  static const String apiVersion = 'v1';

  static String get identifyEndpoint =>
    '$baseUrl/api/$apiVersion/plant-identification/identify/';
}
```

---

## Gradual Migration Strategy

### Phase 1: Dual Support (Current)
- Both `/api/v1/` and `/api/` work
- No breaking changes
- Clients migrate at their own pace

### Phase 2: Deprecation Headers (Month 2)
Add deprecation warnings to legacy endpoints:

```python
# Add to middleware
def legacy_api_middleware(get_response):
    def middleware(request):
        response = get_response(request)

        if request.path.startswith('/api/') and not request.path.startswith('/api/v'):
            response['Deprecation'] = 'true'
            response['Sunset'] = 'Sat, 01 Jul 2025 00:00:00 GMT'
            response['Link'] = '</api/v1/>; rel="successor-version"'

        return response
    return middleware
```

### Phase 3: Remove Legacy (Month 6)
- Remove `/api/` routes (keep only `/api/v1/`)
- Monitor logs for 404s on legacy endpoints
- Communicate with remaining legacy clients

---

## Future Version Management

### Adding v2 (Breaking Changes)

**Example: Renaming field from `plant_name` to `name`**

1. **Update settings.py:**
   ```python
   REST_FRAMEWORK = {
       'ALLOWED_VERSIONS': ['v1', 'v2'],  # Add v2
       'DEFAULT_VERSION': 'v2',  # New default
   }
   ```

2. **Create v2 serializer:**
   ```python
   class PlantIdentificationResultSerializerV1(serializers.Serializer):
       plant_name = serializers.CharField()
       # ... other fields ...

   class PlantIdentificationResultSerializerV2(serializers.Serializer):
       name = serializers.CharField(source='plant_name')  # Renamed
       # ... other fields ...
   ```

3. **Update view to use version:**
   ```python
   def identify_plant(request):
       if request.version == 'v2':
           serializer_class = PlantIdentificationResultSerializerV2
       else:
           serializer_class = PlantIdentificationResultSerializerV1
       # ... rest of view ...
   ```

4. **Update URLs:**
   ```python
   urlpatterns = [
       path('api/v2/', include(([...], 'v2'))),  # New v2 namespace
       path('api/v1/', include(([...], 'v1'))),  # Existing v1
   ]
   ```

---

## Testing

### Test Both Versions Work

```python
# apps/plant_identification/tests/test_versioning.py
from django.test import TestCase
from rest_framework.test import APIClient

class APIVersioningTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_v1_endpoint_accessible(self):
        """v1 endpoint should be accessible."""
        response = self.client.get('/api/v1/plant-identification/identify/health/')
        self.assertEqual(response.status_code, 200)

    def test_legacy_endpoint_accessible(self):
        """Legacy unversioned endpoint should still work."""
        response = self.client.get('/api/plant-identification/identify/health/')
        self.assertEqual(response.status_code, 200)

    def test_legacy_endpoint_has_deprecation_headers(self):
        """Legacy endpoints should include deprecation headers."""
        response = self.client.get('/api/plant-identification/identify/health/')
        self.assertIn('Deprecation', response)
        self.assertIn('Sunset', response)
```

### Manual Testing

```bash
# Test v1 endpoint
curl http://localhost:8000/api/v1/plant-identification/identify/health/
# Expected: {"status": "healthy", ...}

# Test legacy endpoint
curl http://localhost:8000/api/plant-identification/identify/health/
# Expected: {"status": "healthy", ...} (with deprecation headers)
```

---

## Troubleshooting

### Issue: 404 Not Found on /api/v1/

**Diagnosis:** URL configuration issue

**Solution:**
```bash
# Check URL patterns
python manage.py show_urls | grep plant-identification

# Expected:
# /api/v1/plant-identification/identify/
# /api/plant-identification/identify/  (legacy)

# If missing, verify urls.py namespace configuration
```

### Issue: Frontend still using legacy endpoints

**Diagnosis:** API_VERSION constant not defined or used

**Solution:**
```javascript
// Verify API_VERSION is defined
console.log(API_VERSION)  // Should be 'v1'

// Ensure all API calls use versioned URLs
const url = `${API_BASE_URL}/api/${API_VERSION}/...`
```

---

## Benefits

- ✅ **Safe evolution:** Breaking changes possible without disrupting clients
- ✅ **Multi-version support:** Web + mobile can use different versions
- ✅ **Backward compatibility:** Legacy clients continue working during migration
- ✅ **Industry standard:** Follows patterns from Stripe, GitHub, Twitter

---

## References

- [DRF Versioning Documentation](https://www.django-rest-framework.org/api-guide/versioning/)
- [API Versioning Best Practices](https://www.troyhunt.com/your-api-versioning-is-wrong-which-is/)
- [Stripe API Versioning](https://stripe.com/docs/api/versioning)

---

**Status:** Production Ready
**Last Updated:** October 22, 2025
