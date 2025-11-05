"""
Forum signal handlers for cache invalidation.

Connects to Django model lifecycle signals to maintain cache freshness.
Follows project logging standards with [CACHE] bracketed prefix.

Signal Sources:
- django.db.models.signals.post_save: When thread/post is created/updated
- django.db.models.signals.post_delete: When thread/post is deleted

Pattern:
- Import services, not models (avoid circular imports)
- Log all invalidations for monitoring
- Keep handlers lightweight (cache operations are fast)
- Signal receivers registered in apps.py ready() method
"""

import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

logger = logging.getLogger(__name__)


# Lazy import to avoid circular dependencies
def get_forum_cache_service():
    """Lazy import ForumCacheService to avoid circular dependencies."""
    from .services.forum_cache_service import ForumCacheService
    return ForumCacheService


@receiver(post_save, sender='forum.Thread')
def invalidate_cache_on_thread_save(sender, instance, created, **kwargs):
    """
    Invalidate caches when thread is created or updated.

    Called when:
    - New thread is created
    - Thread title/content is updated
    - Thread is pinned/unpinned
    - Thread is locked/unlocked
    - Post count is updated

    Invalidation strategy:
    - Invalidate specific thread cache (by slug)
    - Invalidate ALL thread list caches
    - Invalidate thread's category cache

    Performance:
    - Cache invalidation: <5ms (delete operations are fast)
    """
    try:
        ForumCacheService = get_forum_cache_service()
        ForumCacheService.invalidate_thread(instance.slug)
        ForumCacheService.invalidate_thread_lists()

        # Invalidate category cache if thread count changed
        if instance.category:
            ForumCacheService.invalidate_category(instance.category.slug)

        action = "created" if created else "updated"
        logger.info(f"[CACHE] Invalidated caches for {action} thread: {instance.slug}")
    except Exception as e:
        logger.error(f"[CACHE] Error invalidating cache on thread save: {e}")


@receiver(post_delete, sender='forum.Thread')
def invalidate_cache_on_thread_delete(sender, instance, **kwargs):
    """
    Invalidate caches when thread is deleted.

    Called when:
    - Thread is hard deleted (not soft delete)
    - Cascade delete from category

    Invalidation strategy:
    - Invalidate specific thread cache (now returns 404)
    - Invalidate ALL thread list caches
    - Invalidate thread's category cache
    """
    try:
        ForumCacheService = get_forum_cache_service()
        ForumCacheService.invalidate_thread(instance.slug)
        ForumCacheService.invalidate_thread_lists()

        # Invalidate category cache (thread count changed)
        if instance.category:
            ForumCacheService.invalidate_category(instance.category.slug)

        logger.info(f"[CACHE] Invalidated caches for deleted thread: {instance.slug}")
    except Exception as e:
        logger.error(f"[CACHE] Error invalidating cache on thread delete: {e}")


@receiver(post_save, sender='forum.Post')
def invalidate_cache_on_post_save(sender, instance, created, **kwargs):
    """
    Invalidate caches when post is created or updated.

    Called when:
    - New post is created
    - Post content is edited
    - Post is marked as edited

    Invalidation strategy:
    - Invalidate post list for thread (all pages)
    - Invalidate thread cache (post count may have changed)
    - Invalidate thread lists (last_activity_at may have changed)

    Performance:
    - Post creation triggers multiple invalidations (acceptable)
    - Post edits only invalidate post list + thread detail
    """
    try:
        ForumCacheService = get_forum_cache_service()

        # Invalidate post list for this thread
        ForumCacheService.invalidate_post_list(str(instance.thread.id))

        # Invalidate thread cache (post count, last_activity_at changed)
        ForumCacheService.invalidate_thread(instance.thread.slug)

        # Invalidate thread lists (last_activity_at affects ordering)
        ForumCacheService.invalidate_thread_lists()

        action = "created" if created else "updated"
        logger.info(f"[CACHE] Invalidated caches for {action} post in thread: {instance.thread.slug}")
    except Exception as e:
        logger.error(f"[CACHE] Error invalidating cache on post save: {e}")


