# Phase 2 Blog Caching Patterns - Codified into Reviewer Agent

**Date**: October 24, 2025
**Phase**: Wagtail Blog Phase 2 - Caching Implementation
**Agent Updated**: `code-review-specialist.md`
**Status**: Complete - 5 new patterns added

## Executive Summary

Successfully codified 5 critical patterns from the Phase 2 Wagtail blog caching implementation into the `code-review-specialist` agent. These patterns ensure future implementations benefit from the learnings and avoid the critical bugs discovered during development.

**Key Achievement**: User emphasized "you failed to call the code-review-agent this is becoming a problem" - This codification ensures ALL implementations automatically receive these pattern checks.

## Patterns Codified

### 1. Cache Key Tracking for Non-Redis Backends
**Pattern Number**: 10 in code-review-specialist.md
**Severity**: WARNING
**Category**: Dual-Strategy Cache Invalidation

**Problem Solved**:
- Redis `delete_pattern()` is NOT available on all cache backends
- Memcached, Database cache, and others lack pattern matching
- Relying solely on pattern matching causes silent invalidation failures

**Solution Pattern**:
```python
# Track keys during set operations
cache_key_set = f"{CACHE_PREFIX_BLOG_LIST}:_keys"
tracked_keys = cache.get(cache_key_set, set())
tracked_keys.add(cache_key)
cache.set(cache_key_set, tracked_keys, TTL)

# Dual-strategy invalidation
try:
    cache.delete_pattern(f"{CACHE_PREFIX_BLOG_LIST}:*")  # Primary: Redis
except AttributeError:
    # Fallback: Non-Redis backends
    for key in tracked_keys:
        cache.delete(key)
```

**Review Checklist**:
- [ ] Pattern matching wrapped in try/except AttributeError
- [ ] Cache keys tracked during set operations
- [ ] Tracked keys stored as sets (not lists)
- [ ] Graceful degradation (natural TTL expiration)
- [ ] Logging distinguishes between strategies

**Implementation Reference**:
- `apps/blog/services/blog_cache_service.py:153-168` (tracking)
- `apps/blog/services/blog_cache_service.py:250-271` (invalidation)

---

### 2. Conditional Prefetching with Action-Based Optimization
**Pattern Number**: 11 in code-review-specialist.md
**Severity**: BLOCKER
**Category**: Query Optimization / Memory Management

**Problem Solved**:
- Aggressive prefetching causes memory exhaustion on list views
- Loading full-size image renditions for 100+ posts crashes server
- One-size-fits-all prefetching wastes resources

**Solution Pattern**:
```python
def get_queryset(self):
    queryset = super().get_queryset()
    action = getattr(self, 'action', None)

    if action == 'list':
        # Limited prefetch, thumbnail renditions only
        queryset = queryset.prefetch_related(
            Prefetch('related_plant_species',
                    queryset=Through.objects[:MAX_RELATED_PLANT_SPECIES])
        )
        queryset = queryset.prefetch_related(
            Prefetch('featured_image',
                    queryset=Image.objects.prefetch_renditions('fill-400x300'))
        )

    elif action == 'retrieve':
        # Full prefetch, larger renditions
        queryset = queryset.prefetch_related(
            'related_plant_species',  # All, not limited
            Prefetch('featured_image',
                    queryset=Image.objects.prefetch_renditions('fill-800x600', 'width-1200'))
        )

    return queryset
```

**Review Checklist**:
- [ ] ViewSet uses `self.action` for conditional prefetching
- [ ] List views limit ManyToMany relationships
- [ ] Image renditions match action type (thumbnail vs full-size)
- [ ] Limits defined as constants (no magic numbers)
- [ ] try/except blocks for optional prefetch operations

**Implementation Reference**:
- `apps/blog/api/viewsets.py:146-211`

---

### 3. Hash Collision Prevention with Full 256-bit SHA-256
**Pattern Number**: 12 in code-review-specialist.md
**Severity**: WARNING
**Category**: Cache Key Generation

