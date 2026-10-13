"""
Central email service for the Plant Community application.

Provides a unified interface for sending emails with tracking, preferences,
and template rendering capabilities.
"""

import html
import logging
import re
import smtplib
import uuid
from email.utils import parseaddr
from typing import Any, Dict, List, Optional, Union

from apps.core import email_feedback
from apps.core.constants import EMAIL_TRACKED_LINK_KEYS
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
# The opening tag of a div hidden with an inline display:none: base.html's
# preheader, the inbox preview line, which is not body text (todo 639). Each
# quote style is its own branch, so a style value holding the other quote
# (font-family:'x'; display:none) still matches (todo 649).
_HIDDEN_DIV_OPEN = re.compile(
    r"""<div\b[^>]*\bstyle\s*=\s*(?:"[^"]*?display\s*:\s*none[^"]*"|'[^']*?display\s*:\s*none[^']*')[^>]*>""",
    re.IGNORECASE,
)
_DIV_TAG = re.compile(r"<(/?)div\b[^>]*>", re.IGNORECASE)
# \s before href: an attribute always follows whitespace, so data-href= (where
# "-" makes a word boundary) is never read as the link (todo 639).
_LINK = re.compile(
    r"""<a\b[^>]*?\shref\s*=\s*(["'])(?P<url>.*?)\1[^>]*>(?P<label>.*?)</a\s*>""",
    re.IGNORECASE | re.DOTALL,
)
_LINE_BREAK = re.compile(
    r"<br\s*/?>|</(p|div|h[1-6]|li|tr|table|ul|ol|blockquote)\s*>", re.IGNORECASE
)
_SPACES = re.compile(r"[ \t\r\f\v]+")
_BLANK_LINES = re.compile(r"\n{3,}")


def _strip_hidden_divs(text: str) -> str:
    """Remove each display:none div with everything in it, up to its own
    closing tag: nested divs are counted, so a hidden div that holds one
    never leaks its remainder (todo 649). An unclosed one loses only its
    opening tag, so a template slip never empties the text part."""
    while match := _HIDDEN_DIV_OPEN.search(text):
        depth, end = 1, match.end()
        for tag in _DIV_TAG.finditer(text, match.end()):
            depth += -1 if tag.group(1) else 1
            if depth == 0:
                end = tag.end()
                break
        text = text[: match.start()] + text[end:]
    return text


def html_to_text(html_content: str) -> str:
    """A readable plain-text alternative for an HTML email that has no .txt.

    Drops the head, stylesheet, scripts, comments and the hidden preheader
    (todo 639); keeps every link as ``label (url)`` so the action survives;
    ends blocks with a line break; then strips the remaining tags and decodes
    entities. A fallback only: every live message family ships its own .txt
    (todo 622).
    """
    text = _COMMENT.sub("", _NON_CONTENT.sub("", html_content))
    text = _strip_hidden_divs(text)

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


class EmailOutcome:
    """Why ``EmailService.send_email`` returned what it did (todo 619).

    A bool cannot tell an opt-out from a dead SMTP connection, and a caller
    that retries must: an opt-out retried is a privacy bug, a transport
    failure dropped is a lost message. ``send_email`` records one of these on
    ``EmailService.last_outcome`` every time it returns.
    """

    SENT = "sent"
    # Preferences said no. Never retried.
    SUPPRESSED = "suppressed"
    # Retrying cannot help: a template that does not render, no deliverable
    # recipient, a 5xx SMTP rejection.
    PERMANENT = "permanent"
    # Worth another attempt: connection, timeout, a 4xx SMTP reply.
    TRANSIENT = "transient"


# ``EmailService.last_suppression_reason``: why a send was SUPPRESSED, in the
# outbox's own words (``DeliveryIntent.last_error``).
SUPPRESSED_PREFERENCE = "preference_off"
SUPPRESSED_ADDRESS = "address_suppressed"


def classify_send_error(exc: BaseException) -> str:
    """PERMANENT only when this message or its recipient was refused with a
    5xx: every recipient refused with one, or a 5xx reply to the message
    data. TRANSIENT for anything else: a connection or timeout error, a 4xx
    reply, a disconnect, and a 5xx about the session rather than the
    message (auth 535/530, sender refused, HELO). Those are relay credential
    or config faults: during such an outage every queued row would
    otherwise be failed for good, so they wait out the outbox backoff."""
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        codes = [code for code, _msg in exc.recipients.values()]
        if codes and all(int(code) >= 500 for code in codes):
            return EmailOutcome.PERMANENT
        return EmailOutcome.TRANSIENT
    if isinstance(exc, smtplib.SMTPDataError) and exc.smtp_code >= 500:
        return EmailOutcome.PERMANENT
    return EmailOutcome.TRANSIENT


