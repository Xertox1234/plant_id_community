# Enterprise-Class Logging Implementation Plan

**Status**: Phase 1 Complete ✅ | Phase 2-5 In Progress
**Branch**: `feature/enterprise-logging`
**Started**: October 31, 2025
**Last Updated**: October 31, 2025

## Executive Summary

Implement production-grade structured logging with distributed tracing across React frontend and Django backend, eliminating all 38 console.log and 42 print() statements while providing enterprise-class monitoring and debugging capabilities.

## Requirements (From User Questionnaire)

✅ **Logging Platform**: Sentry (already integrated)
✅ **Log Format**: JSON structured logs with context fields
✅ **Log Levels**: DEBUG, WARNING, ERROR (INFO implicit)
✅ **Distributed Tracing**: Full request ID correlation across frontend/backend

## Current Infrastructure

### Already Installed (Backend)
- ✅ `python-json-logger==4.0.0` - JSON logging formatter
- ✅ `django-request-id==1.0.0` - Request ID middleware
- ✅ `sentry-sdk==2.42.1` - Error tracking
- ✅ JSON formatter configured in `settings.py:792-796`
- ✅ Request ID header: `X-Request-ID` (settings.py:762)

### Already Installed (Frontend)
- ✅ `@sentry/react@10.22.0` - Error tracking
- ✅ Basic logger utility at `web/src/utils/logger.js`

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      FRONTEND (React)                        │
├─────────────────────────────────────────────────────────────┤
│ 1. Generate Request ID (UUID v4)                            │
│ 2. Store in React Context                                   │
│ 3. Log with structured context                              │
│    → logger.error({requestId, userId, component, error})    │
│ 4. Send to Sentry with breadcrumbs                          │
│ 5. Pass X-Request-ID header to backend                      │
└─────────────────────────────────────────────────────────────┘
                             │
                    HTTP Header: X-Request-ID
                             ↓
┌─────────────────────────────────────────────────────────────┐
│                      BACKEND (Django)                        │
├─────────────────────────────────────────────────────────────┤
│ 1. Extract X-Request-ID from header                         │
│ 2. Attach to Django request object                          │
│ 3. Log with structured JSON                                 │
│    → logger.error({request_id, user_id, extra})             │
│ 4. Send to Sentry with context                              │
│ 5. Include in all log messages (filter adds it)             │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Phases

### ✅ Phase 1: Backend Logging Enhancement (COMPLETE)

**Commit**: `9446d7c` - "feat(logging): implement Phase 1 backend structured logging infrastructure"

#### 1.1 Backend Logging Constants ✅
**File**: `backend/apps/core/constants.py`
- Added 7 log prefix constants: `LOG_PREFIX_CACHE`, `LOG_PREFIX_PERF`, `LOG_PREFIX_ERROR`, `LOG_PREFIX_API`, `LOG_PREFIX_DB`, `LOG_PREFIX_CIRCUIT`, `LOG_PREFIX_PARALLEL`
- Added 5 log level constants: `LOG_LEVEL_DEBUG`, `LOG_LEVEL_INFO`, `LOG_LEVEL_WARNING`, `LOG_LEVEL_ERROR`, `LOG_LEVEL_CRITICAL`
- Maintains consistency with existing security constants

#### 1.2 Structured Logger Wrapper ✅
**File**: `backend/apps/core/utils/structured_logger.py` (NEW - 250+ lines)

**Features**:
- StructuredLogger class with automatic context injection
- Auto-includes: `request_id`, `user_id`, `username`, `environment`
- Methods: `debug()`, `info()`, `warning()`, `error()`, `critical()`, `exception()`
- Type hints on all methods (98% coverage maintained)
- Backward compatible with bracket prefix pattern `[CACHE]`, `[PERF]`
- JSON logging ready (pythonjsonlogger integration)
- Sentry integration hooks

**Usage Example**:
```python
from apps.core.utils.structured_logger import get_logger

logger = get_logger(__name__)

# Automatic context injection (request_id, user_id, environment)
logger.info("[CACHE] Cache hit", extra={'key': cache_key, 'hit_rate': 0.42})

# Error logging with full context
logger.error("[API] External API failed", extra={'api': 'plant.id', 'status': 500})
```

