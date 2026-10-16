"""classify_send_error (todo 619, PR #1128 review): only a refusal of this
message or its recipient is PERMANENT. A 5xx about the SMTP session (auth,
sender, HELO) is a relay credential or config fault, so it is TRANSIENT and
the outbox retries it rather than failing every queued row for good.

Todo 652: the same holds when the relay answers at RCPT or DATA instead of
at AUTH. A 5.7.x (security or policy) reply or a bare 554 is about our relay
or account (``554 relay denied`` with blank credentials, ``554 Message
rejected: Sending paused`` from a paused account), so it is TRANSIENT."""

import smtplib

import pytest
from apps.core.services.email_service import EmailOutcome, classify_send_error

PERMANENT = [
    smtplib.SMTPRecipientsRefused({"a@x.test": (550, b"no such user")}),
    smtplib.SMTPRecipientsRefused({"a@x.test": (550, b"5.1.1 user unknown")}),
    smtplib.SMTPRecipientsRefused({"a@x.test": (554, b"5.1.1 user unknown")}),
    smtplib.SMTPRecipientsRefused({"a@x.test": (552, b"5.2.2 mailbox full")}),
    smtplib.SMTPDataError(552, b"message too large"),
    smtplib.SMTPDataError(554, b"5.6.0 content rejected"),
    smtplib.SMTPDataError(550, "5.3.4 message too big"),
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
    # Todo 652: refusals about our relay or account, at RCPT or at DATA.
    smtplib.SMTPRecipientsRefused({"a@x.test": (554, b"5.7.1 relay denied")}),
    smtplib.SMTPRecipientsRefused({"a@x.test": (550, b"5.7.1 relay denied")}),
    smtplib.SMTPRecipientsRefused({"a@x.test": (554, b"relay access denied")}),
    smtplib.SMTPDataError(554, b"Message rejected: Sending paused for this account"),
    smtplib.SMTPDataError(554, b"message rejected"),
    smtplib.SMTPDataError(550, b"5.7.0 account suspended"),
    smtplib.SMTPServerDisconnected("dropped"),
    TimeoutError("timed out"),
]


@pytest.mark.parametrize("exc", PERMANENT, ids=lambda e: type(e).__name__)
def test_a_refusal_of_the_message_or_recipient_is_permanent(exc):
    assert classify_send_error(exc) == EmailOutcome.PERMANENT


@pytest.mark.parametrize("exc", TRANSIENT, ids=lambda e: type(e).__name__)
def test_a_session_or_connection_fault_is_transient(exc):
    assert classify_send_error(exc) == EmailOutcome.TRANSIENT
