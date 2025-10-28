"""
User services for trust level management, forum permissions, and notifications.
"""

import json
import logging
from typing import Optional, Dict, Any
from django.conf import settings
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.contrib.auth.models import Group
from django.utils import timezone
from django.apps import apps
from machina.core.loading import get_class
from machina.apps.forum.models import Forum
from apps.core.utils.pii_safe_logging import log_safe_username, log_safe_user_context, log_safe_email

# External dependency for Web Push (requires: pip install pywebpush)
try:
    from pywebpush import webpush, WebPushException
    WEBPUSH_AVAILABLE = True
except ImportError:
    WEBPUSH_AVAILABLE = False
    WebPushException = Exception

logger = logging.getLogger(__name__)

# Import Django Machina models
ForumPermission = apps.get_model('forum_permission', 'ForumPermission')
GroupForumPermission = apps.get_model('forum_permission', 'GroupForumPermission')
UserForumPermission = apps.get_model('forum_permission', 'UserForumPermission')
PermissionHandler = get_class('forum_permission.handler', 'PermissionHandler')


class TrustLevelService:
    """Service for managing user trust levels and related permissions."""
    
    @staticmethod
    def create_trust_level_groups():
        """Create user groups for different trust levels."""
        trust_groups = {
            'basic_members': 'Basic Members - Can upload images',
            'trusted_members': 'Trusted Members - Enhanced privileges',
            'veteran_members': 'Veteran Members - Advanced privileges'
        }
        
        created_groups = {}
        for group_name, description in trust_groups.items():
            group, created = Group.objects.get_or_create(name=group_name)
            created_groups[group_name] = group
            if created:
                print(f"Created group: {group_name}")
            else:
                print(f"Group already exists: {group_name}")
        
        return created_groups
    
    @staticmethod
    def setup_forum_permissions():
        """Set up forum permissions for trust level groups."""
        # Get or create trust level groups
        groups = TrustLevelService.create_trust_level_groups()
        
        # Get all forums
        forums = Forum.objects.filter(type=Forum.FORUM_POST)
        
        # Get permissions
        try:
            attach_file_perm = ForumPermission.objects.get(codename='can_attach_file')
            download_file_perm = ForumPermission.objects.get(codename='can_download_file')
        except ForumPermission.DoesNotExist:
            print("Forum permissions not found. Run forum setup first.")
            return
        
        # Grant file attachment permissions to basic+ trust levels
        for forum in forums:
            # Basic members and above can attach and download files
            for group_name in ['basic_members', 'trusted_members', 'veteran_members']:
                group = groups[group_name]
                
                # Grant attach file permission
                GroupForumPermission.objects.get_or_create(
                    permission=attach_file_perm,
                    forum=forum,
                    group=group,
                    defaults={'has_perm': True}
                )
                
                # Grant download file permission
                GroupForumPermission.objects.get_or_create(
                    permission=download_file_perm,
                    forum=forum,
                    group=group,
                    defaults={'has_perm': True}
                )
        
        print(f"Set up file permissions for {len(forums)} forums")
    
    @staticmethod
    def assign_user_to_trust_group(user):
        """Assign user to appropriate trust level group based on their trust_level."""
        # Remove user from all trust level groups first
        trust_group_names = ['basic_members', 'trusted_members', 'veteran_members']
        for group_name in trust_group_names:
            try:
                group = Group.objects.get(name=group_name)
                user.groups.remove(group)
            except Group.DoesNotExist:
                continue
        
        # Assign to appropriate group based on trust level
        group_mapping = {
            'basic': 'basic_members',
            'trusted': 'trusted_members', 
            'veteran': 'veteran_members'
        }
        
        if user.trust_level in group_mapping:
            try:
                group = Group.objects.get(name=group_mapping[user.trust_level])
                user.groups.add(group)
                print(f"Assigned {user.username} to {group.name}")
            except Group.DoesNotExist:
                print(f"Trust group {group_mapping[user.trust_level]} not found")
    
    @staticmethod
    def update_all_user_trust_levels():
        """Update trust levels for all users and assign to appropriate groups."""
        from .models import User
        
        updated_count = 0
        
        for user in User.objects.all():
            old_level = user.trust_level
            user.update_trust_level()
            
            # Assign to appropriate group
            TrustLevelService.assign_user_to_trust_group(user)
            
            if user.trust_level != old_level:
                updated_count += 1
                print(f"Updated {user.username}: {old_level} -> {user.trust_level}")
        
        print(f"Updated trust levels for {updated_count} users")
        return updated_count
    
    @staticmethod
    def check_user_can_attach_files(user, forum):
        """Check if user can attach files to a specific forum."""
        # Staff can always attach files
        if user.is_staff or user.is_superuser:
            return True
            
        # Use Django Machina permission system
        perm_handler = PermissionHandler()
        return perm_handler.can_attach_files(forum, user)


