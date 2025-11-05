# Trust Level Signal Integration Guide

**Version**: 1.0.0
**Last Updated**: November 5, 2025
**Status**: ✅ Implemented & Tested

## Overview

This guide explains how to integrate with the Trust Level System's signal-based architecture for automatic user progression, permission updates, and event tracking.

## Signal: `trust_level_changed`

**Location**: `apps/forum/services/trust_level_service.py:48`

Emitted when a user's trust level changes (e.g., promotion from NEW → BASIC).

### Signal Parameters

```python
from django.dispatch import Signal

trust_level_changed = Signal()  # Provides: user, old_level, new_level

# Emitted by:
TrustLevelService.update_user_trust_level(user)
```

**Arguments**:
- `sender`: `TrustLevelService` class
- `user`: Django User instance that was promoted
- `old_level`: Previous trust level string ('new', 'basic', 'trusted', 'veteran', 'expert')
- `new_level`: New trust level string
- `**kwargs`: Additional Django signal kwargs

### Example: Send Promotion Email

```python
from django.dispatch import receiver
from apps.forum.services.trust_level_service import trust_level_changed
from apps.notifications.services import EmailService

@receiver(trust_level_changed)
def send_promotion_email(sender, user, old_level, new_level, **kwargs):
    """Send congratulations email when user is promoted."""
    EmailService.send_template_email(
        to_email=user.email,
        template='emails/trust_level_promotion.html',
        context={
            'username': user.username,
            'old_level': old_level.title(),
            'new_level': new_level.title(),
            'new_permissions': TrustLevelService.get_trust_level_info(user)['permissions'],
        }
    )
```

### Example: Track Metrics in Analytics

```python
from django.dispatch import receiver
from apps.forum.services.trust_level_service import trust_level_changed
from apps.analytics.services import AnalyticsService

@receiver(trust_level_changed)
def track_trust_level_promotion(sender, user, old_level, new_level, **kwargs):
    """Track user progression in analytics."""
    AnalyticsService.track_event(
        event_name='trust_level_promotion',
        user_id=user.id,
        properties={
            'old_level': old_level,
            'new_level': new_level,
            'days_since_signup': (timezone.now() - user.date_joined).days,
            'post_count': user.forum_posts.count(),
        }
    )
```

### Example: Award Badges

```python
from django.dispatch import receiver
from apps.forum.services.trust_level_service import trust_level_changed
from apps.gamification.models import Badge

TRUST_LEVEL_BADGES = {
    'basic': 'verified_member',
    'trusted': 'trusted_contributor',
    'veteran': 'community_veteran',
    'expert': 'expert_contributor',
}

@receiver(trust_level_changed)
def award_trust_level_badge(sender, user, old_level, new_level, **kwargs):
    """Award badge when user reaches new trust level."""
    badge_slug = TRUST_LEVEL_BADGES.get(new_level)
    if badge_slug:
        Badge.objects.get_or_create(
            user=user,
            badge_type=badge_slug,
            defaults={
                'awarded_at': timezone.now(),
                'description': f'Reached {new_level} trust level'
            }
        )
```

### Example: Webhook Notification

```python
from django.dispatch import receiver
from apps.forum.services.trust_level_service import trust_level_changed
import requests
import logging

logger = logging.getLogger(__name__)

@receiver(trust_level_changed)
def notify_webhook_on_promotion(sender, user, old_level, new_level, **kwargs):
    """Send webhook notification to external system."""
    webhook_url = settings.TRUST_LEVEL_WEBHOOK_URL
    if not webhook_url:
        return

    payload = {
        'event': 'trust_level_changed',
        'user_id': str(user.id),
        'username': user.username,
        'old_level': old_level,
        'new_level': new_level,
        'timestamp': timezone.now().isoformat(),
    }

    try:
        response = requests.post(webhook_url, json=payload, timeout=5)
        response.raise_for_status()
        logger.info(f"[WEBHOOK] Sent trust level promotion for {user.username}: {old_level} → {new_level}")
    except Exception as e:
        logger.error(f"[WEBHOOK] Failed to send trust level promotion: {e}")
```

## Automatic Signal Emissions

The following actions **automatically** emit the `trust_level_changed` signal:

### 1. Post Creation Signal (apps/forum/signals.py:223-261)

```python
@receiver(post_save, sender='forum.Post')
def update_user_trust_level_on_post(sender, instance, created, **kwargs):
    """
    Update user's trust level when they create a post.

    Triggered: Every post creation
    Performance: ~20ms (trust level calculation + cache invalidation)
    """
    if created:
        from .services.trust_level_service import TrustLevelService

        old_level, new_level, changed = TrustLevelService.update_user_trust_level(
            instance.author
        )

        if changed:
            # trust_level_changed signal emitted automatically
            logger.info(f"[TRUST] User {instance.author.username} promoted: {old_level} → {new_level}")
```

**Trigger**: Every time a user creates a forum post
**Frequency**: High (depends on user activity)
**Performance**: ~25ms total (trust level check + cache operations)

