---
status: pending
priority: p2
issue_id: "090"
tags: [testing, api, routing, versioning, bug]
dependencies: []
estimated_effort: "4-6 hours"
---

# Fix API Versioning Test Failures

## Problem Statement

21 API tests are failing with "Invalid version in URL path. Does not match any version namespace" errors. This indicates a routing configuration issue where the test client is not properly including API version prefixes in URLs.

## Findings

**Discovered**: November 2, 2025 during post-dependency-update test verification
**Scope**: 21 failing tests in `apps/plant_identification/test_api.py`
**Impact**: API tests cannot verify endpoint functionality

**Error Pattern**:
```
NotFound: Invalid version in URL path. Does not match any version namespace.
```

**Affected Test Classes**:
1. `TestAPIAuthentication` - 2 failures
   - `test_token_refresh`
   - `test_unauthorized_access_protection`

2. `TestAPIErrorHandling` - 3 failures
   - `test_invalid_image_upload`
   - `test_missing_required_fields`
   - `test_non_existent_resource_404`

3. `TestAPIPerformance` - 1 failure
   - `test_search_functionality`

4. `TestCareInstructionsAPI` - 3 failures
   - `test_get_care_instructions_by_species`
   - `test_list_user_saved_care_instructions`
   - `test_save_care_instructions_to_profile`

5. `TestDiseasesDiagnosisAPI` - 2 failures
   - `test_create_disease_diagnosis_request`
   - `test_disease_diagnosis_with_api`

6. `TestPlantIdentificationAPI` - 5 failures
   - `test_create_identification_request_authenticated`
   - `test_create_identification_request_unauthenticated`
   - `test_get_identification_request_detail`
   - `test_plant_identification_workflow`
   - `test_user_can_only_access_own_requests`

**Example URL Patterns Failing**:
- `/api/auth/token/refresh/` (should be `/api/v1/auth/token/refresh/`)
- `/api/plant-identification/requests/` (should be `/api/v1/plant-identification/requests/`)
- `/api/plant-identification/species/` (should be `/api/v1/plant-identification/species/`)

## Root Cause Analysis

**Hypothesis 1**: Tests using `self.client.get('/api/...')` instead of versioned URLs
**Hypothesis 2**: `APIClient` not configured with default version
**Hypothesis 3**: URL routing configuration changed but tests not updated

**Current URL Configuration** (from `backend/plant_community_backend/urls.py`):
```python
# API versioning via NamespaceVersioning
urlpatterns = [
    path('api/v1/', include(('apps.plant_identification.urls', 'v1'))),
    path('api/v2/', include(('apps.blog.api.urls', 'v2'))),
]
```

**Test Client Usage** (from failing tests):
```python
# WRONG - Missing version prefix
response = self.client.post('/api/plant-identification/requests/', data=data)

# CORRECT - With version prefix
response = self.client.post('/api/v1/plant-identification/requests/', data=data)
```

## Proposed Solutions

### Option 1: Fix Test URLs (Recommended)
Update all test files to use versioned URLs.

**Implementation**:
```python
# In test_api.py, add a helper method
class BaseAPITestCase(APITestCase):
    def api_url(self, path):
        """Helper to add version prefix to API URLs."""
        if not path.startswith('/api/v'):
            path = path.replace('/api/', '/api/v1/')
        return path

    def get(self, path, **kwargs):
        return self.client.get(self.api_url(path), **kwargs)

    def post(self, path, **kwargs):
        return self.client.post(self.api_url(path), **kwargs)

# Then update all test classes to inherit from BaseAPITestCase
class TestPlantIdentificationAPI(BaseAPITestCase):
    def test_create_identification_request(self):
        # Old: self.client.post('/api/plant-identification/requests/', ...)
        # New: self.post('/api/plant-identification/requests/', ...)
        response = self.post('/api/plant-identification/requests/', data=data)
```