@receiver(post_delete, sender='forum.Post')
def invalidate_cache_on_post_delete(sender, instance, **kwargs):
    """
    Invalidate caches when post is deleted.

    Called when:
    - Post is hard deleted
    - Cascade delete from thread deletion

    Invalidation strategy:
    - Invalidate post list for thread
    - Invalidate thread cache (post count changed)
    - Invalidate thread lists
    """
    try:
        ForumCacheService = get_forum_cache_service()

        # Invalidate post list for this thread
        ForumCacheService.invalidate_post_list(str(instance.thread.id))

        # Invalidate thread cache (post count changed)
        ForumCacheService.invalidate_thread(instance.thread.slug)

        # Invalidate thread lists
        ForumCacheService.invalidate_thread_lists()

        logger.info(f"[CACHE] Invalidated caches for deleted post in thread: {instance.thread.slug}")
    except Exception as e:
        logger.error(f"[CACHE] Error invalidating cache on post delete: {e}")


@receiver(post_save, sender='forum.Category')
def invalidate_cache_on_category_save(sender, instance, created, **kwargs):
    """
    Invalidate caches when category is created or updated.

    Called when:
    - New category is created
    - Category name/description is updated
    - Category is activated/deactivated

    Invalidation strategy:
    - Invalidate specific category cache
    - Invalidate thread lists (if threads affected by category change)

    Note:
    - Category updates are rare, so aggressive invalidation is acceptable
    """
    try:
        ForumCacheService = get_forum_cache_service()
        ForumCacheService.invalidate_category(instance.slug)

        # If category was just created or is_active changed, invalidate thread lists
        if created or kwargs.get('update_fields') and 'is_active' in kwargs.get('update_fields', []):
            ForumCacheService.invalidate_thread_lists()

        action = "created" if created else "updated"
        logger.info(f"[CACHE] Invalidated caches for {action} category: {instance.slug}")
    except Exception as e:
        logger.error(f"[CACHE] Error invalidating cache on category save: {e}")


@receiver(post_delete, sender='forum.Category')
def invalidate_cache_on_category_delete(sender, instance, **kwargs):
    """
    Invalidate caches when category is deleted.

    Called when:
    - Category is hard deleted

    Invalidation strategy:
    - Invalidate specific category cache
    - Invalidate ALL thread lists (threads may have been cascade deleted)

    Note:
    - Category deletion is rare and typically cascades to threads
    - Aggressive invalidation is necessary
    """
    try:
        ForumCacheService = get_forum_cache_service()
        ForumCacheService.invalidate_category(instance.slug)
        ForumCacheService.invalidate_thread_lists()

        logger.info(f"[CACHE] Invalidated caches for deleted category: {instance.slug}")
    except Exception as e:
        logger.error(f"[CACHE] Error invalidating cache on category delete: {e}")


# ==================== Trust Level Signals ====================


@receiver(post_save, sender='forum.Post')
def update_user_trust_level_on_post(sender, instance, created, **kwargs):
    """
    Update user's trust level when they create a post.

    Called when:
    - New post is created (created=True)

    Strategy:
    - Only update on post creation (not edits)
    - Update trust level asynchronously
    - Invalidate user's cached limits

    Performance:
    - Triggered on every post creation
    - Trust level calculation: ~20ms
    - Cache invalidation: <5ms
    """
    if created:
        try:
            from .services.trust_level_service import TrustLevelService

            # Update trust level (may promote user)
            old_level, new_level, changed = TrustLevelService.update_user_trust_level(
                instance.author
            )

            if changed:
                logger.info(
                    f"[TRUST] User {instance.author.username} promoted after post: "
                    f"{old_level} → {new_level}"
                )

            # Always invalidate cache (daily counts changed)
            TrustLevelService.invalidate_user_cache(instance.author.id)

        except Exception as e:
            logger.error(f"[TRUST] Error updating trust level on post creation: {e}")


@receiver(post_save, sender='forum.UserProfile')
def invalidate_trust_cache_on_profile_update(sender, instance, **kwargs):
    """
    Invalidate trust level cache when UserProfile is updated.

    Called when:
    - Trust level is manually changed
    - Post count is updated
    - Helpful count is updated
    """
    try:
        from .services.trust_level_service import TrustLevelService
        TrustLevelService.invalidate_user_cache(instance.user.id)
        logger.debug(f"[CACHE] Invalidated trust cache for profile update: {instance.user.username}")
    except Exception as e:
        logger.error(f"[CACHE] Error invalidating trust cache on profile update: {e}")