#### 1.3 Documentation Updates ✅
- Updated `backend/apps/blog/services/blog_cache_service.py:397`
- Updated `backend/apps/forum/services/forum_cache_service.py:380`
- Changed docstring examples from `print()` to `logger.info()`

### 🚧 Phase 2: Frontend Logging Enhancement (3-4 hours)

#### 2.1 Create Request ID Context
**File**: `web/src/contexts/RequestContext.jsx` (NEW)

```javascript
import { createContext, useContext, useState, useEffect } from 'react'

const RequestContext = createContext()

export function RequestProvider({ children }) {
  const [requestId] = useState(() => crypto.randomUUID())

  return (
    <RequestContext.Provider value={{ requestId }}>
      {children}
    </RequestContext.Provider>
  )
}

export function useRequestId() {
  const context = useContext(RequestContext)
  if (!context) throw new Error('useRequestId must be used within RequestProvider')
  return context.requestId
}
```

**Integration**: Wrap `<App>` in `main.jsx`

#### 2.2 Enhance Logger Utility
**File**: `web/src/utils/logger.js` (MODIFY - currently 72 lines)

**New Features**:
- Structured logging with context fields
- Auto-include: `requestId`, `userId`, `timestamp`, `component`, `environment`
- Sentry breadcrumb integration
- Development: Pretty-print JSON to console
- Production: Send structured data to Sentry

**New API**:
```javascript
import { logger } from '../utils/logger'

// Automatic context from RequestContext + AuthContext
logger.error('Failed to load data', {
  component: 'BlogListPage',
  error: error,
  context: { filters, page }
})

// Outputs in production:
// {
//   level: 'error',
//   message: 'Failed to load data',
//   requestId: 'uuid-here',
//   userId: 'user-123',
//   component: 'BlogListPage',
//   timestamp: '2025-10-31T...',
//   environment: 'production',
//   error: {...},
//   context: {...}
// }
```

#### 2.3 Create HTTP Interceptor
**File**: `web/src/utils/httpClient.js` (NEW)

```javascript
import axios from 'axios'
import { useRequestId } from '../contexts/RequestContext'

// Create axios instance with interceptor
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000'
})

// Add X-Request-ID header to all requests
apiClient.interceptors.request.use((config) => {
  const requestId = localStorage.getItem('requestId') // Or from context
  if (requestId) {
    config.headers['X-Request-ID'] = requestId
  }
  return config
})

export default apiClient
```

**Migration**: Replace `axios` imports with `httpClient` in services

#### 2.4 Replace console.log Statements (38 instances)

**Priority Order**:
1. **Services** (6 instances):
   - `web/src/services/blogService.js:86, 125, 162, 189`

2. **Pages** (20 instances):
   - `web/src/pages/BlogDetailPage.jsx:40, 57, 69`
   - `web/src/pages/forum/ThreadDetailPage.jsx:54, 98, 116, 136`
   - `web/src/pages/forum/ThreadListPage.jsx:54`
   - `web/src/pages/forum/CategoryListPage.jsx:26`
   - `web/src/pages/BlogListPage.jsx:48, 70`
   - `web/src/pages/BlogPreview.jsx:53`
   - `web/src/main.jsx:36, 37, 44`

3. **Utils** (12 instances):
   - `web/src/utils/formatDate.js:48, 58, 85, 95, 126, 156, 183, 201, 231, 237`
   - `web/src/utils/sanitize.js:206`
   - `web/src/config/sentry.js:32`

4. **Components** (2 instances):
   - `web/src/components/forum/ThreadCard.jsx:20`

**Migration Pattern**:
```javascript
// BEFORE
console.error('[BlogService] Error fetching blog posts:', error);

// AFTER
import { logger } from '../utils/logger';
logger.error('Error fetching blog posts', {
  component: 'BlogService',
  error: error,
  context: { endpoint: '/api/v2/blog-posts' }
});
```

#### 2.5 Add ESLint Rule
**File**: `web/.eslintrc.cjs` or `web/eslint.config.js`

```javascript
export default [
  // ... existing config
  {
    rules: {
      'no-console': ['error', { allow: [] }], // Block all console usage
      'no-restricted-syntax': [
        'error',
        {
          selector: "CallExpression[callee.object.name='console']",
          message: 'Use logger utility from utils/logger.js instead of console'
        }
      ]
    }
  }
]
```