### 2. Management Command: Bulk Updates

```bash
# Update trust levels for all users (cron job)
python manage.py setup_trust_levels --update-users
```

**Trigger**: Manual cron job (recommended: daily at 2 AM)
**Frequency**: Low (scheduled job)
**Performance**: ~20ms per user
**Signal Emissions**: One per promoted user

## Registering Signal Handlers

### AppConfig Registration (Recommended)

Register signal handlers in your app's `apps.py` to ensure they're loaded:

```python
# apps/notifications/apps.py
from django.apps import AppConfig

class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.notifications'

    def ready(self):
        """Import signal handlers when app is ready."""
        from . import signals  # Import signals.py to register handlers
```

```python
# apps/notifications/signals.py
from django.dispatch import receiver
from apps.forum.services.trust_level_service import trust_level_changed

@receiver(trust_level_changed)
def send_promotion_email(sender, user, old_level, new_level, **kwargs):
    """Handler registered when NotificationsConfig.ready() is called."""
    # ... send email
```

### Direct Registration (Testing)

For testing or one-off handlers:

```python
from apps.forum.services.trust_level_service import trust_level_changed

def my_handler(sender, user, old_level, new_level, **kwargs):
    print(f"{user.username} promoted: {old_level} → {new_level}")

# Connect manually
trust_level_changed.connect(my_handler)

# Test
TrustLevelService.update_user_trust_level(some_user)  # Emits signal

# Disconnect after test
trust_level_changed.disconnect(my_handler)
```

## Signal Handler Best Practices

### 1. Keep Handlers Lightweight

```python
# ❌ BAD - Heavy processing blocks signal emission
@receiver(trust_level_changed)
def slow_handler(sender, user, old_level, new_level, **kwargs):
    # Blocks for 5 seconds!
    expensive_calculation()
    send_10_emails()
    update_external_api()

# ✅ GOOD - Offload to background task
@receiver(trust_level_changed)
def async_handler(sender, user, old_level, new_level, **kwargs):
    # Enqueue background task (Celery, Django-RQ, etc.)
    send_promotion_email_task.delay(user.id, old_level, new_level)
```

### 2. Handle Exceptions Gracefully

```python
# ✅ GOOD - Don't let one handler failure break others
@receiver(trust_level_changed)
def safe_handler(sender, user, old_level, new_level, **kwargs):
    try:
        risky_operation()
    except Exception as e:
        logger.error(f"[TRUST] Handler failed for {user.username}: {e}")
        # Signal continues to other handlers
```

### 3. Use Idempotency for External Calls

```python
# ✅ GOOD - Safe to retry/re-run
@receiver(trust_level_changed)
def idempotent_handler(sender, user, old_level, new_level, **kwargs):
    # Use get_or_create for idempotency
    Badge.objects.get_or_create(
        user=user,
        badge_type=f'trust_level_{new_level}',
        defaults={'awarded_at': timezone.now()}
    )
```

### 4. Avoid Circular Signal Dependencies

```python
# ❌ BAD - Creates infinite loop!
@receiver(trust_level_changed)
def circular_handler(sender, user, old_level, new_level, **kwargs):
    # This triggers another trust_level_changed signal!
    TrustLevelService.update_user_trust_level(user)  # DON'T DO THIS

# ✅ GOOD - One-way data flow
@receiver(trust_level_changed)
def one_way_handler(sender, user, old_level, new_level, **kwargs):
    # Update external state, don't modify trust level
    update_leaderboard(user, new_level)
```

## Testing Signal Handlers

### Unit Test Example

```python
from django.test import TestCase
from unittest.mock import patch, call
from apps.forum.services.trust_level_service import TrustLevelService, trust_level_changed

class TrustLevelSignalTests(TestCase):

    def test_signal_emitted_on_promotion(self):
        """Verify signal is emitted when user is promoted."""
        user = User.objects.create_user(username='testuser')

        # Mock the signal handler
        handler = MagicMock()
        trust_level_changed.connect(handler)

        # Promote user (NEW → BASIC requires 7 days + 5 posts)
        user.date_joined = timezone.now() - timedelta(days=8)
        user.save()

        for i in range(5):
            Post.objects.create(author=user, thread=some_thread, content=f'Post {i}')

        # Trigger trust level update
        old_level, new_level, changed = TrustLevelService.update_user_trust_level(user)

        # Verify signal was emitted
        self.assertTrue(changed)
        handler.assert_called_once()

        # Verify signal arguments
        call_args = handler.call_args
        self.assertEqual(call_args.kwargs['user'], user)
        self.assertEqual(call_args.kwargs['old_level'], 'new')
        self.assertEqual(call_args.kwargs['new_level'], 'basic')

        # Cleanup
        trust_level_changed.disconnect(handler)

    @patch('apps.notifications.services.EmailService.send_template_email')
    def test_promotion_email_sent(self, mock_send_email):
        """Verify promotion email is sent when user is promoted."""
        user = User.objects.create_user(username='testuser', email='test@example.com')

        # ... setup user to be promoted ...

        TrustLevelService.update_user_trust_level(user)

        # Verify email was sent
        mock_send_email.assert_called_once()
        self.assertIn('trust_level_promotion.html', str(mock_send_email.call_args))
```

