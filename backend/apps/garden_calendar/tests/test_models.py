"""
Model tests for garden_calendar app.

Tests field validation, model properties, and custom methods.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from ..models import (
    GrowingZone, GardenBed, Plant, PlantImage, CareTask, CareLog, Harvest
)

User = get_user_model()


class GrowingZoneModelTest(TestCase):
    """Test GrowingZone model."""

    def test_create_growing_zone(self):
        """Test creating a growing zone."""
        zone = GrowingZone.objects.create(
            zone_code='7a',
            temp_min=0,
            temp_max=5,
            first_frost_date='10-15',
            last_frost_date='04-15',
            growing_season_days=180
        )
        self.assertEqual(zone.zone_code, '7a')
        self.assertEqual(zone.temp_min, 0)
        self.assertEqual(zone.temp_max, 5)
        self.assertEqual(str(zone), 'Zone 7a (0°F to 5°F)')

    def test_zone_code_unique(self):
        """Test zone_code must be unique."""
        GrowingZone.objects.create(zone_code='7a', temp_min=0, temp_max=5)

        with self.assertRaises(Exception):  # IntegrityError
            GrowingZone.objects.create(zone_code='7a', temp_min=0, temp_max=5)


class GardenBedModelTest(TestCase):
    """Test GardenBed model."""

    def setUp(self):
        """Set up test user."""
        self.user = User.objects.create_user(
            username='gardener',
            email='gardener@test.com',
            password='testpass123'
        )

    def test_create_garden_bed(self):
        """Test creating a garden bed."""
        bed = GardenBed.objects.create(
            owner=self.user,
            name='Vegetable Bed 1',
            bed_type='raised',
            length_inches=96,
            width_inches=48,
            depth_inches=12,
            sun_exposure='full_sun',
            soil_type='loam',
            soil_ph=Decimal('6.5')
        )

        self.assertEqual(bed.name, 'Vegetable Bed 1')
        self.assertEqual(bed.owner, self.user)
        self.assertIsNotNone(bed.uuid)
        self.assertTrue(bed.is_active)

    def test_area_square_feet_calculation(self):
        """Test area_square_feet property."""
        bed = GardenBed.objects.create(
            owner=self.user,
            name='Test Bed',
            bed_type='raised',
            length_inches=96,  # 8 feet
            width_inches=48,   # 4 feet
        )

        # 8 * 4 = 32 square feet
        self.assertEqual(bed.area_square_feet, 32.0)

    def test_area_square_feet_none_when_no_dimensions(self):
        """Test area_square_feet returns None when dimensions missing."""
        bed = GardenBed.objects.create(
            owner=self.user,
            name='Test Bed',
            bed_type='in_ground'
        )

        self.assertIsNone(bed.area_square_feet)

    def test_plant_count_property(self):
        """Test plant_count property."""
        bed = GardenBed.objects.create(
            owner=self.user,
            name='Test Bed',
            bed_type='raised'
        )

        # Create active plants
        Plant.objects.create(
            garden_bed=bed,
            common_name='Tomato',
            health_status='healthy',
            growth_stage='vegetative',
            planted_date=timezone.now().date(),
            is_active=True
        )
        Plant.objects.create(
            garden_bed=bed,
            common_name='Basil',
            health_status='healthy',
            growth_stage='vegetative',
            planted_date=timezone.now().date(),
            is_active=True
        )

        # Create inactive plant (should not count)
        Plant.objects.create(
            garden_bed=bed,
            common_name='Dead Plant',
            health_status='dead',
            growth_stage='dormant',
            planted_date=timezone.now().date(),
            is_active=False
        )

        self.assertEqual(bed.plant_count, 2)

    def test_utilization_rate_property(self):
        """Test utilization_rate property."""
        bed = GardenBed.objects.create(
            owner=self.user,
            name='Test Bed',
            bed_type='raised',
            length_inches=96,  # 8 feet
            width_inches=48,   # 4 feet = 32 sq ft
        )

        # Create 16 plants (0.5 plants per sq ft)
        for i in range(16):
            Plant.objects.create(
                garden_bed=bed,
                common_name=f'Plant {i}',
                health_status='healthy',
                growth_stage='vegetative',
                planted_date=timezone.now().date(),
                is_active=True
            )

        # 16 plants / 32 sq ft = 0.5 utilization rate
        self.assertEqual(bed.utilization_rate, 0.5)


class PlantModelTest(TestCase):
    """Test Plant model."""

    def setUp(self):
        """Set up test user and garden bed."""
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

    def test_create_plant(self):
        """Test creating a plant."""
        plant = Plant.objects.create(
            garden_bed=self.bed,
            common_name='Tomato',
            variety='Cherry',
            health_status='healthy',
            growth_stage='vegetative',
            planted_date=timezone.now().date()
        )

        self.assertEqual(plant.common_name, 'Tomato')
        self.assertEqual(plant.variety, 'Cherry')
        self.assertIsNotNone(plant.uuid)
        self.assertTrue(plant.is_active)

    def test_days_since_planted_property(self):
        """Test days_since_planted property."""
        planted_date = timezone.now().date() - timedelta(days=30)
        plant = Plant.objects.create(
            garden_bed=self.bed,
            common_name='Tomato',
            health_status='healthy',
            growth_stage='vegetative',
            planted_date=planted_date
        )

        self.assertEqual(plant.days_since_planted, 30)

    def test_age_display_property_days(self):
        """Test age_display shows days for recent plants."""
        planted_date = timezone.now().date() - timedelta(days=15)
        plant = Plant.objects.create(
            garden_bed=self.bed,
            common_name='Tomato',
            health_status='healthy',
            growth_stage='seedling',
            planted_date=planted_date
        )

        self.assertEqual(plant.age_display, '15 days')

    def test_age_display_property_weeks(self):
        """Test age_display shows weeks for plants < 1 year."""
        planted_date = timezone.now().date() - timedelta(days=70)
        plant = Plant.objects.create(
            garden_bed=self.bed,
            common_name='Tomato',
            health_status='healthy',
            growth_stage='vegetative',
            planted_date=planted_date
        )

        # 70 days / 7 = 10 weeks
        self.assertEqual(plant.age_display, '10 weeks')

    def test_age_display_property_years(self):
        """Test age_display shows years for plants >= 1 year."""
        planted_date = timezone.now().date() - timedelta(days=400)
        plant = Plant.objects.create(
            garden_bed=self.bed,
            common_name='Apple Tree',
            health_status='healthy',
            growth_stage='vegetative',
            planted_date=planted_date
        )

        # 400 days = 1 year + 35 days (~1 month)
        self.assertIn('1y', plant.age_display)


class CareTaskModelTest(TestCase):
    """Test CareTask model."""

    def setUp(self):
        """Set up test user, bed, and plant."""
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
        self.plant = Plant.objects.create(
            garden_bed=self.bed,
            common_name='Tomato',
            health_status='healthy',
            growth_stage='vegetative',
            planted_date=timezone.now().date()
        )

    def test_create_care_task(self):
        """Test creating a care task."""
        task = CareTask.objects.create(
            plant=self.plant,
            created_by=self.user,
            task_type='watering',
            title='Water tomato plant',
            priority='high',
            scheduled_date=timezone.now() + timedelta(days=1)
        )

        self.assertEqual(task.task_type, 'watering')
        self.assertEqual(task.title, 'Water tomato plant')
        self.assertEqual(task.priority, 'high')
        self.assertEqual(task.created_by, self.user)
        self.assertFalse(task.completed)
        self.assertFalse(task.skipped)

    def test_is_overdue_property_true(self):
        """Test is_overdue returns True for past tasks."""
        task = CareTask.objects.create(
            plant=self.plant,
            created_by=self.user,
            task_type='watering',
            title='Overdue watering task',
            priority='high',
            scheduled_date=timezone.now() - timedelta(days=1)
        )

        self.assertTrue(task.is_overdue)

    def test_is_overdue_property_false_for_completed(self):
        """Test is_overdue returns False for completed tasks."""
        task = CareTask.objects.create(
            plant=self.plant,
            created_by=self.user,
            task_type='watering',
            title='Completed watering task',
            priority='high',
            scheduled_date=timezone.now() - timedelta(days=1),
            completed=True
        )

        self.assertFalse(task.is_overdue)

    def test_mark_complete_method(self):
        """Test mark_complete method."""
        task = CareTask.objects.create(
            plant=self.plant,
            created_by=self.user,
            task_type='watering',
            title='Test watering task',
            priority='high',
            scheduled_date=timezone.now()
        )

        task.mark_complete(self.user)

        self.assertTrue(task.completed)
        self.assertIsNotNone(task.completed_at)
        self.assertEqual(task.completed_by, self.user)

    def test_mark_complete_creates_next_occurrence(self):
        """Test mark_complete creates next occurrence for recurring tasks."""
        task = CareTask.objects.create(
            plant=self.plant,
            created_by=self.user,
            task_type='watering',
            title='Recurring watering task',
            priority='high',
            scheduled_date=timezone.now(),
            is_recurring=True,
            recurrence_interval_days=2
        )

        initial_count = CareTask.objects.count()
        task.mark_complete(self.user)

        # Should create new task
        self.assertEqual(CareTask.objects.count(), initial_count + 1)

        # New task should be 2 days in future
        new_task = CareTask.objects.filter(
            plant=self.plant,
            task_type='watering',
            completed=False
        ).first()

        self.assertIsNotNone(new_task)

    def test_mark_skip_method(self):
        """Test mark_skip method."""
        task = CareTask.objects.create(
            plant=self.plant,
            created_by=self.user,
            task_type='watering',
            title='Task to skip',
            priority='high',
            scheduled_date=timezone.now()
        )

        task.mark_skip(self.user, reason='Rainy weather')

        self.assertTrue(task.skipped)
        self.assertFalse(task.completed)
        self.assertEqual(task.skip_reason, 'Rainy weather')
        self.assertIsNotNone(task.skipped_at)


class HarvestModelTest(TestCase):
    """Test Harvest model."""

    def setUp(self):
        """Set up test user, bed, and plant."""
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
        self.plant = Plant.objects.create(
            garden_bed=self.bed,
            common_name='Tomato',
            health_status='healthy',
            growth_stage='fruiting',
            planted_date=timezone.now().date() - timedelta(days=90)
        )

    def test_create_harvest(self):
        """Test creating a harvest record."""
        harvest = Harvest.objects.create(
            plant=self.plant,
            harvest_date=timezone.now().date(),
            quantity=5.0,
            unit='lb',
            quality_rating=4,
            notes='First harvest of the season - excellent quality!'
        )

        self.assertEqual(harvest.quantity, 5.0)
        self.assertEqual(harvest.unit, 'lb')
        self.assertEqual(harvest.quality_rating, 4)
        self.assertIn('excellent', harvest.notes)

    def test_days_from_planting_property(self):
        """Test days_from_planting property."""
        harvest = Harvest.objects.create(
            plant=self.plant,
            harvest_date=timezone.now().date(),
            quantity=5.0,
            unit='lb'
        )

        # Plant was planted 90 days ago
        self.assertEqual(harvest.days_from_planting, 90)
