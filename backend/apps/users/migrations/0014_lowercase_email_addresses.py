"""Lowercase allauth ``EmailAddress.email`` (todo 447 item 4).

``email_verification._address_for`` and migration 0012 stored ``user.email``
as typed. allauth stores and compares lowercase, and its
``unique_verified_email`` constraint is case-sensitive, so ``Alice@x`` and
``alice@x`` could both be verified on different accounts.

A row is skipped, not changed, when lowercasing it would collide:

- the same account already has the lowercase row (``unique_together``);
- the row is verified and another account holds the lowercase form verified
  (``unique_verified_email``).

Nothing is resolved by guessing which account owns the address: with two
verified case variants, ``get_account_by_email`` finds no single verified
holder and keeps refusing, which is the existing fail-closed behavior.
``User.email`` is left as the user typed it.
"""

import logging

from django.db import IntegrityError, migrations, transaction
from django.db.models import F
from django.db.models.functions import Lower

logger = logging.getLogger(__name__)


def lowercase(apps, schema_editor):
    EmailAddress = apps.get_model("account", "EmailAddress")

    mixed = EmailAddress.objects.annotate(lowered=Lower("email")).exclude(
        email=F("lowered")
    )
    for address in mixed.iterator():
        target = address.email.lower()
        others = EmailAddress.objects.filter(email=target).exclude(pk=address.pk)
        same_account = others.filter(user_id=address.user_id).exists()
        verified_elsewhere = address.verified and others.filter(verified=True).exists()
        if same_account or verified_elsewhere:
            logger.warning(
                "[MIGRATION] EmailAddress %s not lowercased: collides with "
                "an existing row",
                address.pk,
            )
            continue
        try:
            with transaction.atomic():
                EmailAddress.objects.filter(pk=address.pk).update(email=target)
        except IntegrityError:
            logger.warning(
                "[MIGRATION] EmailAddress %s not lowercased: constraint " "violation",
                address.pk,
            )


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0013_user_verification_emails_sent"),
        ("account", "0009_emailaddress_unique_primary_email"),
    ]

    operations = [migrations.RunPython(lowercase, migrations.RunPython.noop)]
