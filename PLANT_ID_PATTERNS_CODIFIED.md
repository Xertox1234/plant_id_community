# Plant Identification Patterns Codified

**Date**: November 1, 2025
**Context**: Fixing completely non-functional plant identification feature
**Result**: Full end-to-end functionality restored with Plant.id + PlantNet dual API integration

---

## Critical Directory Structure

**IMPORTANT**: Files have been moved from root to subdirectories:

- **Active Backend**: `/Users/williamtower/projects/plant_id_community/backend/`
- **Active Frontend**: `/Users/williamtower/projects/plant_id_community/web/`
- **Old Location**: Root directory (deprecated)

All file paths in this document reflect the new structure.

---

## Pattern 1: API Error Response Handling in React

### Problem
UI not displaying errors when Django API returns `{success: false, error: "message"}`. Users saw no feedback when identification failed.

### Root Cause
React component only checked for truthy `data` object, not the `success` flag within it:
```javascript
// ❌ WRONG - Only checks if data exists
if (data) {
  setResults(data)
}
```

### Solution
**File**: `web/src/pages/IdentifyPage.jsx` (lines 51-57)
```javascript
// ✅ CORRECT - Explicitly check success flag
if (data.success === false || data.error) {
  console.log('[IdentifyPage] API returned error:', data.error)
  setError(data.error || 'Identification failed')
  setResults(null)
} else {
  setResults(data)
}
```

### Pattern Rule
**When integrating with Django REST Framework APIs:**
- ✅ Always check `success` flag explicitly (`data.success === false`)
- ✅ Handle both `data.error` (error message) and `data.success` (boolean flag)
- ✅ Clear results state when error occurs (`setResults(null)`)
- ✅ Log errors with bracketed prefix for filtering (`[ComponentName]`)
- ❌ Never assume truthy data means success

### Code Review Checklist
- [ ] Does the component check `data.success === false`?
- [ ] Does it handle `data.error` for error messages?
- [ ] Are results cleared when errors occur?
- [ ] Is error logging present with component prefix?

---

## Pattern 2: Django Settings Environment Variable Loading

### Problem
API key present in `.env` file but Django raising "PLANT_ID_API_KEY must be set in Django settings".

### Root Cause
Environment variable not loaded into Django settings despite being in `.env`:
```python
# ❌ WRONG - Variable exists in .env but not loaded
# .env has: PLANT_ID_API_KEY=MNvOarFi1z...
# settings.py missing: PLANT_ID_API_KEY = config(...)
```

### Solution
**File**: `backend/plant_community_backend/settings.py` (lines 728-730)
```python
# ✅ CORRECT - Use python-decouple to load from .env
from decouple import config

# Plant.id API (Kindwise) - Primary identification service
PLANT_ID_API_KEY = config('PLANT_ID_API_KEY', default='')
PLANT_ID_API_BASE_URL = 'https://api.plant.id/v3'
```

### Pattern Rule
**For all external API configurations:**
- ✅ Use `config('VAR_NAME', default='')` for all `.env` variables
- ✅ Include descriptive comment above config block
- ✅ Set sensible defaults (empty string for optional, raise error for required)
- ✅ Verify with diagnostic script after adding
- ❌ Never hardcode API keys in settings.py
- ❌ Never assume `.env` variables auto-load

### Code Review Checklist
- [ ] Is `from decouple import config` imported?
- [ ] Does each API key use `config('KEY_NAME', default='')`?
- [ ] Are required keys validated at startup (raise if missing)?
- [ ] Is there a comment explaining what the API is for?

### Diagnostic Pattern
```python
# Test API key loading
from django.conf import settings
print(f"PLANT_ID_API_KEY loaded: {bool(settings.PLANT_ID_API_KEY)}")
print(f"Length: {len(settings.PLANT_ID_API_KEY) if settings.PLANT_ID_API_KEY else 0}")
```

---

## Pattern 3: API URL Verification Against Official Docs

### Problem
Plant.id API returning 400 Bad Request for all valid images.

### Root Cause
Using incorrect base URL structure:
```python
# ❌ WRONG - Incorrect domain structure
BASE_URL = "https://plant.id/api/v3"
# Results in: https://plant.id/api/v3/identification
```

### Solution
**File**: `backend/apps/plant_identification/services/plant_id_service.py` (line 71)
```python
# ✅ CORRECT - Per official Postman docs
BASE_URL = "https://api.plant.id/v3"  # Correct URL format per official docs
# Results in: https://api.plant.id/v3/identification
```

