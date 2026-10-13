"""classify_send_error (todo 619, PR #1128 review): only a refusal of this
message or its recipient is PERMANENT. A 5xx about the SMTP session (auth,
sender, HELO) is a relay credential or config fault, so it is TRANSIENT and
the outbox retries it rather than failing every queued row for good."""

import smtplib

import pytest
from apps.core.services.email_service import EmailOutcome, classify_send_error

PERMANENT = [
    smtplib.SMTPRecipientsRefused({"a@x.test": (550, b"no such user")}),
    smtplib.SMTPDataError(554, b"message rejected"),
]
TRANSIENT = [
    smtplib.SMTPAuthenticationError(535, b"bad credentials"),
    smtplib.SMTPAuthenticationError(530, b"authentication required"),
    smtplib.SMTPSenderRefused(550, b"sender refused", "noreply@x.test"),
    smtplib.SMTPHeloError(501, b"bad helo"),
    smtplib.SMTPResponseException(552, b"quota exceeded"),
    smtplib.SMTPRecipientsRefused(
        {"a@x.test": (550, b"no such user"), "b@x.test": (451, b"try later")}
    ),
    smtplib.SMTPDataError(451, b"try later"),
    smtplib.SMTPServerDisconnected("dropped"),
    TimeoutError("timed out"),
]


@pytest.mark.parametrize("exc", PERMANENT, ids=lambda e: type(e).__name__)
def test_a_refusal_of_the_message_or_recipient_is_permanent(exc):
    assert classify_send_error(exc) == EmailOutcome.PERMANENT


@pytest.mark.parametrize("exc", TRANSIENT, ids=lambda e: type(e).__name__)
def test_a_session_or_connection_fault_is_transient(exc):
    assert classify_send_error(exc) == EmailOutcome.TRANSIENT
