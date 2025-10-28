# Rate Limiting Policy

**Last Updated**: October 27, 2025
**Status**: Production-Ready
**Related**: Week 4 Authentication Security, TODO #029

## Overview

This document defines the comprehensive rate limiting policy for the Plant ID Community API. Rate limiting protects against abuse, ensures fair resource allocation, and maintains service quality for all users.

## Configuration Location

All rate limits are centralized in:
```
backend/apps/plant_identification/constants.py
```

Configuration constant: `RATE_LIMITS`

## Rate Limit Tiers

### Anonymous Users (IP-based)

Anonymous users are identified by IP address and have strict limits to prevent abuse:

| Endpoint Type | Rate Limit | Rationale |
|--------------|------------|-----------|
| Plant Identification | 10/hour | Expensive API calls (Plant.id, PlantNet) |
| Read-only Operations | 100/hour | General browsing, viewing results |
| Search Operations | 30/hour | Database search endpoints |

**Key Type**: `ip` (based on client IP address)

### Authenticated Users (user-based)

Authenticated users receive higher limits for better user experience:

| Endpoint Type | Rate Limit | Rationale |
|--------------|------------|-----------|
| Plant Identification | 100/hour | 10x anonymous limit for verified users |
| Write Operations | 50/hour | Create/update operations (gardens, notes) |
| Read-only Operations | 1000/hour | High limit for active users |
| Search Operations | 100/hour | Enhanced search capabilities |
| Care Instructions | 30/minute | Frequent lookups during plant care |
| AI Regeneration | 5/minute | Expensive AI operations (OpenAI API) |

**Key Type**: `user` (based on authenticated user ID)

### Authentication Endpoints (IP-based, Security-focused)

Authentication endpoints have strict limits to prevent brute force attacks:

| Endpoint | Rate Limit | Rationale |
|----------|------------|-----------|
| Login | 5/15 minutes | Prevent credential stuffing attacks |
| Registration | 3/hour | Prevent mass account creation |
| Token Refresh | 10/hour | Normal usage with buffer |
| Password Reset | 3/hour | Prevent email flooding (when implemented) |

**Key Type**: `ip` (IP-based for security)

**Related**: Week 4 Authentication Security implements account lockout after 10 failed attempts, working in conjunction with rate limiting.

### User Feature Endpoints (user-based)

Feature-specific endpoints for authenticated users:

| Endpoint Type | Rate Limit | Rationale |
|--------------|------------|-----------|
| Push Notifications | 10/hour | Subscription management |
| Care Reminders | 20/hour | Frequent actions (complete, snooze, skip) |
| Profile Updates | 10/hour | Prevent rapid profile changes |

**Key Type**: `user` (user-based for per-user limits)

### Blog/Content Endpoints (user_or_ip-based)

Blog API endpoints (when implemented):

| Endpoint Type | Rate Limit | Rationale |
|--------------|------------|-----------|
| Read Operations | 100/hour | Blog post viewing |
| Write Operations | 10/hour | Blog post creation (authenticated only) |
| Comments | 20/hour | Comment submission (when implemented) |

**Key Type**: `user_or_ip` (user if authenticated, IP otherwise)

## Implementation Pattern

### Standard Decorator Usage

```python
from django_ratelimit.decorators import ratelimit
from apps.plant_identification.constants import RATE_LIMITS

# Anonymous endpoint (IP-based)
@ratelimit(
    key='ip',
    rate=RATE_LIMITS['anonymous']['plant_identification'],
    method='POST',
    block=True
)
def identify_plant(request):
    pass

# Authenticated endpoint (user-based)
@ratelimit(
    key='user',
    rate=RATE_LIMITS['authenticated']['plant_identification'],
    method='POST',
    block=True
)
def identify_plant(request):
    pass

# Mixed authentication (user_or_ip)
@ratelimit(
    key='user_or_ip',
    rate=RATE_LIMITS['authenticated']['search'],
    method='GET',
    block=True
)
def search_plants(request):
    pass
```

### Django REST Framework (DRF) ViewSets

```python
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator

@method_decorator(
    ratelimit(
        key='user',
        rate=RATE_LIMITS['authenticated']['write_operations'],
        method='POST',
        block=True
    ),
    name='create'
)
class PlantIdentificationViewSet(viewsets.ModelViewSet):
    pass
```

