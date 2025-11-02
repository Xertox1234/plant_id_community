"""
Comprehensive tests for plant health diagnosis models.

This module tests DiagnosisCard and DiagnosisReminder models including
creation, validation, relationships, CASCADE behavior, and helper methods.
"""

import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db.utils import IntegrityError
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta

from apps.plant_identification.models import (
    DiagnosisCard,
    DiagnosisReminder,
    PlantDiseaseResult,
    PlantDiseaseRequest,
    PlantSpecies,
)

User = get_user_model()


@pytest.mark.django_db
class TestDiagnosisCardModel(TestCase):
    """Test cases for DiagnosisCard model."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        self.user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123'
        )

        # Create plant species for testing
        self.plant_species = PlantSpecies.objects.create(
            scientific_name='Monstera deliciosa',
            common_names='Swiss Cheese Plant, Split-leaf Philodendron',
            family='Araceae',
            genus='Monstera',
        )

        # Create disease request and result
        self.disease_request = PlantDiseaseRequest.objects.create(
            user=self.user,
        )

        self.disease_result = PlantDiseaseResult.objects.create(
            request=self.disease_request,
            suggested_disease_name='Powdery Mildew',
            suggested_disease_type='fungal',
            confidence_score=0.87,
            diagnosis_source='plant_id',
        )

        self.diagnosis_card_data = {
            'user': self.user,
            'diagnosis_result': self.disease_result,
            'plant_scientific_name': 'Monstera deliciosa',
            'plant_common_name': 'Swiss Cheese Plant',
            'disease_name': 'Powdery Mildew',
            'disease_type': 'fungal',
            'severity_assessment': 'moderate',
            'confidence_score': 0.87,
        }

    @pytest.mark.unit
    def test_create_diagnosis_card(self):
        """Test creating a new diagnosis card."""
        card = DiagnosisCard.objects.create(**self.diagnosis_card_data)

        self.assertEqual(card.disease_name, 'Powdery Mildew')
        self.assertEqual(card.disease_type, 'fungal')
        self.assertEqual(card.confidence_score, 0.87)
        self.assertEqual(card.treatment_status, 'not_started')
        self.assertFalse(card.is_favorite)
        self.assertFalse(card.share_with_community)
        self.assertTrue(card.uuid)  # UUID should be auto-generated
        self.assertIsNotNone(card.saved_at)

    @pytest.mark.unit
    def test_diagnosis_card_with_custom_nickname(self):
        """Test diagnosis card with custom plant nickname."""
        card_data = self.diagnosis_card_data.copy()
        card_data['custom_nickname'] = 'My Sick Monstera'

        card = DiagnosisCard.objects.create(**card_data)

        self.assertEqual(card.custom_nickname, 'My Sick Monstera')
        self.assertEqual(card.display_name, 'My Sick Monstera')

    @pytest.mark.unit
    def test_display_name_priority(self):
        """Test display_name property priority: custom_nickname > common_name > scientific_name."""
        # Create additional diagnosis results for each test case to avoid unique_together constraint
        disease_result2 = PlantDiseaseResult.objects.create(
            request=self.disease_request,
            suggested_disease_name='Leaf Spot',
            suggested_disease_type='fungal',
            confidence_score=0.75,
            diagnosis_source='plantnet',
        )

        disease_result3 = PlantDiseaseResult.objects.create(
            request=self.disease_request,
            suggested_disease_name='Root Rot',
            suggested_disease_type='fungal',
            confidence_score=0.82,
            diagnosis_source='plant_id',
        )

        # Test with only scientific name
        card1 = DiagnosisCard.objects.create(
            **{**self.diagnosis_card_data, 'plant_common_name': '', 'custom_nickname': ''}
        )
        self.assertEqual(card1.display_name, 'Monstera deliciosa')

        # Test with common name (no nickname)
        card2_data = self.diagnosis_card_data.copy()
        card2_data['diagnosis_result'] = disease_result2
        card2_data['disease_name'] = 'Leaf Spot'
        card2_data['custom_nickname'] = ''
        card2 = DiagnosisCard.objects.create(**card2_data)
        self.assertEqual(card2.display_name, 'Swiss Cheese Plant')

        # Test with custom nickname (highest priority)
        card3_data = self.diagnosis_card_data.copy()
        card3_data['diagnosis_result'] = disease_result3
        card3_data['disease_name'] = 'Root Rot'
        card3_data['custom_nickname'] = 'My Plant'
        card3 = DiagnosisCard.objects.create(**card3_data)
        self.assertEqual(card3.display_name, 'My Plant')

    @pytest.mark.unit
    def test_confidence_score_validation(self):
        """Test confidence_score must be between 0.0 and 1.0."""
        # Valid score
        card = DiagnosisCard.objects.create(**self.diagnosis_card_data)
        self.assertEqual(card.confidence_score, 0.87)

        # Invalid score - too high
        with self.assertRaises(ValidationError):
            card_data = self.diagnosis_card_data.copy()
            card_data['confidence_score'] = 1.5
            card = DiagnosisCard(**card_data)
            card.full_clean()

        # Invalid score - negative
        with self.assertRaises(ValidationError):
            card_data = self.diagnosis_card_data.copy()
            card_data['confidence_score'] = -0.1
            card = DiagnosisCard(**card_data)
            card.full_clean()

    @pytest.mark.unit
    def test_multiple_cards_same_diagnosis_result_allowed(self):
        """
        Test that multiple cards can share the same diagnosis_result.

        NOTE: unique_together constraint was REMOVED in migration 0023.
        Rationale: With optional diagnosis_result (null=True), the constraint
        could not prevent duplicates for API-created cards (NULL != NULL in SQL).
        Users can now create multiple cards with diagnosis_result=None or the
        same diagnosis_result. Business logic should handle duplicate detection.
        """
        # Create first card
        card1 = DiagnosisCard.objects.create(**self.diagnosis_card_data)
        self.assertIsNotNone(card1.id)

        # Can create another card for same user + diagnosis_result (no constraint)
        card2 = DiagnosisCard.objects.create(**self.diagnosis_card_data)
        self.assertIsNotNone(card2.id)
        self.assertNotEqual(card1.id, card2.id)

        # Different user also works (as before)
        card_data = self.diagnosis_card_data.copy()
        card_data['user'] = self.user2
        card3 = DiagnosisCard.objects.create(**card_data)
        self.assertIsNotNone(card3.id)

    @pytest.mark.unit
    def test_care_instructions_json_field(self):
        """Test care_instructions JSONField accepts StreamField-compatible data."""
        care_data = [
            {
                'type': 'heading',
                'value': 'Treatment Plan'
            },
            {
                'type': 'paragraph',
                'value': 'Remove affected leaves and improve air circulation.'
            },
            {
                'type': 'treatment_step',
                'value': {
                    'step_number': 1,
                    'step_title': 'Isolate Plant',
                    'step_instructions': 'Move plant away from others',
                    'difficulty': 'easy',
                    'materials_needed': ['Gloves', 'Spray bottle'],
                    'estimated_time': '15 minutes'
                }
            }
        ]

        card_data = self.diagnosis_card_data.copy()
        card_data['care_instructions'] = care_data
        card = DiagnosisCard.objects.create(**card_data)

        self.assertEqual(len(card.care_instructions), 3)
        self.assertEqual(card.care_instructions[0]['type'], 'heading')
        self.assertEqual(card.care_instructions[2]['value']['step_number'], 1)

    @pytest.mark.unit
    def test_treatment_status_choices(self):
        """Test treatment_status field choices."""
        valid_statuses = [
            'not_started', 'in_progress', 'successful', 'failed', 'monitoring'
        ]

        for status in valid_statuses:
            card_data = self.diagnosis_card_data.copy()
            card_data['treatment_status'] = status
            card = DiagnosisCard.objects.create(**card_data)
            self.assertEqual(card.treatment_status, status)
            # Clean up for unique constraint
            card.delete()

    @pytest.mark.unit
    def test_plant_recovered_nullable(self):
        """Test plant_recovered field can be null (unknown status)."""
        card = DiagnosisCard.objects.create(**self.diagnosis_card_data)
        self.assertIsNone(card.plant_recovered)

        card.plant_recovered = True
        card.save()
        self.assertTrue(card.plant_recovered)

        card.plant_recovered = False
        card.save()
        self.assertFalse(card.plant_recovered)

    @pytest.mark.unit
    def test_update_last_viewed_method(self):
        """Test update_last_viewed() helper method."""
        card = DiagnosisCard.objects.create(**self.diagnosis_card_data)

        self.assertIsNone(card.last_viewed_at)

        card.update_last_viewed()
        card.refresh_from_db()

        self.assertIsNotNone(card.last_viewed_at)
        self.assertLess(
            timezone.now() - card.last_viewed_at,
            timedelta(seconds=2)
        )

    @pytest.mark.unit
    def test_cascade_delete_user(self):
        """Test CASCADE delete: card deleted when user deleted (GDPR compliance)."""
        card = DiagnosisCard.objects.create(**self.diagnosis_card_data)
        card_id = card.id

        self.user.delete()

        # Card should be deleted
        with self.assertRaises(DiagnosisCard.DoesNotExist):
            DiagnosisCard.objects.get(id=card_id)

    @pytest.mark.unit
    def test_cascade_delete_diagnosis_result(self):
        """Test CASCADE delete: card deleted when diagnosis_result deleted."""
        card = DiagnosisCard.objects.create(**self.diagnosis_card_data)
        card_id = card.id

        self.disease_result.delete()

        # Card should be deleted
        with self.assertRaises(DiagnosisCard.DoesNotExist):
            DiagnosisCard.objects.get(id=card_id)

    @pytest.mark.unit
    def test_str_representation(self):
        """Test string representation of diagnosis card."""
        card = DiagnosisCard.objects.create(**self.diagnosis_card_data)
        expected = f"testuser's diagnosis: Powdery Mildew on Swiss Cheese Plant"
        self.assertEqual(str(card), expected)

        # Test with custom nickname
        card.custom_nickname = 'My Monstera'
        card.save()
        expected = f"testuser's diagnosis: Powdery Mildew on My Monstera"
        self.assertEqual(str(card), expected)

    @pytest.mark.unit
    def test_ordering(self):
        """Test default ordering by -saved_at."""
        card1 = DiagnosisCard.objects.create(**self.diagnosis_card_data)

        # Create second diagnosis result to avoid unique constraint
        disease_result2 = PlantDiseaseResult.objects.create(
            request=self.disease_request,
            suggested_disease_name='Leaf Spot',
            suggested_disease_type='fungal',
            confidence_score=0.75,
            diagnosis_source='plantnet',
        )

        card_data2 = self.diagnosis_card_data.copy()
        card_data2['diagnosis_result'] = disease_result2
        card_data2['disease_name'] = 'Leaf Spot'
        card2 = DiagnosisCard.objects.create(**card_data2)

        cards = list(DiagnosisCard.objects.all())
        self.assertEqual(cards[0].id, card2.id)  # Most recent first
        self.assertEqual(cards[1].id, card1.id)

    @pytest.mark.unit
    def test_is_favorite_filtering(self):
        """Test filtering by is_favorite."""
        card1 = DiagnosisCard.objects.create(
            **{**self.diagnosis_card_data, 'is_favorite': True}
        )

        disease_result2 = PlantDiseaseResult.objects.create(
            request=self.disease_request,
            suggested_disease_name='Leaf Spot',
            suggested_disease_type='bacterial',
            confidence_score=0.75,
            diagnosis_source='plantnet',
        )

        card_data2 = self.diagnosis_card_data.copy()
        card_data2['diagnosis_result'] = disease_result2
        card_data2['disease_name'] = 'Leaf Spot'
        card_data2['is_favorite'] = False
        card2 = DiagnosisCard.objects.create(**card_data2)

        favorites = DiagnosisCard.objects.filter(is_favorite=True)
        self.assertEqual(favorites.count(), 1)
        self.assertEqual(favorites.first().id, card1.id)


@pytest.mark.django_db
class TestDiagnosisReminderModel(TestCase):
    """Test cases for DiagnosisReminder model."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        # Create disease result and diagnosis card
        self.disease_request = PlantDiseaseRequest.objects.create(
            user=self.user,
        )

        self.disease_result = PlantDiseaseResult.objects.create(
            request=self.disease_request,
            suggested_disease_name='Powdery Mildew',
            suggested_disease_type='fungal',
            confidence_score=0.87,
            diagnosis_source='plant_id',
        )

        self.diagnosis_card = DiagnosisCard.objects.create(
            user=self.user,
            diagnosis_result=self.disease_result,
            plant_scientific_name='Monstera deliciosa',
            plant_common_name='Swiss Cheese Plant',
            disease_name='Powdery Mildew',
            disease_type='fungal',
            severity_assessment='moderate',
            confidence_score=0.87,
        )

        self.reminder_data = {
            'diagnosis_card': self.diagnosis_card,
            'reminder_type': 'check_progress',
            'reminder_title': 'Check plant recovery',
            'scheduled_date': timezone.now() + timedelta(days=7),
        }

    @pytest.mark.unit
    def test_create_reminder(self):
        """Test creating a new reminder."""
        reminder = DiagnosisReminder.objects.create(**self.reminder_data)

        self.assertEqual(reminder.reminder_type, 'check_progress')
        self.assertEqual(reminder.reminder_title, 'Check plant recovery')
        self.assertTrue(reminder.is_active)
        self.assertFalse(reminder.sent)
        self.assertFalse(reminder.cancelled)
        self.assertTrue(reminder.uuid)

    @pytest.mark.unit
    def test_reminder_type_choices(self):
        """Test reminder_type field choices."""
        valid_types = [
            'check_progress', 'treatment_step', 'follow_up', 'reapply'
        ]

        for reminder_type in valid_types:
            data = self.reminder_data.copy()
            data['reminder_type'] = reminder_type
            reminder = DiagnosisReminder.objects.create(**data)
            self.assertEqual(reminder.reminder_type, reminder_type)

    @pytest.mark.unit
    def test_snooze_method(self):
        """Test snooze() helper method."""
        reminder = DiagnosisReminder.objects.create(**self.reminder_data)

        self.assertIsNone(reminder.snoozed_until)

        reminder.snooze(hours=24)
        reminder.refresh_from_db()

        self.assertIsNotNone(reminder.snoozed_until)
        self.assertLess(
            abs((reminder.snoozed_until - timezone.now()) - timedelta(hours=24)),
            timedelta(seconds=2)
        )

        # Test custom snooze duration
        reminder.snooze(hours=48)
        reminder.refresh_from_db()
        self.assertLess(
            abs((reminder.snoozed_until - timezone.now()) - timedelta(hours=48)),
            timedelta(seconds=2)
        )

    @pytest.mark.unit
    def test_cancel_method(self):
        """Test cancel() helper method."""
        reminder = DiagnosisReminder.objects.create(**self.reminder_data)

        self.assertTrue(reminder.is_active)
        self.assertFalse(reminder.cancelled)

        reminder.cancel()
        reminder.refresh_from_db()

        self.assertFalse(reminder.is_active)
        self.assertTrue(reminder.cancelled)

    @pytest.mark.unit
    def test_mark_sent_method(self):
        """Test mark_sent() helper method."""
        reminder = DiagnosisReminder.objects.create(**self.reminder_data)

        self.assertFalse(reminder.sent)
        self.assertIsNone(reminder.sent_at)

        reminder.mark_sent()
        reminder.refresh_from_db()

        self.assertTrue(reminder.sent)
        self.assertIsNotNone(reminder.sent_at)
        self.assertLess(
            timezone.now() - reminder.sent_at,
            timedelta(seconds=2)
        )

    @pytest.mark.unit
    def test_acknowledge_method(self):
        """Test acknowledge() helper method."""
        reminder = DiagnosisReminder.objects.create(**self.reminder_data)

        self.assertFalse(reminder.acknowledged)
        self.assertIsNone(reminder.acknowledged_at)

        reminder.acknowledge()
        reminder.refresh_from_db()

        self.assertTrue(reminder.acknowledged)
        self.assertIsNotNone(reminder.acknowledged_at)
        self.assertLess(
            timezone.now() - reminder.acknowledged_at,
            timedelta(seconds=2)
        )

    @pytest.mark.unit
    def test_cascade_delete_diagnosis_card(self):
        """Test CASCADE delete: reminder deleted when diagnosis card deleted."""
        reminder = DiagnosisReminder.objects.create(**self.reminder_data)
        reminder_id = reminder.id

        self.diagnosis_card.delete()

        # Reminder should be deleted
        with self.assertRaises(DiagnosisReminder.DoesNotExist):
            DiagnosisReminder.objects.get(id=reminder_id)

    @pytest.mark.unit
    def test_str_representation(self):
        """Test string representation of reminder."""
        reminder = DiagnosisReminder.objects.create(**self.reminder_data)
        expected_str = f"Reminder: Check plant recovery for Swiss Cheese Plant on"
        self.assertIn(expected_str, str(reminder))

    @pytest.mark.unit
    def test_ordering_by_scheduled_date(self):
        """Test default ordering by scheduled_date."""
        reminder1 = DiagnosisReminder.objects.create(
            **{**self.reminder_data, 'scheduled_date': timezone.now() + timedelta(days=7)}
        )

        reminder2 = DiagnosisReminder.objects.create(
            **{**self.reminder_data, 'scheduled_date': timezone.now() + timedelta(days=3)}
        )

        reminders = list(DiagnosisReminder.objects.all())
        self.assertEqual(reminders[0].id, reminder2.id)  # Earlier date first
        self.assertEqual(reminders[1].id, reminder1.id)

    @pytest.mark.unit
    def test_multiple_reminders_per_card(self):
        """Test creating multiple reminders for same diagnosis card."""
        reminder1 = DiagnosisReminder.objects.create(
            **{**self.reminder_data, 'scheduled_date': timezone.now() + timedelta(days=7)}
        )

        reminder2 = DiagnosisReminder.objects.create(
            **{**self.reminder_data, 'scheduled_date': timezone.now() + timedelta(days=14)}
        )

        reminders = self.diagnosis_card.reminders.all()
        self.assertEqual(reminders.count(), 2)

    @pytest.mark.unit
    def test_active_reminders_filtering(self):
        """Test filtering active, unsent, non-cancelled reminders."""
        # Active reminder
        reminder1 = DiagnosisReminder.objects.create(**self.reminder_data)

        # Sent reminder
        data2 = self.reminder_data.copy()
        data2['scheduled_date'] = timezone.now() + timedelta(days=14)
        reminder2 = DiagnosisReminder.objects.create(**data2)
        reminder2.mark_sent()

        # Cancelled reminder
        data3 = self.reminder_data.copy()
        data3['scheduled_date'] = timezone.now() + timedelta(days=21)
        reminder3 = DiagnosisReminder.objects.create(**data3)
        reminder3.cancel()

        active = DiagnosisReminder.objects.filter(
            is_active=True, sent=False, cancelled=False
        )
        self.assertEqual(active.count(), 1)
        self.assertEqual(active.first().id, reminder1.id)
