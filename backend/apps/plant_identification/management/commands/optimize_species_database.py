"""
Management command to optimize the species database for better performance.

This command:
1. Populates common species from APIs 
2. Warms the cache for frequently identified species
3. Updates species metadata and confidence scores
4. Removes duplicate or low-quality entries
"""

import logging
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, models
from django.db.models import F
from django.core.cache import cache
from django.conf import settings

from apps.plant_identification.models import PlantSpecies, PlantIdentificationResult
from apps.plant_identification.services.species_lookup_service import SpeciesLookupService
from apps.plant_identification.services.trefle_service import TrefleAPIService
from apps.plant_identification.exceptions import RateLimitExceeded

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Optimize the species database and cache for better performance'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--populate-common',
            action='store_true',
            help='Populate database with common plant species'
        )
        parser.add_argument(
            '--warm-cache',
            action='store_true',
            help='Warm cache with popular species data'
        )
        parser.add_argument(
            '--update-metadata',
            action='store_true',
            help='Update species metadata and confidence scores'
        )
        parser.add_argument(
            '--cleanup-duplicates',
            action='store_true',
            help='Remove duplicate or low-quality species entries'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Run all optimization tasks'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=20,
            help='Batch size for API calls (default: 20)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes'
        )
    
    def handle(self, *args, **options):
        """Execute the optimization tasks."""
        self.dry_run = options['dry_run']
        self.batch_size = options['batch_size']
        
        if self.dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No changes will be made')
            )
        
        try:
            # Initialize services
            self.lookup_service = SpeciesLookupService()
            
            # Determine which tasks to run
            tasks = []
            if options['all']:
                tasks = ['cleanup', 'metadata', 'populate', 'cache']
            else:
                if options['cleanup_duplicates']:
                    tasks.append('cleanup')
                if options['update_metadata']:
                    tasks.append('metadata')
                if options['populate_common']:
                    tasks.append('populate')
                if options['warm_cache']:
                    tasks.append('cache')
            
            if not tasks:
                raise CommandError(
                    'No tasks specified. Use --all or specify individual tasks.'
                )
            
            # Execute tasks in optimal order
            for task in tasks:
                self.stdout.write(f"\n{'='*50}")
                getattr(self, f'_run_{task}_task')()
            
            # Final summary
            self._show_final_summary()
            
        except Exception as e:
            raise CommandError(f'Optimization failed: {str(e)}')
    
    def _run_cleanup_task(self):
        """Remove duplicate and low-quality species entries."""
        self.stdout.write(
            self.style.SUCCESS('TASK: Cleaning up duplicate species')
        )
        
        # Find potential duplicates (same scientific name with different cases)
        from django.db.models import Count
        
        duplicates = PlantSpecies.objects.values('scientific_name__iexact').annotate(
            count=Count('scientific_name__iexact')
        ).filter(count__gt=1)
        
        removed_count = 0
        for dup in duplicates:
            # Get all species with this scientific name
            similar_species = PlantSpecies.objects.filter(
                scientific_name__iexact=dup['scientific_name__iexact']
            ).order_by('-identification_count', '-confidence_score', 'created_at')
            
            # Keep the best one, remove others
            best_species = similar_species.first()
            to_remove = similar_species.exclude(id=best_species.id)
            
            if to_remove.exists():
                self.stdout.write(
                    f"Merging {to_remove.count()} duplicates into {best_species.scientific_name}"
                )
                
                if not self.dry_run:
                    # Merge identification results to the best species
                    PlantIdentificationResult.objects.filter(
                        identified_species__in=to_remove
                    ).update(identified_species=best_species)
                    
                    # Update best species counts atomically
                    count_to_add = sum(s.identification_count for s in to_remove)
                    PlantSpecies.objects.filter(id=best_species.id).update(
                        identification_count=F('identification_count') + count_to_add
                    )
                    best_species.refresh_from_db()
                    
                    # Remove duplicates
                    removed_count += to_remove.count()
                    to_remove.delete()
        
        self.stdout.write(
            self.style.SUCCESS(f'Removed {removed_count} duplicate species')
        )
    
    def _run_metadata_task(self):
        """Update species metadata and confidence scores."""
        self.stdout.write(
            self.style.SUCCESS('TASK: Updating species metadata')
        )
        
        # Update identification counts based on actual results
        species_with_results = PlantSpecies.objects.filter(
            identification_results__isnull=False
        ).distinct()
        
        updated_count = 0
        for species in species_with_results:
            actual_count = species.identification_results.count()
            from django.db.models import Max
            max_confidence = species.identification_results.aggregate(
                max_conf=Max('confidence_score')
            )['max_conf'] or 0.0
            
            if species.identification_count != actual_count or \
               (species.confidence_score or 0) < max_confidence:
                
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
            self.style.SUCCESS(f'Updated metadata for {updated_count} species')
        )
    
    def _run_populate_task(self):
        """Populate database with common plant species."""
        self.stdout.write(
            self.style.SUCCESS('TASK: Populating common species')
        )
        
        # List of common plant species to populate
        common_species = [
            'Rosa damascena',      # Damascus Rose
            'Lavandula angustifolia',  # English Lavender
            'Rosmarinus officinalis',  # Rosemary
            'Mentha spicata',      # Spearmint
            'Thymus vulgaris',     # Common Thyme
            'Basil ocimum',        # Sweet Basil
            'Aloe vera',           # Aloe Vera
            'Ficus benjamina',     # Weeping Fig
            'Monstera deliciosa',  # Swiss Cheese Plant
            'Pothos aureus',       # Golden Pothos
            'Sansevieria trifasciata',  # Snake Plant
            'Chlorophytum comosum',     # Spider Plant
            'Hedera helix',        # English Ivy
            'Tradescantia zebrina',     # Inch Plant
            'Epipremnum aureum',   # Devil's Ivy
            'Philodendron scandens',    # Heartleaf Philodendron
            'Dracaena fragrans',   # Corn Plant
            'Spathiphyllum wallisii',   # Peace Lily
            'Ficus elastica',      # Rubber Plant
            'Zamioculcas zamiifolia',   # ZZ Plant
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
                            scientific_name=api_data['scientific_name'],
                            common_names=api_data.get('common_names', ''),
                            family=api_data.get('family', ''),
                            genus=api_data.get('genus', ''),
                            plant_type=api_data.get('plant_type', ''),
                            light_requirements=api_data.get('light_requirements', ''),
                            water_requirements=api_data.get('water_requirements', ''),
                            trefle_id=api_data.get('trefle_id', ''),
                            confidence_score=0.6,
                            api_source='trefle',
                            auto_stored=True
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
                    self.style.WARNING('Rate limit hit during population')
                )
                break
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error processing {scientific_name}: {e}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'Added {added_count} new species')
        )
    
    def _run_cache_task(self):
        """Warm cache with popular species data."""
        self.stdout.write(
            self.style.SUCCESS('TASK: Warming species cache')
        )
        
        if not self.dry_run:
            self.lookup_service.warm_cache_for_popular_species()
        
        # Show cache statistics
        stats = self.lookup_service.get_lookup_stats()
        self.stdout.write(f"Popular species in database: {stats['popular_species_count']}")
        self.stdout.write(f"API available: {stats['api_available']}")
        
        if stats['rate_limited']:
            self.stdout.write(
                self.style.WARNING('Currently rate limited - cache warming skipped')
            )
    
    def _show_final_summary(self):
        """Show final statistics and recommendations."""
        self.stdout.write(f"\n{'='*50}")
        self.stdout.write(self.style.SUCCESS('OPTIMIZATION COMPLETE'))
        self.stdout.write(f"{'='*50}")
        
        # Get current statistics
        stats = self.lookup_service.get_lookup_stats()
        
        self.stdout.write(f"Total species in database: {stats['local_species_count']}")
        self.stdout.write(f"Expert-verified species: {stats['verified_species_count']}")
        self.stdout.write(f"Popular species (≥5 IDs): {stats['popular_species_count']}")
        self.stdout.write(f"API currently available: {stats['api_available']}")
        
        # Performance recommendations
        self.stdout.write("\nPerformance Recommendations:")
        
        if stats['popular_species_count'] < 50:
            self.stdout.write(
                "• Consider running identification requests to build popular species data"
            )
        
        if not stats['api_available']:
            self.stdout.write(
                "• API is rate limited - local database will be used for lookups"
            )
        
        coverage_ratio = stats['popular_species_count'] / max(stats['local_species_count'], 1)
        if coverage_ratio < 0.3:
            self.stdout.write(
                "• Consider populating more common species to improve coverage"
            )
        
        self.stdout.write("\nNext steps:")
        self.stdout.write("• Monitor API usage patterns")
        self.stdout.write("• Run this command periodically to maintain optimization")
        self.stdout.write("• Consider adding expert verification for popular species")