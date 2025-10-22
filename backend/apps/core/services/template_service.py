"""
Template service for managing email templates and rendering.

Provides template loading, caching, and rendering with support for
responsive email design and dynamic content.
"""

import logging
from typing import Dict, Any, Optional, List
from django.template.loader import render_to_string, get_template
from django.template import Context, Template, TemplateDoesNotExist
from django.conf import settings
from django.utils.safestring import mark_safe
from django.contrib.staticfiles.finders import find
import os

logger = logging.getLogger(__name__)


class TemplateService:
    """
    Service for managing and rendering email templates with support for
    responsive design, template inheritance, and dynamic content.
    """
    
    def __init__(self):
        self.template_cache = {}
        self.default_context = {
            'site_name': getattr(settings, 'SITE_NAME', 'Plant Community'),
            'site_url': getattr(settings, 'SITE_URL', 'https://plantcommunity.com'),
            'support_email': getattr(settings, 'SUPPORT_EMAIL', 'support@plantcommunity.com'),
        }
    
    def render_email_template(
        self,
        template_name: str,
        context: Dict[str, Any],
        format_type: str = 'html'
    ) -> str:
        """
        Render an email template with the given context.
        
        Args:
            template_name: Name of the template (without extension)
            context: Template context variables
            format_type: 'html' or 'txt' for format
            
        Returns:
            str: Rendered template content
        """
        # Merge with default context
        full_context = {**self.default_context, **context}
        
        # Add template-specific helper functions
        full_context.update(self._get_template_helpers())
        
        template_path = f'emails/{template_name}.{format_type}'
        
        try:
            return render_to_string(template_path, full_context)
        except TemplateDoesNotExist:
            logger.error(f"Email template not found: {template_path}")
            # Fallback to generic template
            return self._render_fallback_template(
                template_name, full_context, format_type
            )
    
    def render_responsive_email(
        self,
        template_name: str,
        context: Dict[str, Any],
        include_preheader: bool = True
    ) -> Dict[str, str]:
        """
        Render both HTML and text versions of an email template.
        
        Args:
            template_name: Base template name
            context: Template context
            include_preheader: Whether to include email preheader text
            
        Returns:
            Dict with 'html' and 'text' keys containing rendered content
        """
        # Add responsive email helpers
        email_context = {**context}
        
        if include_preheader:
            email_context['preheader_text'] = self._generate_preheader(
                template_name, context
            )
        
        return {
            'html': self.render_email_template(template_name, email_context, 'html'),
            'text': self.render_email_template(template_name, email_context, 'txt')
        }
    
    def _render_fallback_template(
        self,
        template_name: str,
        context: Dict[str, Any],
        format_type: str
    ) -> str:
        """Render a generic fallback template when specific template is missing."""
        fallback_context = {
            **context,
            'template_name': template_name,
            'notification_title': context.get('notification_title', 'Notification'),
            'notification_message': context.get('notification_message', ''),
        }
        
        try:
            return render_to_string(f'emails/generic_notification.{format_type}', fallback_context)
        except TemplateDoesNotExist:
            # Ultimate fallback - plain text
            if format_type == 'html':
                return self._generate_basic_html_email(fallback_context)
            else:
                return self._generate_basic_text_email(fallback_context)
    
    def _generate_basic_html_email(self, context: Dict[str, Any]) -> str:
        """Generate a basic HTML email when no template is available."""
        title = context.get('notification_title', 'Notification')
        message = context.get('notification_message', '')
        site_name = context.get('site_name', 'Plant Community')
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px;">
                <h1 style="color: #2c5f41; margin-bottom: 20px;">{title}</h1>
                <div style="background-color: white; padding: 20px; border-radius: 4px;">
                    <p>{message}</p>
                </div>
                <p style="font-size: 12px; color: #666; margin-top: 20px;">
                    This email was sent by {site_name}
                </p>
            </div>
        </body>
        </html>
        """
    
    def _generate_basic_text_email(self, context: Dict[str, Any]) -> str:
        """Generate a basic text email when no template is available."""
        title = context.get('notification_title', 'Notification')
        message = context.get('notification_message', '')
        site_name = context.get('site_name', 'Plant Community')
        
        return f"""
{title}

{message}

