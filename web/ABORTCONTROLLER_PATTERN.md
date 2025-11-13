# AbortController Pattern for React Fetch Requests

**Issue**: #153
**Date**: November 13, 2025
**Priority**: MEDIUM
**Status**: Documentation Complete, Implementation Required

---

## Problem

React components making fetch requests don't implement AbortController cleanup, causing:
1. **Memory leaks** - Requests continue after component unmounts
2. **State update warnings** - "Can't perform a React state update on an unmounted component"
3. **Wasted bandwidth** - Unnecessary API calls for stale data
4. **Race conditions** - Outdated responses may update state

---

## Affected Components

### Confirmed (from Issue #153)
- `/web/src/pages/forum/SearchPage.tsx` ✅ **Found**
- `/web/src/pages/blog/BlogListPage.tsx` ⚠️ **Not found** (may not exist or renamed)
- `/web/src/components/forum/ThreadList.tsx` ⚠️ **Not found** (may not exist or renamed)

### Additional Components (Likely Affected)
All components using `useEffect` with async data fetching should be audited.

---

## Solution Pattern

### Basic Pattern (Direct fetch)

```typescript
useEffect(() => {
  const controller = new AbortController();

  fetch('/api/endpoint', { signal: controller.signal })
    .then(res => res.json())
    .then(data => setData(data))
    .catch(err => {
      if (err.name === 'AbortError') {
        // Expected on cleanup - don't log as error
        return;
      }
      console.error('Fetch failed:', err);
    });

  return () => controller.abort();  // ✅ Cancel on unmount
}, [dependencies]);
```

###Advanced Pattern (Service Functions)

When using service functions like `searchForum()` or `fetchCategories()`:

#### 1. Update Service Functions to Accept Signal

**File**: `src/services/forumService.ts`

```typescript
// ✅ AFTER: Accept optional AbortSignal
export async function fetchCategories(
  signal?: AbortSignal
): Promise<Category[]> {
  const response = await fetch('/api/v1/forum/categories/', {
    signal,  // Pass to fetch
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch categories: ${response.status}`);
  }

  return response.json();
}

