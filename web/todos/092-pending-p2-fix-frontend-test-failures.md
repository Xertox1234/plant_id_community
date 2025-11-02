---
status: pending
priority: p2
issue_id: "092"
tags: [testing, frontend, vitest, react, bug]
dependencies: []
estimated_effort: "8-12 hours"
---

# Fix Frontend Test Failures (135/479 tests failing)

## Problem Statement

135 out of 479 frontend tests are failing (28% failure rate). This indicates widespread issues with test setup, API mocking, or component behavior that need systematic investigation and fixes.

## Findings

**Discovered**: November 2, 2025 during post-dependency-update test verification
**Scope**: 135 failing tests across 11 test files (11 files failing, 11 passing)
**Impact**: Cannot reliably verify frontend changes

**Test Suite Stats**:
- **Total Tests**: 479
- **Passing**: 343 (72%)
- **Failing**: 135 (28%)
- **Skipped**: 1
- **Test Files**: 22 total (11 failing, 11 passing)
- **Duration**: 10.45s (fast suite, good performance)

**Sample Failing Test** (from `CategoryListPage.test.jsx`):
```javascript
// Test expects console.error to be called for API errors
await waitFor(() => {
  expect(consoleErrorSpy).toHaveBeenCalled();
});

// Error: Assertion failed - console.error not called as expected
```

## Root Cause Categories

Based on test failure patterns, issues likely fall into these categories:

### Category 1: API Mocking Issues
**Symptoms**:
- Tests expecting API calls but mocks not configured correctly
- Network error handling not triggering as expected
- Console error spies not capturing errors

**Example**:
```javascript
// Test expects error but mock doesn't fail properly
api.get('/categories').mockRejectedValue(new Error('Network error'));
// But error doesn't propagate to console.error as expected
```

### Category 2: Async State Management
**Symptoms**:
- `waitFor()` timeouts
- State updates not reflected in time
- Loading states not transitioning correctly

### Category 3: Component Prop Changes
**Symptoms**:
- Tests written for old component APIs
- Props renamed but tests not updated
- Default values changed

### Category 4: React 19 Breaking Changes
**Symptoms**:
- Tests written for React 18 patterns
- Testing Library behavior changes
- New concurrent features affecting test timing

## Investigation Plan

### Phase 1: Categorize Failures (2-3 hours)

**Step 1**: Run tests with detailed output
```bash
cd web
npm run test:watch -- --run --reporter=verbose > test-failures.log 2>&1
```

**Step 2**: Analyze failure patterns
```bash
# Group failures by test file
grep "FAIL" test-failures.log | sort

# Group by error type
grep "AssertionError\|TypeError\|ReferenceError" test-failures.log | sort | uniq -c
```

**Step 3**: Create failure categorization
```markdown
## Failure Breakdown

### API Mocking (estimated 60 failures)
- CategoryListPage: API error handling
- ThreadListPage: API response mocking
- PostListPage: Network error simulation

### Async State (estimated 40 failures)
- Loading states not updating
- waitFor timeouts
- State transitions

### Component Props (estimated 25 failures)
- Renamed props
- Changed default values
- Removed props

### Other (estimated 10 failures)
- Environment setup
- Test utilities
- Edge cases
```

### Phase 2: Fix High-Impact Issues (4-6 hours)

**Priority 1**: API Mocking Framework
```javascript
// Create standardized API mock utility
// File: web/src/test-utils/apiMocks.js

export const mockApiSuccess = (endpoint, data) => {
  vi.spyOn(api, 'get').mockResolvedValue({ data });
};

export const mockApiError = (endpoint, error = 'Network error') => {
  const apiError = new Error(error);
  apiError.response = { status: 500, data: { detail: error } };
  vi.spyOn(api, 'get').mockRejectedValue(apiError);
};

export const mockApiNetworkError = (endpoint) => {
  const networkError = new Error('Network Error');
  networkError.code = 'ECONNABORTED';
  vi.spyOn(api, 'get').mockRejectedValue(networkError);
};
```

**Priority 2**: Console Error Spying
```javascript
// Fix console.error spy pattern
// Common pattern in failing tests:

// WRONG - Spy created but errors don't propagate
const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

// RIGHT - Ensure error handler actually calls console.error
const consoleErrorSpy = vi.spyOn(console, 'error');
// Don't mock implementation - let it call through
// Or ensure component error boundary actually logs to console
```