**Official Documentation**: https://documenter.getpostman.com/view/24599534/2s93z5A4v2

### Pattern Rule
**When debugging 400/404 errors from external APIs:**
1. ✅ Find official documentation (Postman, OpenAPI, GitHub)
2. ✅ Copy exact base URL from "Base URL" or "Host" section
3. ✅ Verify endpoint path matches examples
4. ✅ Add comment with doc URL for future reference
5. ❌ Never assume URL structure follows common patterns
6. ❌ Don't rely on third-party wrappers/tutorials for URLs

### Research Process
```bash
# 1. Find official docs
google "plant.id api documentation"
# Official: https://documenter.getpostman.com/view/24599534/2s93z5A4v2

# 2. Verify base URL
# Postman shows: "https://api.plant.id/v3"

# 3. Check example request
# Example: POST https://api.plant.id/v3/identification

# 4. Update code with exact URL
BASE_URL = "https://api.plant.id/v3"
```

### Code Review Checklist
- [ ] Is base URL copied from official documentation?
- [ ] Is there a comment with documentation URL?
- [ ] Does the full endpoint match official examples?
- [ ] Have you tested with curl/Postman before integrating?

---

## Pattern 4: PlantNet API Parameter Validation

### Problem 1: TypeError - `object of type '_io.BytesIO' has no len()`
**Root Cause**: Passing single BytesIO object when API expects list

### Problem 2: 400 Bad Request - `"include-related-images" is not allowed`
**Root Cause**: Using parameter not in API specification

### Problem 3: 400 Bad Request - `"images[] length and organs[] length must be equal"`
**Root Cause**: Sending 1 image with 4 organs `['flower', 'leaf', 'fruit', 'bark']`

### Solution
**File**: `backend/apps/plant_identification/services/combined_identification_service.py` (lines 298-304)

```python
# ❌ WRONG - Multiple issues
image_file = BytesIO(image_data)
result = self.plantnet.identify_plant(
    image_file,  # Single object, not list
    organs=['flower', 'leaf', 'fruit', 'bark'],  # 4 organs for 1 image
    include_related_images=True  # Unsupported parameter
)

# ✅ CORRECT - All issues fixed
image_file = BytesIO(image_data)
result = self.plantnet.identify_plant(
    [image_file],  # Wrapped in list - PlantNet expects list
    organs=['leaf']  # One organ per image - using 'leaf' as most common
    # Note: include_related_images removed - not supported by PlantNet API
)
```

### Pattern Rules

#### Rule 4.1: Array Parameter Length Matching
**When API requires paired arrays (images + organs):**
- ✅ Ensure arrays have same length: `len(images) == len(organs)`
- ✅ Use 1:1 mapping for single image: `[image]` + `['leaf']`
- ✅ Add comment explaining organ choice
- ❌ Never send multiple organs for single image

#### Rule 4.2: API Parameter Validation
**Before adding any parameter:**
1. ✅ Check official API documentation for allowed parameters
2. ✅ Remove parameters not explicitly documented
3. ✅ Test with minimal required parameters first
4. ✅ Add optional parameters one at a time
5. ❌ Don't assume logical parameters are supported
6. ❌ Don't copy parameters from other similar APIs

#### Rule 4.3: List vs Single Object
**When API expects list/array:**
- ✅ Wrap single items: `[item]` not `item`
- ✅ Check parameter name for plural form (`images[]` = list)
- ✅ Read error messages for "expected list" hints
- ❌ Never pass single object when signature shows `List[T]`

### Code Review Checklist
- [ ] Are paired array parameters same length?
- [ ] Are all parameters documented in official API spec?
- [ ] Are single items wrapped in lists when needed?
- [ ] Is there a comment explaining parameter choices?
- [ ] Have you tested with minimal parameters first?

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

## Pattern 5: Rate Limiting for Development vs Production

### Problem
10/hour rate limit blocking rapid testing during development, causing 403 Forbidden errors.

### Root Cause
Production rate limit applied to development environment:
```python
# ❌ WRONG - Same limit for all environments
RATE_LIMITS = {
    'anonymous': {
        'plant_identification': '10/h',  # Too strict for dev testing
    }
}
```

### Solution
**File**: `backend/apps/plant_identification/constants.py` (line 143)
```python
# ✅ CORRECT - Relaxed for development
RATE_LIMITS = {
    'anonymous': {
        'plant_identification': '100/h',  # Increased for development testing (was 10/h)
    }
}
```