**Exception for Tests**: Allow console in test files via override

### 🚧 Phase 3: Distributed Tracing Integration (2 hours)

#### 3.1 Frontend Request ID Generation
- Generate UUID v4 on app initialization
- Store in RequestContext
- Pass to logger automatically
- Include in Sentry events

#### 3.2 Backend Request ID Extraction
- ✅ Already configured: `django-request-id` middleware
- ✅ Already configured: `X-Request-ID` header (settings.py:762)
- Verify middleware order in settings.py

#### 3.3 Integration Test
**File**: `backend/apps/core/tests/test_distributed_tracing.py` (NEW)

```python
def test_request_id_propagation():
    """Verify request ID flows from frontend to backend logs."""
    request_id = 'test-uuid-12345'

    response = client.post(
        '/api/v1/plant-identification/identify/',
        headers={'X-Request-ID': request_id}
    )

    # Verify request ID in response
    assert response.headers.get('X-Request-ID') == request_id

    # Verify request ID in logs (check captured logs)
    # ... assertion logic
```

### 🚧 Phase 4: Documentation & Testing (1-2 hours)

#### 4.1 Update CLAUDE.md
Add new section:

```markdown
## Enterprise Logging Patterns

### Backend (Django)
from apps.core.utils.structured_logger import get_logger

logger = get_logger(__name__)

# Automatic context: request_id, user_id, environment
logger.info("[CACHE] Hit", extra={'key': key, 'hit_rate': 0.42})
logger.error("[API] Failed", extra={'api': 'plant.id', 'status': 500})

### Frontend (React)
import { logger } from '../utils/logger'

// Automatic context: requestId, userId, component, timestamp
logger.error('Operation failed', {
  component: 'BlogListPage',
  error: error,
  context: { filters }
})

### Log Levels
- DEBUG: Development only, detailed diagnostics
- INFO: Normal operations ([CACHE] hits, [PERF] metrics)
- WARNING: Unexpected but recoverable ([CIRCUIT] opens)
- ERROR: Serious problems (API failures, exceptions)

### Distributed Tracing
Request IDs automatically correlate frontend and backend logs in Sentry.
```

#### 4.2 Create Logging Guide
**File**: `docs/LOGGING_GUIDE.md` (NEW)

Sections:
- When to use each log level
- How to add structured context
- Request tracing examples
- Sentry integration guide
- Debugging with structured logs

#### 4.3 Write Tests
- **Frontend**: `web/src/utils/logger.test.js`
- **Backend**: `backend/apps/core/tests/test_structured_logger.py`
- **Integration**: Request ID propagation test

### 🚧 Phase 5: Migration & Cleanup (2-3 hours)

#### 5.1 Automated Migration (if possible)
- Create codemod script for console.log → logger
- Run ESLint autofix where possible
- Manual review of complex cases

#### 5.2 Remove Obsolete Code
- Clean up "TODO #XXX fix" comments (7 instances)
- Remove resolved TODO comments
- Update test comments about removed blocks

#### 5.3 Verification
- Run all tests (frontend + backend)
- Verify no console.log in non-test files
- Verify no print() in service files
- Check Sentry dashboard for structured logs
- Test request ID correlation

## File Structure

```
backend/
├── apps/core/
│   ├── utils/
│   │   ├── structured_logger.py        # ✅ NEW - Logger wrapper
│   │   └── pii_safe_logging.py         # ✅ Exists
│   ├── constants.py                     # ✅ UPDATED - Log constants
│   └── tests/
│       ├── test_structured_logger.py    # 🚧 NEW - Unit tests
│       └── test_distributed_tracing.py  # 🚧 NEW - Integration test
└── plant_community_backend/
    └── settings.py                      # ✅ JSON logging configured

web/
├── src/
│   ├── contexts/
│   │   ├── RequestContext.jsx           # 🚧 NEW - Request ID context
│   │   └── AuthContext.jsx              # ✅ Exists
│   ├── utils/
│   │   ├── logger.js                    # 🚧 MODIFY - Enhance with structure
│   │   ├── logger.test.js               # 🚧 NEW - Unit tests
│   │   └── httpClient.js                # 🚧 NEW - Axios interceptor
│   ├── config/
│   │   └── sentry.js                    # 🚧 MODIFY - Add request ID
│   ├── services/                        # 🚧 MODIFY - Replace console.log (6 files)
│   ├── pages/                           # 🚧 MODIFY - Replace console.log (8 files)
│   └── components/                      # 🚧 MODIFY - Replace console.log (2 files)
├── .eslintrc.cjs                        # 🚧 MODIFY - Add no-console rule
└── eslint.config.js                     # 🚧 OR modify this file

docs/
├── LOGGING_GUIDE.md                     # 🚧 NEW - Developer guide
└── CLAUDE.md                            # 🚧 MODIFY - Add logging section
```

