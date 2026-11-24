"""Plain text from member-written markup."""

from django.core.exceptions import SuspiciousOperation
from django.utils.html import strip_tags


def safe_strip_tags(value: str) -> str:
    """``strip_tags`` that never raises. Django refuses input crafted to make
    it slow; a member can type that, and one post must not fail a listing or
    stop an account's erasure. What it refuses is returned as it is: like the
    stripped text, it is plain text that consumers escape."""
    try:
        return strip_tags(value)
    except SuspiciousOperation:
        return value
