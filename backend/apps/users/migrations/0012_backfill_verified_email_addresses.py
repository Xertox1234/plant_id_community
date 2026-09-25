"""Backfill allauth ``EmailAddress`` rows for existing users (todo 446).

Sign-in paths now match an existing account by email only when that account's
email is verified (``apps/users/email_verification.py``). Accounts created
before this carry no row, so every returning Google/Firebase user would be
refused. A user's email counts as verified when a provider proved it:

- ``firebase_uid`` is set (the Firebase exchange rejects unverified emails);
- a ``SocialAccount`` row exists (allauth);
- the password is unusable (``!…``): the custom OAuth flow creates users with
  ``create_user(password=None)`` from a provider-verified email.

Anything else is a password registration that never proved ownership, and
stays unverified (it can verify through the emailed link). Never downgrades an
existing verified row, and never verifies an address another user already
holds verified (the DB allows one).
"""

from django.db import migrations

UNUSABLE_PASSWORD_PREFIX = "!"  # django.contrib.auth.hashers


def backfill(apps, schema_editor):
    User = apps.get_model("users", "User")
    EmailAddress = apps.get_model("account", "EmailAddress")
    SocialAccount = apps.get_model("socialaccount", "SocialAccount")

    social_user_ids = set(SocialAccount.objects.values_list("user_id", flat=True))
    for user in User.objects.exclude(email="").iterator():
        provider_verified = (
            bool(user.firebase_uid)
            or user.pk in social_user_ids
            or (user.password or "").startswith(UNUSABLE_PASSWORD_PREFIX)
        )
        address = EmailAddress.objects.filter(
            user=user, email__iexact=user.email
        ).first()
        if address is None:
            address = EmailAddress.objects.create(
                user=user,
                email=user.email,
                verified=False,
                primary=not EmailAddress.objects.filter(
                    user=user, primary=True
                ).exists(),
            )
        if (
            provider_verified
            and not address.verified
            and not EmailAddress.objects.filter(
                email__iexact=user.email, verified=True
            ).exists()
        ):
            address.verified = True
            address.save(update_fields=["verified"])


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0011_username_upper_pattern_index"),
        ("account", "0009_emailaddress_unique_primary_email"),
        ("socialaccount", "0006_alter_socialaccount_extra_data"),
    ]

    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
