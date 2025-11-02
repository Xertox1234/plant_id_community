# Diagnosis API Patterns Codified

**Date**: November 2, 2025
**Context**: Fixing 7 failing diagnosis API integration tests (from 13/20 to 20/20 passing)
**Status**: All patterns validated and production-ready

---

## Overview

This document codifies critical patterns discovered while implementing and fixing the plant health diagnosis API feature. These patterns are essential for working with Django Rest Framework (DRF) ViewSets using UUID lookups instead of integer primary keys.

**Files Covered**:
- `/backend/apps/plant_identification/api/diagnosis_viewsets.py` - ViewSet implementations
- `/backend/apps/plant_identification/api/diagnosis_serializers.py` - DRF serializers
- `/backend/apps/plant_identification/test_diagnosis_api.py` - Integration tests
- `/backend/apps/plant_identification/models.py` - DiagnosisCard and DiagnosisReminder models

---

## Pattern 1: DRF Custom Actions with UUID Lookup

### Problem

When using `lookup_field = 'uuid'` on a ViewSet, custom `@action` methods fail with:

```python
TypeError: toggle_favorite() got an unexpected keyword argument 'uuid'
```

This happens because DRF passes the lookup field value as a keyword argument to detail-level actions, but the method signature doesn't accept it.

### Root Cause

DRF's routing mechanism:
1. When `lookup_field = 'uuid'` is set, DRF extracts the UUID from the URL
2. For detail-level actions (`detail=True`), DRF passes this value as a keyword argument
3. The keyword argument name matches the `lookup_field` value (e.g., `uuid=<value>`)
4. If the action method doesn't accept this parameter, Python raises `TypeError`

### Incorrect Implementation

```python
class DiagnosisCardViewSet(viewsets.ModelViewSet):
    lookup_field = 'uuid'  # Using UUID instead of pk

    @action(detail=True, methods=['post'])
    def toggle_favorite(self, request: Request) -> Response:
        # ❌ Missing uuid parameter - will fail!
        card = self.get_object()
        # ...
```

### Correct Implementation

```python
class DiagnosisCardViewSet(viewsets.ModelViewSet):
    lookup_field = 'uuid'  # Using UUID instead of pk

    @action(detail=True, methods=['post'])
    def toggle_favorite(self, request: Request, uuid=None) -> Response:
        # ✅ Accepts uuid parameter - DRF will pass it
        card = self.get_object()  # get_object() uses lookup_field automatically
        card.is_favorite = not card.is_favorite
        card.save(update_fields=['is_favorite'])
        serializer = DiagnosisCardDetailSerializer(card, context={'request': request})
        return Response(serializer.data)
```

### Critical Rules

1. **ALL custom actions with `detail=True` MUST accept the lookup field parameter**
2. **Parameter name MUST match `lookup_field` value** (e.g., `uuid=None` when `lookup_field = 'uuid'`)
3. **Parameter should default to `None`** (DRF will always pass a value)
4. **Use `self.get_object()` instead of manual lookup** (respects `lookup_field` automatically)

### Applies To

This pattern affects **ALL** detail-level custom actions in the codebase:

**DiagnosisCardViewSet** (`diagnosis_viewsets.py`):
- `toggle_favorite(self, request, uuid=None)` - Line 198
- All future custom actions on this viewset

**DiagnosisReminderViewSet** (`diagnosis_viewsets.py`):
- `snooze(self, request, uuid=None)` - Line 320
- `cancel(self, request, uuid=None)` - Line 339
- `acknowledge(self, request, uuid=None)` - Line 353
- All future custom actions on this viewset

### Detection in Code Reviews

**Red Flags**:
```python
# ❌ ViewSet has lookup_field but action missing parameter
class MyViewSet(viewsets.ModelViewSet):
    lookup_field = 'uuid'

    @action(detail=True, methods=['post'])
    def my_action(self, request):  # ← Missing uuid parameter!
        pass

# ❌ Action has wrong parameter name
@action(detail=True, methods=['post'])
def my_action(self, request, pk=None):  # ← Should be uuid=None
    pass

# ❌ Action manually looks up by UUID instead of using get_object()
@action(detail=True, methods=['post'])
def my_action(self, request, uuid=None):
    obj = MyModel.objects.get(uuid=uuid)  # ← Don't do this!
    # Use self.get_object() instead
```