class ForumPostService:
    """Service for managing forum posts and trust level integration."""
    
    @staticmethod
    def update_user_post_count(user):
        """Update user's verified post count from actual forum posts."""
        from machina.apps.forum_conversation.models import Post
        
        # Count approved posts by this user
        verified_count = Post.objects.filter(
            poster=user,
            approved=True
        ).count()
        
        # Update user's cached count
        user.posts_count_verified = verified_count
        user.save(update_fields=['posts_count_verified'])
        
        # Check if trust level should be updated
        old_level = user.trust_level
        user.update_trust_level()
        
        # If trust level changed, update group membership
        if user.trust_level != old_level:
            TrustLevelService.assign_user_to_trust_group(user)
        
        return verified_count


class NotificationService:
    """
    Service class for handling various types of notifications.
    """
    
    @staticmethod
    def send_web_push_notification(
        subscription,  # PushSubscription instance
        title: str,
        body: str,
        icon: str = '/icons/icon-192x192.png',
        badge: str = '/icons/badge-72x72.png',
        actions: Optional[list] = None,
        data: Optional[Dict[str, Any]] = None,
        tag: Optional[str] = None
    ) -> bool:
        """
        Send a Web Push notification to a specific subscription.
        
        Args:
            subscription: PushSubscription instance
            title: Notification title
            body: Notification body text
            icon: Icon URL for the notification
            badge: Badge icon URL
            actions: List of action buttons
            data: Additional data to include
            tag: Notification tag for grouping/replacing
            
        Returns:
            bool: True if sent successfully, False otherwise
        """
        if not WEBPUSH_AVAILABLE:
            logger.error("pywebpush library not available. Install with: pip install pywebpush")
            return False
            
        try:
            # Prepare notification payload
            payload = {
                'title': title,
                'body': body,
                'icon': icon,
                'badge': badge,
                'tag': tag or 'plant-community',
                'requireInteraction': True,
                'data': data or {},
                'actions': actions or []
            }
            
            # Prepare subscription info for pywebpush
            subscription_info = {
                'endpoint': subscription.endpoint,
                'keys': {
                    'p256dh': subscription.p256dh_key,
                    'auth': subscription.auth_key
                }
            }
            
            # Get VAPID keys from settings
            vapid_private_key = getattr(settings, 'VAPID_PRIVATE_KEY', None)
            vapid_claims = {
                'sub': f'mailto:{getattr(settings, "VAPID_CLAIMS_EMAIL", "admin@plantcommunity.com")}'
            }
            
            if not vapid_private_key:
                logger.error("VAPID_PRIVATE_KEY not configured in settings")
                return False
            
            # Send the push notification
            webpush(
                subscription_info=subscription_info,
                data=json.dumps(payload),
                vapid_private_key=vapid_private_key,
                vapid_claims=vapid_claims,
                content_encoding='aes128gcm'
            )
            
            # Mark subscription as used
            subscription.mark_as_used()
            
            logger.info(f"Push notification sent successfully to {log_safe_user_context(subscription.user)}")
            return True
            
        except WebPushException as e:
            logger.error(f"WebPush error for {log_safe_user_context(subscription.user)}: {e}")
            
            # Handle specific error cases
            if e.response and e.response.status_code in [410, 413, 429]:
                # Subscription is no longer valid or rate limited
                subscription.deactivate()
                logger.warning(f"Deactivated push subscription for {log_safe_user_context(subscription.user)}")
            
            return False
            
        except Exception as e:
            logger.error(f"Unexpected error sending push notification: {e}")
            return False
    
    @staticmethod
    def send_care_reminder_push(reminder) -> bool:
        """
        Send a care reminder push notification to all user's active subscriptions.
        
        Args:
            reminder: CareReminder instance
            
        Returns:
            bool: True if sent to at least one subscription
        """
        if not reminder.user.care_reminder_notifications:
            logger.info(f"Care reminder push disabled for {log_safe_user_context(reminder.user)}")
            return False
        
        # Get all active push subscriptions for the user
        subscriptions = reminder.user.push_subscriptions.filter(is_active=True)
        
        if not subscriptions.exists():
            logger.info(f"No active push subscriptions for {log_safe_user_context(reminder.user)}")
            return False
        
        # Prepare notification content
        plant_name = reminder.saved_care_instructions.display_name
        title = f"🌱 {reminder.title}"
        body = f"Time to {reminder.get_reminder_type_display().lower()} your {plant_name}"
        
        # Prepare action buttons
        actions = [
            {
                'action': 'mark_completed',
                'title': '✅ Mark Completed',
                'icon': '/icons/check.png'
            },
            {
                'action': 'snooze_reminder',
                'title': '⏰ Snooze 24h',
                'icon': '/icons/snooze.png'
            }
        ]
        
        # Prepare data for the notification
        data = {
            'type': 'care_reminder',
            'reminder_id': str(reminder.uuid),
            'plant_name': plant_name,
            'reminder_type': reminder.reminder_type,
            'url': f'/profile/care-reminders/{reminder.uuid}/'
        }
        
        # Send to all active subscriptions
        success_count = 0
        for subscription in subscriptions:
            if NotificationService.send_web_push_notification(
                subscription=subscription,
                title=title,
                body=body,
                actions=actions,
                data=data,
                tag=f'care-reminder-{reminder.uuid}'
            ):
                success_count += 1
        
        # Log the reminder action (import here to avoid circular import)
        from .models import CareReminderLog
        CareReminderLog.objects.create(
            reminder=reminder,
            action='sent',
            action_data={
                'push_sent': success_count > 0,
                'subscriptions_attempted': subscriptions.count(),
                'subscriptions_successful': success_count
            }
        )
        
        logger.info(f"Care reminder sent to {success_count}/{subscriptions.count()} subscriptions for {log_safe_user_context(reminder.user)}")
        return success_count > 0
    
    @staticmethod
    def send_care_reminder_email(reminder) -> bool:
        """
        Send a care reminder email notification.
        
        Args:
            reminder: CareReminder instance
            
        Returns:
            bool: True if sent successfully
        """
        if not (reminder.user.care_reminder_email and reminder.user.email_notifications):
            return False
        
        try:
            plant_name = reminder.saved_care_instructions.display_name
            
            # Prepare email content
            subject = f"🌱 Plant Care Reminder: {reminder.title}"
            
            context = {
                'user': reminder.user,
                'reminder': reminder,
                'plant_name': plant_name,
                'care_instructions': reminder.saved_care_instructions,
                'site_url': getattr(settings, 'SITE_URL', 'http://localhost:3000')
            }
            
            # For now, create simple text content (templates can be added later)
            text_message = f"""
Hello {reminder.user.get_full_name() or reminder.user.username},

This is a reminder to {reminder.get_reminder_type_display().lower()} your {plant_name}.

Reminder Details:
- Type: {reminder.get_reminder_type_display()}
- Frequency: {reminder.get_frequency_display()}
- Plant: {plant_name}

You can manage your care reminders at: {context['site_url']}/profile/care-reminders/

Best regards,
The Plant Community Team
            """.strip()
            
            # Send email
            send_mail(
                subject=subject,
                message=text_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[reminder.user.email],
                fail_silently=False
            )
            
            logger.info(f"Care reminder email sent to {log_safe_email(reminder.user.email)}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending care reminder email: {e}")
            return False
    
    @staticmethod
    def subscribe_to_push(user, subscription_data: Dict[str, Any], user_agent: str = ''):
        """
        Create or update a push subscription for a user.
        
        Args:
            user: User instance
            subscription_data: Subscription data from the client
            user_agent: User agent string for device identification
            
        Returns:
            PushSubscription instance
        """
        from .models import PushSubscription
        
        endpoint = subscription_data.get('endpoint')
        keys = subscription_data.get('keys', {})
        
        # Try to get existing subscription or create new one
        subscription, created = PushSubscription.objects.update_or_create(
            user=user,
            endpoint=endpoint,
            defaults={
                'p256dh_key': keys.get('p256dh', ''),
                'auth_key': keys.get('auth', ''),
                'user_agent': user_agent,
                'device_name': NotificationService._extract_device_name(user_agent),
                'is_active': True
            }
        )
        
        logger.info(f"Push subscription {'created' if created else 'updated'} for {log_safe_user_context(user)}")
        return subscription
    
    @staticmethod
    def unsubscribe_from_push(user, endpoint: str) -> bool:
        """
        Deactivate a push subscription.
        
        Args:
            user: User instance
            endpoint: Subscription endpoint to deactivate
            
        Returns:
            bool: True if deactivated successfully
        """
        from .models import PushSubscription
        
        try:
            subscription = PushSubscription.objects.get(user=user, endpoint=endpoint)
            subscription.deactivate()
            logger.info(f"Push subscription deactivated for {log_safe_user_context(user)}")
            return True
        except PushSubscription.DoesNotExist:
            logger.warning(f"Push subscription not found for {log_safe_user_context(user)} with endpoint {endpoint[:20]}...")
            return False
    
    @staticmethod
    def _extract_device_name(user_agent: str) -> str:
        """
        Extract a human-readable device name from user agent string.
        
        Args:
            user_agent: User agent string
            
        Returns:
            str: Human-readable device name
        """
        if not user_agent:
            return 'Unknown device'
        
        # Simple device detection (can be enhanced with a proper library)
        user_agent_lower = user_agent.lower()
        
        if 'mobile' in user_agent_lower or 'android' in user_agent_lower:
            if 'chrome' in user_agent_lower:
                return 'Chrome on Android'
            elif 'firefox' in user_agent_lower:
                return 'Firefox on Android'
            else:
                return 'Mobile Browser'
        elif 'iphone' in user_agent_lower or 'ipad' in user_agent_lower:
            if 'safari' in user_agent_lower:
                return 'Safari on iOS'
            elif 'chrome' in user_agent_lower:
                return 'Chrome on iOS'
            else:
                return 'iOS Browser'
        elif 'windows' in user_agent_lower:
            if 'chrome' in user_agent_lower:
                return 'Chrome on Windows'
            elif 'firefox' in user_agent_lower:
                return 'Firefox on Windows'
            elif 'edge' in user_agent_lower:
                return 'Edge on Windows'
            else:
                return 'Windows Browser'
        elif 'mac' in user_agent_lower:
            if 'chrome' in user_agent_lower:
                return 'Chrome on Mac'
            elif 'firefox' in user_agent_lower:
                return 'Firefox on Mac'
            elif 'safari' in user_agent_lower:
                return 'Safari on Mac'
            else:
                return 'Mac Browser'
        elif 'linux' in user_agent_lower:
            if 'chrome' in user_agent_lower:
                return 'Chrome on Linux'
            elif 'firefox' in user_agent_lower:
                return 'Firefox on Linux'
            else:
                return 'Linux Browser'
        else:
            return 'Desktop Browser'


