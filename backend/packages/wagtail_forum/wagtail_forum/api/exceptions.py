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

from rest_framework.exceptions import APIException


class Conflict(APIException):
    status_code = 409
    default_detail = "Conflict."
    default_code = "conflict"


class UnprocessableEntity(APIException):
    status_code = 422
    default_detail = "Unprocessable request."
    default_code = "unprocessable"