**Green Flags**:
```python
# ✅ Correct pattern
class MyViewSet(viewsets.ModelViewSet):
    lookup_field = 'uuid'

    @action(detail=True, methods=['post'])
    def my_action(self, request, uuid=None):  # ✅ Accepts uuid
        obj = self.get_object()  # ✅ Uses get_object()
        # ...
```

---

## Pattern 2: SlugRelatedField for UUID Relationships

### Problem

When creating objects with related UUID fields, serializers fail with:

```python
ValidationError: {'diagnosis_result': [ErrorDetail(string='Incorrect type. Expected pk value, received str.', code='incorrect_type')]}
```

This happens when using `PrimaryKeyRelatedField` with UUID-based models.

### Root Cause

`PrimaryKeyRelatedField` expects integer primary keys by default. When models use UUID primary keys, you must use `SlugRelatedField` with `slug_field='uuid'` to accept UUID strings from API clients.

### Incorrect Implementation

```python
class DiagnosisCardCreateSerializer(serializers.ModelSerializer):
    diagnosis_result = serializers.PrimaryKeyRelatedField(
        # ❌ Expects integer pk, but model uses UUID
        queryset=PlantDiseaseResult.objects.all(),
        required=False,
        allow_null=True,
    )
```

### Correct Implementation

```python
class DiagnosisCardCreateSerializer(serializers.ModelSerializer):
    diagnosis_result = serializers.SlugRelatedField(
        slug_field='uuid',  # ✅ Accepts UUID strings
        queryset=PlantDiseaseResult.objects.all(),
        required=False,
        allow_null=True,
        help_text="UUID of the diagnosis result (optional - can be created from API data)"
    )
```

### When to Use

**Use `SlugRelatedField`** when:
- Related model uses UUID as primary key
- API clients send UUID strings (e.g., `"550e8400-e29b-41d4-a716-446655440000"`)
- You want human-readable identifiers in API requests/responses

**Use `PrimaryKeyRelatedField`** when:
- Related model uses integer auto-increment primary key
- API clients send integer IDs (e.g., `42`)
- Legacy API compatibility required

### Example from Codebase

**DiagnosisCardCreateSerializer** (`diagnosis_serializers.py:212-218`):
```python
diagnosis_result = serializers.SlugRelatedField(
    slug_field='uuid',
    queryset=PlantDiseaseResult.objects.all(),
    required=False,
    allow_null=True,
    help_text="UUID of the diagnosis result (optional - can be created from API data)"
)
```

**DiagnosisReminderSerializer** (`diagnosis_serializers.py:304-308`):
```python
diagnosis_card = serializers.SlugRelatedField(
    slug_field='uuid',
    queryset=DiagnosisCard.objects.all(),
    help_text="UUID of the diagnosis card this reminder is for"
)
```

### API Request Example

```json
POST /api/v1/diagnosis-cards/
{
  "diagnosis_result": "550e8400-e29b-41d4-a716-446655440000",  // ✅ UUID string accepted
  "plant_scientific_name": "Aloe vera",
  "disease_name": "Root rot",
  // ... other fields
}
```

### Detection in Code Reviews

**Red Flags**:
```python
# ❌ UUID model with PrimaryKeyRelatedField
class MyModel(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)

class MySerializer(serializers.ModelSerializer):
    related = serializers.PrimaryKeyRelatedField(...)  # ← Wrong!

# ❌ Missing slug_field specification
related = serializers.SlugRelatedField(
    queryset=MyModel.objects.all()  # ← Missing slug_field='uuid'
)
```

**Green Flags**:
```python
# ✅ UUID model with SlugRelatedField
class MyModel(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)

class MySerializer(serializers.ModelSerializer):
    related = serializers.SlugRelatedField(
        slug_field='uuid',  # ✅ Correct
        queryset=MyModel.objects.all(),
        required=False,
        allow_null=True,
    )
```

---

## Pattern 3: Avoiding Duplicate Keyword Arguments in Tests

