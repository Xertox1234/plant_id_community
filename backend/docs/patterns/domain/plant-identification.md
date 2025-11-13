# Plant Identification API Integration Patterns

**Last Updated**: November 13, 2025
**Consolidated From**: `PLANT_ID_PATTERNS_CODIFIED.md`
**Status**: ✅ Production-Tested
**APIs**: Plant.id v3 + PlantNet v2

---

## Table of Contents

1. [API Error Response Handling](#api-error-response-handling)
2. [Environment Variable Configuration](#environment-variable-configuration)
3. [API URL Verification](#api-url-verification)
4. [Parameter Validation Patterns](#parameter-validation-patterns)
5. [Rate Limiting Strategies](#rate-limiting-strategies)
6. [Diagnostic Testing](#diagnostic-testing)
7. [Common Pitfalls](#common-pitfalls)

---

## API Error Response Handling

### Problem: Silent Failures in UI

**Issue**: Django API returns `{success: false, error: "message"}` but React UI doesn't display errors. Users see no feedback when identification fails.

**Root Cause**: React component only checked for truthy `data` object, not the `success` flag:

```javascript
// ❌ WRONG - Only checks if data exists
if (data) {
  setResults(data)  // Sets results even when success: false!
}
```

### Pattern: Explicit Success Flag Checking

**Location**: `web/src/pages/IdentifyPage.jsx`

```javascript
// ✅ CORRECT - Explicitly check success flag
const handleIdentify = async () => {
  try {
    const response = await fetch('/api/v1/plant-identification/identify/', {
      method: 'POST',
      body: formData
    });

    const data = await response.json();

    // Check success flag FIRST, before using data
    if (data.success === false || data.error) {
      console.log('[IdentifyPage] API returned error:', data.error);
      setError(data.error || 'Identification failed');
      setResults(null);  // Clear previous results
    } else {
      console.log('[IdentifyPage] Identification successful');
      setResults(data);
      setError(null);
    }
  } catch (error) {
    console.error('[IdentifyPage] Network error:', error);
    setError('Network error occurred');
    setResults(null);
  }
};
```

### Key Points

- ✅ Check `data.success === false` explicitly (not just falsy check)
- ✅ Handle both `data.error` (message) and `data.success` (boolean)
- ✅ Clear results when error occurs (`setResults(null)`)
- ✅ Log errors with bracketed prefix for filtering (`[ComponentName]`)
- ❌ Never assume truthy data means success

### Testing

```javascript
// Test error handling
const mockErrorResponse = {
  success: false,
  error: 'Plant.id API returned an error'
};

// Should display error, not set results
expect(setError).toHaveBeenCalledWith('Plant.id API returned an error');
expect(setResults).toHaveBeenCalledWith(null);
```

---

## Environment Variable Configuration

### Problem: API Keys Not Loading

**Issue**: API key exists in `.env` file but Django raises "PLANT_ID_API_KEY must be set in Django settings".

**Root Cause**: Environment variable not loaded into Django settings despite being in `.env`:

```python
# ❌ WRONG - Variable exists in .env but not loaded
# .env file:
PLANT_ID_API_KEY=MNvOarFi1z42chars...

# settings.py - MISSING:
# PLANT_ID_API_KEY = config('PLANT_ID_API_KEY')
```

### Pattern: python-decouple Configuration

**Location**: `backend/plant_community_backend/settings.py`

```python
# ✅ CORRECT - Use python-decouple to load from .env
from decouple import config

# Plant.id API (Kindwise) - Primary identification service
# Official docs: https://documenter.getpostman.com/view/24599534/2s93z5A4v2
PLANT_ID_API_KEY = config('PLANT_ID_API_KEY', default='')
PLANT_ID_API_BASE_URL = 'https://api.plant.id/v3'

# PlantNet API - Supplemental care instructions
# Official docs: https://my.plantnet.org/usage
PLANTNET_API_KEY = config('PLANTNET_API_KEY', default='')
PLANTNET_API_BASE_URL = 'https://my-api.plantnet.org/v2'
```

### Key Points

- ✅ Use `config('VAR_NAME', default='')` for all `.env` variables
- ✅ Include descriptive comment above config block
- ✅ Set sensible defaults (empty string for optional keys)
- ✅ Add official documentation URL in comment
- ❌ Never hardcode API keys in settings.py
- ❌ Never assume `.env` variables auto-load

### Validation Pattern

**Location**: `apps/plant_identification/services/plant_id_service.py`

```python
class PlantIDAPIService:
    def __init__(self):
        """Initialize Plant.id API service with key validation."""
        self.api_key = settings.PLANT_ID_API_KEY
        self.base_url = settings.PLANT_ID_API_BASE_URL

        # Validate API key is configured
        if not self.api_key:
            raise ImproperlyConfigured(
                "PLANT_ID_API_KEY must be set in Django settings. "
                "Add to .env file: PLANT_ID_API_KEY=your-key-here"
            )

        # Validate key format (50 characters for Plant.id)
        if len(self.api_key) < 40:
            raise ImproperlyConfigured(
                f"PLANT_ID_API_KEY appears invalid (too short: {len(self.api_key)} chars). "
                "Expected 40+ character key from https://admin.kindwise.com/"
            )

        logger.info(f"[PLANT_ID] Service initialized (key: {len(self.api_key)} chars)")
```

### Diagnostic Testing

```python
# Quick diagnostic in Django shell
from django.conf import settings

# Check if loaded
print(f"PLANT_ID_API_KEY loaded: {bool(settings.PLANT_ID_API_KEY)}")
print(f"Key length: {len(settings.PLANT_ID_API_KEY) if settings.PLANT_ID_API_KEY else 0}")

# Expected output:
# PLANT_ID_API_KEY loaded: True
# Key length: 50
```

---

## API URL Verification

### Problem: 400 Bad Request for All Images

**Issue**: Plant.id API returning 400 Bad Request for all valid images, even those working in Postman.

**Root Cause**: Using incorrect base URL structure:

```python
# ❌ WRONG - Incorrect domain structure
BASE_URL = "https://plant.id/api/v3"
# Results in: https://plant.id/api/v3/identification
# Actual endpoint: https://api.plant.id/v3/identification
```

### Pattern: Official Documentation First

**Research Process**:
1. Search for official documentation: "plant.id api documentation"
2. Verify base URL from Postman collection
3. Copy exact URL from "Base URL" section
4. Test with curl before integrating

**Official Documentation**: https://documenter.getpostman.com/view/24599534/2s93z5A4v2

### Correct Implementation

**Location**: `apps/plant_identification/services/plant_id_service.py`

```python
class PlantIDAPIService:
    """
    Plant.id API v3 integration.

    Official docs: https://documenter.getpostman.com/view/24599534/2s93z5A4v2
    Base URL: https://api.plant.id/v3 (per Postman docs)
    """

    def __init__(self):
        # ✅ CORRECT - Exact URL from official Postman docs
        self.base_url = "https://api.plant.id/v3"  # NOT plant.id/api/v3!
        self.api_key = settings.PLANT_ID_API_KEY

    def identify_plant(self, image_data: bytes) -> Dict[str, Any]:
        """
        Identify plant using Plant.id API v3.

        Endpoint: POST /identification
        Full URL: https://api.plant.id/v3/identification
        """
        url = f"{self.base_url}/identification"  # Correct: api.plant.id/v3/identification

        response = requests.post(
            url,
            json={
                'images': [base64.b64encode(image_data).decode()],
                'plant_details': ['common_names', 'taxonomy', 'wiki_description']
            },
            headers={'Api-Key': self.api_key},
            timeout=30
        )

        response.raise_for_status()
        return response.json()
```

### Key Points

- ✅ Find official documentation (Postman, OpenAPI, GitHub)
- ✅ Copy exact base URL from "Base URL" or "Host" section
- ✅ Verify endpoint path matches examples
- ✅ Add comment with doc URL for future reference
- ✅ Test with curl/Postman before integrating
- ❌ Never assume URL structure follows common patterns
- ❌ Don't rely on third-party wrappers/tutorials for URLs

### Verification Command

```bash
# Test Plant.id API directly
curl -X POST "https://api.plant.id/v3/identification" \
  -H "Api-Key: YOUR_KEY_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "images": ["base64_encoded_image"],
    "plant_details": ["common_names"]
  }'

# Should return 200 with plant suggestions
```

---

## Parameter Validation Patterns

### Problem 1: TypeError - BytesIO Length

**Issue**: `TypeError: object of type '_io.BytesIO' has no len()`

**Root Cause**: Passing single BytesIO object when PlantNet API expects list.

### Problem 2: Array Length Mismatch

**Issue**: `400 Bad Request: "images[] length and organs[] length must be equal"`

**Root Cause**: Sending 1 image with 4 organs `['flower', 'leaf', 'fruit', 'bark']`.

### Problem 3: Unsupported Parameters

**Issue**: `400 Bad Request: "include-related-images" is not allowed`

**Root Cause**: Using parameter not in API specification.

### Pattern: Minimal, Validated Parameters

**Location**: `apps/plant_identification/services/combined_identification_service.py`

**Anti-Pattern** ❌:
```python
# ❌ WRONG - Multiple issues
image_file = BytesIO(image_data)
result = self.plantnet.identify_plant(
    image_file,  # Single object, not list
    organs=['flower', 'leaf', 'fruit', 'bark'],  # 4 organs for 1 image
    include_related_images=True  # Unsupported parameter
)
```

**Correct Pattern** ✅:
```python
# ✅ CORRECT - All issues fixed
image_file = BytesIO(image_data)
result = self.plantnet.identify_plant(
    [image_file],  # Wrapped in list - PlantNet expects list
    organs=['leaf']  # One organ per image - using 'leaf' as most common
    # Note: include_related_images removed - not supported by PlantNet API
)
```

### Validation Rules

**Rule 1: Array Parameter Length Matching**
- ✅ Ensure arrays have same length: `len(images) == len(organs)`
- ✅ Use 1:1 mapping for single image: `[image]` + `['leaf']`
- ✅ Add comment explaining organ choice
- ❌ Never send multiple organs for single image

**Rule 2: API Parameter Validation**
Before adding any parameter:
1. ✅ Check official API documentation for allowed parameters
2. ✅ Remove parameters not explicitly documented
3. ✅ Test with minimal required parameters first
4. ✅ Add optional parameters one at a time
5. ❌ Don't assume logical parameters are supported
6. ❌ Don't copy parameters from other similar APIs

**Rule 3: List vs Single Object**
- ✅ Wrap single items: `[item]` not `item`
- ✅ Check parameter name for plural form (`images[]` = list)
- ✅ Read error messages for "expected list" hints
- ❌ Never pass single object when signature shows `List[T]`

### Error Message Patterns

```
"images[] length and organs[] length must be equal"
→ Array length mismatch, check parameter counts

"parameter X is not allowed"
→ Unsupported parameter, check API docs

"object of type 'X' has no len()"
→ Expected list, got single object
```

---

## Rate Limiting Strategies

### Problem: Blocked During Development

**Issue**: 10/hour rate limit blocking rapid testing during development, causing 403 Forbidden errors.

**Root Cause**: Production rate limit applied to development environment.

### Pattern: Environment-Aware Rate Limits

**Location**: `apps/plant_identification/constants.py`

**Anti-Pattern** ❌:
```python
# ❌ BAD - Same limit for all environments
RATE_LIMITS = {
    'anonymous': {
        'plant_identification': '10/h',  # Too strict for dev testing
    }
}
```

**Correct Pattern** ✅:
```python
# ✅ GOOD - Environment-aware limits
from django.conf import settings

RATE_LIMITS = {
    'anonymous': {
        # Development: 100/h (rapid testing)
        # Production: 10/h (cost control)
        'plant_identification': '100/h' if settings.DEBUG else '10/h',
    },
    'authenticated': {
        # Development: 1000/h (unlimited testing)
        # Production: 100/h (generous for paid users)
        'plant_identification': '1000/h' if settings.DEBUG else '100/h',
    }
}
```

### Key Points

- ✅ Use higher limits in development (10x-100x production)
- ✅ Document production limits in comments
- ✅ Use `settings.DEBUG` for environment detection
- ✅ Clear cache after changing limits
- ❌ Never deploy with dev rate limits to production

### Cache Clearing

**LocMemCache** (default):
```bash
# Restart Django server to clear in-memory cache
pkill -f "python manage.py runserver"
python manage.py runserver
```

**Redis Cache**:
```bash
# Clear all rate limit cache keys
redis-cli FLUSHALL

# Or clear specific pattern
redis-cli --eval "return redis.call('del', unpack(redis.call('keys', 'rl:*')))" 0
```

---

## Diagnostic Testing

### Problem: Multi-API Debugging Complexity

**Issue**: Multiple external APIs (Plant.id, PlantNet) make debugging difficult - unclear which service is failing.

### Pattern: Standalone Diagnostic Script

**Location**: `backend/test_api_services.py`

```python
#!/usr/bin/env python
"""
Diagnostic script for plant identification APIs.
Tests each service independently to isolate failures.

Usage:
    python test_api_services.py

Exit codes:
    0 - All services passed
    1 - One or more services failed
"""
import os
import sys
import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'plant_community_backend.settings')
django.setup()

from django.conf import settings
from apps.plant_identification.services.plant_id_service import PlantIDAPIService
from apps.plant_identification.services.plantnet_service import PlantNetAPIService

def test_plant_id():
    """Test Plant.id API configuration and connectivity."""
    print("\n=== Testing Plant.id API ===")

    # Check API key loaded
    api_key = getattr(settings, 'PLANT_ID_API_KEY', None)
    if not api_key:
        print("❌ PLANT_ID_API_KEY not set in settings")
        print("   Add to .env: PLANT_ID_API_KEY=your-key-here")
        return False

    print(f"✅ API key loaded ({len(api_key)} chars)")

    # Check key format
    if len(api_key) < 40:
        print(f"⚠️  API key seems short ({len(api_key)} chars, expected 40+)")

    # Try to initialize service
    try:
        service = PlantIDAPIService()
        print("✅ Service initialized successfully")
        print(f"   Base URL: {service.base_url}")
        return True
    except Exception as e:
        print(f"❌ Service initialization failed: {type(e).__name__}")
        print(f"   Error: {e}")
        return False

def test_plantnet():
    """Test PlantNet API configuration and connectivity."""
    print("\n=== Testing PlantNet API ===")

    # Check API key loaded
    api_key = getattr(settings, 'PLANTNET_API_KEY', None)
    if not api_key:
        print("❌ PLANTNET_API_KEY not set in settings")
        print("   Add to .env: PLANTNET_API_KEY=your-key-here")
        return False

    print(f"✅ API key loaded ({len(api_key)} chars)")

    # Try to initialize service
    try:
        service = PlantNetAPIService()
        print("✅ Service initialized successfully")
        print(f"   Base URL: {service.base_url}")
        return True
    except Exception as e:
        print(f"❌ Service initialization failed: {type(e).__name__}")
        print(f"   Error: {e}")
        return False

def main():
    """Run all diagnostic tests."""
    print("=" * 60)
    print("Plant Identification API Diagnostic")
    print("=" * 60)

    results = {
        'Plant.id': test_plant_id(),
        'PlantNet': test_plantnet(),
    }

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    for service, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {service}")

    print("=" * 60)

    # Exit code: 0 if all passed, 1 if any failed
    exit_code = 0 if all(results.values()) else 1
    sys.exit(exit_code)

if __name__ == '__main__':
    main()
```

### Usage

```bash
cd /Users/williamtower/projects/plant_id_community/backend
python test_api_services.py

# Example output:
# ============================================================
# Plant Identification API Diagnostic
# ============================================================
#
# === Testing Plant.id API ===
# ✅ API key loaded (50 chars)
# ✅ Service initialized successfully
#    Base URL: https://api.plant.id/v3
#
# === Testing PlantNet API ===
# ✅ API key loaded (26 chars)
# ✅ Service initialized successfully
#    Base URL: https://my-api.plantnet.org/v2
#
# ============================================================
# Summary
# ============================================================
# ✅ PASS - Plant.id
# ✅ PASS - PlantNet
# ============================================================
```

### Key Points

- ✅ Create standalone diagnostic script in `backend/` root
- ✅ Test each service independently (no dependencies)
- ✅ Check configuration first (API keys, base URLs)
- ✅ Attempt service initialization
- ✅ Use emoji status indicators (✅/❌) for quick scanning
- ✅ Print summary at end
- ✅ Exit with non-zero code on failure (CI/CD integration)
- ✅ Make script executable: `chmod +x test_api_services.py`

---

## Common Pitfalls

### Pitfall 1: Assuming Truthy Data Means Success

**Problem**:
```javascript
// ❌ BAD
if (data) {
  setResults(data);  // Even if data.success === false!
}
```

**Solution**: Always check `data.success === false` explicitly.

---

### Pitfall 2: Not Loading Environment Variables

**Problem**:
```python
# ❌ BAD - Missing in settings.py
# .env file has key, but Django doesn't load it
PLANT_ID_API_KEY=abc123
```

**Solution**: Add `config('PLANT_ID_API_KEY')` to settings.py.

---

### Pitfall 3: Incorrect Base URL Structure

**Problem**:
```python
# ❌ BAD - Wrong domain
BASE_URL = "https://plant.id/api/v3"
# Actual: https://api.plant.id/v3
```

**Solution**: Verify against official documentation, not assumptions.

---

### Pitfall 4: Array Length Mismatch

**Problem**:
```python
# ❌ BAD - 1 image, 4 organs
plantnet.identify([image], organs=['flower', 'leaf', 'fruit', 'bark'])
```

**Solution**: Match array lengths: 1 image = 1 organ.

---

### Pitfall 5: Production Rate Limits in Development

**Problem**:
```python
# ❌ BAD - Blocks rapid testing
RATE_LIMIT = '10/h'  # Same for dev and prod
```

**Solution**: Use environment-aware limits with `settings.DEBUG`.

---

## Deployment Checklist

### Pre-Deployment

**Configuration**:
- [ ] API keys loaded in settings.py with `config()`
- [ ] Base URLs match official documentation
- [ ] Rate limits set appropriately (10/h for anonymous, 100/h for auth)
- [ ] Diagnostic script passes all tests

**Code Review**:
- [ ] React components check `data.success === false` explicitly
- [ ] API parameters validated against official docs
- [ ] Array lengths match (images vs organs)
- [ ] Unsupported parameters removed

**Testing**:
- [ ] Test with 3+ different plant species
- [ ] Test error handling (blurry images, network failures)
- [ ] Verify both Plant.id and PlantNet return results
- [ ] Check cache is working (same image = instant response)
- [ ] Run diagnostic script - all services should pass

---

## Summary

These plant identification patterns ensure:

1. ✅ **Error Visibility**: Explicit `success` flag checking in React
2. ✅ **Configuration**: Proper `.env` loading with python-decouple
3. ✅ **URL Accuracy**: Base URLs verified against official docs
4. ✅ **Parameter Validation**: Arrays matched, unsupported params removed
5. ✅ **Development Flow**: Environment-aware rate limits
6. ✅ **Diagnostics**: Standalone testing script for quick debugging

**Result**: Production-ready plant identification with dual API integration (Plant.id + PlantNet).

---

## Related Patterns

- **Caching**: See `architecture/caching.md` for response caching
- **Rate Limiting**: See `architecture/rate-limiting.md` for advanced patterns
- **Services**: See `architecture/services.md` for parallel API processing

---

**Last Reviewed**: November 13, 2025
**Pattern Count**: 6 plant identification patterns
**Status**: ✅ Production-validated
**Official Docs**: Plant.id (https://documenter.getpostman.com/view/24599534/2s93z5A4v2), PlantNet (https://my.plantnet.org/usage)
