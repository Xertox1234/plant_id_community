"""
User services for trust level management and notifications.
"""

import hmac
import json
import logging
from contextlib import nullcontext
from typing import Any, Dict, Optional

import requests
from apps.core.utils.pii_safe_logging import log_safe_user_context
from django.conf import settings
from django.db import transaction

from .constants import (
    WEB_PUSH_GONE_STATUSES,
    WEB_PUSH_TIMEOUT_SECONDS,
    WEB_PUSH_TTL_SECONDS,
)

# External dependency for Web Push (requires: pip install pywebpush)
try:
    from pywebpush import WebPushException, webpush

    WEBPUSH_AVAILABLE = True
except ImportError:
    WEBPUSH_AVAILABLE = False
    WebPushException = Exception

logger = logging.getLogger(__name__)


def vapid_claims_email() -> str:
    """The VAPID ``sub`` contact address without a ``mailto:`` prefix, or ""."""
    email = (getattr(settings, "VAPID_CLAIMS_EMAIL", "") or "").strip()
    if email.lower().startswith("mailto:"):
        email = email[len("mailto:") :].strip()
    return email


def web_push_enabled() -> bool:
    """True when the server can both hand out a key and sign a push."""
    return bool(
        getattr(settings, "VAPID_PUBLIC_KEY", "")
        and getattr(settings, "VAPID_PRIVATE_KEY", "")
        and vapid_claims_email()
    )


class NoRedirectSession(requests.Session):
    """A requests session that never follows a redirect (todo 456 item 6).

    The push endpoint passed the SSRF allowlist once, at subscribe time
    (``web_push.is_allowed_push_endpoint``). A redirect from it would send the
    signed POST to a host nobody checked. pywebpush passes no
    ``allow_redirects``, and ``Session.request`` defaults it to True, so it is
    forced off here. The 3xx then fails the send (pywebpush raises for any
    status above 202) and is logged; it is not a gone status, so the row stays.
    """

    def request(self, method, url, *args, **kwargs):
        kwargs["allow_redirects"] = False
        return super().request(method, url, *args, **kwargs)


def web_push_session() -> requests.Session:
    """One connection pool for a batch of sends, redirects off (todo 456)."""
    return NoRedirectSession()


