"""
Management command to optimize the species database for better performance.

This command:
1. Populates common species from APIs
2. Warms the cache for frequently identified species
3. Updates species metadata and confidence scores
4. Removes duplicate or low-quality entries
"""

import logging
from typing import Dict, List, Sequence

from apps.blog.models import BlogPostPage
from apps.garden_calendar.models import Plant as GardenPlant
from apps.plant_identification.exceptions import RateLimitExceeded
from apps.plant_identification.models import (
    PlantDiseaseDatabase,
    PlantDiseaseRequest,
    PlantIdentificationResult,
    PlantSpecies,
    SavedCareInstructions,
    UserPlant,
)
from apps.plant_identification.services.species_lookup_service import (
    SpeciesLookupService,
)
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction
from django.db.models import Count, F
from django.db.models.fields.reverse_related import ManyToManyRel
from django.db.models.functions import Lower

logger = logging.getLogger(__name__)

# Every reference to a PlantSpecies row, moved onto the kept row before a
# duplicate is deleted. The FKs are all SET_NULL, so deleting without moving
# would silently unlink users' plants, garden plants and disease requests.
SPECIES_FK_REFERENCES = (
    (PlantIdentificationResult, "identified_species"),
    (UserPlant, "species"),
    (PlantDiseaseRequest, "plant_species"),
    (SavedCareInstructions, "plant_species"),
    (GardenPlant, "plant_species"),
)
# (through model, its FK to the owning model). Blog pages: only the live links
# move; stored page revisions keep the old id.
SPECIES_M2M_REFERENCES = (
    (PlantDiseaseDatabase.affected_plants.through, "plantdiseasedatabase"),
    (BlogPostPage.related_plant_species.through, "blogpostpage"),
)