**Priority 3**: Async Test Utilities
```javascript
// Create helper for common async patterns
// File: web/src/test-utils/asyncHelpers.js

export const waitForLoadingToFinish = async () => {
  await waitFor(() => {
    expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
  }, { timeout: 3000 });
};

export const waitForError = async (errorText) => {
  await waitFor(() => {
    expect(screen.getByText(new RegExp(errorText, 'i'))).toBeInTheDocument();
  }, { timeout: 2000 });
};
```

### Phase 3: Systematic Fixes (3-5 hours)

**Approach**: Fix by test file, validate each before moving to next

```bash
# Fix one file at a time
npm run test:watch -- CategoryListPage.test.jsx

# Once passing, move to next
npm run test:watch -- ThreadListPage.test.jsx

# Track progress
echo "Fixed: CategoryListPage.test.jsx" >> fix-progress.md
```

**Common Fix Patterns**:

1. **API Mock Pattern**:
```javascript
// Before
vi.mock('../../services/api');
api.get.mockRejectedValue(new Error('Network error'));

// After
import { mockApiNetworkError } from '../test-utils/apiMocks';
mockApiNetworkError('/api/categories');
```

2. **Console Error Pattern**:
```javascript
// Before
const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
// ... test code ...
expect(spy).toHaveBeenCalled(); // Fails

// After
const spy = vi.spyOn(console, 'error');
// Ensure component actually calls console.error in catch blocks
expect(spy).toHaveBeenCalledWith(expect.stringContaining('Network error'));
```

3. **Async Timing Pattern**:
```javascript
// Before
await waitFor(() => {
  expect(consoleErrorSpy).toHaveBeenCalled();
}); // Times out

// After
await waitFor(() => {
  expect(consoleErrorSpy).toHaveBeenCalled();
}, { timeout: 3000, interval: 100 }); // More forgiving timing
```

### Phase 4: Prevent Regression (1 hour)

**Add Pre-commit Hook**:
```yaml
# .husky/pre-commit
npm run test -- --run --bail
# Exit if tests fail
```

**Update CI**:
```yaml
# .github/workflows/frontend-tests.yml
- name: Run frontend tests
  run: npm run test -- --run --coverage

- name: Upload coverage
  if: always()
  uses: codecov/codecov-action@v3

- name: Fail if coverage < 80%
  run: |
    coverage=$(cat coverage/coverage-summary.json | jq '.total.lines.pct')
    if (( $(echo "$coverage < 80" | bc -l) )); then
      echo "Coverage $coverage% is below 80%"
      exit 1
    fi
```

## Proposed Solutions

### Option 1: Systematic File-by-File Fix (Recommended)
Fix tests methodically, one file at a time, with proper investigation.

**Pros**:
- Thorough understanding of each issue
- High-quality fixes
- Prevents similar issues in future
- Builds test utility library

**Cons**:
- Time-consuming (8-12 hours)
- Requires focus and discipline

**Effort**: 8-12 hours
**Risk**: Low

### Option 2: Quick Pattern-Based Fix
Apply common fixes across all files without deep investigation.

**Pros**:
- Faster (4-6 hours)
- Gets tests passing quickly

**Cons**:
- May mask underlying issues
- Could introduce technical debt
- Doesn't improve test quality

**Effort**: 4-6 hours
**Risk**: Medium

### Option 3: Rewrite Failing Tests
Start fresh with current best practices.

**Pros**:
- Modern test patterns
- Clean slate
- Best practices from start

**Cons**:
- Very time-consuming (15-20 hours)
- Lose existing test coverage temporarily
- Risk of missing edge cases

**Effort**: 15-20 hours
**Risk**: High

## Recommended Action

**Option 1** - Systematic file-by-file fix with test utilities.

**Rationale**:
1. 72% of tests already passing (good foundation)
2. Failures concentrated in specific patterns (fixable)
3. Builds reusable test utilities for future
4. Improves overall test quality