class NotificationService:
    """
    Service class for handling various types of notifications.
    """

    @staticmethod
    def send_web_push_notification(
        subscription,  # PushSubscription instance
        title: str,
        body: str,
        icon: str = "/icons/icon-192x192.png",
        badge: str = "/icons/badge-72x72.png",
        actions: Optional[list] = None,
        data: Optional[Dict[str, Any]] = None,
        tag: Optional[str] = None,
        requests_session: Optional[requests.Session] = None,
        mark_used: bool = True,
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
            requests_session: The session to POST with. A batch passes one
                shared session (todo 456); None makes a no-redirect one.
            mark_used: Save ``last_used`` on success. A batch passes False
                and updates every sent row in one query instead.

        Returns:
            bool: True if sent successfully, False otherwise
        """
        if not WEBPUSH_AVAILABLE:
            logger.error(
                "[PUSH] pywebpush library not available. Install with: pip install pywebpush"
            )
            return False

        try:
            # Prepare notification payload
            payload = {
                "title": title,
                "body": body,
                "icon": icon,
                "badge": badge,
                "tag": tag or "plant-community",
                "requireInteraction": True,
                "data": data or {},
                "actions": actions or [],
            }

            # Prepare subscription info for pywebpush
            subscription_info = {
                "endpoint": subscription.endpoint,
                "keys": {
                    "p256dh": subscription.p256dh_key,
                    "auth": subscription.auth_key,
                },
            }

            vapid_private_key = getattr(settings, "VAPID_PRIVATE_KEY", None)
            claims_email = vapid_claims_email()
            if not vapid_private_key or not claims_email:
                logger.error(
                    "[PUSH] VAPID_PRIVATE_KEY or VAPID_CLAIMS_EMAIL not configured"
                )
                return False

            # A caller's session stays open for its next send; one made here
            # is closed here.
            with (
                nullcontext(requests_session)
                if requests_session is not None
                else web_push_session()
            ) as session:
                webpush(
                    subscription_info=subscription_info,
                    data=json.dumps(payload),
                    vapid_private_key=vapid_private_key,
                    vapid_claims={"sub": f"mailto:{claims_email}"},
                    content_encoding="aes128gcm",
                    ttl=WEB_PUSH_TTL_SECONDS,
                    timeout=WEB_PUSH_TIMEOUT_SECONDS,
                    requests_session=session,
                )

            if mark_used:
                subscription.mark_as_used()

            logger.info(
                f"[PUSH] Push notification sent successfully to {log_safe_user_context(subscription.user)}"
            )
            return True

        except WebPushException as e:
            logger.error(
                f"[PUSH] WebPush error for {log_safe_user_context(subscription.user)}: {e}"
            )

            # `is not None`, never truthiness: requests.Response.__bool__ is
            # `.ok`, so an error response is falsy (PR #852 review).
            if (
                e.response is not None
                and e.response.status_code in WEB_PUSH_GONE_STATUSES
            ):
                subscription.deactivate()
                logger.warning(
                    f"[PUSH] Deactivated push subscription for {log_safe_user_context(subscription.user)}"
                )

            return False

        except Exception as e:
            logger.error(f"[PUSH] Unexpected error sending push notification: {e}")
            return False

    @staticmethod
    def subscribe_to_push(
        user, subscription_data: Dict[str, Any], user_agent: str = ""
    ):
        """
        Create or update a push subscription for a user.

        Args:
            user: User instance
            subscription_data: Subscription data from the client
            user_agent: User agent string for device identification

        Returns:
            PushSubscription instance
        """
        endpoint = subscription_data.get("endpoint")
        keys = subscription_data.get("keys", {})

        with transaction.atomic():
            return NotificationService._store_subscription(
                user, endpoint, keys, user_agent
            )

    @staticmethod
    def _store_subscription(user, endpoint: str, keys: Dict[str, Any], user_agent: str):
        """The body of ``subscribe_to_push``, run inside one transaction so the
        release and the upsert land together (PR #852 round-2 note)."""
        from .models import PushSubscription

        # One browser endpoint belongs to one account: a shared browser where
        # another user subscribed last must not keep getting their
        # notifications (PR #852 review).
        released = (
            PushSubscription.objects.filter(endpoint=endpoint, is_active=True)
            .exclude(user=user)
            .update(is_active=False)
        )
        if released:
            logger.info(
                f"[PUSH] Released {released} subscription(s) on this endpoint "
                f"held by another account, for {log_safe_user_context(user)}"
            )

        subscription, created = PushSubscription.objects.update_or_create(
            user=user,
            endpoint=endpoint,
            defaults={
                "p256dh_key": keys.get("p256dh", ""),
                "auth_key": keys.get("auth", ""),
                "user_agent": user_agent,
                "device_name": NotificationService._extract_device_name(user_agent),
                "is_active": True,
            },
        )

        logger.info(
            f"[PUSH] Push subscription {'created' if created else 'updated'} for {log_safe_user_context(user)}"
        )
        return subscription

    @staticmethod
    def resubscribe_push(
        old_endpoint: Any,
        old_auth: Any,
        subscription_data: Dict[str, Any],
        user_agent: str = "",
    ):
        """Swap a browser's replaced push subscription for its new one (todo 456).

        The service worker's ``pushsubscriptionchange`` handler calls this. It
        has no cookie and no CSRF token, so the caller proves it holds the old
        subscription with the old one's endpoint AND its ``auth`` secret (16
        random bytes the browser generated, and only the browser and this
        server know). Only an ACTIVE row matches: a shared browser leaves
        released rows for other accounts on the same endpoint, with the same
        secret, and none of those may be revived.

        ``subscription_data`` must already be through ``clean_subscription``.
        Returns the new row, or None when nothing matched.
        """
        from .models import PushSubscription

        if not (isinstance(old_endpoint, str) and isinstance(old_auth, str)):
            return None
        if not old_endpoint or not old_auth:
            return None
        with transaction.atomic():
            old = (
                PushSubscription.objects.select_for_update()
                .filter(endpoint=old_endpoint, is_active=True)
                .select_related("user")
                .first()
            )
            if old is None or not hmac.compare_digest(
                old.auth_key.encode(), old_auth.encode()
            ):
                return None
            if old.endpoint != subscription_data["endpoint"]:
                old.deactivate()
            subscription = NotificationService._store_subscription(
                old.user,
                subscription_data["endpoint"],
                subscription_data["keys"],
                user_agent or old.user_agent,
            )
        logger.info(
            f"[PUSH] Browser replaced its push subscription for {log_safe_user_context(old.user)}"
        )
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
            logger.info(
                f"[PUSH] Push subscription deactivated for {log_safe_user_context(user)}"
            )
            return True
        except PushSubscription.DoesNotExist:
            logger.warning(
                f"[PUSH] Push subscription not found for {log_safe_user_context(user)} with endpoint {endpoint[:20]}..."
            )
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
            return "Unknown device"

        # Simple device detection (can be enhanced with a proper library)
        user_agent_lower = user_agent.lower()

        if "mobile" in user_agent_lower or "android" in user_agent_lower:
            if "chrome" in user_agent_lower:
                return "Chrome on Android"
            elif "firefox" in user_agent_lower:
                return "Firefox on Android"
            else:
                return "Mobile Browser"
        elif "iphone" in user_agent_lower or "ipad" in user_agent_lower:
            if "safari" in user_agent_lower:
                return "Safari on iOS"
            elif "chrome" in user_agent_lower:
                return "Chrome on iOS"
            else:
                return "iOS Browser"
        elif "windows" in user_agent_lower:
            if "chrome" in user_agent_lower:
                return "Chrome on Windows"
            elif "firefox" in user_agent_lower:
                return "Firefox on Windows"
            elif "edge" in user_agent_lower:
                return "Edge on Windows"
            else:
                return "Windows Browser"
        elif "mac" in user_agent_lower:
            if "chrome" in user_agent_lower:
                return "Chrome on Mac"
            elif "firefox" in user_agent_lower:
                return "Firefox on Mac"
            elif "safari" in user_agent_lower:
                return "Safari on Mac"
            else:
                return "Mac Browser"
        elif "linux" in user_agent_lower:
            if "chrome" in user_agent_lower:
                return "Chrome on Linux"
            elif "firefox" in user_agent_lower:
                return "Firefox on Linux"
            else:
                return "Linux Browser"
        else:
            return "Desktop Browser"