class Command(BaseCommand):
    help = "Optimize the species database and cache for better performance"

    def add_arguments(self, parser):
        parser.add_argument(
            "--populate-common",
            action="store_true",
            help="Populate database with common plant species",
        )
        parser.add_argument(
            "--warm-cache",
            action="store_true",
            help="Warm cache with popular species data",
        )
        parser.add_argument(
            "--update-metadata",
            action="store_true",
            help="Update species metadata and confidence scores",
        )
        parser.add_argument(
            "--cleanup-duplicates",
            action="store_true",
            help="Remove duplicate or low-quality species entries",
        )
        parser.add_argument(
            "--all", action="store_true", help="Run all optimization tasks"
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=20,
            help="Batch size for API calls (default: 20)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without making changes",
        )

    def handle(self, *args, **options):
        """Execute the optimization tasks."""
        self.dry_run = options["dry_run"]
        self.batch_size = options["batch_size"]

        if self.dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No changes will be made")
            )

        try:
            # Initialize services
            self.lookup_service = SpeciesLookupService()

            # Determine which tasks to run
            tasks = []
            if options["all"]:
                tasks = ["cleanup", "metadata", "populate", "cache"]
            else:
                if options["cleanup_duplicates"]:
                    tasks.append("cleanup")
                if options["update_metadata"]:
                    tasks.append("metadata")
                if options["populate_common"]:
                    tasks.append("populate")
                if options["warm_cache"]:
                    tasks.append("cache")

            if not tasks:
                raise CommandError(
                    "No tasks specified. Use --all or specify individual tasks."
                )

            # Execute tasks in optimal order
            for task in tasks:
                self.stdout.write(f"\n{'='*50}")
                getattr(self, f"_run_{task}_task")()

            # Final summary
            self._show_final_summary()

        except Exception as e:
            raise CommandError(f"Optimization failed: {str(e)}") from e

    def _run_cleanup_task(self):
        """Merge species rows whose scientific names differ only in case."""
        self.stdout.write(self.style.SUCCESS("TASK: Cleaning up duplicate species"))

        # One key for grouping and membership: Lower() both times (iexact
        # compiles to UPPER(), which can disagree on non-ASCII names).
        keyed = PlantSpecies.objects.annotate(name_key=Lower("scientific_name"))
        duplicate_keys = [
            row["name_key"]
            for row in keyed.values("name_key")
            .annotate(count=Count("id"))
            .filter(count__gt=1)
        ]

        removed_count = 0
        for key in duplicate_keys:
            group = list(
                keyed.filter(name_key=key).order_by(
                    "-identification_count", "-confidence_score", "created_at"
                )
            )
            best, duplicates = group[0], group[1:]
            dup_ids = [species.pk for species in duplicates]
            self.stdout.write(
                f"Merging {len(duplicates)} duplicates into {best.scientific_name}: "
                f"{self._species_references(dup_ids) or 'no references'}"
            )
            if self.dry_run:
                continue
            try:
                with transaction.atomic():
                    self._merge_species(best, duplicates)
            except IntegrityError as e:
                # e.g. one user holds both variants under the same nickname in
                # one collection (UserPlant unique_together). Left for a human.
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipped {best.scientific_name}: merging would break a "
                        f"uniqueness rule ({self._constraint_name(e)}); resolve by hand"
                    )
                )
                continue
            removed_count += len(duplicates)

        self.stdout.write(
            self.style.SUCCESS(f"Removed {removed_count} duplicate species")
        )

    @staticmethod
    def _constraint_name(error: IntegrityError) -> str:
        diag = getattr(error.__cause__, "diag", None)
        return getattr(diag, "constraint_name", None) or type(error).__name__

    def _species_references(self, species_ids: List[int]) -> Dict[str, int]:
        """Count the rows of every relation that point at these species."""
        counts: Dict[str, int] = {}
        for rel in PlantSpecies._meta.related_objects:
            owner = rel.field.model  # the model that declares the relation
            if isinstance(rel, ManyToManyRel):
                through = rel.through
                if through is None:  # set for every M2M once the app registry loads
                    raise CommandError(
                        f"{owner._meta.label}: M2M without a through model"
                    )
                lookup = f"{rel.field.m2m_reverse_field_name()}__in"
                count = through._base_manager.filter(**{lookup: species_ids}).count()
            else:
                count = owner._base_manager.filter(
                    **{f"{rel.field.name}__in": species_ids}
                ).count()
            if count:
                counts[f"{owner._meta.label}.{rel.field.name}"] = count
        return counts

    def _merge_species(
        self, best: PlantSpecies, duplicates: Sequence[PlantSpecies]
    ) -> None:
        """Move every reference onto ``best``, then delete ``duplicates``."""
        dup_ids = [species.pk for species in duplicates]
        for model, field in SPECIES_FK_REFERENCES:
            model._base_manager.filter(**{f"{field}__in": dup_ids}).update(
                **{field: best}
            )
        for through, owner in SPECIES_M2M_REFERENCES:
            owner_id = f"{owner}_id"
            owners = set(
                through._base_manager.filter(plantspecies__in=dup_ids).values_list(
                    owner_id, flat=True
                )
            )
            through._base_manager.filter(plantspecies__in=dup_ids).delete()
            already = set(
                through._base_manager.filter(
                    plantspecies=best, **{f"{owner_id}__in": owners}
                ).values_list(owner_id, flat=True)
            )
            through._base_manager.bulk_create(
                [
                    through(**{owner_id: o, "plantspecies": best})
                    for o in owners - already
                ]
            )
        tags = {tag for species in duplicates for tag in species.tags.all()}
        if tags:
            best.tags.add(*tags)
        PlantSpecies.objects.filter(pk=best.pk).update(
            identification_count=F("identification_count")
            + sum(species.identification_count for species in duplicates)
        )

        # A relation added to PlantSpecies without a rule above would be
        # nulled or cascaded by the delete; refuse instead.
        leftover = self._species_references(dup_ids)
        if leftover:
            raise CommandError(
                f"Unmerged references to duplicate species: {leftover}; add them to "
                "SPECIES_FK_REFERENCES / SPECIES_M2M_REFERENCES"
            )
        PlantSpecies.objects.filter(pk__in=dup_ids).delete()

    def _run_metadata_task(self):
        """Update species metadata and confidence scores."""
        self.stdout.write(self.style.SUCCESS("TASK: Updating species metadata"))

        # Update identification counts based on actual results
        species_with_results = PlantSpecies.objects.filter(
            identification_results__isnull=False
        ).distinct()

        updated_count = 0
        for species in species_with_results:
            actual_count = species.identification_results.count()
            from django.db.models import Max

            max_confidence = (
                species.identification_results.aggregate(
                    max_conf=Max("confidence_score")
                )["max_conf"]
                or 0.0
            )

            if (
                species.identification_count != actual_count
                or (species.confidence_score or 0) < max_confidence
            ):

                if not self.dry_run:
                    species.identification_count = actual_count
                    species.confidence_score = max_confidence
                    species.save()

                updated_count += 1
                self.stdout.write(
                    f"Updated {species.scientific_name}: {actual_count} IDs, "
                    f"confidence {max_confidence:.2f}"
                )

        self.stdout.write(
            self.style.SUCCESS(f"Updated metadata for {updated_count} species")
        )

    def _run_populate_task(self):
        """Populate database with common plant species."""
        self.stdout.write(self.style.SUCCESS("TASK: Populating common species"))

        # List of common plant species to populate
        common_species = [
            "Rosa damascena",  # Damascus Rose
            "Lavandula angustifolia",  # English Lavender
            "Rosmarinus officinalis",  # Rosemary
            "Mentha spicata",  # Spearmint
            "Thymus vulgaris",  # Common Thyme
            "Basil ocimum",  # Sweet Basil
            "Aloe vera",  # Aloe Vera
            "Ficus benjamina",  # Weeping Fig
            "Monstera deliciosa",  # Swiss Cheese Plant
            "Pothos aureus",  # Golden Pothos
            "Sansevieria trifasciata",  # Snake Plant
            "Chlorophytum comosum",  # Spider Plant
            "Hedera helix",  # English Ivy
            "Tradescantia zebrina",  # Inch Plant
            "Epipremnum aureum",  # Devil's Ivy
            "Philodendron scandens",  # Heartleaf Philodendron
            "Dracaena fragrans",  # Corn Plant
            "Spathiphyllum wallisii",  # Peace Lily
            "Ficus elastica",  # Rubber Plant
            "Zamioculcas zamiifolia",  # ZZ Plant
        ]

        added_count = 0
        for scientific_name in common_species:
            try:
                # Check if already exists
                existing = PlantSpecies.objects.filter(
                    scientific_name__iexact=scientific_name
                ).first()

                if existing:
                    self.stdout.write(f"Species already exists: {scientific_name}")
                    continue

                # Try to get data from API
                if self.lookup_service._can_call_api():
                    api_data = self.lookup_service._fetch_from_api(scientific_name)
                    if api_data and not self.dry_run:
                        # Create species from API data
                        species = PlantSpecies.objects.create(
                            scientific_name=api_data["scientific_name"],
                            common_names=api_data.get("common_names", ""),
                            family=api_data.get("family", ""),
                            genus=api_data.get("genus", ""),
                            plant_type=api_data.get("plant_type", ""),
                            light_requirements=api_data.get("light_requirements", ""),
                            water_requirements=api_data.get("water_requirements", ""),
                            trefle_id=api_data.get("trefle_id", ""),
                            confidence_score=0.6,
                            api_source="trefle",
                            auto_stored=True,
                        )
                        added_count += 1
                        self.stdout.write(f"Added: {species.scientific_name}")
                    else:
                        self.stdout.write(f"No API data found for: {scientific_name}")
                else:
                    self.stdout.write("Cannot fetch from API - rate limited")
                    break

            except RateLimitExceeded:
                self.stdout.write(
                    self.style.WARNING("Rate limit hit during population")
                )
                break
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error processing {scientific_name}: {e}")
                )

        self.stdout.write(self.style.SUCCESS(f"Added {added_count} new species"))

    def _run_cache_task(self):
        """Warm cache with popular species data."""
        self.stdout.write(self.style.SUCCESS("TASK: Warming species cache"))

        if not self.dry_run:
            self.lookup_service.warm_cache_for_popular_species()

        # Show cache statistics
        stats = self.lookup_service.get_lookup_stats()
        self.stdout.write(
            f"Popular species in database: {stats['popular_species_count']}"
        )
        self.stdout.write(f"API available: {stats['api_available']}")

        if stats["rate_limited"]:
            self.stdout.write(
                self.style.WARNING("Currently rate limited - cache warming skipped")
            )

    def _show_final_summary(self):
        """Show final statistics and recommendations."""
        self.stdout.write(f"\n{'='*50}")
        self.stdout.write(self.style.SUCCESS("OPTIMIZATION COMPLETE"))
        self.stdout.write(f"{'='*50}")

        # Get current statistics
        stats = self.lookup_service.get_lookup_stats()

        self.stdout.write(f"Total species in database: {stats['local_species_count']}")
        self.stdout.write(f"Expert-verified species: {stats['verified_species_count']}")
        self.stdout.write(f"Popular species (≥5 IDs): {stats['popular_species_count']}")
        self.stdout.write(f"API currently available: {stats['api_available']}")

        # Performance recommendations
        self.stdout.write("\nPerformance Recommendations:")

        if stats["popular_species_count"] < 50:
            self.stdout.write(
                "• Consider running identification requests to build popular species data"
            )

        if not stats["api_available"]:
            self.stdout.write(
                "• API is rate limited - local database will be used for lookups"
            )

        coverage_ratio = stats["popular_species_count"] / max(
            stats["local_species_count"], 1
        )
        if coverage_ratio < 0.3:
            self.stdout.write(
                "• Consider populating more common species to improve coverage"
            )

        self.stdout.write("\nNext steps:")
        self.stdout.write("• Monitor API usage patterns")
        self.stdout.write("• Run this command periodically to maintain optimization")
        self.stdout.write("• Consider adding expert verification for popular species")