## Performance Considerations

### Signal Emission Overhead

- **Trust level calculation**: ~20ms (database query with caching)
- **Signal emission**: <1ms (synchronous dispatch)
- **Handler execution**: Varies (depends on handler complexity)

### Optimization Tips

1. **Use caching**: Trust level data is cached for 1 hour (90% query reduction)
2. **Batch updates**: Use `update_all_user_trust_levels()` for bulk operations
3. **Async handlers**: Offload heavy work to background tasks
4. **Selective handlers**: Only process signals when `changed=True`

```python
# Example: Only process actual promotions
@receiver(trust_level_changed)
def efficient_handler(sender, user, old_level, new_level, **kwargs):
    if old_level == new_level:
        return  # No change, skip processing

    # Process promotion
    ...
```

## Monitoring and Debugging

### Logging Signal Emissions

The TrustLevelService logs all promotions:

```python
# Service logs (apps/forum/services/trust_level_service.py:131-133)
logger.info(f"[TRUST] User {user.username} promoted: {old_level} → {new_level}")
```

### Debugging Signal Handlers

```python
import logging
from django.dispatch import receiver
from apps.forum.services.trust_level_service import trust_level_changed

logger = logging.getLogger(__name__)

@receiver(trust_level_changed)
def debug_handler(sender, user, old_level, new_level, **kwargs):
    """Debug handler to log all trust level changes."""
    logger.debug(
        f"[TRUST_SIGNAL] User {user.username} promoted: {old_level} → {new_level}\n"
        f"  Sender: {sender}\n"
        f"  Kwargs: {kwargs}"
    )
```

### Viewing Signal Receivers

```python
# In Django shell
from apps.forum.services.trust_level_service import trust_level_changed

# List all connected receivers
for receiver in trust_level_changed.receivers:
    print(f"Handler: {receiver[1]()}")
```

## Migration Guide

### Adding a New Signal Handler

1. **Create signal handler** in `apps/your_app/signals.py`:

```python
from django.dispatch import receiver
from apps.forum.services.trust_level_service import trust_level_changed

@receiver(trust_level_changed)
def your_handler(sender, user, old_level, new_level, **kwargs):
    # Your logic here
    pass
```

2. **Register in AppConfig** (`apps/your_app/apps.py`):

```python
class YourAppConfig(AppConfig):
    name = 'apps.your_app'

    def ready(self):
        from . import signals  # Import to register
```

3. **Add to INSTALLED_APPS** (if not already):

```python
# settings.py
INSTALLED_APPS = [
    # ...
    'apps.your_app',  # Ensure your app is loaded
]
```

4. **Test the handler**:

```python
from apps.forum.services.trust_level_service import TrustLevelService

# Trigger signal
user = User.objects.get(username='testuser')
TrustLevelService.update_user_trust_level(user)
```

## API Reference

### TrustLevelService Methods

**`update_user_trust_level(user) -> Tuple[str, str, bool]`**
- Updates user's trust level if they've progressed
- Emits `trust_level_changed` signal if level changed
- Returns: `(old_level, new_level, changed)`

**`update_all_user_trust_levels() -> int`**
- Bulk updates all users (cron job)
- Emits `trust_level_changed` for each promoted user
- Returns: Count of users promoted

**`get_trust_level_info(user) -> Dict[str, Any]`**
- Get comprehensive trust level info
- Returns: `{current_level, limits, permissions, next_level, progress_to_next}`

### Signal Arguments

| Argument | Type | Description |
|----------|------|-------------|
| `sender` | Type[TrustLevelService] | The TrustLevelService class |
| `user` | User | Django User instance that was promoted |
| `old_level` | str | Previous trust level ('new', 'basic', 'trusted', 'veteran', 'expert') |
| `new_level` | str | New trust level ('new', 'basic', 'trusted', 'veteran', 'expert') |
| `**kwargs` | dict | Additional Django signal kwargs |

## Related Documentation

- `apps/forum/services/trust_level_service.py` - Service implementation (500 lines)
- `apps/forum/signals.py:220-279` - Signal handlers for automatic updates
- `apps/forum/constants.py:52-127` - Trust level configuration
- `CLAUDE.md:341-363` - Trust Level System overview
- `TRUST_LEVEL_PATTERNS_CODIFIED.md` - Implementation patterns

## Support

For questions or issues:
- Check service implementation: `apps/forum/services/trust_level_service.py`
- Review signal handlers: `apps/forum/signals.py`
- Open GitHub issue: https://github.com/Xertox1234/plant_id_community/issues

---

**Document Version**: 1.0.0
**Last Updated**: November 5, 2025
**Lines**: 515
**Status**: ✅ Production Ready
