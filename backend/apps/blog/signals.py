"""
Blog signal handlers for cache invalidation.

Connects to Wagtail page lifecycle signals to maintain cache freshness.
Follows project logging standards with [CACHE] bracketed prefix.

Signal Sources:
- wagtail.signals.page_published: When blog post goes live
- wagtail.signals.page_unpublished: When blog post is taken offline
- django.db.models.signals.post_delete: When blog post is deleted

Pattern:
- Import services, not models (avoid circular imports)
- Log all invalidations for monitoring
- Keep handlers lightweight (cache operations are fast)
- Signal receivers registered in apps.py ready() method
"""

import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from wagtail.signals import page_published, page_unpublished

from .models import BlogCategory, BlogComment, BlogPostPage

logger = logging.getLogger(__name__)


# Import services here to avoid circular imports
# Models imported only for type hints and signal sender
def get_blog_cache_service():
    """Lazy import to avoid circular dependencies."""
    from .services.blog_cache_service import BlogCacheService

    return BlogCacheService


@receiver(page_published)
def invalidate_blog_cache_on_publish(sender, **kwargs):
    """
    Invalidate caches when blog post is published.

    Called when:
    - Blog post is published for first time
    - Blog post is republished after edits
    - Blog post is scheduled and goes live

    Invalidation strategy:
    - Invalidate specific post cache (by slug)
    - Invalidate ALL list caches (any list may include this post)
    - Do NOT invalidate categories yet (wait for category signal)

    Performance:
    - Cache invalidation: <5ms (delete operations are fast)
    - Acceptable trade-off for cache freshness
    """
    instance = kwargs.get("instance")

    # Only handle blog posts (not other Wagtail pages)
    # Use isinstance() check - Wagtail uses multi-table inheritance
    if not instance or not isinstance(instance, BlogPostPage):
        return

    try:
        BlogCacheService = get_blog_cache_service()
        BlogCacheService.invalidate_blog_post(instance.slug)
        BlogCacheService.invalidate_blog_lists()
        BlogCacheService.invalidate_popular_posts()  # TODO 040 fix
        logger.info(f"[CACHE] Invalidated caches for published post: {instance.slug}")
    except Exception as e:
        logger.error(f"[CACHE] Error invalidating cache on publish: {e}")


@receiver(page_unpublished)
def invalidate_blog_cache_on_unpublish(sender, **kwargs):
    """
    Invalidate caches when blog post is unpublished.

    Called when:
    - Blog post is manually unpublished
    - Blog post expires (scheduled unpublish)

    Invalidation strategy:
    - Invalidate specific post cache (now returns 404)
    - Invalidate ALL list caches (post no longer visible)
    """
    instance = kwargs.get("instance")

    # Only handle blog posts
    # Use isinstance() check - Wagtail uses multi-table inheritance
    if not instance or not isinstance(instance, BlogPostPage):
        return

    try:
        BlogCacheService = get_blog_cache_service()
        BlogCacheService.invalidate_blog_post(instance.slug)
        BlogCacheService.invalidate_blog_lists()
        BlogCacheService.invalidate_popular_posts()  # TODO 040 fix
        logger.info(f"[CACHE] Invalidated caches for unpublished post: {instance.slug}")
    except Exception as e:
        logger.error(f"[CACHE] Error invalidating cache on unpublish: {e}")


@receiver(post_delete, sender=BlogPostPage)
def invalidate_blog_cache_on_delete(sender, **kwargs):
    """
    Invalidate caches when blog post is deleted.

    Called when:
    - Blog post is permanently deleted from database

    Invalidation strategy:
    - Invalidate specific post cache (prevent 404 caching)
    - Invalidate ALL list caches (post removed from all lists)

    Scoped to ``sender=BlogPostPage`` so it does not fire on every project-wide
    delete; the isinstance() guard below is kept as defense-in-depth.
    """
    instance = kwargs.get("instance")

    if not instance or not isinstance(instance, BlogPostPage):
        return

    try:
        BlogCacheService = get_blog_cache_service()
        BlogCacheService.invalidate_blog_post(instance.slug)
        BlogCacheService.invalidate_blog_lists()
        BlogCacheService.invalidate_popular_posts()  # TODO 040 fix
        logger.info(f"[CACHE] Invalidated caches for deleted post: {instance.slug}")
    except Exception as e:
        logger.error(f"[CACHE] Error invalidating cache on delete: {e}")


@receiver(post_save, sender=BlogComment)
@receiver(post_delete, sender=BlogComment)
def invalidate_blog_cache_on_comment_change(sender, instance, **kwargs):
    """
    Invalidate the parent post's caches when a comment changes.

    Called when a comment is created, edited, approved/unapproved, or deleted.

    Cached post-detail and list responses embed ``comment_count`` (and popular
    posts rank on it), so a comment write must clear those keys — otherwise the
    count is stale until the 24h TTL expires (audit finding H4).
    """
    post = getattr(instance, "post", None)
    if post is None:
        return

    try:
        BlogCacheService = get_blog_cache_service()
        BlogCacheService.invalidate_blog_post(post.slug)
        BlogCacheService.invalidate_blog_lists()
        BlogCacheService.invalidate_popular_posts()
        logger.info(
            f"[CACHE] Invalidated caches for comment change on post: {post.slug}"
        )
    except Exception as e:
        logger.error(f"[CACHE] Error invalidating cache on comment change: {e}")


@receiver(post_save, sender=BlogCategory)
@receiver(post_delete, sender=BlogCategory)
def invalidate_blog_cache_on_category_change(sender, instance, **kwargs):
    """
    Invalidate category + list caches when a category changes.

    Called when a category is created, renamed, updated, or deleted. Cached blog
    list/detail responses embed the category's name/slug/color via
    ``BlogCategorySerializer``, so a category edit must clear those keys —
    otherwise they are stale until the 24h TTL expires (audit finding M8).
    """
    try:
        BlogCacheService = get_blog_cache_service()
        BlogCacheService.invalidate_blog_category(instance.slug)
        BlogCacheService.invalidate_blog_lists()
        logger.info(f"[CACHE] Invalidated caches for category change: {instance.slug}")
    except Exception as e:
        logger.error(f"[CACHE] Error invalidating category cache: {e}")
