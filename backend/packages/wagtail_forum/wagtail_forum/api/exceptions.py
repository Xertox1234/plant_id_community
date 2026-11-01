"""APIException subclasses so every error path flows through the DRF exception
handler (one consistent error envelope per response, audit M9).

Hand-built ``Response({"detail": ...}, status=...)`` returns bypass the
handler, so a single endpoint would emit two different error shapes depending
on which branch failed.

The envelope contract is documented in ``README.md`` ("Error envelope"). The
package ships a reference handler at
``wagtail_forum.api.exception_handler.forum_exception_handler`` (audit M39); a
host registers it or provides a compatible one (the plant_id host uses
``apps.core.exceptions.custom_exception_handler``).
"""

from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import APIException


class Conflict(APIException):
    status_code = 409
    default_detail = _("Conflict.")
    default_code = "conflict"


class UnprocessableEntity(APIException):
    status_code = 422
    default_detail = _("Unprocessable request.")
    default_code = "unprocessable"


class ForumLocked(APIException):
    """A password forum this session has not unlocked (todo 680)."""

    status_code = 403
    default_detail = _("This forum needs a password.")
    default_code = "forum_locked"


class ForumClosed(APIException):
    """A closed forum (todo 669): no new topics or replies. Staff and the
    forum's moderators are exempt."""

    status_code = 403
    default_detail = _("This forum is closed to new topics and replies.")
    default_code = "forum_closed"


class ForumPostDenied(APIException):
    """The caller lacks ``post`` on this forum (todo 677)."""

    status_code = 403
    default_detail = _("You cannot start topics in this forum.")
    default_code = "forum_post_denied"


class ForumReplyDenied(APIException):
    """The caller lacks ``reply`` on this forum (todo 677)."""

    status_code = 403
    default_detail = _("You cannot reply in this forum.")
    default_code = "forum_reply_denied"


class ForumPollDenied(APIException):
    """The caller lacks ``poll`` on this forum (todo 677)."""

    status_code = 403
    default_detail = _("You cannot add a poll in this forum.")
    default_code = "forum_poll_denied"


class ForumAttachDenied(APIException):
    """The caller lacks ``attach`` on this forum (todo 677): an image upload
    naming the forum, or an image block in a post body."""

    status_code = 403
    default_detail = _("You cannot attach images in this forum.")
    default_code = "forum_attach_denied"