class EmailType:
    """Email type constants for categorization and preferences."""

    # Plant care related emails
    DISEASE_ALERT = "disease_alert"

    # Forum related emails
    FORUM_REPLY = "forum_reply"
    FORUM_MENTION = "forum_mention"
    # Optional important-event email (todo 624), off by default.
    FORUM_QUOTE = "forum_quote"
    FORUM_SOLUTION = "forum_solution"
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


# Account mail: always sent, whatever the optional-mail preferences say, and
# held back only by a hard bounce, never by a spam complaint (todo 625).
SYSTEM_EMAIL_TYPES = frozenset(
    {
        EmailType.ACCOUNT_VERIFICATION,
        EmailType.PASSWORD_RESET,
        EmailType.SECURITY_ALERT,
    }
)


# Email type -> the list its unsubscribe link leaves (a key of
# apps.users.email_unsubscribe.LISTS). A type with no entry carries no link.
UNSUBSCRIBE_LISTS = {
    EmailType.FORUM_REPLY: "forum_reply",
    EmailType.FORUM_MENTION: "forum_mention",
    EmailType.FORUM_QUOTE: "forum_quote",
    EmailType.FORUM_SOLUTION: "forum_solution",
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
        self.site_name = getattr(settings, "SITE_NAME", "Houseplant MD")
        # The EmailOutcome of the last send_email call (todo 619).
        self.last_outcome: Optional[str] = None
        # Why it was SUPPRESSED, for an outbox to record (todo 625):
        # SUPPRESSED_PREFERENCE or SUPPRESSED_ADDRESS, else None.
        self.last_suppression_reason: Optional[str] = None

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
        respect_preferences: bool = True,
    ) -> bool:
        """
        Send an email with preference and suppression checks.

        Opens are never tracked (no pixel; owner decision 2026-10-12, todo
        625). The content links named by ``EMAIL_TRACKED_LINK_KEYS`` go
        through a signed first-party click redirect when ``API_PUBLIC_URL``
        is set (``apps.core.email_feedback.click_url``).

        Args:
            email_type: Type of email from EmailType constants
            recipient: Email address string or User instance
            subject: Email subject line
            template_name: Base name of email template (without .html/.txt)
            context: Template context variables
            from_email: Sender email (defaults to site default)
            attachments: List of file attachments
            priority: Email priority ('low', 'normal', 'high')
            respect_preferences: Whether to check user preferences

        Returns:
            bool: True if email was sent successfully. Why it was not is on
            ``self.last_outcome`` (an ``EmailOutcome``).
        """
        self.last_outcome = None
        self.last_suppression_reason = None
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
            self.last_outcome = EmailOutcome.SUPPRESSED
            self.last_suppression_reason = SUPPRESSED_PREFERENCE
            return False

        # The provider reported this address as undeliverable, or its owner
        # as complaining (todo 625). Terminal: retrying cannot help.
        if email_feedback.is_suppressed(
            recipient_email, optional=email_type not in SYSTEM_EMAIL_TYPES
        ):
            logger.info(
                f"[EMAIL] Email {email_type} to {log_safe_email(recipient_email)} "
                "not sent: the address is suppressed"
            )
            self.last_outcome = EmailOutcome.SUPPRESSED
            self.last_suppression_reason = SUPPRESSED_ADDRESS
            return False

        # The row's uuid exists before the send: it names the click redirects
        # and the Message-ID the provider's feedback is matched on (todo 625).
        notification_uuid = uuid.uuid4()
        message_id = self._message_id(notification_uuid, from_email)

        # Prepare context
        context = context or {}
        context.update(self._get_base_context(user, email_type))
        for key in EMAIL_TRACKED_LINK_KEYS:
            if isinstance(context.get(key), str):
                context[key] = email_feedback.click_url(
                    notification_uuid, key, context[key]
                )

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
            self.last_outcome = EmailOutcome.PERMANENT
            return False
        except Exception as e:
            # The type only: a template error can quote a context value, such
            # as the signed unsubscribe link (todo 649 finding 1).
            logger.error(
                f"[EMAIL] Failed to render email template {template_name}.html: "
                f"{type(e).__name__}"
            )
            self.last_outcome = EmailOutcome.PERMANENT
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
                f"(falling back to stripped HTML): {type(e).__name__}"
            )
            text_content = html_to_text(html_content)

        # Create email message. List-Unsubscribe (RFC 2369, plus RFC 8058
        # one-click when API_PUBLIC_URL is set) puts a signed link in the mail
        # client's own "Unsubscribe" button (todo 416).
        headers = dict(context.get("unsubscribe_headers") or {})
        headers["Message-ID"] = message_id
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
                if recipient_email:
                    # A real address that reached nobody: the mail backend's
                    # suppression backstop dropped it (suppressed after the
                    # check above). Terminal, and recorded as such (todo 625).
                    self.last_outcome = EmailOutcome.SUPPRESSED
                    self.last_suppression_reason = SUPPRESSED_ADDRESS
                else:
                    self.last_outcome = EmailOutcome.PERMANENT
                return False

            # Track email sending
            self._track_email_sent(
                notification_uuid=notification_uuid,
                message_id=message_id,
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
            self.last_outcome = EmailOutcome.SENT
            return True

        except Warning:
            # A RemovedInDjango70Warning is an error under pytest.ini (todo 364)
            # and Warning subclasses Exception: never log it as a failed send
            # (todo 454).
            raise
        except ConnectionError as e:
            logger.error(
                f"[EMAIL] Email connection failed for {email_type} to "
                f"{log_safe_email(recipient_email)}: {type(e).__name__}"
            )
            self.last_outcome = EmailOutcome.TRANSIENT
            return False
        except Exception as e:
            logger.error(
                # The type only: an SMTP refusal's text quotes the raw
                # recipient address (todo 619).
                f"[EMAIL] Failed to send email {email_type} to "
                f"{log_safe_email(recipient_email)}: {type(e).__name__}"
            )
            self.last_outcome = classify_send_error(e)
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
        if email_type in SYSTEM_EMAIL_TYPES:
            return True

        # Check master email toggle (using direct user model attributes)
        if not user.email_notifications:
            return False

        # Check specific email type preferences
        email_preference_map = {
            EmailType.DISEASE_ALERT: user.plant_id_notifications,
            EmailType.FORUM_REPLY: user.forum_notifications,
            EmailType.FORUM_MENTION: user.forum_notifications,
            EmailType.FORUM_QUOTE: user.forum_notifications,
            EmailType.FORUM_SOLUTION: user.forum_notifications,
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

    def _message_id(
        self, notification_uuid: uuid.UUID, from_email: Optional[str]
    ) -> str:
        """The RFC 5322 Message-ID for a tracked email, on the sender's own
        domain, so Resend's ``data.message_id`` names the row (todo 625)."""
        sender = parseaddr(from_email or self.from_email)[1]
        # Lowercased: the feedback lookup compares a normalized id
        # (``email_feedback.normalize_message_id``).
        domain = sender.rpartition("@")[2].lower() or "localhost"
        return f"<hpmd.{notification_uuid.hex}@{domain}>"

    def _track_email_sent(
        self,
        notification_uuid: uuid.UUID,
        message_id: str,
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
                uuid=notification_uuid,
                message_id=message_id,
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

        # Account mail: only a hard bounce holds it back (todo 625). The
        # caller's flow (tokens, allowance, its response) is unchanged.
        self.last_outcome = None
        self.last_suppression_reason = None
        if email_feedback.is_suppressed(recipient_email, optional=False):
            logger.info(
                f"[EMAIL] Transactional email to {log_safe_email(recipient_email)} "
                "not sent: the address is suppressed"
            )
            self.last_outcome = EmailOutcome.SUPPRESSED
            self.last_suppression_reason = SUPPRESSED_ADDRESS
            return False

        try:
            sent_count = send_mail(
                subject=subject,
                message=message,
                from_email=self.from_email,
                recipient_list=[recipient_email],
                html_message=html_message,
            )
            if not sent_count:
                # The mail backend's suppression backstop dropped the only
                # recipient (an address suppressed after the check above),
                # or there was no address: not a send (todo 625).
                logger.warning(
                    f"[EMAIL] Transactional email to {log_safe_email(recipient_email)} "
                    "reached 0 recipients — not marking as sent"
                )
                self.last_outcome = EmailOutcome.SUPPRESSED
                self.last_suppression_reason = SUPPRESSED_ADDRESS
                return False
            logger.info(
                f"[EMAIL] Transactional email sent to {log_safe_email(recipient_email)}"
            )
            self.last_outcome = EmailOutcome.SENT
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
            subject=f"🎉 Welcome to {self.site_name}, {user.first_name or user.username}!",
            template_name="welcome_email",
            context=context,
            priority="high",
            respect_preferences=False,  # Welcome emails should always be sent
        )
