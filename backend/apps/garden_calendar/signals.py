"""
Garden Calendar Signals

Signal handlers for automatic actions when calendar events occur.
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from apps.core.services.notification_service import NotificationService
from .models import CommunityEvent, EventAttendee, WeatherAlert


@receiver(post_save, sender=CommunityEvent)
def notify_community_event_created(sender, instance, created, **kwargs):
    """
    Send notifications when a new community event is created.
    """
    if created and instance.privacy_level in ['public', 'local']:
        try:
            from apps.users.models import User
            
            # Build location-based query
            queryset = User.objects.filter(
                email_notifications=True,
                location_privacy__in=['zone_only', 'city', 'precise']
            ).exclude(id=instance.organizer.id)
            
            # Filter by location based on privacy level
            if instance.privacy_level == 'local' and instance.city:
                queryset = queryset.filter(location__icontains=instance.city)
            
            # Further filter by hardiness zone if available
            if instance.hardiness_zone:
                queryset = queryset.filter(hardiness_zone=instance.hardiness_zone)
            
            # Limit to prevent spam (max 100 notifications per event)
            users_to_notify = queryset[:100]
            
            for user in users_to_notify:
                NotificationService.send_email_notification(
                    user=user,
                    subject=f"New {instance.get_event_type_display()} in your area",
                    template='emails/community_event_created.html',
                    context={
                        'event': instance,
                        'user': user,
                        'organizer': instance.organizer,
                    }
                )
                
        except Exception as e:
            # Log error but don't fail the event creation
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send community event notifications: {e}")


@receiver(post_save, sender=EventAttendee)
def notify_event_rsvp_updated(sender, instance, created, **kwargs):
    """
    Notify event organizer when someone RSVPs to their event.
    """
    if created and instance.status == 'going':
        try:
            organizer = instance.event.organizer
            if organizer.email_notifications and organizer != instance.user:
                NotificationService.send_email_notification(
                    user=organizer,
                    subject=f"New RSVP for {instance.event.title}",
                    template='emails/event_rsvp_notification.html',
                    context={
                        'event': instance.event,
                        'attendee': instance.user,
                        'organizer': organizer,
                        'total_attendees': instance.event.attendee_count,
                    }
                )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send RSVP notification: {e}")


@receiver(post_save, sender=WeatherAlert)
def notify_weather_alert_created(sender, instance, created, **kwargs):
    """
    Send notifications for high-severity weather alerts that affect gardening.
    """
    if created and instance.severity in ['high', 'critical'] and instance.is_active:
        try:
            from apps.users.models import User
            
            # Find users in the affected area
            queryset = User.objects.filter(
                care_reminder_notifications=True,  # Use care reminder setting for weather alerts
                location_privacy__in=['zone_only', 'city', 'precise']
            )
            
            # Filter by ZIP code (exact match) or city (partial match)
            if instance.zip_code:
                queryset = queryset.filter(zip_code=instance.zip_code)
            elif instance.city:
                queryset = queryset.filter(location__icontains=instance.city)
            
            # Further filter by hardiness zone if available
            if instance.hardiness_zone:
                queryset = queryset.filter(hardiness_zone=instance.hardiness_zone)
            
            # Limit to prevent spam
            users_to_notify = queryset[:200]
            
            for user in users_to_notify:
                NotificationService.send_push_notification(
                    user=user,
                    title=f"⚠️ {instance.get_alert_type_display()}",
                    message=instance.title,
                    data={
                        'type': 'weather_alert',
                        'alert_id': str(instance.id),
                        'severity': instance.severity,
                        'alert_type': instance.alert_type,
                    }
                )
                
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send weather alert notifications: {e}")


@receiver(post_delete, sender=CommunityEvent)
def cleanup_orphaned_forum_topics(sender, instance, **kwargs):
    """
    Handle cleanup when community events are deleted.
    """
    try:
        # If the event had an associated forum topic, we might want to:
        # 1. Archive it
        # 2. Add a note that the event was canceled
        # 3. Leave it as-is for historical discussion
        # For now, we'll leave forum topics intact
        pass
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error cleaning up deleted community event: {e}")


# Weather alert cleanup task - remove expired alerts
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """
    Management command to clean up expired weather alerts.
    This should be run periodically via cron or Celery Beat.
    """
    help = 'Remove expired weather alerts from the database'
    
    def handle(self, *args, **options):
        now = timezone.now()
        expired_count = WeatherAlert.objects.filter(
            expires_at__lt=now,
            is_active=True
        ).count()
        
        WeatherAlert.objects.filter(
            expires_at__lt=now,
            is_active=True
        ).update(is_active=False)
        
        self.stdout.write(
            self.style.SUCCESS(f'Deactivated {expired_count} expired weather alerts')
        )