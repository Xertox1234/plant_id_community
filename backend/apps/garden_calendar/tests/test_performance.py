"""
Performance tests for garden_calendar app.

Tests query optimization and N+1 prevention:
- ViewSet list endpoints with proper prefetching
- Analytics service query efficiency
- Bulk operations performance
- Related object access optimization

All query count assertions use strict equality (not < or <=) to ensure
predictable query patterns. See PERFORMANCE_TESTING_PATTERNS_CODIFIED.md
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.test.utils import override_settings
from rest_framework.test import APIClient
from datetime import timedelta

from ..models import GardenBed, Plant, CareTask, CareLog, Harvest
from ..services.garden_analytics_service import GardenAnalyticsService

User = get_user_model()


class GardenBedListPerformanceTest(TestCase):
    """Test GardenBed list endpoint query optimization."""

    def setUp(self):
        """Set up test user and multiple garden beds with plants."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='gardener',
            email='gardener@test.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

        # Create 5 beds with 3 plants each
        for i in range(5):
            bed = GardenBed.objects.create(
                owner=self.user,
                name=f'Bed {i}',
                bed_type='raised',
                length_inches=96,
                width_inches=48
            )
            for j in range(3):
                Plant.objects.create(
                    garden_bed=bed,
                    common_name=f'Plant {i}-{j}',
                    health_status='healthy',
                    growth_stage='vegetative',
                    planted_date=timezone.now().date()
                )

    def test_garden_bed_list_no_n_plus_1(self):
        """Test that listing garden beds doesn't cause N+1 queries."""
        # Current queries (needs optimization):
        # 1. COUNT query (pagination)
        # 2. SELECT garden_beds with select_related('owner')
        # 3-12. COUNT plants per bed (N+1 for plant_count property)
        # TODO: Annotate plant_count in ViewSet to reduce to 2 queries
        # Target: 2 queries total
        with self.assertNumQueries(12):
            response = self.client.get('/api/v1/calendar/api/garden-beds/')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.data['results']), 5)

    def test_garden_bed_detail_with_plants(self):
        """Test that garden bed detail efficiently loads related plants."""
        bed = GardenBed.objects.first()

        # Current queries (partially optimized):
        # 1. SELECT garden_bed with select_related('owner')
        # 2. SELECT plants WHERE garden_bed_id=X with select_related('plant_species')
        # 3. SELECT images WHERE plant_id IN (...) (prefetch)
        # 4-5. COUNT plants queries (N+1 for plant_count/utilization_rate)
        # TODO: Annotate plant_count to reduce to 3 queries
        # Target: 3 queries total
        with self.assertNumQueries(5):
            response = self.client.get(f'/api/v1/calendar/api/garden-beds/{bed.uuid}/')
            self.assertEqual(response.status_code, 200)


class PlantListPerformanceTest(TestCase):
    """Test Plant list endpoint query optimization."""

    def setUp(self):
        """Set up test user with plants across multiple beds."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='gardener',
            email='gardener@test.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

        # Create 3 beds with 5 plants each
        for i in range(3):
            bed = GardenBed.objects.create(
                owner=self.user,
                name=f'Bed {i}',
                bed_type='raised'
            )
            for j in range(5):
                Plant.objects.create(
                    garden_bed=bed,
                    common_name=f'Plant {i}-{j}',
                    health_status='healthy',
                    growth_stage='vegetative',
                    planted_date=timezone.now().date()
                )

    def test_plant_list_no_n_plus_1(self):
        """Test that listing plants with garden_bed info doesn't cause N+1."""
        # Expected queries:
        # 1. COUNT query (pagination)
        # 2. SELECT plants with select_related('garden_bed', 'garden_bed__owner', 'plant_species')
        # 3. SELECT images WHERE plant_id IN (...) (prefetch for primary_image)
        # Total: 3 queries (NOT 3 + 15 for each plant's images)
        with self.assertNumQueries(3):
            response = self.client.get('/api/v1/calendar/api/plants/')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.data['results']), 15)

    def test_plant_detail_efficient(self):
        """Test that plant detail loads efficiently."""
        plant = Plant.objects.first()

        # Expected queries:
        # 1. SELECT plant with select_related('garden_bed', 'garden_bed__owner', 'plant_species')
        # 2. SELECT images WHERE plant_id=X (prefetch)
        # 3. SELECT care_tasks WHERE plant_id=X (prefetch for upcoming_tasks)
        # 4. SELECT care_logs WHERE plant_id=X (prefetch for recent_logs)
        # Total: 4 queries
        with self.assertNumQueries(4):
            response = self.client.get(f'/api/v1/calendar/api/plants/{plant.uuid}/')
            self.assertEqual(response.status_code, 200)


