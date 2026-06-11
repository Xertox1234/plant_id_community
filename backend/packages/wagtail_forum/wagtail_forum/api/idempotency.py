import hashlib
import json

from django.core.cache import cache

IDEMPOTENCY_TTL = 60 * 60 * 24  # 24h
PROCESSING_TTL = 60  # in-flight sentinel; short so a crash can't wedge the key


def idempotency_cache_key(request, scope):
    """Per-(endpoint, user, Idempotency-Key) cache key, or None if absent.

    The raw header is hashed before keying: it is user-controlled input, so an
    unbounded value would waste cache memory (24h TTL each) and non-Redis
    backends reject long keys or control characters. `scope` isolates
    endpoints so the same key sent to two endpoints cannot replay across them.
    """
    key = request.headers.get("Idempotency-Key")
    if key and request.user.is_authenticated:
        digest = hashlib.sha256(key.encode()).hexdigest()
        return f"forum:idem:{scope}:{request.user.pk}:{digest}"
    return None


def fingerprint(payload):
    """Stable hash of the request payload.

    Stored with the cached response so reusing a key with a DIFFERENT body is
    rejected (422) instead of silently replaying the old response — per
    draft-ietf-httpapi-idempotency-key-header.
    """
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()


def reserve(cache_key):
    """Mark the key in-flight. cache.add() is atomic: if a concurrent twin
    already reserved it, raise 409 instead of creating a duplicate resource."""
    if not cache_key:
        return
    from .exceptions import Conflict

    if not cache.add(cache_key, {"processing": True}, PROCESSING_TTL):
        raise Conflict("A request with this Idempotency-Key is being processed.")


def replay(cache_key):
    """Return the remembered {"data", "status", "fingerprint"} entry, or None."""
    return cache.get(cache_key) if cache_key else None


def remember(cache_key, data, status, payload_fingerprint):
    if cache_key:
        cache.set(
            cache_key,
            {"data": data, "status": status, "fingerprint": payload_fingerprint},
            IDEMPOTENCY_TTL,
        )