### Problem

Tests fail with:

```python
TypeError: QuerySet.create() got multiple values for keyword argument 'treatment_status'
```

This happens when passing the same keyword argument both explicitly and via `**kwargs`.

### Root Cause

Python doesn't allow duplicate keyword arguments. When you do:
```python
Model.objects.create(field='value', **{'field': 'value'})
```

Python sees `field` twice and raises `TypeError`.

### Incorrect Implementation

```python
# Test setup with shared data
self.card_data = {
    'plant_scientific_name': 'Aloe vera',
    'treatment_status': 'not_started',  # ← Already in dict
    # ... other fields
}

# Test case
def test_filter_by_treatment_status(self):
    # Create cards with different statuses
    DiagnosisCard.objects.create(
        user=self.user1,
        treatment_status='not_started',  # ❌ Duplicate!
        **self.card_data  # ← Already contains treatment_status
    )
```

### Correct Implementation

**Option 1: Remove from explicit args (prefer this)**
```python
def test_filter_by_treatment_status(self):
    # First card with not_started status (from self.card_data)
    DiagnosisCard.objects.create(
        user=self.user1,
        **self.card_data  # ✅ Uses treatment_status from dict
    )

    # Second card with custom status
    card_data_in_progress = self.card_data.copy()
    card_data_in_progress['treatment_status'] = 'in_progress'
    DiagnosisCard.objects.create(
        user=self.user1,
        **card_data_in_progress  # ✅ No duplicates
    )
```

**Option 2: Remove from dict before spreading**
```python
def test_filter_by_treatment_status(self):
    # Create modified dict without treatment_status
    card_data_without_status = self.card_data.copy()
    card_data_without_status.pop('treatment_status')

    # Now safe to pass explicit status
    DiagnosisCard.objects.create(
        user=self.user1,
        treatment_status='not_started',
        **card_data_without_status  # ✅ No treatment_status in dict
    )
```

### Prevention Strategy

1. **Be explicit about what's in shared test data**: Document which fields are in `self.card_data`
2. **Use `.copy()` before modifying**: Never mutate shared test data
3. **Prefer Option 1**: Override fields by modifying a copy of the dict

### Example from Codebase

**Before** (`test_diagnosis_api.py:208-212`):
```python
# ❌ Duplicate treatment_status
DiagnosisCard.objects.create(
    user=self.user1,
    treatment_status='not_started',  # Explicit
    **self.card_data  # Contains treatment_status='not_started'
)
```

**After** (`test_diagnosis_api.py:208-212`):
```python
# ✅ No duplicates
# First card with not_started status (from self.card_data)
DiagnosisCard.objects.create(
    user=self.user1,
    **self.card_data
)

# Second card with in_progress status
card_data_in_progress = self.card_data.copy()
card_data_in_progress['treatment_status'] = 'in_progress'
DiagnosisCard.objects.create(
    user=self.user2,
    **card_data_in_progress
)
```

### Detection in Code Reviews

**Red Flags**:
```python
# ❌ Obvious duplicate
obj = Model.create(field='value', **{'field': 'other_value'})

# ❌ Hidden duplicate with shared data
shared_data = {'field': 'value'}
obj = Model.create(field='value', **shared_data)

# ❌ Mutating shared test data
self.base_data['field'] = 'new_value'  # Changes for all tests!
```

**Green Flags**:
```python
# ✅ No duplicates
obj = Model.create(**shared_data)

# ✅ Explicit override with copy
data = shared_data.copy()
data['field'] = 'new_value'
obj = Model.create(**data)

# ✅ Remove before explicit override
data = shared_data.copy()
data.pop('field')
obj = Model.create(field='new_value', **data)
```

---

## Pattern 4: Test Data Consistency with Model Choices

### Problem

Tests fail with assertion errors:

```python
AssertionError: 'treatment_step' != 'treatment'
```

This happens when test data is corrected to use valid model choices, but assertions still expect the old invalid values.

### Root Cause

Django model fields with `choices` only accept specific values. When test data is fixed to use valid choices, ALL assertions must be updated to match.

### Incorrect Implementation