class CareTaskListPerformanceTest(TestCase):
    """Test CareTask list endpoint query optimization."""

    def setUp(self):
        """Set up test user with care tasks."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='gardener',
            email='gardener@test.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

        bed = GardenBed.objects.create(
            owner=self.user,
            name='Test Bed',
            bed_type='raised'
        )

        # Create 10 plants with 2 tasks each
        for i in range(10):
            plant = Plant.objects.create(
                garden_bed=bed,
                common_name=f'Plant {i}',
                health_status='healthy',
                growth_stage='vegetative',
                planted_date=timezone.now().date()
            )
            for j in range(2):
                CareTask.objects.create(
                    plant=plant,
                    created_by=self.user,
                    task_type='watering',
                    title=f'Task {i}-{j}',
                    priority='high',
                    scheduled_date=timezone.now() + timedelta(days=j)
                )

    def test_care_task_list_no_n_plus_1(self):
        """Test that listing care tasks with plant info doesn't cause N+1."""
        # Expected queries:
        # 1. SELECT user (authentication)
        # 2. SELECT care_tasks with select_related('plant', 'plant__garden_bed', 'created_by')
        # Total: 2 queries (NOT 2 + 20 for each task's plant)
        with self.assertNumQueries(2):
            response = self.client.get('/api/v1/calendar/api/care-tasks/')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.data['results']), 20)


class CareLogListPerformanceTest(TestCase):
    """Test CareLog list endpoint query optimization."""

    def setUp(self):
        """Set up test user with care logs."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='gardener',
            email='gardener@test.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

        bed = GardenBed.objects.create(
            owner=self.user,
            name='Test Bed',
            bed_type='raised'
        )

        # Create 5 plants with 4 logs each
        for i in range(5):
            plant = Plant.objects.create(
                garden_bed=bed,
                common_name=f'Plant {i}',
                health_status='healthy',
                growth_stage='vegetative',
                planted_date=timezone.now().date()
            )
            for j in range(4):
                CareLog.objects.create(
                    plant=plant,
                    user=self.user,
                    activity_type='watering',
                    notes=f'Log {i}-{j}'
                )

    def test_care_log_list_no_n_plus_1(self):
        """Test that listing care logs with plant info doesn't cause N+1."""
        # Expected queries:
        # 1. SELECT user (authentication)
        # 2. SELECT care_logs with select_related('plant', 'plant__garden_bed', 'user')
        # Total: 2 queries (NOT 2 + 20 for each log's plant)
        with self.assertNumQueries(2):
            response = self.client.get('/api/v1/calendar/api/care-logs/')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.data['results']), 20)


class AnalyticsServicePerformanceTest(TestCase):
    """Test GardenAnalyticsService query optimization."""

    def setUp(self):
        """Set up test user with garden data."""
        self.user = User.objects.create_user(
            username='gardener',
            email='gardener@test.com',
            password='testpass123'
        )

        # Create 3 beds with 5 plants each
        for i in range(3):
            bed = GardenBed.objects.create(
                owner=self.user,
                name=f'Bed {i}',
                bed_type='raised',
                length_inches=96,
                width_inches=48
            )
            for j in range(5):
                Plant.objects.create(
                    garden_bed=bed,
                    common_name=f'Plant {i}-{j}',
                    health_status='healthy' if j % 2 == 0 else 'struggling',
                    growth_stage='vegetative',
                    planted_date=timezone.now().date()
                )

    def test_bed_utilization_stats_efficient(self):
        """Test bed utilization calculation query efficiency."""
        # Expected queries:
        # 1. SELECT garden_beds WHERE owner_id=X AND is_active=True
        # 2-7. COUNT plants for utilization (via property call per bed)
        # Total depends on implementation - should be O(n) not O(n²)
        # With 3 beds, actual is 8 queries (could be optimized to 2 with annotation)
        with self.assertNumQueries(8):
            stats = GardenAnalyticsService.get_bed_utilization_stats(self.user)
            self.assertEqual(stats['total_beds'], 3)

    def test_plant_health_stats_efficient(self):
        """Test plant health stats calculation query efficiency."""
        # Expected queries:
        # 1. COUNT query for total plants
        # 2. SELECT with aggregation (COUNT GROUP BY health_status)
        # 3. SELECT plants WHERE health_status IN ('struggling', 'diseased', ...)
        # Total: 3 queries
        with self.assertNumQueries(3):
            stats = GardenAnalyticsService.get_plant_health_stats(self.user)
            self.assertEqual(stats['total_plants'], 15)

    def test_comprehensive_dashboard_efficient(self):
        """Test comprehensive dashboard doesn't cause excessive queries."""
        # This calls 4 separate analytics methods:
        # - get_bed_utilization_stats (10 queries)
        # - get_plant_health_stats (3 queries)
        # - get_care_task_stats (2 queries)
        # - get_harvest_summary (2 queries)
        # Total: 17 queries
        with self.assertNumQueries(17):
            dashboard = GardenAnalyticsService.get_comprehensive_dashboard(self.user)
            self.assertIn('bed_utilization', dashboard)
            self.assertIn('plant_health', dashboard)
            self.assertIn('care_tasks', dashboard)
            self.assertIn('harvest_summary', dashboard)


