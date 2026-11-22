"""Template context helpers.

``email_sender`` is the one place email templates get the sender identity
(todo 703): the operator's name and postal address, which CASL s. 6(2) with
SOR/2012-36 s. 2(1)(d) and CAN-SPAM 15 U.S.C. 7704(a)(5)(A)(iii) require on
commercial email. It is a context processor for templates rendered with a
request, and the ``email_sender`` template tags call it for the rest: most
email is rendered by a bare ``render_to_string`` with no request, where no
context processor runs.
"""

from django.conf import settings


def email_sender(request=None) -> dict[str, str]:
    """``EMAIL_SENDER_NAME`` and ``EMAIL_SENDER_ADDRESS``, read now.

    Read at call time, not import time, so ``override_settings`` and a
    changed environment both apply. Blank values stay blank: the footer then
    prints no sender line rather than a placeholder.
    """
    return {
        "email_sender_name": (getattr(settings, "EMAIL_SENDER_NAME", "") or "").strip(),
        "email_sender_address": (
            getattr(settings, "EMAIL_SENDER_ADDRESS", "") or ""
        ).strip(),
    }