## Rate Limit Headers (Future Enhancement)

Standard HTTP headers for rate limit visibility:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1698765432
```

**Status**: Not yet implemented (planned for future enhancement)

## Response Format

When rate limit is exceeded, the API returns:

```json
{
  "detail": "Request was throttled. Expected available in 3600 seconds."
}
```

**HTTP Status**: `429 Too Many Requests`

## Endpoint Audit

### Plant Identification App

| Endpoint | Current Rate Limit | Centralized Config |
|----------|-------------------|-------------------|
| `POST /api/v1/plant-identification/identify/` | `10/m` (user) | `RATE_LIMITS['authenticated']['plant_identification']` |
| `GET /api/v1/care-instructions/<id>/` | `30/m` (user_or_ip) | `RATE_LIMITS['authenticated']['care_instructions']` |
| `GET /api/v1/search-local-plants/` | `20/m` (user_or_ip) | `RATE_LIMITS['authenticated']['search']` |
| `GET /api/v1/search-local-diseases/` | `20/m` (user_or_ip) | `RATE_LIMITS['authenticated']['search']` |
| `GET /api/v1/enrich-plant-data/` | `30/m` (user_or_ip) | `RATE_LIMITS['authenticated']['read_only']` |
| `GET /api/v1/search-plant-species/` | `30/m` (user_or_ip) | `RATE_LIMITS['authenticated']['search']` |
| `GET /api/v1/plant-characteristics/<id>/` | `30/m` (user_or_ip) | `RATE_LIMITS['authenticated']['read_only']` |
| `GET /api/v1/plant-growth-info/<id>/` | `30/m` (user_or_ip) | `RATE_LIMITS['authenticated']['read_only']` |
| `POST /api/v1/regenerate-care-instructions/<id>/` | `5/m` (user_or_ip) | `RATE_LIMITS['authenticated']['regenerate']` |

### Users App

| Endpoint | Current Rate Limit | Centralized Config |
|----------|-------------------|-------------------|
| `POST /api/users/register/` | `3/h` (ip) | `RATE_LIMITS['auth_endpoints']['register']` |
| `POST /api/users/login/` | `5/15m` (ip) | `RATE_LIMITS['auth_endpoints']['login']` |
| `POST /api/users/token/refresh/` | `10/h` (ip) | `RATE_LIMITS['auth_endpoints']['token_refresh']` |
| `POST /api/users/push-notifications/subscribe/` | `10/h` (user) | `RATE_LIMITS['user_features']['push_notifications']` |
| `POST /api/users/care-reminders/<uuid>/action/` | `20/h` (user) | `RATE_LIMITS['user_features']['care_reminders']` |

### Blog App

| Endpoint | Current Status | Recommendation |
|----------|---------------|----------------|
| `GET /api/v2/blog-posts/` | No rate limit | Add `RATE_LIMITS['blog']['read']` |
| `GET /api/v2/blog-posts/<id>/` | No rate limit | Add `RATE_LIMITS['blog']['read']` |
| `GET /api/v2/blog-categories/` | No rate limit | Add `RATE_LIMITS['blog']['read']` |
| `GET /api/v2/blog-authors/` | No rate limit | Add `RATE_LIMITS['blog']['read']` |

**Note**: Blog endpoints are Wagtail API v2 and may require different rate limiting approach.

## Testing Rate Limits

### Manual Testing

```bash
# Test anonymous plant identification (10/hour)
for i in {1..11}; do
  curl -X POST http://localhost:8000/api/v1/plant-identification/identify/ \
    -H "Content-Type: multipart/form-data" \
    -F "image=@test_plant.jpg"
done
# Expected: 11th request returns 429

# Test authenticated login (5/15min)
for i in {1..6}; do
  curl -X POST http://localhost:8000/api/users/login/ \
    -H "Content-Type: application/json" \
    -d '{"username":"test","password":"wrong"}'
done
# Expected: 6th request returns 429 or 403 (account lockout)
```

### Automated Testing

```python
from django.test import TestCase
from django.contrib.auth import get_user_model

class RateLimitTestCase(TestCase):
    def test_plant_identification_rate_limit(self):
        """Test plant identification rate limit (10/hour for anonymous)"""
        for i in range(10):
            response = self.client.post('/api/v1/plant-identification/identify/')
            self.assertIn(response.status_code, [200, 400])  # Allow success or validation error

        # 11th request should be rate limited
        response = self.client.post('/api/v1/plant-identification/identify/')
        self.assertEqual(response.status_code, 429)