### Pattern Rule
**For all rate-limited endpoints:**
- ✅ Use higher limits in development (10x-100x production)
- ✅ Document original production limit in comment
- ✅ Add inline comment explaining it's for development
- ✅ Use environment-aware limits if possible:
  ```python
  from django.conf import settings
  limit = '100/h' if settings.DEBUG else '10/h'
  ```
- ✅ Clear cache after changing limits (LocMemCache persists until restart)
- ❌ Never deploy with dev rate limits to production

### Testing Pattern
```bash
# Clear rate limit cache (LocMemCache)
# Restart Django server to clear in-memory cache
pkill -f "python manage.py runserver"
python manage.py runserver

# Or switch to Redis cache for instant clearing
redis-cli FLUSHALL
```

### Code Review Checklist
- [ ] Are dev rate limits documented with comments?
- [ ] Is original production limit preserved in comment?
- [ ] Will limits be changed before production deployment?
- [ ] Is cache clearing documented for limit changes?

---

## Pattern 6: Diagnostic Scripts for Multi-API Systems

### Problem
Multiple external APIs (Plant.id, PlantNet, Trefle) make debugging difficult - unclear which service is failing.

### Solution
Create diagnostic script to test each API independently.

**File**: `backend/test_api_services.py` (example)
```python
#!/usr/bin/env python
"""
Diagnostic script for plant identification APIs.
Tests each service independently to isolate failures.
"""
import os
import sys
import django

# Setup Django environment
sys.path.insert(0, '/Users/williamtower/projects/plant_id_community/backend')
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
        return False
    print(f"✅ API key loaded ({len(api_key)} chars)")

    # Try to initialize service
    try:
        service = PlantIDAPIService()
        print("✅ Service initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Service initialization failed: {e}")
        return False

def test_plantnet():
    """Test PlantNet API configuration and connectivity."""
    print("\n=== Testing PlantNet API ===")

    # Check API key loaded
    api_key = getattr(settings, 'PLANTNET_API_KEY', None)
    if not api_key:
        print("❌ PLANTNET_API_KEY not set in settings")
        return False
    print(f"✅ API key loaded ({len(api_key)} chars)")

    # Try to initialize service
    try:
        service = PlantNetAPIService()
        print("✅ Service initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Service initialization failed: {e}")
        return False

if __name__ == '__main__':
    results = {
        'Plant.id': test_plant_id(),
        'PlantNet': test_plantnet(),
    }

    print("\n=== Summary ===")
    for service, success in results.items():
        status = "✅" if success else "❌"
        print(f"{status} {service}")

    # Exit code: 0 if all passed, 1 if any failed
    sys.exit(0 if all(results.values()) else 1)
```

### Usage
```bash
cd /Users/williamtower/projects/plant_id_community/backend
python test_api_services.py

# Example output:
# === Testing Plant.id API ===
# ✅ API key loaded (42 chars)
# ✅ Service initialized successfully
#
# === Testing PlantNet API ===
# ✅ API key loaded (26 chars)
# ✅ Service initialized successfully
#
# === Summary ===
# ✅ Plant.id
# ✅ PlantNet
```

### Pattern Rule
**For systems with 3+ external service integrations:**
- ✅ Create standalone diagnostic script in `backend/` root
- ✅ Test each service independently (no dependencies)
- ✅ Check configuration first (API keys, base URLs)
- ✅ Attempt service initialization
- ✅ Use emoji status indicators (✅/❌) for quick scanning
- ✅ Print summary at end
- ✅ Exit with non-zero code on failure (CI/CD integration)
- ✅ Make script executable: `chmod +x test_api_services.py`

### Diagnostic Components
```python
# 1. Environment Setup
import django
django.setup()

# 2. Configuration Checks
api_key = getattr(settings, 'API_KEY', None)
if not api_key:
    print("❌ API_KEY not set")

# 3. Service Initialization
try:
    service = APIService()
    print("✅ Service initialized")
except Exception as e:
    print(f"❌ Failed: {e}")

# 4. Summary Report
results = {'Service1': True, 'Service2': False}
for service, success in results.items():
    print(f"{'✅' if success else '❌'} {service}")

# 5. Exit Code
sys.exit(0 if all(results.values()) else 1)
```

