"""
Core services for the Plant Community application.

This module provides centralized services for email, notifications, and templates.
"""

# Avoid circular imports during Django startup
# Import services when needed using:
# from apps.core.services.email_service import EmailService

__all__ = [
    'EmailService',
    'NotificationService', 
    'TemplateService',
]