**Pros**:
- Fixes all tests systematically
- Adds helper for future tests
- Centralized version management
- Minimal code changes

**Cons**:
- Requires updating all 21 failing tests
- Needs thorough verification

**Effort**: 4-6 hours
**Risk**: Low

### Option 2: Configure Default API Version
Set default version in test settings or APIClient configuration.

**Implementation**:
```python
# In test_api.py setUp() method
class TestPlantIdentificationAPI(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.default_format = 'json'
        # Add version to all requests
        self.client.defaults['HTTP_ACCEPT'] = 'application/json; version=v1'
```

**Pros**:
- No URL changes needed
- Single configuration point

**Cons**:
- Relies on header-based versioning (may not work with NamespaceVersioning)
- Less explicit than URL-based versioning
- Doesn't match production URL structure

**Effort**: 2-3 hours
**Risk**: Medium (may not work with current routing)

### Option 3: Add URL Rewriting Middleware for Tests
Create test middleware to automatically add version prefix.

**Implementation**:
```python
# In apps/core/middleware/test_middleware.py
class TestAPIVersionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/api/') and not request.path.startswith('/api/v'):
            # Rewrite /api/foo to /api/v1/foo
            request.path = request.path.replace('/api/', '/api/v1/', 1)
            request.path_info = request.path
        return self.get_response(request)

# In test settings
MIDDLEWARE = [
    'apps.core.middleware.test_middleware.TestAPIVersionMiddleware',
    # ... other middleware
]
```

**Pros**:
- Zero test changes needed
- Automatic for all tests

**Cons**:
- Adds complexity
- Tests don't match production URLs
- Masks the real issue

**Effort**: 2 hours
**Risk**: Medium (could hide real routing problems)

## Recommended Action

**Option 1** - Fix test URLs with helper methods.

**Rationale**:
1. Makes tests match production URL structure
2. Explicit and clear
3. Prevents future versioning issues
4. Best practice for API versioning tests

**Implementation Plan**:

### Phase 1: Create Base Test Class (1 hour)
```python
# In apps/plant_identification/tests/base.py
from rest_framework.test import APITestCase

class VersionedAPITestCase(APITestCase):
    """Base test class with API versioning support."""

    API_VERSION = 'v1'

    def versioned_url(self, path):
        """Add version prefix to API URLs."""
        if path.startswith('/api/') and not path.startswith('/api/v'):
            return path.replace('/api/', f'/api/{self.API_VERSION}/')
        return path

    def get(self, path, **kwargs):
        """GET request with automatic versioning."""
        return self.client.get(self.versioned_url(path), **kwargs)

    def post(self, path, data=None, **kwargs):
        """POST request with automatic versioning."""
        return self.client.post(self.versioned_url(path), data=data, **kwargs)

    def put(self, path, data=None, **kwargs):
        """PUT request with automatic versioning."""
        return self.client.put(self.versioned_url(path), data=data, **kwargs)

    def patch(self, path, data=None, **kwargs):
        """PATCH request with automatic versioning."""
        return self.client.patch(self.versioned_url(path), data=data, **kwargs)

    def delete(self, path, **kwargs):
        """DELETE request with automatic versioning."""
        return self.client.delete(self.versioned_url(path), **kwargs)
```

### Phase 2: Update Test Classes (2-3 hours)
1. Import `VersionedAPITestCase`
2. Update class inheritance:
   ```python
   # Old
   class TestPlantIdentificationAPI(APITestCase):

   # New
   from apps.plant_identification.tests.base import VersionedAPITestCase
   class TestPlantIdentificationAPI(VersionedAPITestCase):
   ```
3. Replace `self.client.METHOD` with `self.METHOD`:
   ```python
   # Old
   response = self.client.post('/api/plant-identification/requests/', data=data)

   # New
   response = self.post('/api/plant-identification/requests/', data=data)
   ```