```python
# Model with choices
class DiagnosisReminder(models.Model):
    REMINDER_TYPE_CHOICES = [
        ('check_progress', 'Check Progress'),
        ('treatment_step', 'Treatment Step'),  # ← Valid choice
        ('follow_up', 'Follow-up'),
        ('reapply', 'Reapply Treatment'),
    ]
    reminder_type = models.CharField(max_length=20, choices=REMINDER_TYPE_CHOICES)

# Test data (fixed to use valid choice)
reminder_data = {
    'reminder_type': 'treatment_step',  # ✅ Valid choice
    # ...
}

# Test assertion (not updated)
def test_create_reminder(self):
    response = self.client.post(url, reminder_data, format='json')
    self.assertEqual(response.data['reminder_type'], 'treatment')  # ❌ Old value!
```

### Correct Implementation

```python
# Test assertion (updated to match valid choice)
def test_create_reminder(self):
    response = self.client.post(url, reminder_data, format='json')
    self.assertEqual(response.data['reminder_type'], 'treatment_step')  # ✅ Matches test data
```

### Prevention Strategy

1. **Always validate test data against model choices**: Check `Model._meta.get_field('field_name').choices`
2. **Update ALL assertions when fixing test data**: Use find/replace to update expected values
3. **Use constants for choices**: Define choices as module-level constants and import in tests

### Example with Constants

**Better approach** (using constants):

```python
# models.py
class DiagnosisReminder(models.Model):
    # Choice constants (reusable in tests)
    REMINDER_TYPE_CHECK_PROGRESS = 'check_progress'
    REMINDER_TYPE_TREATMENT_STEP = 'treatment_step'
    REMINDER_TYPE_FOLLOW_UP = 'follow_up'
    REMINDER_TYPE_REAPPLY = 'reapply'

    REMINDER_TYPE_CHOICES = [
        (REMINDER_TYPE_CHECK_PROGRESS, 'Check Progress'),
        (REMINDER_TYPE_TREATMENT_STEP, 'Treatment Step'),
        (REMINDER_TYPE_FOLLOW_UP, 'Follow-up'),
        (REMINDER_TYPE_REAPPLY, 'Reapply Treatment'),
    ]

    reminder_type = models.CharField(
        max_length=20,
        choices=REMINDER_TYPE_CHOICES,
        default=REMINDER_TYPE_CHECK_PROGRESS
    )

# test_diagnosis_api.py
from apps.plant_identification.models import DiagnosisReminder

def test_create_reminder(self):
    reminder_data = {
        'reminder_type': DiagnosisReminder.REMINDER_TYPE_TREATMENT_STEP,  # ✅ Use constant
        # ...
    }
    response = self.client.post(url, reminder_data, format='json')
    # ✅ Use same constant in assertion
    self.assertEqual(
        response.data['reminder_type'],
        DiagnosisReminder.REMINDER_TYPE_TREATMENT_STEP
    )
```

### Detection in Code Reviews

**Red Flags**:
```python
# ❌ Hardcoded invalid choice
data = {'status': 'wrong_value'}  # Not in model choices

# ❌ Test data and assertion mismatch
data = {'status': 'active'}
assert response.data['status'] == 'pending'  # ← Different value!

# ❌ Magic strings in tests
data = {'status': 'active'}  # What if model choices change?
```

**Green Flags**:
```python
# ✅ Use model constants
data = {'status': MyModel.STATUS_ACTIVE}
assert response.data['status'] == MyModel.STATUS_ACTIVE

# ✅ Validate against model choices
valid_statuses = [choice[0] for choice in MyModel.STATUS_CHOICES]
assert data['status'] in valid_statuses

# ✅ Test data matches assertions
data = {'status': 'active'}
assert response.data['status'] == 'active'  # ✅ Consistent
```

---

## Pattern 5: Comprehensive Integration Test Coverage

### Problem

API endpoints work in manual testing but break in production due to untested edge cases.

### Solution

Write comprehensive integration tests covering:
1. **CRUD operations** (Create, Read, Update, Delete)
2. **Authentication and permissions** (anonymous, authenticated, owner-only)
3. **Validation** (required fields, invalid data, field constraints)
4. **Filtering and search** (query parameters, multiple filters)
5. **Custom actions** (toggle, snooze, cancel, acknowledge)
6. **Pagination** (large datasets, page navigation)
7. **Edge cases** (empty results, non-existent objects, duplicate requests)

