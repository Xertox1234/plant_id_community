---
status: ready
priority: p4
issue_id: "034"
tags: [code-quality, duplication, frontend]
dependencies: []
---

# Consolidate Duplicate DOMPurify Sanitization

## Problem

DOMPurify.sanitize() called in 4 different components with slightly different configurations. Inconsistent XSS protection.

## Findings

**pattern-recognition-specialist**:
- `StreamFieldRenderer.jsx`: Uses DOMPurify with custom config
- `BlogDetailPage.jsx`: Different DOMPurify config for excerpts
- `BlogCard.jsx`: Another DOMPurify config variant
- `sanitize.js`: Utility function with standardized config (not always used)

**code-simplicity-reviewer**:
- Duplication: 4 implementations of same sanitization logic
- Inconsistency: Different ALLOWED_TAGS across components
- Risk: One component might have weaker XSS protection

**Locations**:
```javascript
// web/src/utils/sanitize.js (standardized version)
export function sanitizeHtml(html) {
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: ['p', 'b', 'i', 'em', 'strong', 'a', 'br'],
    ALLOWED_ATTR: ['href', 'target', 'rel']
  });
}

// web/src/components/StreamFieldRenderer.jsx (custom config)
DOMPurify.sanitize(block.value.html, {
  ALLOWED_TAGS: ['p', 'h1', 'h2', 'h3', 'ul', 'ol', 'li', 'code', 'pre'],
  // Different from sanitize.js!
});
```

## Proposed Solutions

### Option 1: Centralized Sanitization Service (Recommended)
```javascript
// web/src/utils/sanitize.js
const CONFIGS = {
  basic: {
    ALLOWED_TAGS: ['p', 'b', 'i', 'em', 'strong', 'a', 'br'],
    ALLOWED_ATTR: ['href', 'target', 'rel']
  },
  richText: {
    ALLOWED_TAGS: ['p', 'h1', 'h2', 'h3', 'h4', 'ul', 'ol', 'li', 'blockquote', 'code', 'pre'],
    ALLOWED_ATTR: ['href', 'target', 'rel', 'class']
  },
  streamField: {
    ALLOWED_TAGS: ['p', 'h1', 'h2', 'h3', 'ul', 'ol', 'li', 'code', 'pre', 'img'],
    ALLOWED_ATTR: ['href', 'target', 'rel', 'class', 'src', 'alt']
  }
};

export function sanitizeHtml(html, configName = 'basic') {
  return DOMPurify.sanitize(html, CONFIGS[configName]);
}
```

**Usage**:
```javascript
// StreamFieldRenderer.jsx
import { sanitizeHtml } from '../utils/sanitize';
dangerouslySetInnerHTML={{ __html: sanitizeHtml(block.value.html, 'streamField') }}

// BlogCard.jsx
import { sanitizeHtml } from '../utils/sanitize';
dangerouslySetInnerHTML={{ __html: sanitizeHtml(post.excerpt, 'basic') }}
```

**Pros**: Single source of truth, consistent XSS protection, testable
**Cons**: Requires refactoring 4 components
**Effort**: 3 hours
**Risk**: Low (already have sanitize.js tests)

### Option 2: Keep Component-Specific Sanitization
**Pros**: Flexibility per component
**Cons**: Duplication, inconsistent protection, harder to audit
**Risk**: Medium (XSS protection inconsistency)

## Recommended Action

**Option 1** - Centralize sanitization:
1. Expand `sanitize.js` with 3 config presets (basic, richText, streamField)
2. Update StreamFieldRenderer.jsx to use `sanitizeHtml(html, 'streamField')`
3. Update BlogCard.jsx to use `sanitizeHtml(excerpt, 'basic')`
4. Update BlogDetailPage.jsx to use `sanitizeHtml(introduction, 'richText')`
5. Add tests for each config preset
6. Document XSS protection strategy in README

## Technical Details

**Current duplication**:
```bash
# Find all DOMPurify.sanitize calls
grep -r "DOMPurify.sanitize" web/src/
# Result: 4 files with different configs
```

**Files to refactor**:
1. `web/src/components/StreamFieldRenderer.jsx` (line ~45)
2. `web/src/components/BlogCard.jsx` (line ~28)
3. `web/src/pages/BlogDetailPage.jsx` (line ~67)
4. `web/src/utils/sanitize.js` (already good, expand this)

**Test coverage impact**:
- Current: `sanitize.test.js` tests only basic config
- After: Add tests for richText and streamField configs
- Add integration test: "All components use sanitize utility"

## Resources

- DOMPurify configuration: https://github.com/cure53/DOMPurify#can-i-configure-dompurify
- OWASP XSS Prevention: https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html
- React dangerouslySetInnerHTML: https://react.dev/reference/react-dom/components/common#dangerously-setting-the-inner-html

## Acceptance Criteria

- [ ] All DOMPurify calls use centralized `sanitizeHtml()` function
- [ ] 3 config presets defined: basic, richText, streamField
- [ ] All 4 components refactored to use utility
- [ ] Tests verify each config preset works correctly
- [ ] ESLint rule: "no-direct-dompurify" (enforce using utility)
- [ ] Documentation explains which config to use when

## Work Log

- 2025-10-25: Issue identified by pattern-recognition-specialist agent

## Notes

**Priority rationale**: P4 (Low) - Code quality improvement, XSS protection already works
**Current state**: All components do sanitize, just inconsistently
**Security impact**: Low (all components use DOMPurify, just with different configs)
**Related**: XSS testing (issue #032 - React component tests)