### Code Review Checklist
- [ ] Does diagnostic test each service independently?
- [ ] Are configuration checks performed first?
- [ ] Is output easy to scan (emoji, clear sections)?
- [ ] Does script exit with proper status code?
- [ ] Is script documented with usage examples?

---

## Combined Pattern: End-to-End API Integration Debugging

### Debugging Workflow
When plant identification completely fails ("does nothing at all"):

1. **Frontend First** - Check browser console
   ```javascript
   // Add logging to button click handler
   console.log('[IdentifyPage] Button clicked')
   console.log('[IdentifyPage] API response:', data)
   ```

2. **API Response** - Check for `success: false`
   ```javascript
   if (data.success === false || data.error) {
     setError(data.error)
   }
   ```

3. **Backend Logs** - Check Django output
   ```bash
   tail -f /tmp/django_restart.log | grep ERROR
   ```

4. **Configuration** - Run diagnostic script
   ```bash
   python test_api_services.py
   ```

5. **Environment Variables** - Verify `.env` loaded
   ```python
   from django.conf import settings
   print(settings.PLANT_ID_API_KEY)
   ```

6. **API URLs** - Verify against official docs
   ```python
   # Check service file for base URL
   # Compare with official documentation
   ```

7. **Parameters** - Test with minimal payload
   ```python
   # Start with required parameters only
   # Add optional parameters one at a time
   ```

8. **Rate Limits** - Check and increase for dev
   ```python
   # Increase in constants.py
   # Restart server to clear LocMemCache
   ```

### Success Criteria
- ✅ Button click triggers API call (console logs)
- ✅ API response includes `success: true` or `success: false`
- ✅ Errors display in UI with clear messages
- ✅ Backend logs show no exceptions
- ✅ Diagnostic script reports all services ✅
- ✅ Plant identified correctly (verify with known species)

---

## File Reference

### Backend Files Modified
- `backend/plant_community_backend/settings.py` (lines 728-730)
  - Added Plant.id API configuration with `config()`

- `backend/apps/plant_identification/services/plant_id_service.py` (line 71)
  - Corrected base URL to `https://api.plant.id/v3`

- `backend/apps/plant_identification/services/combined_identification_service.py` (lines 298-304)
  - Fixed PlantNet parameter validation (list wrapping, organ matching)

- `backend/apps/plant_identification/constants.py` (line 143)
  - Increased rate limit to 100/h for development

### Frontend Files Modified
- `web/src/pages/IdentifyPage.jsx` (lines 51-57)
  - Added explicit `success: false` checking

### Configuration Files
- `backend/.env`
  - Contains: `PLANT_ID_API_KEY=MNvOarFi1z...`
  - Contains: `PLANTNET_API_KEY=2b10BRvewU0u3JbgK53CnaBWvu`

---

## Testing Checklist

Before deploying plant identification changes:

- [ ] Test with clear, well-lit plant images (3+ different species)
- [ ] Test with unclear/blurry images (should show error message)
- [ ] Verify both Plant.id and PlantNet return results
- [ ] Check console for any errors or warnings
- [ ] Verify rate limiting doesn't block legitimate requests
- [ ] Run diagnostic script - all services should pass
- [ ] Test error display for network failures
- [ ] Verify results display correctly in UI
- [ ] Check cache is working (same image = instant response)

---

## Related Documentation

- Official Plant.id API Docs: https://documenter.getpostman.com/view/24599534/2s93z5A4v2
- PlantNet API Docs: https://my.plantnet.org/usage
- Django python-decouple: https://pypi.org/project/python-decouple/
- Django Rate Limiting: https://django-ratelimit.readthedocs.io/

---

## Appendix: Common Error Messages

### Frontend Errors
```
"Identification Failed / Unable to identify plant. Please try a clearer image."
→ API returned success: false, check backend logs

"Network error occurred"
→ Frontend can't reach backend, check CORS/server status

"Rate limit exceeded"
→ Too many requests, increase limit in constants.py for dev
```

### Backend Errors
```
"PLANT_ID_API_KEY must be set in Django settings"
→ Missing config() call in settings.py

"object of type '_io.BytesIO' has no len()"
→ Wrap single object in list: [item]

"images[] length and organs[] length must be equal"
→ Match array lengths: 1 image = 1 organ

"parameter X is not allowed"
→ Remove unsupported parameter, check API docs

400 Bad Request (all images)
→ Verify base URL against official documentation
```

---

**End of Pattern Documentation**
