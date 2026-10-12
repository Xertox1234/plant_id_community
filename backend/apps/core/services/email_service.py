"""
Central email service for the Plant Community application.

Provides a unified interface for sending emails with tracking, preferences,
and template rendering capabilities.
"""

import html
import logging
import re
from typing import Any, Dict, List, Optional, Union

from apps.core.utils.pii_safe_logging import log_safe_email, log_safe_user_context
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives, send_mail
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags

User = get_user_model()
logger = logging.getLogger(__name__)

# html_to_text() patterns (todo 622). The plain-text part of a message whose
# template ships no .txt: never the stylesheet, never a lost button URL.
_NON_CONTENT = re.compile(
    r"<(head|style|script|title)\b[^>]*>.*?</\1\s*>", re.IGNORECASE | re.DOTALL
)
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_LINK = re.compile(
    r"""<a\b[^>]*?\bhref\s*=\s*(["'])(?P<url>.*?)\1[^>]*>(?P<label>.*?)</a\s*>""",
    re.IGNORECASE | re.DOTALL,
)
_LINE_BREAK = re.compile(
    r"<br\s*/?>|</(p|div|h[1-6]|li|tr|table|ul|ol|blockquote)\s*>", re.IGNORECASE
)
_SPACES = re.compile(r"[ \t\r\f\v]+")
_BLANK_LINES = re.compile(r"\n{3,}")


def html_to_text(html_content: str) -> str:
    """A readable plain-text alternative for an HTML email that has no .txt.

    Drops the head, stylesheet, scripts and comments; keeps every link as
    ``label (url)`` so the action survives; ends blocks with a line break;
    then strips the remaining tags and decodes entities. A fallback only:
    every live message family ships its own .txt (todo 622).
    """
    text = _COMMENT.sub("", _NON_CONTENT.sub("", html_content))

    def _link(match: "re.Match[str]") -> str:
        url = match.group("url").strip()
        label = " ".join(strip_tags(match.group("label")).split())
        if not url or url.startswith("#") or url == label:
            return label or url
        return f"{label} ({url})" if label else url

    text = _LINK.sub(_link, text)
    text = _LINE_BREAK.sub("\n", text)
    text = html.unescape(strip_tags(text))
    lines = [_SPACES.sub(" ", line).strip() for line in text.split("\n")]
    return _BLANK_LINES.sub("\n\n", "\n".join(lines)).strip() + "\n"


class EmailType:
    """Email type constants for categorization and preferences."""

    # Plant care related emails
    DISEASE_ALERT = "disease_alert"

    # Forum related emails
    FORUM_REPLY = "forum_reply"
    FORUM_MENTION = "forum_mention"
    FORUM_DIGEST = "forum_digest"

    # Newsletter and content
    BLOG_POST = "blog_post"
    PLANT_TIPS = "plant_tips"

    # System emails
    ACCOUNT_VERIFICATION = "account_verification"
    PASSWORD_RESET = "password_reset"
    SECURITY_ALERT = "security_alert"

    # Community emails
    IDENTIFICATION_RESULT = "identification_result"
    COMMUNITY_UPDATE = "community_update"


# Email type -> the list its unsubscribe link leaves (a key of
# apps.users.email_unsubscribe.LISTS). A type with no entry carries no link.
UNSUBSCRIBE_LISTS = {
    EmailType.FORUM_REPLY: "forum_reply",
    EmailType.FORUM_DIGEST: "forum_digest",
}


