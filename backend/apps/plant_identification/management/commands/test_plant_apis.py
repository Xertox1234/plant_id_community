"""
Management command to test plant identification API integrations.
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from apps.plant_identification.services import (
    TrefleAPIService, PlantNetAPIService, PlantIdentificationService
)


class Command(BaseCommand):
    help = 'Test plant identification API integrations'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--service',
            type=str,
            choices=['trefle', 'plantnet', 'combined', 'all'],
            default='all',
            help='Which service to test'
        )
        
        parser.add_argument(
            '--query',
            type=str,
            default='Rosa damascena',
            help='Plant name to search for (for Trefle)'
        )
    
    def handle(self, *args, **options):
        service = options['service']
        query = options['query']
        
        self.stdout.write(
            self.style.SUCCESS(f'Testing plant identification APIs...')
        )
        
        if service in ['trefle', 'all']:
            self.test_trefle(query)
        
        if service in ['plantnet', 'all']:
            self.test_plantnet()
        
        if service in ['combined', 'all']:
            self.test_combined_service()
    
    def test_trefle(self, query):
        """Test Trefle API service."""
        self.stdout.write('\n' + '='*50)
        self.stdout.write('Testing Trefle API Service')
        self.stdout.write('='*50)
        
        try:
            trefle = TrefleAPIService()
            
            # Test service status
            status = trefle.get_service_status()
            self.stdout.write(f"Service Status: {status}")
            
            if status['status'] != 'available':
                self.stdout.write(
                    self.style.ERROR('Trefle API not available - check API key')
                )
                return
            
            # Test plant search
            self.stdout.write(f"\nSearching for: {query}")
            plants = trefle.search_plants(query, limit=3)
            
            if plants:
                self.stdout.write(f"Found {len(plants)} plants:")
                for i, plant in enumerate(plants, 1):
                    self.stdout.write(f"{i}. {plant.get('scientific_name', 'Unknown')}")
                    self.stdout.write(f"   Common names: {plant.get('common_names', {}).get('en', [])}")
                    
                # Test detailed plant info
                first_plant = plants[0]
                plant_id = first_plant.get('id')
                if plant_id:
                    details = trefle.get_plant_details(plant_id)
                    if details:
                        self.stdout.write(f"\nDetailed info for {first_plant.get('scientific_name')}:")
                        main_species = details.get('main_species', {})
                        self.stdout.write(f"Family: {main_species.get('family', 'Unknown')}")
                        self.stdout.write(f"Genus: {main_species.get('genus', 'Unknown')}")
            else:
                self.stdout.write("No plants found")
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Trefle API test failed: {str(e)}')
            )
    
    def test_plantnet(self):
        """Test PlantNet API service."""
        self.stdout.write('\n' + '='*50)
        self.stdout.write('Testing PlantNet API Service')
        self.stdout.write('='*50)
        
        try:
            plantnet = PlantNetAPIService()
            
            # Test service status
            status = plantnet.get_service_status()
            self.stdout.write(f"Service Status: {status}")
            
            if status['status'] != 'available':
                self.stdout.write(
                    self.style.ERROR('PlantNet API not available - check API key')
                )
                return
            
            # Test available projects
            projects = plantnet.get_available_projects()
            if projects:
                self.stdout.write(f"\nAvailable projects ({len(projects)}):")
                for project in projects[:3]:  # Show first 3
                    self.stdout.write(f"- {project['region']}: {project['name']}")
                    self.stdout.write(f"  Species: {project['species_count']}, Images: {project['image_count']}")
            
            self.stdout.write(
                self.style.WARNING(
                    '\nNote: Full PlantNet testing requires plant images. '
                    'Use the Django admin or API endpoints to test image identification.'
                )
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'PlantNet API test failed: {str(e)}')
            )
    
    def test_combined_service(self):
        """Test combined plant identification service."""
        self.stdout.write('\n' + '='*50)
        self.stdout.write('Testing Combined Plant Identification Service')
        self.stdout.write('='*50)
        
        try:
            service = PlantIdentificationService()
            
            # Test service status
            status = service.get_service_status()
            self.stdout.write("Combined Service Status:")
            for service_name, service_status in status.items():
                status_text = service_status.get('status', 'unknown')
                if status_text == 'available':
                    self.stdout.write(f"  {service_name}: " + self.style.SUCCESS('✓ Available'))
                else:
                    self.stdout.write(f"  {service_name}: " + self.style.ERROR('✗ Not Available'))
            
            # Check if any service is available
            if status['combined_service']['available']:
                self.stdout.write(
                    self.style.SUCCESS('\n✓ Plant identification service is ready!')
                )
            else:
                self.stdout.write(
                    self.style.ERROR('\n✗ No plant identification APIs are available')
                )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Combined service test failed: {str(e)}')
            )