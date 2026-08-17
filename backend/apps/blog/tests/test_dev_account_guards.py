"""Tests guarding against dev-account creation paths reaching production.

Covers the fix for the audit finding that `migrate` (via blog migration 0004)
could mint a superuser with a hardcoded password. The sibling finding — that
`create_demo_blog_posts` created a staff account with a known password — is
moot: that command was retired (Canopy PR 3, spec §5) in favor of
`seed_demo_blog`, which never creates a known-credential account.
"""

from apps.plant_identification.models import PlantCareGuide, PlantSpecies
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

User = get_user_model()


class MigrateCareGuidesCommandTests(TestCase):
    @override_settings(DEBUG=False)
    def test_refuses_to_run_when_debug_false(self):
        with self.assertRaises(CommandError):
            call_command("migrate_care_guides_to_blog")

    @override_settings(DEBUG=True)
    def test_never_creates_author_account(self):
        species = PlantSpecies.objects.create(scientific_name="Epipremnum aureum")
        PlantCareGuide.objects.create(
            plant_species=species, quick_care_summary="Water weekly."
        )
        with self.assertRaises(CommandError):
            call_command("migrate_care_guides_to_blog")
        self.assertEqual(User.objects.filter(username="plant_care_admin").count(), 0)
        self.assertEqual(
            User.objects.filter(email="admin@plantcommunity.com").count(), 0
        )