```

## Monitoring and Metrics

### Log Format

Rate limit events should be logged with `[RATELIMIT]` prefix:

```python
import logging
logger = logging.getLogger(__name__)

# When rate limit is hit
logger.warning(
    "[RATELIMIT] Rate limit exceeded: endpoint=%s, key=%s, limit=%s",
    request.path,
    request.META.get('REMOTE_ADDR'),
    rate_limit
)
```

### Metrics to Track

1. **Rate Limit Hits by Endpoint**: Which endpoints are most constrained?
2. **Rate Limit Hits by User**: Are specific users hitting limits frequently?
3. **Rate Limit Hits by IP**: Identify potential abuse patterns
4. **Time Distribution**: When do rate limits get hit most often?

### Admin Dashboard (Future Enhancement)

Admin users should be able to view:
- Rate limit hit statistics
- Top rate-limited IPs/users
- Rate limit configuration per endpoint
- Option to temporarily increase limits for specific users

## Adjusting Rate Limits

### Process

1. **Identify Need**: Performance testing, user feedback, or abuse patterns
2. **Update Constants**: Modify `RATE_LIMITS` in `constants.py`
3. **Document Change**: Update this file with rationale
4. **Test Impact**: Verify new limits work as expected
5. **Monitor**: Watch metrics for unintended consequences

### Example Scenarios

**Scenario 1: Users complaining about search limits**
- Current: `30/h` for anonymous search
- Analysis: Search is cheap (database-only, no external APIs)
- Action: Increase to `100/h` for anonymous, `500/h` for authenticated
- Rationale: Database search is not resource-intensive

**Scenario 2: Abuse detected on registration endpoint**
- Current: `3/h` per IP
- Analysis: Bot registering accounts from multiple IPs
- Action: Add CAPTCHA or reduce to `2/h`
- Rationale: Legitimate users rarely register more than once

## Security Considerations

### IP Spoofing Protection

Rate limiting by IP can be bypassed if users spoof their IP address. The users app implements IP spoofing detection (Week 4 Authentication Security):

```python
from apps.users.services.security_service import SecurityService

# Validate IP is not spoofed
if not SecurityService.is_valid_client_ip(request):
    logger.warning("[SECURITY] IP spoofing detected")
    # Handle accordingly
```

### Distributed Denial of Service (DDoS)

Rate limiting helps mitigate application-level DDoS attacks but should be combined with:
- **Cloudflare/CDN**: Network-level DDoS protection
- **Web Application Firewall (WAF)**: Pattern-based blocking
- **Geographic Restrictions**: Block countries with high abuse rates

### Account Lockout Integration

Login endpoint has both rate limiting AND account lockout (Week 4):
- **Rate Limit**: `5/15m` per IP (prevents brute force)
- **Account Lockout**: 10 failed attempts locks account for 1 hour (prevents credential stuffing)

These work together:
1. First 5 attempts: rate limited (IP-based)
2. Attempts 6-10: may hit account lockout (user-based)
3. After 10 attempts: account locked for 1 hour + IP rate limited

## Related Documentation

- **Week 4 Authentication Security**: `backend/docs/security/AUTHENTICATION_SECURITY.md`
- **Circuit Breakers**: `backend/docs/quick-wins/circuit-breaker.md`
- **Distributed Locks**: `backend/docs/quick-wins/distributed-locks.md`
- **django-ratelimit**: https://django-ratelimit.readthedocs.io/

## Changelog

### October 27, 2025
- Initial documentation created (TODO #029)
- Centralized rate limit configuration in `constants.py`
- Standardized rate limit policy across all apps
- Documented all current endpoints and their limits

## Future Enhancements

1. **Rate Limit Headers**: Add `X-RateLimit-*` headers to all responses
2. **Admin Dashboard**: Real-time rate limit monitoring and configuration
3. **Dynamic Rate Limits**: Adjust based on system load or time of day
4. **User-Specific Overrides**: Allow trusted users higher limits
5. **Redis-Based Limits**: Move from in-memory to distributed rate limiting (for multi-server deployments)
6. **CAPTCHA Integration**: Add CAPTCHA for endpoints that hit rate limits frequently