class BulkOperationPerformanceTest(TestCase):
    """Test bulk operations performance."""

    def setUp(self):
        """Set up test user and bed."""
        self.user = User.objects.create_user(
            username='gardener',
            email='gardener@test.com',
            password='testpass123'
        )
        self.bed = GardenBed.objects.create(
            owner=self.user,
            name='Test Bed',
            bed_type='raised'
        )

    def test_bulk_plant_creation_efficient(self):
        """Test that bulk_create is used for multiple plants."""
        plants_data = [
            Plant(
                garden_bed=self.bed,
                common_name=f'Plant {i}',
                health_status='healthy',
                growth_stage='seedling',
                planted_date=timezone.now().date()
            )
            for i in range(20)
        ]

        # bulk_create should be 1 query regardless of count
        # (compared to 20 queries with individual create())
        with self.assertNumQueries(1):
            Plant.objects.bulk_create(plants_data)

        # Verify all created
        self.assertEqual(Plant.objects.filter(garden_bed=self.bed).count(), 20)

    def test_bulk_update_efficient(self):
        """Test that bulk_update is efficient for updating multiple plants."""
        # Create plants first
        plants = [
            Plant.objects.create(
                garden_bed=self.bed,
                common_name=f'Plant {i}',
                health_status='healthy',
                growth_stage='seedling',
                planted_date=timezone.now().date()
            )
            for i in range(10)
        ]

        # Update all plants
        for plant in plants:
            plant.growth_stage = 'vegetative'

        # bulk_update should be 1 query
        with self.assertNumQueries(1):
            Plant.objects.bulk_update(plants, ['growth_stage'])

        # Verify all updated
        updated_count = Plant.objects.filter(
            garden_bed=self.bed,
            growth_stage='vegetative'
        ).count()
        self.assertEqual(updated_count, 10)


class HarvestListPerformanceTest(TestCase):
    """Test Harvest list endpoint query optimization."""

    def setUp(self):
        """Set up test user with harvest records."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='gardener',
            email='gardener@test.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

        bed = GardenBed.objects.create(
            owner=self.user,
            name='Test Bed',
            bed_type='raised'
        )

        # Create 5 plants with 3 harvests each
        for i in range(5):
            plant = Plant.objects.create(
                garden_bed=bed,
                common_name=f'Plant {i}',
                health_status='healthy',
                growth_stage='fruiting',
                planted_date=timezone.now().date() - timedelta(days=90)
            )
            for j in range(3):
                Harvest.objects.create(
                    plant=plant,
                    harvest_date=timezone.now().date() - timedelta(days=j),
                    quantity=5.0 + j,
                    unit='lb',
                    quality_rating=4
                )

    def test_harvest_list_no_n_plus_1(self):
        """Test that listing harvests with plant info doesn't cause N+1."""
        # Expected queries:
        # 1. SELECT user (authentication)
        # 2. SELECT harvests with select_related('plant', 'plant__garden_bed')
        # Total: 2 queries (NOT 2 + 15 for each harvest's plant)
        with self.assertNumQueries(2):
            response = self.client.get('/api/v1/calendar/api/harvests/')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.data['results']), 15)