**Problem Solved**:
- Short hashes (8 chars = 32 bits) have high collision probability
- Birthday paradox: 50% collision at √(2^32) ≈ 65,000 combinations
- 64-bit hashes (16 chars): 50% collision at ~5 billion combinations
- Cache collisions cause wrong data to be served

**Solution Pattern**:
```python
# Full 256-bit hash: Virtually no collision risk (2^256 combinations)
filters_hash = hashlib.sha256(
    str(sorted(filters.items())).encode()
).hexdigest()  # Full 64 hex chars = 256 bits

cache_key = f"{CACHE_PREFIX_BLOG_LIST}:{page}:{limit}:{filters_hash}"
```

**Key Principles**:
- **64 characters (full SHA-256)** for virtually no collision risk
- **Sort dictionaries** before hashing (order-independence)
- **SHA-256 algorithm** (not MD5 or weak hashes)
- **Document collision probability** in comments

**Review Checklist**:
- [ ] Full SHA-256 hash used (64 characters, 256 bits)
- [ ] Filter dictionaries sorted before hashing
- [ ] SHA-256 used (not MD5)
- [ ] Hash lengths defined as constants

**Implementation Reference**:
- `apps/blog/services/blog_cache_service.py:122`

---

### 4. Wagtail Signal Handler Filtering with isinstance()
**Pattern Number**: 13 in code-review-specialist.md
**Severity**: BLOCKER (Critical Bug)
**Category**: Wagtail Multi-Table Inheritance

**Problem Solved**:
- **CRITICAL BUG**: `hasattr(instance, 'blogpostpage')` FAILS with Wagtail
- Wagtail uses multi-table inheritance (BlogPostPage IS a Page)
- Django creates separate tables: wagtailcore_page, blog_blogpostpage
- hasattr() looks for reverse relation that doesn't exist
- Result: Signal handlers NEVER execute for blog posts

**Solution Pattern**:
```python
@receiver(page_published)
def invalidate_blog_cache_on_publish(sender, **kwargs):
    from .models import BlogPostPage  # Import inside to avoid circular imports
    instance = kwargs.get('instance')

    # CORRECT: isinstance() handles multi-table inheritance
    if not instance or not isinstance(instance, BlogPostPage):
        return

    # Only BlogPostPage instances proceed
    BlogCacheService.invalidate_blog_post(instance.slug)
    BlogCacheService.invalidate_blog_lists()
```

**Anti-Pattern (FAILS)**:
```python
# BAD - hasattr() doesn't work with multi-table inheritance
if not hasattr(instance, 'blogpostpage'):
    return  # This incorrectly filters out BlogPostPage instances!

# BAD - Checking sender is unreliable
if sender != BlogPostPage:
    return  # May miss subclasses or related signals
```

**Why hasattr() Fails**:
1. BlogPostPage inherits from Page (multi-table inheritance)
2. Instance IS a BlogPostPage object, not a Page with blogpostpage attribute
3. hasattr() looks for reverse OneToOne relation
4. Relation doesn't exist in this direction
5. Signal handler silently skips ALL blog posts

**Review Checklist**:
- [ ] Uses `isinstance()` instead of `hasattr()`
- [ ] Model imported inside handler (avoid circular imports)
- [ ] Checks for `instance` existence before isinstance()
- [ ] Signal receivers registered in apps.py ready() method

**Implementation Reference**:
- `apps/blog/signals.py:53-70` (page_published)
- `apps/blog/signals.py:72-100` (page_unpublished)
- `apps/blog/signals.py:103-134` (post_delete)

---

### 5. Module Re-export Pattern for Package Shadowing
**Pattern Number**: 14 in code-review-specialist.md
**Severity**: WARNING
**Category**: Python Import System / Backward Compatibility

**Problem Solved**:
- Creating `services/` package shadows parent `services.py` file
- Python prefers packages over modules: `from .services import X` → `services/__init__.py`
- Existing code expects imports from `services.py`
- Without re-export: ImportError for all existing imports