### Phase 3: Verification (1 hour)
```bash
# Run failing tests to verify fix
python manage.py test apps.plant_identification.test_api.TestAPIAuthentication --keepdb -v 2
python manage.py test apps.plant_identification.test_api.TestAPIErrorHandling --keepdb -v 2
python manage.py test apps.plant_identification.test_api.TestCareInstructionsAPI --keepdb -v 2
python manage.py test apps.plant_identification.test_api.TestDiseasesDiagnosisAPI --keepdb -v 2
python manage.py test apps.plant_identification.test_api.TestPlantIdentificationAPI --keepdb -v 2

# All tests should pass
python manage.py test apps.plant_identification --keepdb
```

### Phase 4: Documentation (30 minutes)
Update testing documentation:
- Add to `backend/docs/development/TESTING_GUIDE.md`
- Document `VersionedAPITestCase` usage
- Add examples for future test authors

## Technical Details

**Files to Modify**:
1. `backend/apps/plant_identification/tests/base.py` (NEW)
2. `backend/apps/plant_identification/test_api.py` (21 test methods)
3. `backend/docs/development/TESTING_GUIDE.md` (documentation)

**API Versioning Configuration**:
- **Strategy**: `rest_framework.versioning.NamespaceVersioning`
- **Current Version**: `v1`
- **URL Pattern**: `/api/v1/<endpoint>/`
- **Blog API**: Uses `v2` (`/api/v2/blog-*`)

**Related Files**:
- `backend/plant_community_backend/urls.py` - Main URL routing
- `backend/apps/plant_identification/urls.py` - Plant ID API URLs
- `backend/plant_community_backend/settings.py` - DRF versioning config

## Acceptance Criteria

- [ ] Create `VersionedAPITestCase` base class
- [ ] Update all 21 failing tests to use new base class
- [ ] All `TestAPIAuthentication` tests pass (2 tests)
- [ ] All `TestAPIErrorHandling` tests pass (3 tests)
- [ ] All `TestAPIPerformance` tests pass (1 test)
- [ ] All `TestCareInstructionsAPI` tests pass (3 tests)
- [ ] All `TestDiseasesDiagnosisAPI` tests pass (2 tests)
- [ ] All `TestPlantIdentificationAPI` tests pass (5 tests)
- [ ] Full test suite passes: `python manage.py test apps.plant_identification --keepdb`
- [ ] Documentation updated with versioning best practices
- [ ] No regression in other test suites

## Work Log

### 2025-11-02 - Test Failure Discovery
**By:** Dependency Update Verification Process
**Actions:**
- Ran full test suite after merging 27 dependency updates
- Identified 21 API tests failing with versioning errors
- Analyzed error patterns and root cause
- Determined failures are pre-existing (not from dependency updates)
- Created TODO for systematic fix

**Analysis**:
- All failures follow same pattern: "Invalid version in URL path"
- Tests were written without version prefix in URLs
- Likely existed before dependency updates but not caught in CI
- Not a blocker for dependency updates (isolated to tests)

**Priority**: P2 (Medium-High)
- Tests are critical for API reliability
- But doesn't block production deployment
- Should be fixed before next major API changes

## Resources

- DRF Versioning: https://www.django-rest-framework.org/api-guide/versioning/
- Testing APIs: https://www.django-rest-framework.org/api-guide/testing/
- API Versioning Best Practices: https://restfulapi.net/versioning/

## Notes

**Why This Matters**:
- API tests verify critical functionality (auth, plant ID, disease diagnosis)
- Without working tests, can't verify API changes safely
- Versioning errors could indicate routing configuration issues

**Not Urgent Because**:
- Production API works correctly (tests use wrong URLs, not production)
- Manual testing shows APIs functional
- Only affects test suite, not user-facing features

**Future Prevention**:
- Add pre-commit hook to check test URL patterns
- Include API versioning in test templates
- CI should catch these before merge (investigate why it didn't)
