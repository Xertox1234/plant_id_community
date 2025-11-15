"""
Firebase Configuration

Centralized Firebase Admin SDK initialization and configuration.

Provides:
- Firebase Admin SDK initialization
- Firestore client access
- FCM messaging client access
- Configuration validation
"""

import logging
from typing import Optional
from django.conf import settings

logger = logging.getLogger(__name__)

# Lazy-loaded Firebase instances
_firebase_app = None
_firestore_client = None
_fcm_client = None


def get_firebase_credentials_path() -> Optional[str]:
    """Get Firebase service account credentials path from settings."""
    return getattr(settings, 'FIREBASE_CREDENTIALS_PATH', None)


def initialize_firebase() -> bool:
    """
    Initialize Firebase Admin SDK.

    Returns:
        True if initialization successful, False otherwise
    """
    global _firebase_app

    if _firebase_app is not None:
        logger.info("[FIREBASE] Already initialized")
        return True

    credentials_path = get_firebase_credentials_path()
    if not credentials_path:
        logger.warning("[FIREBASE] No credentials path configured")
        return False

    try:
        import firebase_admin
        from firebase_admin import credentials

        # Initialize Firebase app
        cred = credentials.Certificate(credentials_path)
        _firebase_app = firebase_admin.initialize_app(cred)

        logger.info("[FIREBASE] ✅ Firebase Admin SDK initialized successfully")
        return True

    except ImportError:
        logger.error("[FIREBASE] firebase-admin library not installed")
        return False
    except Exception as e:
        logger.error(f"[FIREBASE] Initialization failed: {str(e)}")
        return False


def get_firestore_client():
    """
    Get Firestore client instance.

    Returns:
        Firestore client or None if unavailable
    """
    global _firestore_client

    if _firestore_client is not None:
        return _firestore_client

    if not initialize_firebase():
        return None

    try:
        from firebase_admin import firestore

        _firestore_client = firestore.client()
        logger.info("[FIREBASE] Firestore client initialized")
        return _firestore_client

    except Exception as e:
        logger.error(f"[FIREBASE] Failed to get Firestore client: {str(e)}")
        return None


def get_fcm_client():
    """
    Get Firebase Cloud Messaging client instance.

    Returns:
        FCM client or None if unavailable
    """
    global _fcm_client

    if _fcm_client is not None:
        return _fcm_client

    if not initialize_firebase():
        return None

    try:
        from firebase_admin import messaging

        _fcm_client = messaging
        logger.info("[FIREBASE] FCM client initialized")
        return _fcm_client

    except Exception as e:
        logger.error(f"[FIREBASE] Failed to get FCM client: {str(e)}")
        return None


def is_firebase_available() -> bool:
    """
    Check if Firebase is properly configured and available.

    Returns:
        True if Firebase is available, False otherwise
    """
    return get_firebase_credentials_path() is not None


def reset_firebase():
    """
    Reset Firebase initialization (for testing).

    WARNING: Only use in tests!
    """
    global _firebase_app, _firestore_client, _fcm_client

    _firebase_app = None
    _firestore_client = None
    _fcm_client = None

    try:
        import firebase_admin
        if firebase_admin._apps:
            for app in firebase_admin._apps.values():
                firebase_admin.delete_app(app)
    except:
        pass

    logger.info("[FIREBASE] Firebase reset complete")