class CareReminderService:
    """
    Service class for managing care reminders.
    """
    
    @staticmethod
    def create_reminder(
        user,
        saved_care_instructions,
        reminder_type: str,
        frequency: str,
        custom_interval_days: Optional[int] = None,
        title: Optional[str] = None
    ):
        """
        Create a new care reminder.
        
        Args:
            user: User instance
            saved_care_instructions: SavedCareInstructions instance
            reminder_type: Type of reminder (watering, fertilizing, etc.)
            frequency: How often to remind
            custom_interval_days: Custom interval for 'custom' frequency
            title: Custom title (auto-generated if not provided)
            
        Returns:
            CareReminder instance
        """
        from .models import CareReminder
        
        if not title:
            plant_name = saved_care_instructions.display_name
            type_display = dict(CareReminder.REMINDER_TYPES)[reminder_type]
            title = f"{type_display} for {plant_name}"
        
        # Calculate first reminder date
        from datetime import timedelta
        
        if frequency == 'custom' and custom_interval_days:
            next_date = timezone.now() + timedelta(days=custom_interval_days)
        else:
            frequency_map = {
                'daily': timedelta(days=1),
                'weekly': timedelta(weeks=1),
                'biweekly': timedelta(weeks=2),
                'monthly': timedelta(days=30),
                'quarterly': timedelta(days=90),
                'biannual': timedelta(days=180),
                'annual': timedelta(days=365),
            }
            next_date = timezone.now() + frequency_map.get(frequency, timedelta(weeks=1))
        
        reminder = CareReminder.objects.create(
            user=user,
            saved_care_instructions=saved_care_instructions,
            reminder_type=reminder_type,
            title=title,
            frequency=frequency,
            custom_interval_days=custom_interval_days,
            next_reminder_date=next_date,
            send_push_notification=user.care_reminder_notifications,
            send_email_notification=user.care_reminder_email
        )
        
        logger.info(f"Care reminder created for {log_safe_user_context(user)}: {title}")
        return reminder
    
    @staticmethod
    def process_due_reminders():
        """
        Process all reminders that are due to be sent.
        This method should be called by a periodic task (Celery, cron, etc.).
        """
        from .models import CareReminder
        
        due_reminders = CareReminder.objects.filter(
            is_active=True,
            next_reminder_date__lte=timezone.now()
        ).select_related('user', 'saved_care_instructions')
        
        sent_count = 0
        for reminder in due_reminders:
            try:
                reminder.send_reminder()
                sent_count += 1
            except Exception as e:
                logger.error(f"Error sending reminder {reminder.id}: {e}")
        
        logger.info(f"Processed {sent_count} care reminders")
        return sent_count


