"""
API integration tests for diagnosis card endpoints.

Tests the DiagnosisCardViewSet and DiagnosisReminderViewSet REST API endpoints
including authentication, CRUD operations, filtering, custom actions, and permissions.
"""

import pytest
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from apps.plant_identification.models import (
    DiagnosisCard,
    DiagnosisReminder,
    PlantDiseaseRequest,
    PlantDiseaseResult,
)

User = get_user_model()


@pytest.mark.django_db
class TestDiagnosisCardAPI(APITestCase):
    """Test DiagnosisCard ViewSet API endpoints."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()

        # Create test users
        self.user1 = User.objects.create_user(
            username='testuser1',
            email='test1@example.com',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123'
        )

        # Create PlantDiseaseRequest and Result for foreign key
        self.disease_request = PlantDiseaseRequest.objects.create(
            user=self.user1
        )
        self.disease_result = PlantDiseaseResult.objects.create(
            request=self.disease_request,
            suggested_disease_name='Powdery Mildew',
            suggested_disease_type='fungal',
            confidence_score=0.87,
            diagnosis_source='plant_id'
        )

        # Base diagnosis card data
        self.card_data = {
            'plant_scientific_name': 'Rosa damascena',
            'plant_common_name': 'Damask Rose',
            'disease_name': 'Powdery Mildew',
            'disease_type': 'fungal',
            'severity_assessment': 'moderate',
            'confidence_score': 0.87,
            'care_instructions': [
                {'type': 'heading', 'value': 'Treatment Plan'},
                {'type': 'paragraph', 'value': 'Remove affected leaves immediately'},
            ],
            'treatment_status': 'not_started',
        }

    def test_list_diagnosis_cards_requires_authentication(self):
        """Test that listing diagnosis cards requires authentication."""
        url = reverse('v1:plant_identification:diagnosis-cards-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_diagnosis_cards_authenticated(self):
        """Test authenticated user can list their diagnosis cards."""
        # Create cards for user1
        DiagnosisCard.objects.create(user=self.user1, **self.card_data)
        DiagnosisCard.objects.create(
            user=self.user1,
            plant_scientific_name='Solanum lycopersicum',
            plant_common_name='Tomato',
            disease_name='Leaf Spot',
            disease_type='bacterial',
            severity_assessment='mild',
            confidence_score=0.75,
            care_instructions=[],
            treatment_status='in_progress',
        )

        # Create card for user2 (should not be visible)
        DiagnosisCard.objects.create(user=self.user2, **self.card_data)

        # Authenticate as user1
        self.client.force_authenticate(user=self.user1)
        url = reverse('v1:plant_identification:diagnosis-cards-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)  # Only user1's cards

    def test_create_diagnosis_card(self):
        """Test creating a new diagnosis card."""
        self.client.force_authenticate(user=self.user1)
        url = reverse('v1:plant_identification:diagnosis-cards-list')
        response = self.client.post(url, self.card_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['plant_common_name'], 'Damask Rose')
        self.assertEqual(response.data['disease_name'], 'Powdery Mildew')
        self.assertEqual(response.data['treatment_status'], 'not_started')
        self.assertIn('uuid', response.data)

    def test_create_diagnosis_card_with_optional_diagnosis_result(self):
        """Test creating card with optional diagnosis_result field."""
        self.client.force_authenticate(user=self.user1)
        url = reverse('v1:plant_identification:diagnosis-cards-list')

        # Test with diagnosis_result
        data_with_result = self.card_data.copy()
        data_with_result['diagnosis_result'] = str(self.disease_result.uuid)
        response1 = self.client.post(url, data_with_result, format='json')
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)

        # Test without diagnosis_result (API flow)
        data_without_result = self.card_data.copy()
        response2 = self.client.post(url, data_without_result, format='json')
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)

    def test_create_diagnosis_card_validation(self):
        """Test validation on diagnosis card creation."""
        self.client.force_authenticate(user=self.user1)
        url = reverse('v1:plant_identification:diagnosis-cards-list')

        # Test invalid confidence_score
        invalid_data = self.card_data.copy()
        invalid_data['confidence_score'] = 1.5  # > 1.0
        response = self.client.post(url, invalid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Test invalid StreamField structure
        invalid_data = self.card_data.copy()
        invalid_data['care_instructions'] = [
            {'type': 'invalid_type', 'value': 'test'}
        ]
        response = self.client.post(url, invalid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_retrieve_diagnosis_card(self):
        """Test retrieving a specific diagnosis card."""
        card = DiagnosisCard.objects.create(user=self.user1, **self.card_data)

        self.client.force_authenticate(user=self.user1)
        url = reverse('v1:plant_identification:diagnosis-cards-detail', kwargs={'uuid': str(card.uuid)})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['uuid'], str(card.uuid))
        self.assertEqual(response.data['disease_name'], 'Powdery Mildew')
        self.assertIn('care_instructions', response.data)
        self.assertIn('active_reminders_count', response.data)

    def test_retrieve_other_user_card_forbidden(self):
        """Test that users cannot retrieve other users' cards."""
        card = DiagnosisCard.objects.create(user=self.user2, **self.card_data)

        self.client.force_authenticate(user=self.user1)
        url = reverse('v1:plant_identification:diagnosis-cards-detail', kwargs={'uuid': str(card.uuid)})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_diagnosis_card(self):
        """Test updating diagnosis card fields."""
        card = DiagnosisCard.objects.create(user=self.user1, **self.card_data)

        self.client.force_authenticate(user=self.user1)
        url = reverse('v1:plant_identification:diagnosis-cards-detail', kwargs={'uuid': str(card.uuid)})

        update_data = {
            'custom_nickname': 'My Rose Plant',
            'treatment_status': 'in_progress',
            'personal_notes': 'Started treatment today',
        }
        response = self.client.patch(url, update_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['custom_nickname'], 'My Rose Plant')
        self.assertEqual(response.data['treatment_status'], 'in_progress')
        self.assertEqual(response.data['personal_notes'], 'Started treatment today')

    def test_delete_diagnosis_card(self):
        """Test deleting diagnosis card."""
        card = DiagnosisCard.objects.create(user=self.user1, **self.card_data)

        self.client.force_authenticate(user=self.user1)
        url = reverse('v1:plant_identification:diagnosis-cards-detail', kwargs={'uuid': str(card.uuid)})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(DiagnosisCard.objects.filter(uuid=card.uuid).exists())

    def test_filter_by_treatment_status(self):
        """Test filtering diagnosis cards by treatment_status."""
        # First card with not_started status (from self.card_data)
        DiagnosisCard.objects.create(
            user=self.user1,
            **self.card_data
        )
        DiagnosisCard.objects.create(
            user=self.user1,
            plant_scientific_name='Test',
            plant_common_name='Test',
            disease_name='Test',
            disease_type='fungal',
            severity_assessment='mild',
            confidence_score=0.5,
            care_instructions=[],
            treatment_status='in_progress',
        )

        self.client.force_authenticate(user=self.user1)
        url = reverse('v1:plant_identification:diagnosis-cards-list') + '?treatment_status=in_progress'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['treatment_status'], 'in_progress')

    def test_search_diagnosis_cards(self):
        """Test searching diagnosis cards by plant names and disease."""
        DiagnosisCard.objects.create(user=self.user1, **self.card_data)
        DiagnosisCard.objects.create(
            user=self.user1,
            plant_scientific_name='Solanum lycopersicum',
            plant_common_name='Tomato',
            disease_name='Leaf Spot',
            disease_type='bacterial',
            severity_assessment='mild',
            confidence_score=0.75,
            care_instructions=[],
            treatment_status='not_started',
        )

        self.client.force_authenticate(user=self.user1)
        url = reverse('v1:plant_identification:diagnosis-cards-list') + '?search=Rose'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertIn('Rose', response.data['results'][0]['plant_common_name'])

    def test_toggle_favorite_action(self):
        """Test toggle_favorite custom action."""
        card = DiagnosisCard.objects.create(
            user=self.user1,
            is_favorite=False,
            **self.card_data
        )

        self.client.force_authenticate(user=self.user1)
        url = reverse('v1:plant_identification:diagnosis-cards-toggle-favorite', kwargs={'uuid': str(card.uuid)})

        # Toggle to true
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_favorite'])

        # Toggle back to false
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['is_favorite'])

    def test_favorites_action(self):
        """Test favorites custom action returns only favorited cards."""
        DiagnosisCard.objects.create(
            user=self.user1,
            is_favorite=True,
            **self.card_data
        )
        DiagnosisCard.objects.create(
            user=self.user1,
            plant_scientific_name='Test',
            plant_common_name='Test',
            disease_name='Test',
            disease_type='fungal',
            severity_assessment='mild',
            confidence_score=0.5,
            care_instructions=[],
            treatment_status='not_started',
            is_favorite=False,
        )

        self.client.force_authenticate(user=self.user1)
        url = reverse('v1:plant_identification:diagnosis-cards-favorites')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertTrue(response.data['results'][0]['is_favorite'])

    def test_pagination(self):
        """Test pagination of diagnosis cards list."""
        # Create 25 cards
        for i in range(25):
            DiagnosisCard.objects.create(
                user=self.user1,
                plant_scientific_name=f'Plant {i}',
                plant_common_name=f'Common {i}',
                disease_name='Test Disease',
                disease_type='fungal',
                severity_assessment='mild',
                confidence_score=0.5,
                care_instructions=[],
                treatment_status='not_started',
            )

        self.client.force_authenticate(user=self.user1)
        url = reverse('v1:plant_identification:diagnosis-cards-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('count', response.data)
        self.assertIn('next', response.data)
        self.assertIn('previous', response.data)
        self.assertEqual(response.data['count'], 25)
        # Default page size should be 20
        self.assertEqual(len(response.data['results']), 20)


@pytest.mark.django_db
class TestDiagnosisReminderAPI(APITestCase):
    """Test DiagnosisReminder ViewSet API endpoints."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()

        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        # Create diagnosis card
        self.card = DiagnosisCard.objects.create(
            user=self.user,
            plant_scientific_name='Rosa damascena',
            plant_common_name='Damask Rose',
            disease_name='Powdery Mildew',
            disease_type='fungal',
            severity_assessment='moderate',
            confidence_score=0.87,
            care_instructions=[],
            treatment_status='in_progress',
        )

        # Base reminder data
        self.reminder_data = {
            'diagnosis_card': str(self.card.uuid),
            'reminder_type': 'treatment_step',
            'reminder_title': 'Apply fungicide',
            'reminder_message': 'Apply fungicide spray to affected areas',
            'scheduled_date': (timezone.now() + timedelta(days=7)).isoformat(),
        }

    def test_create_reminder(self):
        """Test creating a new reminder."""
        self.client.force_authenticate(user=self.user)
        url = reverse('v1:plant_identification:diagnosis-reminders-list')
        response = self.client.post(url, self.reminder_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['reminder_title'], 'Apply fungicide')
        self.assertEqual(response.data['reminder_type'], 'treatment_step')
        self.assertFalse(response.data['sent'])
        self.assertFalse(response.data['cancelled'])

    def test_create_reminder_past_date_validation(self):
        """Test validation prevents creating reminders in the past."""
        self.client.force_authenticate(user=self.user)
        url = reverse('v1:plant_identification:diagnosis-reminders-list')

        invalid_data = self.reminder_data.copy()
        invalid_data['scheduled_date'] = (timezone.now() - timedelta(days=1)).isoformat()
        response = self.client.post(url, invalid_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_reminders(self):
        """Test listing reminders for user's cards."""
        DiagnosisReminder.objects.create(
            diagnosis_card=self.card,
            reminder_type='treatment',
            reminder_title='Test 1',
            reminder_message='Message 1',
            scheduled_date=timezone.now() + timedelta(days=1),
        )
        DiagnosisReminder.objects.create(
            diagnosis_card=self.card,
            reminder_type='checkup',
            reminder_title='Test 2',
            reminder_message='Message 2',
            scheduled_date=timezone.now() + timedelta(days=2),
        )

        self.client.force_authenticate(user=self.user)
        url = reverse('v1:plant_identification:diagnosis-reminders-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)

    def test_snooze_action(self):
        """Test snooze custom action."""
        reminder = DiagnosisReminder.objects.create(
            diagnosis_card=self.card,
            reminder_type='treatment',
            reminder_title='Test',
            reminder_message='Message',
            scheduled_date=timezone.now() + timedelta(days=1),
        )

        self.client.force_authenticate(user=self.user)
        url = reverse('v1:plant_identification:diagnosis-reminders-snooze', kwargs={'uuid': str(reminder.uuid)})
        response = self.client.post(url, {'hours': 24}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data['snoozed_until'])

    def test_cancel_action(self):
        """Test cancel custom action."""
        reminder = DiagnosisReminder.objects.create(
            diagnosis_card=self.card,
            reminder_type='treatment',
            reminder_title='Test',
            reminder_message='Message',
            scheduled_date=timezone.now() + timedelta(days=1),
        )

        self.client.force_authenticate(user=self.user)
        url = reverse('v1:plant_identification:diagnosis-reminders-cancel', kwargs={'uuid': str(reminder.uuid)})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['cancelled'])
        self.assertFalse(response.data['is_active'])

    def test_acknowledge_action(self):
        """Test acknowledge custom action."""
        reminder = DiagnosisReminder.objects.create(
            diagnosis_card=self.card,
            reminder_type='treatment',
            reminder_title='Test',
            reminder_message='Message',
            scheduled_date=timezone.now() + timedelta(days=1),
            sent=True,
        )

        self.client.force_authenticate(user=self.user)
        url = reverse('v1:plant_identification:diagnosis-reminders-acknowledge', kwargs={'uuid': str(reminder.uuid)})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['acknowledged'])
        self.assertIsNotNone(response.data['acknowledged_at'])