## Success Criteria

- ✅ **Zero console.log in production code** (tests OK)
- ✅ **Zero print() in service files** (migrations/tests OK)
- ✅ **All logs structured JSON in production**
- ✅ **Request IDs in 100% of logs**
- ✅ **Frontend/backend logs correlated in Sentry**
- ✅ **ESLint enforces logger usage**
- ✅ **All tests passing**

## Risk Mitigation

1. **Gradual rollout**: Phase-by-phase implementation ✅
2. **Backwards compatibility**: Keep bracket prefixes `[CACHE]` ✅
3. **Testing**: Comprehensive unit + integration tests
4. **Monitoring**: Watch Sentry for logging errors
5. **Rollback plan**: Git commits per phase for easy revert ✅

## Estimated Timeline

- ✅ **Phase 1** (Backend): 2-3 hours - COMPLETE
- 🚧 **Phase 2** (Frontend): 3-4 hours - IN PROGRESS
- 🚧 **Phase 3** (Tracing): 2 hours
- 🚧 **Phase 4** (Docs/Tests): 1-2 hours
- 🚧 **Phase 5** (Migration): 2-3 hours

**Total**: 10-14 hours (1.5-2 days)

## Progress Tracking

### Completed ✅
- [x] Create feature branch `feature/enterprise-logging`
- [x] Phase 1.1: Add backend logging constants
- [x] Phase 1.2: Create structured logger wrapper
- [x] Phase 1.3: Update cache service documentation
- [x] Commit Phase 1 (commit: `9446d7c`)

### In Progress 🚧
- [ ] Phase 2.1: Create RequestContext
- [ ] Phase 2.2: Enhance logger utility
- [ ] Phase 2.3: Create HTTP interceptor
- [ ] Phase 2.4: Replace 38 console.log statements
- [ ] Phase 2.5: Add ESLint rule

### Todo ⏳
- [ ] Phase 3: Distributed tracing verification
- [ ] Phase 4: Documentation and tests
- [ ] Phase 5: Final cleanup and verification
- [ ] Create pull request
- [ ] Code review
- [ ] Merge to main

## Quick Reference Commands

```bash
# Backend
cd backend
source venv/bin/activate

# Test structured logger
python -c "from apps.core.utils.structured_logger import get_logger; logger = get_logger('test'); logger.info('[TEST] Hello', extra={'key': 'value'})"

# Frontend
cd web
npm run dev          # Dev server
npm run lint         # Check for console.log violations
npm run test         # Run tests

# Git
git status
git log --oneline feature/enterprise-logging
git diff main...feature/enterprise-logging
```

## Related Documentation

- Initial audit report: See conversation history (38 console.log, 42 print() found)
- Django logging: https://docs.djangoproject.com/en/5.2/topics/logging/
- Sentry React: https://docs.sentry.io/platforms/javascript/guides/react/
- python-json-logger: https://github.com/madzak/python-json-logger

## Notes

- **Print statements**: Most (40/42) are in migrations and tests (acceptable)
- **Console.log**: All 38 need migration to logger utility
- **Sentry already configured**: Backend (settings.py:866-881), Frontend (web/src/config/sentry.js)
- **Request ID middleware**: Already installed and configured (django-request-id)

---

**Last Updated**: October 31, 2025
**Branch**: `feature/enterprise-logging`
**Current Phase**: Phase 2 (Frontend Enhancement)
**Next**: Create RequestContext and enhance logger utility