### Test Organization Pattern

**Location**: `/backend/apps/plant_identification/test_diagnosis_api.py`

**Structure**:
```python
class TestDiagnosisCardAPI(APITestCase):
    """Integration tests for DiagnosisCard API endpoints."""

    def setUp(self):
        """Create test users, authentication, and shared test data."""
        # User setup
        # Authentication setup
        # Shared test data setup

    # Authentication tests
    def test_list_requires_authentication(self):
        """Anonymous users cannot list diagnosis cards."""
        # ...

    # CRUD tests
    def test_list_diagnosis_cards(self):
        """Authenticated users can list their own cards."""
        # ...

    def test_create_diagnosis_card(self):
        """Users can create new diagnosis cards."""
        # ...

    def test_retrieve_diagnosis_card(self):
        """Users can retrieve their own card details."""
        # ...

    def test_update_diagnosis_card(self):
        """Users can update their own cards."""
        # ...

    def test_delete_diagnosis_card(self):
        """Users can delete their own cards."""
        # ...

    # Validation tests
    def test_create_diagnosis_card_validation(self):
        """Validation errors for invalid data."""
        # ...

    # Filtering tests
    def test_filter_by_treatment_status(self):
        """Filter cards by treatment status."""
        # ...

    def test_filter_by_favorite(self):
        """Filter favorite cards only."""
        # ...

    # Search tests
    def test_search_diagnosis_cards(self):
        """Search cards by plant/disease names."""
        # ...

    # Custom action tests
    def test_favorites_action(self):
        """Custom action returns favorite cards."""
        # ...

    def test_toggle_favorite_action(self):
        """Toggle favorite status of a card."""
        # ...

    # Pagination tests
    def test_pagination(self):
        """List endpoint is paginated."""
        # ...

    # Permission tests
    def test_cannot_access_other_user_cards(self):
        """Users cannot access other users' cards."""
        # ...
```

### Test Data Setup Pattern

```python
def setUp(self):
    """Create reusable test data."""
    # Users
    self.user1 = User.objects.create_user(
        username='user1',
        email='user1@example.com',
        password='testpass123'
    )
    self.user2 = User.objects.create_user(
        username='user2',
        email='user2@example.com',
        password='testpass123'
    )

    # Authentication
    self.client = APIClient()
    self.client.force_authenticate(user=self.user1)

    # Base test data (reusable across tests)
    self.card_data = {
        'plant_scientific_name': 'Aloe vera',
        'plant_common_name': 'Aloe',
        'disease_name': 'Root rot',
        'disease_type': 'fungal',
        'severity_assessment': 'moderate',
        'confidence_score': 0.92,
        'treatment_status': 'not_started',
        'care_instructions': [
            {
                'type': 'heading',
                'value': {'text': 'Treatment Steps', 'level': 2}
            },
            {
                'type': 'paragraph',
                'value': 'Remove affected roots and repot in fresh soil.'
            }
        ],
    }
```

### Coverage Metrics

