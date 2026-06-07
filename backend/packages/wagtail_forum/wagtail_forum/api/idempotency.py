from django.core.cache import cache

IDEMPOTENCY_TTL = 60 * 60 * 24  # 24h


def idempotency_cache_key(request):
    """Return a per-(user, Idempotency-Key) cache key, or None if absent."""
    key = request.headers.get("Idempotency-Key")
    if key and request.user.is_authenticated:
        return f"forum:idem:{request.user.pk}:{key}"
    return None


def replay(cache_key):
    return cache.get(cache_key) if cache_key else None


def remember(cache_key, data):
    if cache_key:
        cache.set(cache_key, data, IDEMPOTENCY_TTL)
