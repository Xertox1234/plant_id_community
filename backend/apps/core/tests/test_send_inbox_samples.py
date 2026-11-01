"""send_inbox_samples (todo 626): one message per live email family, sent only
to the --to addresses, each with an HTML and a text part and no empty link."""

import re

import pytest
from apps.core.management.commands.send_inbox_samples import (
    MAX_RECIPIENTS,
    SUBJECT_PREFIX,
    Command,
)
from django.core import mail
from django.core.management import CommandError, call_command

FAMILIES = list(Command()._families())
TO = "inbox-check@example.com"


@pytest.fixture(autouse=True)
def _site(settings):
    settings.SITE_URL = "https://web.example"
    settings.API_PUBLIC_URL = "https://api.example"


@pytest.mark.django_db
def test_every_family_sends_one_complete_message():
    call_command("send_inbox_samples", "--to", TO)

    assert len(mail.outbox) == len(FAMILIES) == 10
    for message in mail.outbox:
        assert message.to == [TO]
        assert message.subject.startswith(SUBJECT_PREFIX)
        assert message.body.strip(), message.subject
        ((html, mimetype),) = message.alternatives
        assert mimetype == "text/html"
        assert not re.search(r'href="\s*"', html), message.subject
        # Every link is absolute: a relative href is dead in a mail client.
        hrefs = re.findall(r'href="([^"]+)"', html)
        assert hrefs, message.subject
        for href in hrefs:
            assert href.startswith(("https://", "mailto:")), (message.subject, href)


@pytest.mark.django_db
def test_dry_run_sends_nothing():
    call_command("send_inbox_samples", "--to", TO, "--dry-run")
    assert mail.outbox == []


@pytest.mark.django_db
def test_family_filter():
    call_command("send_inbox_samples", "--to", TO, "--family", "forum_digest")
    assert len(mail.outbox) == 1


def test_refuses_too_many_recipients():
    many = [f"t{i}@example.com" for i in range(MAX_RECIPIENTS + 1)]
    with pytest.raises(CommandError):
        call_command("send_inbox_samples", "--to", *many)


def test_refuses_unknown_family():
    with pytest.raises(CommandError):
        call_command("send_inbox_samples", "--to", TO, "--family", "nope")
