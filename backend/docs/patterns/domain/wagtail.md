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

## `.specific()` Is Incompatible with `Prefetch(to_attr=…)`

**Rule**: Never add `.specific()` to a queryset used as the inner queryset of a `Prefetch`.

Wagtail's `.specific()` makes a second queryset pass that replaces the Python objects in memory. When you pass a `.specific()` queryset to `Prefetch("blogpostpage_set", queryset=posts_qs, to_attr="_prefetched_posts")`, the `to_attr` list is populated with the pre-specific objects. The `.specific()` re-fetch creates *new* objects that are never stored back into `to_attr` — the list stays populated with the originals, and any `prefetch_related` attached to the specific subclass is silently discarded.

```python
# WRONG — .specific() invalidates the Prefetch result
posts_qs = BlogPostPage.objects.live().public().specific()  # ❌
categories = BlogCategory.objects.prefetch_related(
    Prefetch("blogpostpage_set", queryset=posts_qs, to_attr="_posts")
)
for cat in categories:
    cat._posts  # contains base-class Page objects, not BlogPostPage specifics

# CORRECT — use the concrete subclass queryset directly
posts_qs = BlogPostPage.objects.live().public()  # ✅  already the concrete model
categories = BlogCategory.objects.prefetch_related(
    Prefetch("blogpostpage_set", queryset=posts_qs, to_attr="_posts")
)
```

The same incompatibility applies to `.specific()` on the outer queryset when the outer objects are later iterated and their prefetch caches accessed.

---

## `ParentalManyToManyField.set()` Does Not Persist After `add_child()`

**Rule**: After `parent.add_child(instance=post)`, do NOT call `post.categories.set([cat])` to persist M2M relations. Write directly to the through table instead.

`ParentalManyToManyField` is backed by `django-modelcluster`. Calling `.set()` (or `.add()`) updates only the in-memory modelcluster state; no SQL `INSERT` is issued. The through table row is never written, so `cat.blogpostpage_set.count()` returns 0.

This matters most in tests where you create pages via `add_child()` and then assign M2M relations:

```python
# WRONG — .set() only mutates in-memory modelcluster state; DB through table stays empty
post.categories.set([cat])  # ❌

# CORRECT — write the through-table row directly
Through = BlogPostPage.categories.through
Through.objects.get_or_create(blogpostpage=post, blogcategory=cat)  # ✅
```

The same applies to `.add()` and `.remove()` when called on a page that was saved via `add_child()`. If the page goes through a Wagtail form (e.g., the admin editor), the form save handles persistence correctly — the workaround is only needed for programmatic creation.

---

## Wagtail Version — Single Source of Truth

Dev and prod run the **same** Wagtail version. `requirements-dev.txt` is now a
thin overlay (`-r requirements.txt`) with no pins of its own, so the authoritative
version lives only in `requirements.txt` (`wagtail==7.4`).

This used to be a dev/prod split (`requirements-dev.txt: wagtail==7.1.2` vs
`requirements.txt: wagtail==7.4`) that papered over version-specific breakage —
most notably the Django 6.0 `format_html` admin 500 that "worked on 5.x".
Reconciled in todo 217; there is no longer a divergence to annotate.

## Publish-Signal Semantics for DraftStateMixin Snippets (2026-06-10, forum audit)

`wagtail.signals.published` fires on **every** publish — first publish, moderator
edit-republish, scheduled republish. Side effects that must happen once (push
notifications, "created" events) need a first-publish guard:

```python
def _is_first_publish(instance):
    # Wagtail stamps both with the same value on the first publish; later
    # publishes move only last_published_at.
    return (
        instance.first_published_at is not None
        and instance.first_published_at == instance.last_published_at
    )
```

Caveats discovered the hard way:

- **Republish only fresh instances.** `save_revision()` snapshots the in-memory
  instance; calling it on a stale object (pre-publish timestamps) and publishing
  resets `first_published_at` itself. Admin flows load fresh; programmatic
  republish must `refresh_from_db()` first.
- **`unpublished` + `post_delete` are part of the same contract** — any
  denormalized counter or derived privilege maintained on `published` goes stale
  (or stays wrongly granted) without the reverse hooks.
- **Activity ordering should derive from `first_published_at`**, not
  `last_published_at` — otherwise an edit-republish of an old post stamps "new
  activity" and corrupts `-last_post_at` ordering.
- **`objects.create()` is born `live=True`** for DraftStateMixin models — test
  fixtures built on it never exercise the draft→publish transitions.