**Solution Pattern**:
```python
# apps/blog/services/__init__.py
from .blog_cache_service import BlogCacheService

def __getattr__(name):
    """Lazy import from parent services.py to avoid circular imports."""
    if name in ('BlockAutoPopulationService', 'PlantDataLookupService'):
        import importlib.util
        import os

        # Load parent services.py as separate module
        parent_dir = os.path.dirname(os.path.dirname(__file__))
        services_file = os.path.join(parent_dir, 'services.py')

        spec = importlib.util.spec_from_file_location(
            "apps.blog._parent_services",
            services_file
        )
        parent_services_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(parent_services_module)

        return getattr(parent_services_module, name)

    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__all__ = ['BlogCacheService', 'BlockAutoPopulationService', 'PlantDataLookupService']
```

**Why This is Needed**:
- Python import resolution: `from .services import X`
  1. Check for `services/` directory → Found
  2. Import from `services/__init__.py`
  3. Never checks `services.py` file
- Existing code: `from .services import BlockAutoPopulationService`
- Without re-export: ImportError (class in services.py, not services/)

**Alternative Solution** (Breaking Change):
1. Rename `services.py` to `block_services.py`
2. Update all existing imports
3. Create `services/` package without conflict
4. No __getattr__ needed

**Review Checklist**:
- [ ] __getattr__ implemented for lazy re-export
- [ ] Raises AttributeError for unknown attributes
- [ ] __all__ defined with complete export list
- [ ] Imports are lazy (avoid circular dependencies)
- [ ] Documentation explains the shadowing

**Implementation Reference**:
- `apps/blog/services/__init__.py:18-38`

---

## Test Coverage Standards

All patterns were validated with comprehensive tests:
- **18/18 cache service tests passing** (100% pass rate)
- Edge cases: empty filters, complex filter values
- Hash collision prevention validated (64-char full SHA-256)
- Filter order independence tested
- Dual invalidation strategy tested (pattern + tracked keys)

**Grade**: A (94/100)
**Status**: APPROVED for production

## Integration with Reviewer Agents

### Updated Agent
- **File**: `/Users/williamtower/projects/plant_id_community/.claude/agents/code-review-specialist.md`
- **Lines Added**: ~230 lines (patterns 10-14)
- **Section**: "Wagtail CMS Performance Patterns (Phase 2 Blog Caching)"

### Review Workflow
```
1. Complete coding task
2. 🚨 INVOKE code-review-specialist (MANDATORY)
3. Wait for review to complete
4. Address any BLOCKERS identified
5. Fix any WARNINGS if applicable
6. THEN commit changes
7. THEN mark task complete
```

### Complementary Agents
- **code-review-specialist**: General code quality, security, testing, NEW Wagtail patterns
- **django-performance-reviewer**: Database optimization, N+1 queries, thread safety

## Key Learnings from Phase 2

### 1. Critical User Feedback
**Quote**: "you failed to call the code-review-agent this is becoming a problem"

**Action Taken**:
- Codified patterns immediately after implementation
- Updated agent with specific, actionable detection strategies
- Added comprehensive review checklists
- Included anti-patterns with explanations

### 2. Wagtail Multi-Table Inheritance
**Critical Discovery**: `hasattr()` does NOT work with Wagtail models
- Caused silent failure of ALL cache invalidation signals
- Bug was not caught until manual testing
- Pattern now BLOCKER-level in agent

### 3. Backend Portability
**Learning**: Don't assume Redis-specific features
- `delete_pattern()` not available on all backends
- Dual-strategy approach ensures compatibility
- Graceful degradation prevents silent failures

### 4. Memory Management
**Learning**: Conditional prefetching is REQUIRED for Wagtail
- Image renditions can exhaust memory
- Action-based optimization prevents crashes
- List vs detail views need different strategies

### 5. Import System Edge Cases
**Learning**: Package shadowing requires explicit handling
- Python prefers packages over modules
- __getattr__ enables lazy re-export
- Backward compatibility preserved without breaking changes

## Detection Strategies

Each pattern includes automated detection commands:

### 1. Cache Key Tracking
```bash
# Find pattern matching without try/except
grep -n "delete_pattern" apps/*/services/*.py | while read line; do
    file=$(echo $line | cut -d: -f1)
    linenum=$(echo $line | cut -d: -f2)
    if ! sed -n "$((linenum-5)),$((linenum+5))p" "$file" | grep -q "try:"; then
        echo "WARNING: $file:$linenum - delete_pattern without try/except"
    fi
done
```

### 2. Conditional Prefetching
```bash
# Find ViewSets with prefetch_related but no action check
grep -l "prefetch_related" apps/*/api/viewsets.py | while read file; do
    if ! grep -q "self.action" "$file"; then
        echo "WARNING: $file - prefetch_related without action check"
    fi
done
```

### 3. Hash Collision Risk
```bash
# Find truncated hashes (should use full 64-char SHA-256)
grep -n "hexdigest()\[:" apps/*/services/*.py | while read line; do
    echo "WARNING: $line - Hash is truncated, should use full SHA-256 (64 chars)"
done

# Verify full hashes are used
grep -n "hexdigest()$" apps/*/services/*.py | grep -v "hexdigest()\[:"
# All hash uses should appear here (full 64-character hashes)
```

### 4. Wagtail Signal Handlers
```bash
# Find hasattr() checks in signal handlers
grep -n "hasattr.*instance" apps/*/signals.py
# If found: BLOCKER - Should use isinstance() instead
```

### 5. Module Shadowing
```bash
# Find directories with same name as .py files
find apps/ -type d -name "services" -exec sh -c '
    parent=$(dirname "{}")
    if [ -f "$parent/services.py" ]; then
        echo "WARNING: {} shadows $parent/services.py - Check for __getattr__ re-export"
    fi
' \;
```

## Future Pattern Candidates

Patterns to monitor for future codification:

1. **Wagtail StreamField Validation**
   - Custom block validation patterns
   - Error handling for malformed StreamField data

2. **Image Rendition Caching**
   - Optimal rendition sizes for different contexts
   - Lazy vs eager rendition generation

3. **Wagtail API Serialization**
   - Nested serializer performance patterns
   - StreamField to JSON serialization

4. **Search Integration**
   - Wagtail search backend optimization
   - Full-text search with caching

## References

### Implementation Files
- `/Users/williamtower/projects/plant_id_community/.worktrees/wagtail-blog/backend/apps/blog/services/blog_cache_service.py`
- `/Users/williamtower/projects/plant_id_community/.worktrees/wagtail-blog/backend/apps/blog/signals.py`
- `/Users/williamtower/projects/plant_id_community/.worktrees/wagtail-blog/backend/apps/blog/api/viewsets.py`
- `/Users/williamtower/projects/plant_id_community/.worktrees/wagtail-blog/backend/apps/blog/services/__init__.py`

### Agent Configuration
- `/Users/williamtower/projects/plant_id_community/.claude/agents/code-review-specialist.md`

### Related Documentation
- `/Users/williamtower/projects/plant_id_community/.worktrees/wagtail-blog/backend/apps/blog/constants.py` - Cache timeout constants
- CLAUDE.md - Project-wide development patterns

## Conclusion

Successfully codified 5 critical patterns from Phase 2 Wagtail blog caching implementation. These patterns are now automatically checked by the `code-review-specialist` agent for ALL future code changes.

**Impact**:
- Prevents cache invalidation bugs (Pattern 4 was CRITICAL)
- Ensures backend portability (Pattern 1)
- Prevents memory exhaustion (Pattern 2)
- Reduces cache collision risk (Pattern 3)
- Maintains backward compatibility (Pattern 5)

**Next Steps**:
1. Use code-review-specialist agent on ALL code changes (MANDATORY)
2. Monitor for additional Wagtail-specific patterns
3. Consider creating dedicated `wagtail-cms-reviewer` agent if patterns grow
4. Update CLAUDE.md with reference to new Wagtail patterns section

**Agent Effectiveness**: Grade A (94/100) on Phase 2 review - Patterns are production-ready and well-documented.