export async function searchForum(
  params: SearchParams,
  signal?: AbortSignal
): Promise<SearchResults> {
  const queryString = new URLSearchParams(params as Record<string, string>).toString();
  const response = await fetch(`/api/v1/forum/search/?${queryString}`, {
    signal,  // Pass to fetch
  });

  if (!response.ok) {
    throw new Error(`Search failed: ${response.status}`);
  }

  return response.json();
}
```

#### 2. Update Components to Use AbortController

**File**: `src/pages/forum/SearchPage.tsx`

**BEFORE (Lines 67-81)** - ❌ Memory leak:
```typescript
useEffect(() => {
  const loadCategories = async () => {
    try {
      const data = await fetchCategories();
      setCategories(data.results || []);
    } catch (err) {
      logger.error('Error loading categories', { error: err });
    }
  };

  loadCategories();
}, []);
```

**AFTER** - ✅ With cleanup:
```typescript
useEffect(() => {
  const controller = new AbortController();

  const loadCategories = async () => {
    try {
      const data = await fetchCategories(controller.signal);
      setCategories(data.results || []);
    } catch (err) {
      // Ignore abort errors (expected on unmount)
      if (err instanceof Error && err.name === 'AbortError') {
        return;
      }
      logger.error('Error loading categories', { error: err });
    }
  };

  loadCategories();

  return () => {
    controller.abort();  // ✅ Cancel request on unmount
  };
}, []);
```

**BEFORE (Lines 84-125)** - ❌ Memory leak:
```typescript
useEffect(() => {
  if (!query) {
    setSearchResults(null);
    return;
  }

  const performSearch = async () => {
    try {
      setLoading(true);
      setError(null);

      const results = await searchForum({
        q: query,
        category,
        author,
        date_from: dateFrom,
        date_to: dateTo,
        page,
        page_size: pageSize,
      });

      setSearchResults(results);
    } catch (err) {
      logger.error('Error performing search', { error: err });
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  performSearch();
}, [query, category, author, dateFrom, dateTo, page, pageSize]);
```

**AFTER** - ✅ With cleanup:
```typescript
useEffect(() => {
  if (!query) {
    setSearchResults(null);
    return;
  }

  const controller = new AbortController();

  const performSearch = async () => {
    try {
      setLoading(true);
      setError(null);

      const results = await searchForum({
        q: query,
        category,
        author,
        date_from: dateFrom,
        date_to: dateTo,
        page,
        page_size: pageSize,
      }, controller.signal);  // ✅ Pass signal

      setSearchResults(results);
    } catch (err) {
      // Ignore abort errors (expected on unmount or re-render)
      if (err instanceof Error && err.name === 'AbortError') {
        logger.debug('Search aborted (component unmounted or query changed)');
        return;
      }
      logger.error('Error performing search', { error: err });
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  performSearch();

  return () => {
    controller.abort();  // ✅ Cancel on unmount or dependency change
  };
}, [query, category, author, dateFrom, dateTo, page, pageSize]);
```

---

## Benefits

### 1. Prevents Memory Leaks
- Ongoing requests are cancelled when component unmounts
- No state updates on unmounted components

### 2. Improves Performance
- Cancelled requests free up browser resources
- Reduces unnecessary network traffic
- Prevents race conditions from stale responses

### 3. Better UX
- Fast navigation doesn't wait for old requests
- No console warnings
- Cleaner component lifecycle

### 4. TypeScript Type Safety
```typescript
// AbortSignal is built into TypeScript
interface FetchOptions {
  signal?: AbortSignal;  // Optional cleanup signal
}
```

---

## Implementation Checklist

### Phase 1: Service Layer (2 hours)
- [ ] Update `forumService.ts` - Add `signal?` parameter to all fetch functions
- [ ] Update `blogService.ts` - Add `signal?` parameter to all fetch functions
- [ ] Update `plantIdService.ts` - Add `signal?` parameter to identification calls
- [ ] Update `authService.ts` - Add `signal?` parameter (if applicable)

### Phase 2: Component Updates (3-4 hours)
- [ ] `SearchPage.tsx` - Add AbortController to 2 useEffect hooks
- [ ] Search for all `useEffect` + async patterns: `grep -r "useEffect.*async" src/`
- [ ] Audit and fix each component systematically

### Phase 3: Testing (1 hour)
- [ ] Test rapid navigation (mount/unmount cycles)
- [ ] Verify no console warnings about unmounted components
- [ ] Check Network tab - cancelled requests show proper status
- [ ] Memory profiling - verify no leaks

### Phase 4: Documentation (30 minutes)
- [ ] Add pattern to `TYPESCRIPT_MIGRATION_PATTERNS_CODIFIED.md`
- [ ] Update component README with AbortController examples
- [ ] Add to code review checklist

---

## Testing

### Manual Testing
```bash
# 1. Open browser DevTools → Network tab
# 2. Navigate to SearchPage
# 3. Type search query
# 4. Quickly navigate away before results load
# 5. Verify request shows "cancelled" status (not completed)

# Without fix: Request completes, warns about setState on unmounted component
# With fix: Request cancelled cleanly, no warnings
```

### Automated Testing (Vitest)
```typescript
import { render, waitFor } from '@testing-library/react';
import { vi } from 'vitest';

test('cancels fetch on unmount', async () => {
  const abortSpy = vi.spyOn(AbortController.prototype, 'abort');

  const { unmount } = render(<SearchPage />);

  // Unmount before fetch completes
  unmount();

  await waitFor(() => {
    expect(abortSpy).toHaveBeenCalled();
  });
});
```

---

## Browser Compatibility

AbortController is supported in all modern browsers:
- ✅ Chrome 66+
- ✅ Firefox 57+
- ✅ Safari 12.1+
- ✅ Edge 16+

---

## Common Pitfalls

### ❌ Don't Create New Controller on Every Render
```typescript
// ❌ Wrong - creates new controller on every render
const controller = new AbortController();

useEffect(() => {
  fetch('/api', { signal: controller.signal });
}, []);
```

### ✅ Create Controller Inside useEffect
```typescript
// ✅ Correct - controller scoped to effect
useEffect(() => {
  const controller = new AbortController();
  fetch('/api', { signal: controller.signal });
  return () => controller.abort();
}, []);
```

### ❌ Don't Log Abort Errors as Failures
```typescript
// ❌ Wrong - abort is expected, not an error
.catch(err => {
  console.error('Request failed:', err);  // Logs abort as error
});
```

### ✅ Ignore AbortError Gracefully
```typescript
// ✅ Correct - abort is cleanup, not failure
.catch(err => {
  if (err.name === 'AbortError') return;  // Expected
  console.error('Request failed:', err);   // Real error
});
```

---

## Acceptance Criteria

- [ ] All service functions accept optional `signal?: AbortSignal`
- [ ] All useEffect hooks with fetch have cleanup
- [ ] No "unmounted component" warnings in console
- [ ] Cancelled requests show in Network tab
- [ ] Tests verify abort behavior
- [ ] Pattern documented in codebase

---

## References

- **MDN**: [AbortController](https://developer.mozilla.org/en-US/docs/Web/API/AbortController)
- **React Docs**: [useEffect cleanup](https://react.dev/reference/react/useEffect#my-effect-runs-twice-when-the-component-mounts)
- **Issue**: #153
- **Estimated Effort**: 6-7 hours total

---

## Status

**Created**: November 13, 2025
**Reviewed**: Pending
**Implemented**: Partial (needs Phase 1-3)
**Priority**: MEDIUM (memory leak + UX improvement)