**Implementation Timeline**:
- **Week 1**: Investigation + High-impact fixes (Phases 1-2: 6-9 hours)
- **Week 2**: Systematic fixes + Regression prevention (Phases 3-4: 4-6 hours)
- **Total**: 10-15 hours over 2 weeks

## Technical Details

**Test Configuration**:
- **Framework**: Vitest 4.0.6
- **React Version**: React 19
- **Testing Library**: @testing-library/react
- **Coverage Tool**: @vitest/coverage-v8 4.0.6
- **Test Runner**: Vitest with jsdom environment

**Test File Structure**:
```
web/src/
├── pages/
│   ├── blog/
│   │   ├── BlogListPage.test.jsx
│   │   └── BlogDetailPage.test.jsx
│   └── forum/
│       ├── CategoryListPage.test.jsx ❌ (failing)
│       ├── ThreadListPage.test.jsx ❌ (failing)
│       └── PostListPage.test.jsx ❌ (failing)
├── components/
│   ├── blog/
│   │   └── BlogCard.test.jsx ✅ (passing)
│   └── forum/
│       └── CategoryCard.test.jsx ❌ (failing)
└── services/
    └── api.test.js ✅ (passing)
```

**Dependencies Recently Updated** (may affect tests):
- `vitest`: 3.2.4 → 4.0.6 (major update)
- `@vitest/ui`: 3.2.4 → 4.0.6
- `@vitest/coverage-v8`: 3.2.4 → 4.0.6
- `jsdom`: 26.1.0 → 27.1.0 (major update)
- `globals`: 16.4.0 → 16.5.0
- `eslint`: 9.38.0 → 9.39.0

**Note**: Vitest 4.x and jsdom 27.x may have breaking changes affecting tests.

## Acceptance Criteria

- [ ] Categorize all 135 failures by type
- [ ] Create reusable API mocking utilities
- [ ] Create reusable async test helpers
- [ ] Fix all API mocking failures (estimated 60 tests)
- [ ] Fix all async state failures (estimated 40 tests)
- [ ] Fix all component prop failures (estimated 25 tests)
- [ ] Fix remaining failures (estimated 10 tests)
- [ ] All 479 tests passing (100%)
- [ ] Test coverage > 80%
- [ ] Documentation updated with test utilities
- [ ] Pre-commit hook added to prevent regression

## Work Log

### 2025-11-02 - Test Failure Discovery
**By:** Dependency Update Verification Process
**Actions:**
- Ran full frontend test suite after dependency updates
- Identified 135/479 tests failing (28% failure rate)
- Noted test suite runs fast (10.45s) - good performance
- Observed failure pattern: mostly in forum components and API mocking
- Created TODO for systematic investigation and fix

**Initial Analysis**:
- Tests run successfully (no crashes)
- Failures concentrated in specific areas (forum, API handling)
- Recent Vitest 4.x and jsdom 27.x updates may contribute
- But likely pre-existing issues exposed by better testing

**Priority**: P2 (Medium-High)
- 72% pass rate is acceptable for development
- But blocks reliable CI/CD
- Should fix before adding new features
- Not blocking current deployment (manual testing verifies functionality)

## Resources

- Vitest 4.0 Migration: https://vitest.dev/guide/migration.html
- React Testing Library: https://testing-library.com/docs/react-testing-library/intro/
- Vitest Mocking: https://vitest.dev/guide/mocking.html
- jsdom 27.x Changes: https://github.com/jsdom/jsdom/releases/tag/27.0.0

## Notes

**Why This Matters**:
- Test suite is critical for safe refactoring
- 135 failing tests = large blind spots in test coverage
- Can't confidently deploy without reliable tests
- Future feature development needs working test foundation

**Why P2 (Not P1)**:
- Manual testing shows UI works correctly
- Production monitoring shows no issues
- 343 tests still passing provide some coverage
- Not blocking immediate deployment

**Investigation Priority**:
1. Check Vitest 4.x breaking changes (may need config updates)
2. Check jsdom 27.x changes (DOM API differences)
3. Review API mocking patterns (most common failure)
4. Fix one test file completely before moving to next

**Future Prevention**:
- Add pre-commit hook to run tests
- Add CI step that fails on test failures
- Set up test coverage requirements (>80%)
- Document test utility patterns for consistency