class EmailService:
    """
    Central email service that handles all email sending with user preferences,
    tracking, and template rendering.
    """

    def __init__(self):
        self.from_email = getattr(
            settings, "DEFAULT_FROM_EMAIL", "noreply@plantcommunity.com"
        )
        self.site_name = getattr(settings, "SITE_NAME", "Houseplant-MD")

    def send_email(
        self,
        email_type: str,
        recipient: Union[str, User],
        subject: str,
        template_name: str,
        context: Optional[Dict[str, Any]] = None,
        from_email: Optional[str] = None,
        attachments: Optional[List] = None,
        priority: str = "normal",
        track_opens: bool = True,
        respect_preferences: bool = True,
    ) -> bool:
        """
        Send an email with full tracking and preference checking.

        Args:
            email_type: Type of email from EmailType constants
            recipient: Email address string or User instance
            subject: Email subject line
            template_name: Base name of email template (without .html/.txt)
            context: Template context variables
            from_email: Sender email (defaults to site default)
            attachments: List of file attachments
            priority: Email priority ('low', 'normal', 'high')
            track_opens: Whether to track email opens
            respect_preferences: Whether to check user preferences

        Returns:
            bool: True if email was sent successfully
        """
        # Normalize recipient
        if isinstance(recipient, User):
            user = recipient
            recipient_email = user.email
        else:
            recipient_email = recipient
            try:
                user = User.objects.get(email=recipient_email)
            except User.DoesNotExist:
                user = None

        # Check user preferences if requested
        if (
            respect_preferences
            and user
            and not self._should_send_email(user, email_type)
        ):
            logger.info(
                f"[EMAIL] Email {email_type} skipped for {log_safe_email(recipient_email)} due to user preferences"
            )
            return False

        # Prepare context
        context = context or {}
        context.update(self._get_base_context(user, email_type))

        # Render email content. The .html body is REQUIRED — a missing/broken
        # .html is a hard failure. The .txt alternative is OPTIONAL: a missing
        # .txt falls back to html_to_text() of the HTML (todo 622: never raw
        # strip_tags, which kept the stylesheet and lost every button URL)
        # rather than silently dropping the
        # whole email (todo 267, finding 2 — before this, a missing .txt raised
        # TemplateDoesNotExist that was caught into a silent `return False`, so
        # e.g. every new-user welcome email no-op'd at the render step).
        try:
            html_content = render_to_string(f"emails/{template_name}.html", context)
        except TemplateDoesNotExist as e:
            logger.error(
                f"[EMAIL] Email template not found: {template_name}.html - {e}"
            )
            return False
        except Exception as e:
            logger.error(
                f"[EMAIL] Failed to render email template {template_name}.html: {e}"
            )
            return False

        try:
            text_content = render_to_string(f"emails/{template_name}.txt", context)
        except TemplateDoesNotExist:
            # Expected for the legacy .html-only templates — derive plain text
            # from the HTML that already rendered.
            text_content = html_to_text(html_content)
        except Exception as e:
            # A genuine .txt render bug shouldn't drop an email whose .html is
            # fine; fall back to the stripped HTML but surface the bug in logs.
            logger.warning(
                f"[EMAIL] Failed to render email template {template_name}.txt "
                f"(falling back to stripped HTML): {e}"
            )
            text_content = html_to_text(html_content)

        # Create email message. List-Unsubscribe (RFC 2369, plus RFC 8058
        # one-click when API_PUBLIC_URL is set) puts a signed link in the mail
        # client's own "Unsubscribe" button (todo 416).
        headers = dict(context.get("unsubscribe_headers") or {})
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email or self.from_email,
            to=[recipient_email],
            headers=headers,
        )
        email.attach_alternative(html_content, "text/html")

        # Add attachments
        if attachments:
            for attachment in attachments:
                email.attach(*attachment)

        # Send email
        try:
            sent_count = email.send()

            # Django's EmailMessage.send() returns the number of messages
            # delivered, and returns 0 WITHOUT raising when every recipient
            # address is filtered out (e.g. a blank/empty To). Treat 0 as a
            # failure instead of tracking + logging a phantom success (todo 267,
            # finding 1): callers act on this bool, so a phantom True would
            # record a send the user never received.
            if not sent_count:
                logger.warning(
                    f"[EMAIL] Email {email_type} to {log_safe_email(recipient_email)} "
                    "reached 0 recipients — not marking as sent"
                )
                return False

            # Track email sending
            self._track_email_sent(
                email_type=email_type,
                recipient_email=recipient_email,
                user=user,
                subject=subject,
                template_name=template_name,
                priority=priority,
            )

            logger.info(
                f"[EMAIL] Email {email_type} sent successfully to {log_safe_email(recipient_email)}"
            )
            return True

        except Warning:
            # A RemovedInDjango70Warning is an error under pytest.ini (todo 364)
            # and Warning subclasses Exception: never log it as a failed send
            # (todo 454).
            raise
        except ConnectionError as e:
            logger.error(
                f"[EMAIL] Email connection failed for {email_type} to {log_safe_email(recipient_email)}: {e}"
            )
            return False
        except Exception as e:
            logger.error(
                f"[EMAIL] Failed to send email {email_type} to {log_safe_email(recipient_email)}: {e}"
            )
            return False

    def send_bulk_email(
        self,
        email_type: str,
        recipients: List[Union[str, User]],
        subject: str,
        template_name: str,
        context_factory: callable,
        **kwargs,
    ) -> Dict[str, int]:
        """
        Send bulk emails with individual context for each recipient.

        Args:
            email_type: Type of email
            recipients: List of email addresses or User instances
            subject: Email subject line
            template_name: Email template name
            context_factory: Function that takes recipient and returns context
            **kwargs: Additional arguments passed to send_email

        Returns:
            Dict with 'sent' and 'failed' counts
        """
        results = {"sent": 0, "failed": 0}

        for recipient in recipients:
            try:
                context = context_factory(recipient)
                if self.send_email(
                    email_type=email_type,
                    recipient=recipient,
                    subject=subject,
                    template_name=template_name,
                    context=context,
                    **kwargs,
                ):
                    results["sent"] += 1
                else:
                    results["failed"] += 1
            except Warning:
                # Re-raised by send_email (todo 454): never count it as one
                # recipient's failure.
                raise
            except Exception as e:
                # recipient could be email or User object - handle both cases
                safe_recipient = (
                    log_safe_email(recipient)
                    if isinstance(recipient, str)
                    else log_safe_user_context(recipient)
                )
                logger.error(
                    f"[EMAIL] Bulk email failed for recipient {safe_recipient}: {e}"
                )
                results["failed"] += 1

        logger.info(
            f"[EMAIL] Bulk email {email_type} completed: {results['sent']} sent, {results['failed']} failed"
        )
        return results

    def _should_send_email(self, user: User, email_type: str) -> bool:
        """
        Check if user preferences allow sending this email type.

        Args:
            user: User instance
            email_type: Type of email to check

        Returns:
            bool: True if email should be sent
        """
        # System emails (security, verification) always send: no optional-mail
        # preference, the master toggle included, may hold them back (todo
        # 622 — the toggle used to be checked first and did).
        system_emails = {
            EmailType.ACCOUNT_VERIFICATION,
            EmailType.PASSWORD_RESET,
            EmailType.SECURITY_ALERT,
        }

        if email_type in system_emails:
            return True

        # Check master email toggle (using direct user model attributes)
        if not user.email_notifications:
            return False

        # Check specific email type preferences
        email_preference_map = {
            EmailType.DISEASE_ALERT: user.plant_id_notifications,
            EmailType.FORUM_REPLY: user.forum_notifications,
            EmailType.FORUM_MENTION: user.forum_notifications,
            EmailType.FORUM_DIGEST: user.forum_notifications,
            EmailType.IDENTIFICATION_RESULT: user.plant_id_notifications,
        }

        # Check specific preference or default to True
        return email_preference_map.get(email_type, True)

    def _get_base_context(
        self, user: Optional[User], email_type: str
    ) -> Dict[str, Any]:
        """
        Get base context variables for all email templates.

        Args:
            user: User instance or None
            email_type: Type of email being sent

        Returns:
            Dict: Base context variables
        """
        # No trailing slash: every template appends a path that starts with
        # "/", so "https://web.example/" would build "//identify" (todo 622).
        site_url = getattr(settings, "SITE_URL", "https://plantcommunity.com")
        site_url = (site_url or "").rstrip("/")

        context = {
            "site_name": self.site_name,
            "site_url": site_url,
            "app_url": site_url,  # PWA-compatible URL (same as site_url for now)
            "user": user,
            "email_type": email_type,
            "current_year": timezone.now().year,
        }

        # The web app's Settings page holds every email choice a user can
        # change (todo 408; the old "#!/settings/..." PWA fragment led nowhere).
        context["preferences_url"] = f"{site_url}/settings"

        # A signed one-user, one-list link — only for an email type that has a
        # list to leave. No link beats one that 500s or does nothing.
        list_id = UNSUBSCRIBE_LISTS.get(email_type)
        if user and list_id:
            from apps.users.email_unsubscribe import (
                make_token,
                unsubscribe_headers,
                unsubscribe_url,
            )

            # One token for the body link and the header (PR #819 review).
            token = make_token(user, list_id)
            context["unsubscribe_url"] = unsubscribe_url(user, list_id, token)
            context["unsubscribe_headers"] = unsubscribe_headers(user, list_id, token)

        return context

    def _track_email_sent(
        self,
        email_type: str,
        recipient_email: str,
        user: Optional[User],
        subject: str,
        template_name: str,
        priority: str,
    ):
        """
        Track email sending for analytics and debugging.
        """
        # Import here to avoid circular imports
        try:
            from apps.core.models import EmailNotification

            EmailNotification.objects.create(
                email_type=email_type,
                recipient_email=recipient_email,
                user=user,
                subject=subject,
                template_name=template_name,
                priority=priority,
                sent_at=timezone.now(),
                status=EmailNotification.STATUS_SENT,
            )
        except (ImportError, Exception) as e:
            # Log but don't fail email sending if tracking fails
            logger.warning(f"[EMAIL] Failed to track email: {e}")

    def send_transactional_email(
        self,
        recipient: Union[str, User],
        subject: str,
        message: str,
        html_message: Optional[str] = None,
    ) -> bool:
        """
        Send a simple transactional email without templates.

        Args:
            recipient: Email address or User instance
            subject: Email subject
            message: Plain text message
            html_message: Optional HTML message

        Returns:
            bool: True if sent successfully
        """
        if isinstance(recipient, User):
            recipient_email = recipient.email
        else:
            recipient_email = recipient

        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=self.from_email,
                recipient_list=[recipient_email],
                html_message=html_message,
            )
            logger.info(
                f"[EMAIL] Transactional email sent to {log_safe_email(recipient_email)}"
            )
            return True
        except Warning:
            # A RemovedInDjango70Warning is an error under pytest.ini (todo 364)
            # and Warning subclasses Exception: never log it as a failed send
            # (todo 454).
            raise
        except Exception as e:
            logger.error(
                f"[EMAIL] Failed to send transactional email to {log_safe_email(recipient_email)}: {e}"
            )
            return False

    def send_welcome_email(self, user: User) -> bool:
        """
        Send welcome email to newly verified users.

        Args:
            user: User instance who just verified their email

        Returns:
            bool: True if email was sent successfully
        """
        context = {
            "user": user,
            "user_first_name": user.first_name or user.username,
        }

        return self.send_email(
            email_type=EmailType.ACCOUNT_VERIFICATION,
            recipient=user,
            subject=f"🎉 Welcome to Houseplant-MD, {user.first_name or user.username}!",
            template_name="welcome_email",
            context=context,
            priority="high",
            respect_preferences=False,  # Welcome emails should always be sent
        )
