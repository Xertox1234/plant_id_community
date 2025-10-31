"""
Plant care reminder service for automated plant care notifications.

Manages creation, scheduling, and sending of plant care reminders
based on user's saved plants and care instructions.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse

from apps.core.models import PlantCareReminder
from apps.core.services.notification_service import NotificationService
from apps.core.services.email_service import EmailType
from apps.core.utils.pii_safe_logging import log_safe_user_context
from .trefle_service import TrefleAPIService

User = get_user_model()
logger = logging.getLogger(__name__)


class PlantCareReminderService:
    """
    Service for managing plant care reminders and automated notifications.
    """
    
    def __init__(self):
        self.notification_service = NotificationService()
        self.trefle_service = TrefleAPIService()
    
    def create_reminder_from_care_instructions(
        self,
        user: User,
        saved_care_instructions_id: int,
        care_type: str,
        frequency: str = 'weekly',
        custom_instructions: str = None
    ) -> PlantCareReminder:
        """
        Create a new plant care reminder from saved care instructions.
        
        Args:
            user: User to create reminder for
            saved_care_instructions_id: ID of SavedCareInstructions
            care_type: Type of care (watering, fertilizing, etc.)
            frequency: How often to remind (daily, weekly, etc.)
            custom_instructions: User's custom care notes
            
        Returns:
            PlantCareReminder: Created reminder instance
        """
        try:
            from apps.plant_identification.models import SavedCareInstructions
            care_instructions = SavedCareInstructions.objects.get(
                id=saved_care_instructions_id,
                user=user
            )
        except SavedCareInstructions.DoesNotExist:
            raise ValueError(f"Care instructions {saved_care_instructions_id} not found for user {user.username}")
        
        # Calculate initial reminder date
        next_reminder_date = self._calculate_next_reminder_date(frequency)
        
        reminder = PlantCareReminder.objects.create(
            user=user,
            saved_care_instructions=care_instructions,
            plant_name=care_instructions.plant_scientific_name or "Your Plant",
            plant_scientific_name=care_instructions.plant_scientific_name,
            care_type=care_type,
            frequency=frequency,
            custom_instructions=custom_instructions,
            next_reminder_date=next_reminder_date
        )

        logger.info(f"Created care reminder for {log_safe_user_context(user)}: {care_type} for {reminder.plant_name}")
        return reminder
    
    def create_custom_reminder(
        self,
        user: User,
        plant_name: str,
        plant_scientific_name: str = None,
        care_type: str = 'watering',
        frequency: str = 'weekly',
        custom_instructions: str = None
    ) -> PlantCareReminder:
        """
        Create a custom plant care reminder not tied to saved care instructions.
        
        Args:
            user: User to create reminder for
            plant_name: Name of the plant
            plant_scientific_name: Scientific name (optional)
            care_type: Type of care
            frequency: Reminder frequency
            custom_instructions: Custom care instructions
            
        Returns:
            PlantCareReminder: Created reminder instance
        """
        next_reminder_date = self._calculate_next_reminder_date(frequency)
        
        reminder = PlantCareReminder.objects.create(
            user=user,
            plant_name=plant_name,
            plant_scientific_name=plant_scientific_name,
            care_type=care_type,
            frequency=frequency,
            custom_instructions=custom_instructions,
            next_reminder_date=next_reminder_date
        )

        logger.info(f"Created custom care reminder for {log_safe_user_context(user)}: {care_type} for {plant_name}")
        return reminder
    
    def get_due_reminders(self, as_of: datetime = None) -> List[PlantCareReminder]:
        """
        Get all reminders that are due to be sent.
        
        Args:
            as_of: Check reminders due as of this datetime (defaults to now)
            
        Returns:
            List of PlantCareReminder instances due for sending
        """
        if as_of is None:
            as_of = timezone.now()
        
        return PlantCareReminder.objects.filter(
            is_active=True,
            next_reminder_date__lte=as_of
        ).select_related('user', 'saved_care_instructions')
    
    def send_reminder(self, reminder: PlantCareReminder) -> bool:
        """
        Send a single plant care reminder email.
        
        Args:
            reminder: PlantCareReminder instance to send
            
        Returns:
            bool: True if reminder sent successfully
        """
        try:
            # Get enhanced care instructions
            care_context = self._build_care_context(reminder)
            
            # Send notification
            success = self.notification_service.send_plant_care_reminder(
                user=reminder.user,
                plant_name=reminder.plant_name,
                care_type=reminder.care_type,
                care_instructions=care_context['care_instructions'],
                care_data=care_context
            )
            
            if success:
                # Mark reminder as sent and calculate next date
                reminder.mark_reminder_sent()
                logger.info(f"Sent care reminder to {log_safe_user_context(reminder.user)} for {reminder.plant_name}")
            else:
                logger.warning(f"Failed to send care reminder to {log_safe_user_context(reminder.user)}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending care reminder {reminder.id}: {e}")
            return False
    
    def send_due_reminders(self) -> Dict[str, int]:
        """
        Send all due reminders.
        
        Returns:
            Dict with 'sent' and 'failed' counts
        """
        due_reminders = self.get_due_reminders()
        results = {'sent': 0, 'failed': 0}
        
        for reminder in due_reminders:
            if self.send_reminder(reminder):
                results['sent'] += 1
            else:
                results['failed'] += 1
        
        logger.info(f"Reminder batch complete: {results['sent']} sent, {results['failed']} failed")
        return results
    
    def get_user_reminders(self, user: User, active_only: bool = True) -> List[PlantCareReminder]:
        """
        Get all reminders for a specific user.
        
        Args:
            user: User to get reminders for
            active_only: Only return active reminders
            
        Returns:
            List of PlantCareReminder instances
        """
        queryset = PlantCareReminder.objects.filter(user=user)
        
        if active_only:
            queryset = queryset.filter(is_active=True)
        
        return queryset.select_related('saved_care_instructions').order_by('next_reminder_date')
    
    def update_reminder_frequency(self, reminder: PlantCareReminder, new_frequency: str) -> bool:
        """
        Update the frequency of an existing reminder.
        
        Args:
            reminder: PlantCareReminder to update
            new_frequency: New frequency setting
            
        Returns:
            bool: True if updated successfully
        """
        try:
            reminder.frequency = new_frequency
            reminder.next_reminder_date = reminder.calculate_next_reminder_date()
            reminder.save(update_fields=['frequency', 'next_reminder_date'])
            
            logger.info(f"Updated reminder frequency for {reminder.plant_name} to {new_frequency}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update reminder frequency: {e}")
            return False
    
    def disable_reminder(self, reminder: PlantCareReminder) -> bool:
        """
        Disable a reminder (stop sending).
        
        Args:
            reminder: PlantCareReminder to disable
            
        Returns:
            bool: True if disabled successfully
        """
        try:
            reminder.is_active = False
            reminder.save(update_fields=['is_active'])
            
            logger.info(f"Disabled reminder for {reminder.plant_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to disable reminder: {e}")
            return False
    
    def _calculate_next_reminder_date(self, frequency: str) -> datetime:
        """Calculate the next reminder date based on frequency."""
        now = timezone.now()
        
        if frequency == PlantCareReminder.FREQUENCY_DAILY:
            return now + timedelta(days=1)
        elif frequency == PlantCareReminder.FREQUENCY_WEEKLY:
            return now + timedelta(weeks=1)
        elif frequency == PlantCareReminder.FREQUENCY_BIWEEKLY:
            return now + timedelta(weeks=2)
        elif frequency == PlantCareReminder.FREQUENCY_MONTHLY:
            return now + timedelta(days=30)
        elif frequency == PlantCareReminder.FREQUENCY_SEASONAL:
            return now + timedelta(days=90)
        
        return now + timedelta(weeks=1)  # Default to weekly
    
    def _build_care_context(self, reminder: PlantCareReminder) -> Dict[str, Any]:
        """
        Build context data for care reminder email.
        
        Args:
            reminder: PlantCareReminder instance
            
        Returns:
            Dict with context data for email template
        """
        context = {
            'plant_name': reminder.plant_name,
            'care_type': reminder.care_type,
            'frequency': reminder.frequency,
            'reminder_count': reminder.reminder_count,
        }
        
        # Get care instructions
        if reminder.saved_care_instructions:
            try:
                care_data = reminder.saved_care_instructions.care_instructions_data
                context['care_instructions'] = self._extract_care_instructions(
                    care_data, reminder.care_type
                )
                context['plant_image_url'] = care_data.get('image_url')
            except Exception:
                context['care_instructions'] = reminder.custom_instructions or "Care for your plant as needed."
        else:
            context['care_instructions'] = reminder.custom_instructions or "Care for your plant as needed."
        
        # Add URLs
        context.update({
            'care_instructions_url': self._build_care_instructions_url(reminder),
            'manage_reminders_url': self._build_manage_reminders_url(reminder.user),
            'forum_url': self._build_forum_url(),
            'next_care_date': reminder.next_reminder_date.strftime('%B %d, %Y'),
        })
        
        # Get plant-specific tips
        context['plant_tips'] = self._get_care_tips(reminder.plant_scientific_name, reminder.care_type)
        
        return context
    
    def _extract_care_instructions(self, care_data: Dict, care_type: str) -> str:
        """Extract specific care instructions from care data."""
        if not care_data:
            return "Care for your plant as needed."
        
        care_map = {
            'watering': ['watering', 'water'],
            'fertilizing': ['fertilizing', 'fertilizer', 'feeding'],
            'pruning': ['pruning', 'trimming'],
            'repotting': ['repotting', 'replanting'],
            'inspection': ['inspection', 'checking', 'monitoring'],
            'cleaning': ['cleaning', 'dusting']
        }
        
        # Look for specific care instructions
        keywords = care_map.get(care_type, [care_type])
        
        for key in keywords:
            if key in care_data:
                return care_data[key]
        
        # Fallback to general instructions
        return care_data.get('care_summary', "Care for your plant according to its needs.")
    
    def _get_care_tips(self, scientific_name: str, care_type: str) -> Optional[str]:
        """Get plant-specific care tips."""
        if not scientific_name:
            return None
        
        # This could be enhanced to use AI or a tips database
        tips_map = {
            'watering': "Check soil moisture by inserting your finger 1-2 inches deep. Water when the top layer feels dry.",
            'fertilizing': "Use a balanced fertilizer during growing season (spring/summer) and reduce in winter.",
            'pruning': "Remove dead, damaged, or yellowing leaves to promote healthy growth.",
            'repotting': "Repot when roots are visible at drainage holes or soil drains too quickly.",
            'inspection': "Look for signs of pests, disease, or stress like yellowing leaves or unusual spots.",
            'cleaning': "Gently wipe leaves with a damp cloth to remove dust and improve photosynthesis."
        }
        
        return tips_map.get(care_type)
    
    def _build_care_instructions_url(self, reminder: PlantCareReminder) -> str:
        """Build URL to full care instructions."""
        if reminder.saved_care_instructions:
            return f"/profile/care-instructions/{reminder.saved_care_instructions.uuid}/"
        return "/plant-care-guide/"
    
    def _build_manage_reminders_url(self, user: User) -> str:
        """Build URL to manage reminders."""
        return "/profile/reminders/"
    
    def _build_forum_url(self) -> str:
        """Build URL to plant care forum."""
        return "/forum/plant-care/"
    
    def create_reminders_for_saved_care(
        self,
        user: User,
        saved_care_instructions_id: int,
        care_types: List[str] = None,
        frequency: str = 'weekly'
    ) -> List[PlantCareReminder]:
        """
        Create multiple reminders for different care types for a plant.
        
        Args:
            user: User to create reminders for
            saved_care_instructions_id: ID of SavedCareInstructions
            care_types: List of care types to create reminders for
            frequency: Default frequency for all reminders
            
        Returns:
            List of created PlantCareReminder instances
        """
        if care_types is None:
            care_types = ['watering', 'fertilizing']
        
        reminders = []
        
        for care_type in care_types:
            try:
                reminder = self.create_reminder_from_care_instructions(
                    user=user,
                    saved_care_instructions_id=saved_care_instructions_id,
                    care_type=care_type,
                    frequency=frequency
                )
                reminders.append(reminder)
            except Exception as e:
                logger.error(f"Failed to create {care_type} reminder: {e}")

        logger.info(f"Created {len(reminders)} reminders for {log_safe_user_context(user)}")
        return reminders