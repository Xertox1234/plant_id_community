"""
Blog app tests package.

Test Coverage:
- test_blog_cache_service.py: BlogCacheService caching functionality (20+ tests)
  - Cache hit/miss behavior for posts and lists
  - Hash collision prevention (16-char validation)
  - Filter order independence
  - Pattern matching vs tracked key invalidation
  - Edge cases (empty filters, complex values)

- test_blog_signals.py: Signal handlers and cache invalidation (15+ tests)
  - Cache invalidation on publish/unpublish/delete
  - Non-blog page filtering
  - Error handling and logging
  - Full workflow integration tests

- test_blog_viewsets_caching.py: ViewSet caching integration (18+ tests)
  - Cache hit/miss performance validation
  - Pagination cache key generation
  - Filter cache key generation
  - Conditional prefetching behavior
  - Performance targets (<50ms cached)

Run all tests:
    python manage.py test apps.blog --keepdb -v 2

Run specific test file:
    python manage.py test apps.blog.tests.test_blog_cache_service --keepdb -v 2
    python manage.py test apps.blog.tests.test_blog_signals --keepdb -v 2
    python manage.py test apps.blog.tests.test_blog_viewsets_caching --keepdb -v 2
"""