**Current coverage** (20 tests):
- ✅ Authentication: 2 tests (anonymous access, authenticated access)
- ✅ CRUD operations: 6 tests (list, create, retrieve, update, delete, create with optional fields)
- ✅ Validation: 1 test (required fields)
- ✅ Filtering: 3 tests (treatment status, favorite, plant recovery)
- ✅ Search: 1 test (plant/disease name search)
- ✅ Custom actions: 5 tests (favorites list, toggle favorite, active treatments, successful treatments, reminders)
- ✅ Pagination: 1 test (large dataset)
- ✅ Permissions: 1 test (cannot access other user's cards)

**Reminder API coverage** (8 tests):
- ✅ CRUD: 4 tests (list, create, retrieve, delete)
- ✅ Validation: 2 tests (card ownership, future date requirement)
- ✅ Custom actions: 3 tests (snooze, cancel, acknowledge)
- ✅ Filtering: 1 test (upcoming reminders)

### Example Test Implementation

```python
def test_toggle_favorite_action(self):
    """Toggle favorite status of a diagnosis card."""
    # Create a card
    card = DiagnosisCard.objects.create(
        user=self.user1,
        is_favorite=False,
        **self.card_data
    )

    # Toggle favorite on
    url = reverse('v1:plant_identification:diagnosiscard-toggle-favorite', kwargs={'uuid': card.uuid})
    response = self.client.post(url)

    self.assertEqual(response.status_code, status.HTTP_200_OK)
    self.assertTrue(response.data['is_favorite'])

    # Verify database updated
    card.refresh_from_db()
    self.assertTrue(card.is_favorite)

    # Toggle favorite off
    response = self.client.post(url)

    self.assertEqual(response.status_code, status.HTTP_200_OK)
    self.assertFalse(response.data['is_favorite'])

    # Verify database updated
    card.refresh_from_db()
    self.assertFalse(card.is_favorite)
```

### Test Naming Convention

**Pattern**: `test_<action>_<scenario>`

**Examples**:
- `test_list_diagnosis_cards` - Basic list functionality
- `test_list_requires_authentication` - Authentication requirement
- `test_create_diagnosis_card_validation` - Validation rules
- `test_filter_by_treatment_status` - Filtering behavior
- `test_cannot_access_other_user_cards` - Permission enforcement

### Detection in Code Reviews

**Red Flags**:
```python
# ❌ Only testing happy path
def test_create_card(self):
    response = self.client.post(url, valid_data)
    assert response.status_code == 201
    # Missing: validation errors, authentication, permissions

# ❌ Not verifying database changes
def test_update_card(self):
    response = self.client.patch(url, data)
    assert response.status_code == 200
    # Missing: card.refresh_from_db() and assertions

# ❌ Testing multiple things in one test
def test_everything(self):
    # Creates, updates, deletes, filters, searches...
    # Should be split into separate tests
```

**Green Flags**:
```python
# ✅ Clear, focused test
def test_update_diagnosis_card(self):
    """Users can update their own cards."""
    card = DiagnosisCard.objects.create(user=self.user1, ...)

    update_data = {'personal_notes': 'Updated notes'}
    url = reverse('...', kwargs={'uuid': card.uuid})
    response = self.client.patch(url, update_data)

    self.assertEqual(response.status_code, 200)
    self.assertEqual(response.data['personal_notes'], 'Updated notes')

    # ✅ Verify database changed
    card.refresh_from_db()
    self.assertEqual(card.personal_notes, 'Updated notes')

# ✅ Testing edge cases
def test_create_card_without_required_fields(self):
    """Validation error when required fields missing."""
    response = self.client.post(url, {})
    self.assertEqual(response.status_code, 400)
    self.assertIn('plant_scientific_name', response.data)
```

---

## Pattern 6: UUID Lookup Field Configuration

### Problem

ViewSets default to using integer `pk` for lookups, but models use UUID primary keys. This causes 404 errors when accessing objects by UUID.

### Solution

Configure `lookup_field = 'uuid'` on ViewSets that work with UUID-based models.

### Implementation

```python
class DiagnosisCardViewSet(viewsets.ModelViewSet):
    """ViewSet for diagnosis cards."""

    permission_classes = [IsAuthenticated]
    lookup_field = 'uuid'  # ✅ Use UUID instead of integer pk

    def get_queryset(self):
        return DiagnosisCard.objects.filter(user=self.request.user)
```

### URL Pattern

When `lookup_field = 'uuid'` is set, DRF expects UUID in URLs:

```python
# URL routing
path('diagnosis-cards/<uuid:uuid>/', viewset.as_view({'get': 'retrieve'}))

# Example URL
# ✅ /api/v1/diagnosis-cards/550e8400-e29b-41d4-a716-446655440000/
# ❌ /api/v1/diagnosis-cards/42/  (integer pk won't work)
```

### Related Pattern

This setting affects:
1. **Detail endpoints**: retrieve, update, partial_update, destroy
2. **Custom actions with `detail=True`**: Must accept `uuid=None` parameter (see Pattern 1)
3. **URL reverse lookups**: Must pass `uuid` kwarg instead of `pk`

### Example from Codebase

**DiagnosisCardViewSet** (`diagnosis_viewsets.py:30-62`):
```python
class DiagnosisCardViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    lookup_field = 'uuid'  # ✅ UUID lookup

    def get_queryset(self):
        return DiagnosisCard.objects.filter(user=self.request.user)

    @action(detail=True, methods=['post'])
    def toggle_favorite(self, request, uuid=None):  # ✅ Accepts uuid parameter
        card = self.get_object()  # ✅ Uses lookup_field automatically
        # ...
```

**DiagnosisReminderViewSet** (`diagnosis_viewsets.py:213-237`):
```python
class DiagnosisReminderViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    lookup_field = 'uuid'  # ✅ UUID lookup

    def get_queryset(self):
        return DiagnosisReminder.objects.filter(diagnosis_card__user=self.request.user)
```

---

## Testing Checklist

Use this checklist when implementing new API endpoints with UUID lookups:

### ViewSet Configuration
- [ ] Set `lookup_field = 'uuid'` on ViewSet class
- [ ] All custom `@action(detail=True)` methods accept `uuid=None` parameter
- [ ] Use `self.get_object()` instead of manual UUID lookups
- [ ] QuerySet filtered by current user for security

### Serializer Configuration
- [ ] Related UUID fields use `SlugRelatedField(slug_field='uuid')`
- [ ] Validation methods check user ownership
- [ ] Display methods use `get_<field>_display()` for choice fields
- [ ] Type hints on all custom methods

### Model Configuration
- [ ] UUID primary key: `uuid = models.UUIDField(primary_key=True, default=uuid.uuid4)`
- [ ] Choice fields use constants (e.g., `STATUS_ACTIVE = 'active'`)
- [ ] Related models use `on_delete=models.CASCADE` or `models.SET_NULL`
- [ ] Indexes on frequently queried fields

### Test Coverage
- [ ] Authentication tests (anonymous, authenticated)
- [ ] CRUD operation tests (create, read, update, delete)
- [ ] Validation tests (required fields, invalid data)
- [ ] Filtering tests (query parameters)
- [ ] Search tests (full-text search)
- [ ] Custom action tests (all `@action` methods)
- [ ] Pagination tests (large datasets)
- [ ] Permission tests (user isolation)
- [ ] Edge case tests (empty results, non-existent objects)

### Integration
- [ ] URLs configured with `<uuid:uuid>` parameter
- [ ] API documentation updated (OpenAPI/Swagger)
- [ ] Frontend service updated with UUID handling
- [ ] All tests passing (100%)

---

## Summary

These 6 patterns are essential for working with the diagnosis API feature:

1. **DRF Custom Actions with UUID Lookup** - Custom actions must accept `uuid=None` parameter when `lookup_field = 'uuid'`
2. **SlugRelatedField for UUID Relationships** - Use `SlugRelatedField(slug_field='uuid')` for related UUID fields
3. **Avoiding Duplicate Keyword Arguments** - Never pass same keyword both explicitly and via `**kwargs`
4. **Test Data Consistency with Model Choices** - Update ALL assertions when fixing test data choices
5. **Comprehensive Integration Test Coverage** - Test CRUD, auth, validation, filtering, actions, pagination, permissions
6. **UUID Lookup Field Configuration** - Set `lookup_field = 'uuid'` on ViewSets with UUID models

**Production Status**: All patterns validated with 20/20 tests passing (100%)

**Files to Reference**:
- `/backend/TEST_FIXES_PLAN.md` - Detailed fix plan with root cause analysis
- `/backend/apps/plant_identification/api/diagnosis_viewsets.py` - ViewSet implementations
- `/backend/apps/plant_identification/api/diagnosis_serializers.py` - Serializer implementations
- `/backend/apps/plant_identification/test_diagnosis_api.py` - Comprehensive test suite

**Related Documentation**:
- `/backend/docs/testing/AUTHENTICATION_TESTS.md` - Testing patterns
- `/backend/docs/architecture/analysis.md` - Design decisions
- `CLAUDE.md` - Project-wide patterns and conventions