---
This email was sent by {site_name}
        """.strip()
    
    def _generate_preheader(self, template_name: str, context: Dict[str, Any]) -> str:
        """Generate preheader text for email templates."""
        preheader_map = {
            'plant_care_reminder': 'Time to care for your plants!',
            'forum_reply': 'New activity in the community',
            'identification_result': 'Your plant has been identified',
            'newsletter': 'Your weekly plant care digest',
            'disease_alert': 'Important plant health information',
        }
        
        # Try to get context-specific preheader
        if 'preheader_text' in context:
            return context['preheader_text']
        
        # Use template-specific preheader
        return preheader_map.get(template_name, 'New notification from Plant Community')
    
    def _get_template_helpers(self) -> Dict[str, Any]:
        """Get helper functions for use in email templates."""
        return {
            'format_plant_name': self._format_plant_name,
            'format_confidence': self._format_confidence,
            'format_care_frequency': self._format_care_frequency,
            'get_button_style': self._get_button_style,
            'get_plant_emoji': self._get_plant_emoji,
        }
    
    def _format_plant_name(self, scientific_name: str, common_name: str = None) -> str:
        """Format plant names for display in emails."""
        if common_name and scientific_name:
            return f"{common_name} ({scientific_name})"
        return scientific_name or common_name or "Unknown Plant"
    
    def _format_confidence(self, confidence: float) -> str:
        """Format confidence scores for display."""
        percentage = confidence * 100
        if percentage >= 90:
            return f"{percentage:.0f}% (Very Confident)"
        elif percentage >= 70:
            return f"{percentage:.0f}% (Confident)"
        elif percentage >= 50:
            return f"{percentage:.0f}% (Moderately Confident)"
        else:
            return f"{percentage:.0f}% (Low Confidence)"
    
    def _format_care_frequency(self, frequency: str) -> str:
        """Format care frequency for display."""
        frequency_map = {
            'daily': 'every day',
            'weekly': 'once a week',
            'biweekly': 'every two weeks',
            'monthly': 'once a month',
            'seasonal': 'seasonally',
        }
        return frequency_map.get(frequency.lower(), frequency)
    
    def _get_button_style(self, button_type: str = 'primary') -> str:
        """Get CSS styles for email buttons."""
        styles = {
            'primary': (
                'background-color: #2c5f41; color: white; padding: 12px 24px; '
                'text-decoration: none; border-radius: 4px; display: inline-block; '
                'font-weight: bold; font-size: 16px;'
            ),
            'secondary': (
                'background-color: #f8f9fa; color: #2c5f41; padding: 12px 24px; '
                'text-decoration: none; border-radius: 4px; display: inline-block; '
                'font-weight: bold; font-size: 16px; border: 2px solid #2c5f41;'
            ),
            'danger': (
                'background-color: #dc3545; color: white; padding: 12px 24px; '
                'text-decoration: none; border-radius: 4px; display: inline-block; '
                'font-weight: bold; font-size: 16px;'
            ),
        }
        return styles.get(button_type, styles['primary'])
    
    def _get_plant_emoji(self, plant_type: str = None) -> str:
        """Get appropriate emoji for plant types."""
        plant_emojis = {
            'succulent': '🌵',
            'flowering': '🌸',
            'tree': '🌳',
            'herb': '🌿',
            'fern': '🌿',
            'cactus': '🌵',
            'orchid': '🌺',
            'rose': '🌹',
            'sunflower': '🌻',
            'tulip': '🌷',
        }
        
        if plant_type:
            plant_type_lower = plant_type.lower()
            for key, emoji in plant_emojis.items():
                if key in plant_type_lower:
                    return emoji
        
        return '🌱'  # Default plant emoji
    
    def create_template_context_for_plant_care(
        self,
        user_name: str,
        plant_name: str,
        care_type: str,
        care_instructions: str,
        next_care_date: str = None,
        plant_image_url: str = None
    ) -> Dict[str, Any]:
        """Create template context for plant care emails."""
        return {
            'user_name': user_name,
            'plant_name': plant_name,
            'care_type': care_type,
            'care_instructions': care_instructions,
            'next_care_date': next_care_date,
            'plant_image_url': plant_image_url,
            'plant_emoji': self._get_plant_emoji(plant_name),
            'care_frequency_text': self._format_care_frequency(care_type),
        }
    
    def create_template_context_for_forum_notification(
        self,
        user_name: str,
        topic_title: str,
        author_name: str,
        post_excerpt: str,
        topic_url: str,
        forum_name: str = None
    ) -> Dict[str, Any]:
        """Create template context for forum notification emails."""
        return {
            'user_name': user_name,
            'topic_title': topic_title,
            'author_name': author_name,
            'post_excerpt': post_excerpt,
            'topic_url': topic_url,
            'forum_name': forum_name or 'Plant Community Forum',
        }
    
    def create_template_context_for_identification(
        self,
        user_name: str,
        plant_name: str,
        confidence: float,
        identifier_name: str,
        result_url: str,
        plant_image_url: str = None
    ) -> Dict[str, Any]:
        """Create template context for identification result emails."""
        return {
            'user_name': user_name,
            'plant_name': plant_name,
            'confidence': confidence,
            'confidence_text': self._format_confidence(confidence),
            'identifier_name': identifier_name,
            'result_url': result_url,
            'plant_image_url': plant_image_url,
            'plant_emoji': self._get_plant_emoji(plant_name),
        }
    
    def validate_template_exists(self, template_name: str) -> Dict[str, bool]:
        """Check if both HTML and text versions of a template exist."""
        html_path = f'emails/{template_name}.html'
        txt_path = f'emails/{template_name}.txt'
        
        try:
            get_template(html_path)
            html_exists = True
        except TemplateDoesNotExist:
            html_exists = False
        
        try:
            get_template(txt_path)
            txt_exists = True
        except TemplateDoesNotExist:
            txt_exists = False
        
        return {
            'html': html_exists,
            'txt': txt_exists,
            'complete': html_exists and txt_exists
        }