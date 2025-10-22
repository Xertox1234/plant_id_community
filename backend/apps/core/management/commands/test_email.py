"""
Django management command to test email functionality.

Usage:
    python manage.py test_email recipient@example.com
    python manage.py test_email recipient@example.com --template welcome
    python manage.py test_email recipient@example.com --type plant_care_reminder
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.conf import settings
from apps.core.services.email_service import EmailService, EmailType
from apps.core.services.notification_service import NotificationService

User = get_user_model()


class Command(BaseCommand):
    help = 'Test email functionality by sending a test email'

    def add_arguments(self, parser):
        parser.add_argument(
            'recipient',
            type=str,
            help='Email address to send test email to'
        )
        parser.add_argument(
            '--template',
            type=str,
            default='generic_notification',
            help='Email template to use (default: generic_notification)'
        )
        parser.add_argument(
            '--type',
            type=str,
            default='system_test',
            help='Email type for tracking (default: system_test)'
        )
        parser.add_argument(
            '--user',
            type=str,
            help='Username or email of user to use as context (optional)'
        )

    def handle(self, *args, **options):
        recipient = options['recipient']
        template = options['template']
        email_type = options['type']
        user_identifier = options.get('user')

        self.stdout.write(f"Testing email functionality...")
        self.stdout.write(f"Recipient: {recipient}")
        self.stdout.write(f"Template: {template}")
        self.stdout.write(f"Type: {email_type}")

        # Get user if specified
        user = None
        if user_identifier:
            try:
                if '@' in user_identifier:
                    user = User.objects.get(email=user_identifier)
                else:
                    user = User.objects.get(username=user_identifier)
                self.stdout.write(f"Using user context: {user.username}")
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(f"User not found: {user_identifier}")
                )

        # Prepare test context
        context = {
            'test_message': 'This is a test email from Plant Community!',
            'user': user,
            'site_name': 'Plant Community',
            'plant_name': 'Monstera Deliciosa',
            'care_type': 'Watering',
            'care_instructions': 'Water when the top inch of soil feels dry.',
        }

        # Send email
        email_service = EmailService()
        
        try:
            success = email_service.send_email(
                email_type=email_type,
                recipient=recipient,
                subject=f"🌱 Test Email from Plant Community",
                template_name=template,
                context=context,
                priority='normal',
                respect_preferences=False  # Always send test emails
            )

            if success:
                self.stdout.write(
                    self.style.SUCCESS(f"✅ Test email sent successfully to {recipient}")
                )
                self.stdout.write(
                    f"Check the email inbox for {recipient} to verify delivery."
                )
                
                # Also show console output if using console backend
                if 'console' in settings.EMAIL_BACKEND:
                    self.stdout.write(
                        self.style.WARNING(
                            "📧 Note: Using console email backend - check server logs for email content."
                        )
                    )
            else:
                self.stdout.write(
                    self.style.ERROR(f"❌ Failed to send test email to {recipient}")
                )
                raise CommandError("Email sending failed")

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Error sending test email: {e}")
            )
            raise CommandError(f"Email test failed: {e}")

    def print_available_templates(self):
        """Print available email templates."""
        self.stdout.write("\nAvailable email templates:")
        templates = [
            'generic_notification',
            'welcome_email', 
            'plant_care_reminder',
            'forum_reply',
            'forum_mention',
            'identification_result',
            'newsletter',
        ]
        for template in templates:
            self.stdout.write(f"  - {template}")
        
        self.stdout.write("\nAvailable email types:")
        types = [
            EmailType.PLANT_CARE_REMINDER,
            EmailType.FORUM_REPLY,
            EmailType.FORUM_MENTION,
            EmailType.IDENTIFICATION_RESULT,
            EmailType.ACCOUNT_VERIFICATION,
            EmailType.NEWSLETTER,
        ]
        for email_type in types:
            self.stdout.write(f"  - {email_type}")