class DemoDataService:
    """
    Service for creating and managing demo data for new users.
    """
    
    def __init__(self, user):
        self.user = user
    
    def create_demo_data(self, include_care_reminders=True):
        """
        Create comprehensive demo data for a user to explore the platform.
        
        Args:
            include_care_reminders: Whether to create demo care reminders
            
        Returns:
            DemoData instance with created content summary
        """
        from .models import DemoData
        from django.db import transaction
        
        with transaction.atomic():
            # Create demo data record
            demo_data = DemoData.objects.create(
                user=self.user,
                demo_type='comprehensive',
                created_data={}
            )
            
            created_items = {
                'identifications_count': 0,
                'forum_posts_count': 0,
                'care_reminders_count': 0,
            }
            
            # Create demo plant identifications
            identifications = self._create_demo_identifications()
            created_items['identifications_count'] = len(identifications)
            
            # Create demo forum posts (if forum is enabled)
            if self._is_forum_enabled():
                forum_posts = self._create_demo_forum_posts()
                created_items['forum_posts_count'] = len(forum_posts)
            
            # Create demo care reminders (if requested)
            if include_care_reminders and identifications:
                care_reminders = self._create_demo_care_reminders(identifications[:3])
                created_items['care_reminders_count'] = len(care_reminders)
            
            # Store summary in demo data
            demo_data.created_data = created_items
            demo_data.save(update_fields=['created_data'])
            
            logger.info(f"Created demo data for user {self.user.id}: {created_items}")
            return demo_data
    
    def _create_demo_identifications(self):
        """Create sample plant identification requests with results."""
        from apps.plant_identification.models import (
            PlantIdentificationRequest, IdentificationResult, SavedCareInstructions
        )
        from apps.common.models import PlantSpecies
        
        # Sample plant data
        demo_plants = [
            {
                'species_name': 'Monstera deliciosa',
                'common_names': 'Swiss Cheese Plant, Split-leaf Philodendron',
                'confidence': 0.92,
                'care_notes': 'Thrives in bright, indirect light. Water when top inch of soil is dry. Loves humidity and climbing support.',
                'difficulty': 'easy'
            },
            {
                'species_name': 'Ficus lyrata',
                'common_names': 'Fiddle Leaf Fig',
                'confidence': 0.88,
                'care_notes': 'Needs bright, filtered light. Water thoroughly but infrequently. Sensitive to changes in environment.',
                'difficulty': 'moderate'
            },
            {
                'species_name': 'Sansevieria trifasciata',
                'common_names': 'Snake Plant, Mother-in-Law\'s Tongue',
                'confidence': 0.95,
                'care_notes': 'Extremely low maintenance. Tolerates low light and infrequent watering. Perfect for beginners.',
                'difficulty': 'easy'
            },
            {
                'species_name': 'Epipremnum aureum',
                'common_names': 'Golden Pothos, Devil\'s Ivy',
                'confidence': 0.91,
                'care_notes': 'Very forgiving plant. Bright, indirect light preferred. Water when soil feels dry. Great for trailing.',
                'difficulty': 'easy'
            },
            {
                'species_name': 'Spathiphyllum wallisii',
                'common_names': 'Peace Lily',
                'confidence': 0.89,
                'care_notes': 'Moderate to bright, indirect light. Keep soil consistently moist. Dramatic when thirsty!',
                'difficulty': 'moderate'
            }
        ]
        
        created_identifications = []
        
        for i, plant_data in enumerate(demo_plants):
            # Create or get species
            species, _ = PlantSpecies.objects.get_or_create(
                scientific_name=plant_data['species_name'],
                defaults={
                    'common_names': plant_data['common_names'],
                    'is_demo_data': True
                }
            )
            
            # Create identification request
            request = PlantIdentificationRequest.objects.create(
                user=self.user,
                image_1_url=f'/demo/plants/plant_{i+1}.jpg',
                location_data={'demo': True, 'city': 'Demo Location'},
                is_demo_data=True
            )
            
            # Create identification result
            result = IdentificationResult.objects.create(
                identification_request=request,
                identified_species=species,
                confidence_score=plant_data['confidence'],
                ai_service_used='demo',
                additional_data={
                    'demo': True,
                    'care_difficulty': plant_data['difficulty']
                },
                is_demo_data=True
            )
            
            # Create saved care instructions
            care_instructions = SavedCareInstructions.objects.create(
                user=self.user,
                identification_result=result,
                display_name=plant_data['common_names'].split(',')[0],
                care_instructions=plant_data['care_notes'],
                additional_notes=f"Demo plant #{i+1} - {plant_data['difficulty']} care level",
                is_demo_data=True
            )
            
            created_identifications.append({
                'request': request,
                'result': result,
                'care_instructions': care_instructions
            })
        
        return created_identifications
    
    def _create_demo_forum_posts(self):
        """Create sample forum topics and posts."""
        if not self._is_forum_enabled():
            return []
        
        try:
            from machina.apps.forum_conversation.models import Topic, Post
            from machina.apps.forum.models import Forum
            
            # Get or create a demo forum category
            plant_id_forum, _ = Forum.objects.get_or_create(
                name='Plant Identification Help',
                defaults={
                    'description': 'Get help identifying your plants from the community',
                    'type': Forum.FORUM_POST,
                    'is_demo_data': True
                }
            )
            
            # Sample forum topics
            demo_topics = [
                {
                    'subject': 'Help! What is this trailing plant?',
                    'content': 'I found this beautiful trailing plant at the nursery but forgot to ask what it was. The leaves are heart-shaped and have golden variegation. Any ideas?',
                    'replies': [
                        'That looks like a Golden Pothos (Epipremnum aureum)! Super easy to care for and great for beginners.',
                        'Definitely a Pothos! They\'re amazing for low-light conditions and very forgiving with watering.'
                    ]
                },
                {
                    'subject': 'My peace lily leaves are turning yellow - help!',
                    'content': 'I\'ve had my peace lily for 6 months and recently the leaves started turning yellow. I water it once a week and keep it by a bright window. What am I doing wrong?',
                    'replies': [
                        'Yellow leaves on peace lilies can indicate overwatering or too much direct sunlight. Try moving it away from the window and reducing watering frequency.',
                        'Check the soil moisture before watering. Peace lilies prefer to dry out slightly between waterings.'
                    ]
                },
                {
                    'subject': 'Brown spots on my fiddle leaf fig leaves',
                    'content': 'I\'ve noticed brown spots appearing on my fiddle leaf fig\'s lower leaves. The plant otherwise seems healthy. Should I be concerned?',
                    'replies': [
                        'Brown spots can be caused by overwatering, bacterial infection, or inconsistent watering. Make sure you\'re not watering too frequently.',
                        'I had the same issue! Turned out I was watering too often. Let the top inch of soil dry out before watering again.'
                    ]
                }
            ]
            
            created_posts = []
            
            for topic_data in demo_topics:
                # Create topic
                topic = Topic.objects.create(
                    forum=plant_id_forum,
                    subject=topic_data['subject'],
                    poster=self.user,
                    is_demo_data=True
                )
                
                # Create initial post
                initial_post = Post.objects.create(
                    topic=topic,
                    poster=self.user,
                    content=topic_data['content'],
                    is_demo_data=True
                )
                
                # Create reply posts (using system user for variety)
                for reply_content in topic_data['replies']:
                    reply_post = Post.objects.create(
                        topic=topic,
                        poster=self.user,  # In real implementation, could use different demo users
                        content=reply_content,
                        is_demo_data=True
                    )
                    created_posts.append(reply_post)
                
                created_posts.append(initial_post)
            
            return created_posts
            
        except Exception as e:
            logger.warning(f"Could not create demo forum posts: {e}")
            return []
    
    def _create_demo_care_reminders(self, demo_identifications):
        """Create sample care reminders for demo plants."""
        from .models import CareReminder
        from datetime import timedelta
        
        reminder_configs = [
            {
                'reminder_type': 'watering',
                'frequency': 'weekly',
                'title': 'Water your Monstera',
                'description': 'Check if the top inch of soil is dry, then water thoroughly.'
            },
            {
                'reminder_type': 'fertilizing',
                'frequency': 'monthly',
                'title': 'Fertilize your Fiddle Leaf Fig',
                'description': 'Use diluted liquid fertilizer during growing season.'
            },
            {
                'reminder_type': 'inspection',
                'frequency': 'weekly',
                'title': 'Check your Snake Plant',
                'description': 'Look for any signs of overwatering or pests.'
            }
        ]
        
        created_reminders = []
        
        for i, config in enumerate(reminder_configs):
            if i < len(demo_identifications):
                identification = demo_identifications[i]
                
                # Calculate next reminder date
                if config['frequency'] == 'daily':
                    next_date = timezone.now() + timedelta(days=1)
                elif config['frequency'] == 'weekly':
                    next_date = timezone.now() + timedelta(weeks=1)
                elif config['frequency'] == 'monthly':
                    next_date = timezone.now() + timedelta(days=30)
                else:
                    next_date = timezone.now() + timedelta(weeks=1)
                
                reminder = CareReminder.objects.create(
                    user=self.user,
                    saved_care_instructions=identification['care_instructions'],
                    reminder_type=config['reminder_type'],
                    title=config['title'],
                    description=config['description'],
                    frequency=config['frequency'],
                    next_reminder_date=next_date,
                    send_push_notification=True,
                    send_email_notification=False,
                    is_demo_data=True
                )
                
                created_reminders.append(reminder)
        
        return created_reminders
    
    def cleanup_demo_data(self, demo_data):
        """
        Remove all demo data for a user.
        
        Args:
            demo_data: DemoData instance to clean up
        """
        from django.db import transaction
        
        with transaction.atomic():
            # Delete demo plant identifications
            from apps.plant_identification.models import PlantIdentificationRequest
            PlantIdentificationRequest.objects.filter(
                user=self.user,
                is_demo_data=True
            ).delete()
            
            # Delete demo forum posts (if forum enabled)
            if self._is_forum_enabled():
                try:
                    from machina.apps.forum_conversation.models import Topic, Post
                    Topic.objects.filter(poster=self.user, is_demo_data=True).delete()
                    Post.objects.filter(poster=self.user, is_demo_data=True).delete()
                except Exception as e:
                    logger.warning(f"Could not delete demo forum posts: {e}")
            
            # Delete demo care reminders
            from .models import CareReminder
            CareReminder.objects.filter(
                user=self.user,
                is_demo_data=True
            ).delete()
            
            # Delete demo data record
            demo_data.delete()
            
            logger.info(f"Cleaned up demo data for user {self.user.id}")
    
    def _is_forum_enabled(self):
        """Check if forum functionality is enabled."""
        return getattr(settings, 'ENABLE_FORUM', False)