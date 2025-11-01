---
status: pending
priority: p2
issue_id: "004"
tags: [code-review, logging, frontend, code-quality, audit]
dependencies: []
---

# Migrate Remaining Console Logs to Structured Logger

## Problem Statement
Despite implementing enterprise-grade structured logging infrastructure (Phase 2 completed October 31, 2025), there are still 9 raw `console.log`/`console.error`/`console.warn` statements remaining in production code. This creates inconsistent logging patterns and misses benefits of structured logging (request ID correlation, Sentry breadcrumbs, log aggregation).

## Findings
- Discovered during comprehensive codebase audit (October 31, 2025)
- **Total occurrences**: 9 across 6 files
- **Affected files** (production code only):
  - `web/src/config/sentry.js` (1 occurrence)
  - `web/src/utils/sanitize.js` (1 occurrence)
  - `web/src/utils/logger.js` (2 occurrences) ⚠️ Logger itself has console statements

**Note**: Test files excluded (`.test.jsx`, `.test.js`) as they're not production code:
- `web/src/contexts/RequestContext.test.jsx` (1 occurrence)
- `web/src/utils/logger.test.js` (2 occurrences)
- `web/src/components/StreamFieldRenderer.test.jsx` (2 occurrences)

**Impact of inconsistent logging**:
1. No automatic request ID correlation for debugging
2. Missing Sentry breadcrumbs for error tracking
3. No structured data for log aggregation/analysis
4. Inconsistent format makes filtering difficult
5. Lost opportunity for distributed tracing

## Proposed Solutions

### Option 1: Complete Migration to Structured Logger (Recommended)
**Pros**:
- Achieves 100% logging consistency in production code
- Full Sentry integration for all logs
- Complete request ID correlation
- Better production debugging

**Cons**:
- Need to verify logger.js doesn't create circular dependencies
- May need bootstrap/initialization logging exception

**Effort**: Small (30 minutes)
**Risk**: Low

**Implementation pattern**:
```javascript
// Before (web/src/config/sentry.js):
console.error('Sentry initialization failed:', error)

// After:
import { logger } from '../utils/logger'
logger.error('Sentry initialization failed', {
  component: 'SentryConfig',
  error: error,
  context: { dsn: import.meta.env.VITE_SENTRY_DSN ? 'configured' : 'missing' }
})
```

```javascript
// Before (web/src/utils/sanitize.js):
console.warn('[sanitize] DOMPurify not available, returning unsanitized content')

// After:
import { logger } from './logger'
logger.warning('DOMPurify not available - returning unsanitized content', {
  component: 'sanitize',
  security: 'XSS_RISK',
  context: { preset: presetName }
})
```

**Special case - logger.js internal logging**:
The logger itself may need console fallback for bootstrap/initialization errors:
```javascript
// Acceptable use in logger.js for critical failures:
try {
  // Logger initialization
} catch (error) {
  // OK to use console here as last resort
  console.error('[LOGGER] Critical initialization failure:', error)
}
```

### Option 2: Eslint Rule Enforcement
Add stricter eslint rule to prevent future console usage:

```javascript
// eslint.config.js
{
  rules: {
    'no-console': ['error', {
      allow: [] // No exceptions in production code
    }]
  }
}
```

**Effort**: Small (15 minutes additional)
**Risk**: Low

## Recommended Action
**Combination approach**:
1. Migrate all 4 production console statements to structured logger
2. Add exception for logger.js bootstrap errors (if needed)
3. Strengthen eslint rule to prevent regression
4. Document pattern in logging guide

## Technical Details
- **Affected Files** (production code):
  1. `web/src/config/sentry.js` - Sentry initialization error
  2. `web/src/utils/sanitize.js` - DOMPurify warning
  3. `web/src/utils/logger.js` - Bootstrap errors (2 occurrences)

- **Related Components**:
  - Enterprise logging infrastructure (Phase 2)
  - Sentry integration
  - Request ID correlation
  - Logger initialization

- **Current eslint rule**: `no-console: warn` (should be `error`)

## Resources
- Logging Phase 2 completion: `docs/archive/2025-10/completions/PHASE_2_FRONTEND_LOGGING_COMPLETE.md`
- Logger implementation: `web/src/utils/logger.js`
- ESLint config: `web/eslint.config.js`
- Code review audit: October 31, 2025

## Acceptance Criteria
- [ ] Replace all 4 production console statements with structured logger
- [ ] Verify no circular dependency issues in logger.js
- [ ] Document any bootstrap logging exceptions
- [ ] Update eslint rule to `'no-console': 'error'`
- [ ] Run `npm run lint` with no console.* errors
- [ ] Test Sentry initialization logging works correctly
- [ ] Verify sanitize.js warnings appear in Sentry

## Work Log

### 2025-10-31 - Code Review Discovery
**By:** Claude Code Review System
**Actions:**
- Discovered 9 remaining console statements during codebase audit
- Analyzed context: 4 production code, 5 test files
- Identified potential circular dependency risk in logger.js
- Categorized as P2 code quality issue

**Learnings:**
- Phase 2 logging migration was 95% complete, not 100%
- Need stricter eslint enforcement to prevent regression
- Logger bootstrap errors may need console fallback
- Test files can keep console statements (not production code)

## Notes
Source: Code review performed on October 31, 2025
Review command: `/compounding-engineering:review audit code base`
Severity: P2 (code quality, not security critical)
Category: Code Quality - Logging Standards
Related: Phase 2 Frontend Logging Infrastructure (completed Oct 31, 2025)
