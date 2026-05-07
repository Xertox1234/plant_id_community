# Wagtail CMS Patterns

**Versions**: dev `wagtail==7.1.2` · prod `wagtail==7.4`
Any pattern that behaves differently between versions must note which applies.

---

## Multi-Table Inheritance — Page Type Checks

**Rule**: Always use `isinstance(instance, BlogPostPage)` — never `hasattr(instance, 'blogpostpage')`.

Multi-table inheritance makes `hasattr` checks unreliable in signal handlers because the parent `Page` model is what receives the signal, and attribute lookup on the parent doesn't guarantee the child table row exists.

```python
# CORRECT
@receiver(page_published)
def invalidate_blog_cache(sender, instance, **kwargs):
    if isinstance(instance, BlogPostPage):
        BlogCacheService.invalidate_post_cache(instance.slug)

# WRONG — hasattr returns False when page_published fires on Page base class
@receiver(page_published)
def invalidate_blog_cache(sender, instance, **kwargs):
    if hasattr(instance, 'blogpostpage'):  # ❌ unreliable
        ...
```

---

## Cache Invalidation — Dual Strategy

Invalidate both the individual post cache AND all list key variations on any publish/unpublish.

Cache keys:
- Post detail: `blog:post:{slug}` (TTL 24h)
- Post list: `blog:list:{page}:{limit}:{filters_hash}` (TTL 24h)
- Popular posts: `blog:popular:{period}:{limit}` (TTL 1h)
- Categories: `blog:categories` (TTL 24h)

```python
class BlogCacheService:
    @staticmethod
    def invalidate_post_cache(slug: str) -> None:
        cache.delete(f"blog:post:{slug}")
        # Also invalidate list caches — use wildcard delete via redis-py scan
        BlogCacheService._delete_pattern("blog:list:*")

    @staticmethod
    def _delete_pattern(pattern: str) -> None:
        keys = cache.keys(pattern)
        if keys:
            cache.delete_many(keys)
```

---

## Wagtail Admin URL

Wagtail admin is at `/cms/`, not `/admin/`. Never hardcode `/admin/` in code that references the CMS.

---

## StreamField API Serialization

Wagtail API v2 may return `content_blocks` as a JSON string rather than a parsed object. Consumers must handle both:

```python
import json

content_blocks = api_response.get("content_blocks", "[]")
if isinstance(content_blocks, str):
    content_blocks = json.loads(content_blocks)
```

---

## AI Integration (Wagtail AI 3.0)

- AI prompts live in `apps/blog/ai_integration.py` — not scattered through views.
- All AI generation routes require lazy-init pattern so tests can run without credentials.
- Rate limits enforced: 10/50/100 calls per hour by user tier (NEW/BASIC/TRUSTED).

---

## Version Mismatch — Dev vs Prod

The project runs different Wagtail versions in dev and production:
- `requirements-dev.txt`: `wagtail==7.1.2`
- `requirements.txt`: `wagtail==7.4`

When writing migration files, admin configuration, or using any Wagtail API that changed between these versions, add an explicit comment noting which version the code targets.
