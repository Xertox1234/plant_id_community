---
status: ready
priority: p4
issue_id: "032"
tags: [testing, frontend, react]
dependencies: []
---

# Add React Component Unit Tests

## Problem

React components lack unit tests. No test coverage for BlogCard, StreamFieldRenderer, Header, Footer components.

## Findings

**pattern-recognition-specialist**:
- 0 test files in `web/src/components/`
- 0 test files in `web/src/pages/`
- Vitest configured but only utility tests present:
  - `web/src/utils/formatDate.test.js` ✅
  - `web/src/utils/sanitize.test.js` ✅
  - `web/src/utils/validation.test.js` ✅
- No component tests for 15+ React components

**best-practices-researcher**:
- Industry standard: 80% component test coverage
- Testing Library (React): Component testing best practice
- Critical components untested: StreamFieldRenderer (XSS risk), AuthContext, Header

## Proposed Solutions

### Option 1: React Testing Library (Recommended)
```javascript
// BlogCard.test.jsx
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import BlogCard from './BlogCard';

describe('BlogCard', () => {
  it('renders post title and excerpt', () => {
    const post = {
      title: 'Test Post',
      excerpt: 'Test excerpt',
      slug: 'test-post',
      published_date: '2025-10-25',
      author: { name: 'Test Author' }
    };

    render(
      <BrowserRouter>
        <BlogCard post={post} />
      </BrowserRouter>
    );

    expect(screen.getByText('Test Post')).toBeInTheDocument();
    expect(screen.getByText('Test excerpt')).toBeInTheDocument();
  });

  it('sanitizes XSS in excerpt', () => {
    const post = {
      title: 'Test',
      excerpt: '<script>alert("xss")</script>Safe text',
      slug: 'test'
    };

    render(<BrowserRouter><BlogCard post={post} /></BrowserRouter>);

    expect(screen.queryByText('alert("xss")')).not.toBeInTheDocument();
    expect(screen.getByText('Safe text')).toBeInTheDocument();
  });
});
```

**Pros**: Industry standard, excellent React support, accessibility testing
**Cons**: Requires test file for each component
**Effort**: 16 hours (15 components × ~1 hour each)
**Risk**: Low

### Option 2: Visual Regression Testing (Chromatic/Percy)
**Pros**: Catches visual bugs, less manual test writing
**Cons**: Paid service, doesn't test logic
**Effort**: 8 hours (setup)
**Risk**: Medium (external dependency)

### Option 3: Defer Component Testing
**Pros**: No effort now
**Cons**: No safety net for refactoring, XSS regressions possible
**Risk**: Medium (already has utility tests for XSS prevention)

## Recommended Action

**Phased approach**:
1. **Phase 1** (Priority): Test critical security components
   - StreamFieldRenderer.test.jsx (XSS protection)
   - sanitize.test.js (already exists ✅)
   - AuthContext.test.jsx (authentication logic)
2. **Phase 2**: Test UI components
   - Header.test.jsx, Footer.test.jsx, UserMenu.test.jsx
   - BlogCard.test.jsx, BlogListPage.test.jsx
3. **Phase 3**: Test pages
   - LoginPage.test.jsx, SignupPage.test.jsx
   - BlogDetailPage.test.jsx

**Effort estimate**:
- Phase 1: 4 hours (3 critical tests)
- Phase 2: 8 hours (UI components)
- Phase 3: 4 hours (pages)

## Technical Details

**Vitest + React Testing Library setup** (already configured in `vitest.config.js`):
```javascript
// vitest.config.js
export default defineConfig({
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/tests/setup.js',
  }
})
```

**Test utilities to create**:
```javascript
// src/tests/utils.jsx
import { render } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { AuthProvider } from '../contexts/AuthContext';

export function renderWithRouter(ui, options = {}) {
  return render(
    <BrowserRouter>
      <AuthProvider>
        {ui}
      </AuthProvider>
    </BrowserRouter>,
    options
  );
}
```

**Current test coverage** (estimate):
- Utility functions: 80% ✅ (formatDate, sanitize, validation)
- Components: 0% ❌
- Pages: 0% ❌
- Services: 0% ❌ (authService, blogService)

**Target coverage**:
- Overall: 80% (Vitest threshold already set in package.json)
- Critical components: 100% (StreamFieldRenderer, AuthContext)

## Resources

- React Testing Library: https://testing-library.com/react
- Vitest React guide: https://vitest.dev/guide/testing-react.html
- Testing Library best practices: https://kentcdodds.com/blog/common-mistakes-with-react-testing-library

## Acceptance Criteria

- [ ] StreamFieldRenderer has XSS prevention tests (Phase 1)
- [ ] AuthContext tests for login/logout/token refresh (Phase 1)
- [ ] All UI components have basic render tests (Phase 2)
- [ ] Critical user flows tested (login, blog viewing) (Phase 3)
- [ ] `npm run test:coverage` shows ≥80% coverage
- [ ] CI/CD runs tests on every PR

## Work Log

- 2025-10-25: Issue identified by pattern-recognition-specialist agent
- Current: 3 utility test files exist, 0 component tests

## Notes

**Priority rationale**: P4 (Low) - Quality improvement, not blocking production
**Utility tests exist**: XSS prevention already tested in `sanitize.test.js`
**Trade-off**: Test effort vs. refactoring confidence
**Related**: XSS protection (issue #016), bundle optimization may break tests
