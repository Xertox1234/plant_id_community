# Diagnosis API & UUID Patterns

**Last Updated**: November 13, 2025
**Consolidated From**: `DIAGNOSIS_API_PATTERNS_CODIFIED.md`
**Status**: ✅ Production-Tested (20/20 tests passing)

---

## Table of Contents

1. [DRF Custom Actions with UUID Lookup](#drf-custom-actions-with-uuid-lookup)
2. [SlugRelatedField for UUID Relationships](#slugrelatedfield-for-uuid-relationships)
3. [UUID Lookup Field Configuration](#uuid-lookup-field-configuration)
4. [Test Data Consistency](#test-data-consistency)
5. [Integration Test Patterns](#integration-test-patterns)
6. [Common Pitfalls](#common-pitfalls)

---

## DRF Custom Actions with UUID Lookup

### Problem: TypeError with Custom Actions

**Issue**: When using `lookup_field = 'uuid'` on a ViewSet, custom `@action` methods fail with:

```python
TypeError: toggle_favorite() got an unexpected keyword argument 'uuid'
```

**Root Cause**: DRF's routing mechanism:
1. When `lookup_field = 'uuid'` is set, DRF extracts the UUID from URL
2. For detail-level actions (`detail=True`), DRF passes this as a keyword argument
3. The keyword argument name matches the `lookup_field` value (e.g., `uuid=<value>`)
4. If the action method doesn't accept this parameter, Python raises `TypeError`

### Pattern: Accept Lookup Field Parameter

**Anti-Pattern** ❌:
```python
class DiagnosisCardViewSet(viewsets.ModelViewSet):
    lookup_field = 'uuid'  # Using UUID instead of pk

    @action(detail=True, methods=['post'])
    def toggle_favorite(self, request: Request) -> Response:
        # ❌ Missing uuid parameter - will fail!
        card = self.get_object()
        # ...
```

**Correct Pattern** ✅:
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

### Examples from Codebase

**DiagnosisCardViewSet** (`diagnosis_viewsets.py`):
```python
@action(detail=True, methods=['post'])
def toggle_favorite(self, request: Request, uuid=None) -> Response:
    """Toggle favorite status of a diagnosis card."""
    card = self.get_object()  # ✅ Respects lookup_field='uuid'
    card.is_favorite = not card.is_favorite
    card.save(update_fields=['is_favorite'])
    return Response(DiagnosisCardDetailSerializer(card, context={'request': request}).data)
```

**DiagnosisReminderViewSet** (`diagnosis_viewsets.py`):
```python
@action(detail=True, methods=['post'])
def snooze(self, request: Request, uuid=None) -> Response:
    """Snooze a reminder for a specified duration."""
    reminder = self.get_object()  # ✅ Respects lookup_field='uuid'
    # ...
    return Response(DiagnosisReminderDetailSerializer(reminder).data)

@action(detail=True, methods=['post'])
def cancel(self, request: Request, uuid=None) -> Response:
    """Cancel a reminder permanently."""
    reminder = self.get_object()
    # ...

@action(detail=True, methods=['post'])
def acknowledge(self, request: Request, uuid=None) -> Response:
    """Mark a reminder as acknowledged."""
    reminder = self.get_object()
    # ...
```

### Code Review Red Flags

**❌ Missing UUID Parameter**:
```python
@action(detail=True, methods=['post'])
def my_action(self, request):  # ← Missing uuid parameter!
    pass
```

**❌ Wrong Parameter Name**:
```python
@action(detail=True, methods=['post'])
def my_action(self, request, pk=None):  # ← Should be uuid=None
    pass
```

**❌ Manual UUID Lookup**:
```python
@action(detail=True, methods=['post'])
def my_action(self, request, uuid=None):
    obj = MyModel.objects.get(uuid=uuid)  # ← Don't do this!
    # Use self.get_object() instead
```

**✅ Correct Pattern**:
```python
@action(detail=True, methods=['post'])
def my_action(self, request, uuid=None):  # ✅ Accepts uuid
    obj = self.get_object()  # ✅ Uses get_object()
    # ...
```

---

## SlugRelatedField for UUID Relationships

### Problem: UUID Validation Errors

**Issue**: When creating objects with related UUID fields, serializers fail with:

```python
ValidationError: {'diagnosis_result': [
    ErrorDetail(string='Incorrect type. Expected pk value, received str.', code='incorrect_type')
]}
```

**Root Cause**: `PrimaryKeyRelatedField` expects integer primary keys by default. When models use UUID primary keys, you must use `SlugRelatedField` with `slug_field='uuid'` to accept UUID strings from API clients.

### Pattern: SlugRelatedField for UUID Models

**Anti-Pattern** ❌:
```python
class DiagnosisCardCreateSerializer(serializers.ModelSerializer):
    diagnosis_result = serializers.PrimaryKeyRelatedField(
        # ❌ Expects integer pk, but model uses UUID
        queryset=PlantDiseaseResult.objects.all(),
        required=False,
        allow_null=True,
    )
```

**Correct Pattern** ✅:
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

### Examples from Codebase

**DiagnosisCardCreateSerializer** (`diagnosis_serializers.py`):
```python
class DiagnosisCardCreateSerializer(serializers.ModelSerializer):
    diagnosis_result = serializers.SlugRelatedField(
        slug_field='uuid',
        queryset=PlantDiseaseResult.objects.all(),
        required=False,
        allow_null=True,
        help_text="UUID of the diagnosis result (optional - can be created from API data)"
    )

    class Meta:
        model = DiagnosisCard
        fields = [
            'title',
            'notes',
            'diagnosis_result',
            'custom_diagnosis',
            'severity',
            'is_favorite'
        ]
```

**DiagnosisReminderSerializer** (`diagnosis_serializers.py`):
```python
class DiagnosisReminderSerializer(serializers.ModelSerializer):
    diagnosis_card = serializers.SlugRelatedField(
        slug_field='uuid',
        queryset=DiagnosisCard.objects.all(),
        help_text="UUID of the diagnosis card this reminder is for"
    )

    class Meta:
        model = DiagnosisReminder
        fields = [
            'uuid',
            'diagnosis_card',
            'reminder_date',
            'reminder_type',
            'notes'
        ]
```

### Testing Pattern

```python
def test_create_diagnosis_card_with_uuid_result(self):
    """Test creating diagnosis card with UUID reference to diagnosis result."""
    # Create diagnosis result
    result = PlantDiseaseResult.objects.create(
        plant_name="Sick Rose",
        confidence=0.92
    )

    # Create diagnosis card referencing result by UUID
    response = self.client.post(
        '/api/v1/plant-identification/diagnosis-cards/',
        {
            'title': 'Powdery Mildew on Rose',
            'notes': 'White powder on leaves',
            'diagnosis_result': str(result.uuid),  # ✅ UUID string
            'severity': 'moderate'
        },
        format='json'
    )

    self.assertEqual(response.status_code, 201)
    self.assertEqual(response.data['diagnosis_result'], str(result.uuid))
```

---

## UUID Lookup Field Configuration

### Pattern: ViewSet UUID Configuration

**Location**: `apps/plant_identification/api/diagnosis_viewsets.py`

```python
class DiagnosisCardViewSet(viewsets.ModelViewSet):
    """
    ViewSet for DiagnosisCard CRUD operations.

    Uses UUID for lookups instead of integer primary keys.
    All detail-level routes use UUID in URL: /api/.../diagnosis-cards/{uuid}/
    """
    queryset = DiagnosisCard.objects.all()
    serializer_class = DiagnosisCardSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    # ✅ Critical: Tells DRF to use 'uuid' field for lookups instead of 'pk'
    lookup_field = 'uuid'

    # ✅ Critical: Tells DRF the URL parameter name to extract
    lookup_url_kwarg = 'uuid'

    def get_queryset(self):
        """Filter to user's own diagnosis cards."""
        if self.request.user.is_authenticated:
            return DiagnosisCard.objects.filter(user=self.request.user)
        return DiagnosisCard.objects.none()

    def get_serializer_class(self):
        """Use different serializers for different actions."""
        if self.action == 'create':
            return DiagnosisCardCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return DiagnosisCardUpdateSerializer
        elif self.action == 'retrieve':
            return DiagnosisCardDetailSerializer
        return DiagnosisCardSerializer

    @action(detail=True, methods=['post'])
    def toggle_favorite(self, request: Request, uuid=None) -> Response:
        # ✅ All custom actions must accept uuid parameter
        card = self.get_object()
        # ...
```

### URL Configuration

**Location**: `apps/plant_identification/urls.py`

```python
from rest_framework.routers import DefaultRouter
from .api.diagnosis_viewsets import DiagnosisCardViewSet, DiagnosisReminderViewSet

router = DefaultRouter()

# ✅ Register viewsets - router automatically uses lookup_field from ViewSet
router.register('diagnosis-cards', DiagnosisCardViewSet, basename='diagnosiscard')
router.register('diagnosis-reminders', DiagnosisReminderViewSet, basename='diagnosisreminder')

urlpatterns = router.urls

# Generated URLs:
# /api/v1/plant-identification/diagnosis-cards/
# /api/v1/plant-identification/diagnosis-cards/{uuid}/
# /api/v1/plant-identification/diagnosis-cards/{uuid}/toggle_favorite/
# /api/v1/plant-identification/diagnosis-reminders/{uuid}/snooze/
```

---

## Test Data Consistency

### Problem: Model Choice Validation Failures

**Issue**: Tests fail with validation errors when using invalid choice values:

```python
ValidationError: {'severity': [ErrorDetail(string='"low" is not a valid choice.', code='invalid_choice')]}
```

**Root Cause**: Test data uses invalid choice values that don't match model field `choices` definition.

### Pattern: Match Model Choices Exactly

**Model Definition**:
```python
class DiagnosisCard(models.Model):
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('moderate', 'Moderate'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        default='low',
        help_text="Severity level of the diagnosis"
    )
```

**Anti-Pattern** ❌:
```python
def test_create_diagnosis_card(self):
    response = self.client.post(
        '/api/v1/plant-identification/diagnosis-cards/',
        {
            'title': 'Fungal Infection',
            'severity': 'medium',  # ❌ Not in SEVERITY_CHOICES!
        },
        format='json'
    )
    # Fails with: '"medium" is not a valid choice.'
```

**Correct Pattern** ✅:
```python
def test_create_diagnosis_card(self):
    response = self.client.post(
        '/api/v1/plant-identification/diagnosis-cards/',
        {
            'title': 'Fungal Infection',
            'severity': 'moderate',  # ✅ Matches model choice
        },
        format='json'
    )
    self.assertEqual(response.status_code, 201)
```

### Key Points

- ✅ Always use exact choice values from model definition
- ✅ Verify choice values in model before writing tests
- ✅ Use constants if choices are defined in `constants.py`
- ❌ Never guess at choice values based on similar words

---

## Integration Test Patterns

### Pattern: Comprehensive CRUD Testing

**Location**: `apps/plant_identification/test_diagnosis_api.py`

```python
class DiagnosisCardAPITestCase(APITestCase):
    """
    Integration tests for DiagnosisCard API endpoints.

    Tests all CRUD operations + custom actions.
    """

    def setUp(self):
        """Create test user and authenticate client."""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

        # Create test diagnosis result
        self.diagnosis_result = PlantDiseaseResult.objects.create(
            plant_name="Test Disease",
            confidence=0.85
        )

    def test_create_diagnosis_card(self):
        """Test creating a diagnosis card."""
        response = self.client.post(
            '/api/v1/plant-identification/diagnosis-cards/',
            {
                'title': 'Powdery Mildew',
                'notes': 'White powder on leaves',
                'diagnosis_result': str(self.diagnosis_result.uuid),
                'severity': 'moderate',
                'is_favorite': False
            },
            format='json'
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['title'], 'Powdery Mildew')
        self.assertIsNotNone(response.data['uuid'])

    def test_retrieve_diagnosis_card(self):
        """Test retrieving a specific diagnosis card by UUID."""
        card = DiagnosisCard.objects.create(
            user=self.user,
            title='Fungal Infection',
            severity='high'
        )

        response = self.client.get(
            f'/api/v1/plant-identification/diagnosis-cards/{card.uuid}/'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['uuid'], str(card.uuid))
        self.assertEqual(response.data['title'], 'Fungal Infection')

    def test_toggle_favorite_action(self):
        """Test toggling favorite status (custom action)."""
        card = DiagnosisCard.objects.create(
            user=self.user,
            title='Test Card',
            is_favorite=False
        )

        # Toggle to favorite
        response = self.client.post(
            f'/api/v1/plant-identification/diagnosis-cards/{card.uuid}/toggle_favorite/'
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['is_favorite'])

        # Toggle back
        response = self.client.post(
            f'/api/v1/plant-identification/diagnosis-cards/{card.uuid}/toggle_favorite/'
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['is_favorite'])

    def test_user_isolation(self):
        """Test that users can only access their own cards."""
        other_user = User.objects.create_user(
            username='otheruser',
            password='password123'
        )
        other_card = DiagnosisCard.objects.create(
            user=other_user,
            title='Other User Card'
        )

        # Current user should not see other user's card
        response = self.client.get(
            f'/api/v1/plant-identification/diagnosis-cards/{other_card.uuid}/'
        )

        self.assertEqual(response.status_code, 404)
```

### Test Coverage Checklist

For each ViewSet with UUID lookup:
- [ ] Test CREATE (POST to list endpoint)
- [ ] Test RETRIEVE (GET to detail endpoint with UUID)
- [ ] Test UPDATE (PUT/PATCH to detail endpoint with UUID)
- [ ] Test DELETE (DELETE to detail endpoint with UUID)
- [ ] Test LIST (GET to list endpoint)
- [ ] Test each custom `@action` with UUID parameter
- [ ] Test user isolation (can't access other users' objects)
- [ ] Test UUID validation (invalid UUID returns 404)

---

## Common Pitfalls

### Pitfall 1: Missing UUID Parameter in Custom Actions

**Problem**:
```python
@action(detail=True, methods=['post'])
def my_action(self, request):  # ❌ Missing uuid parameter!
    obj = self.get_object()
```

**Solution**: Always accept lookup field parameter in custom actions.

---

### Pitfall 2: Using PrimaryKeyRelatedField with UUID Models

**Problem**:
```python
diagnosis_result = serializers.PrimaryKeyRelatedField(
    queryset=PlantDiseaseResult.objects.all()
)  # ❌ Fails with UUID models
```

**Solution**: Use `SlugRelatedField(slug_field='uuid')` for UUID relationships.

---

### Pitfall 3: Hardcoding 'pk' in URLs

**Problem**:
```python
url = f'/api/diagnosis-cards/{card.pk}/'  # ❌ Should use .uuid
```

**Solution**: Use UUID field for URL construction.
```python
url = f'/api/diagnosis-cards/{card.uuid}/'  # ✅ Correct
```

---

### Pitfall 4: Invalid Test Choice Values

**Problem**:
```python
{
    'severity': 'low',  # ✅ Valid
    'severity': 'medium',  # ❌ Invalid if not in SEVERITY_CHOICES
}
```

**Solution**: Always verify choice values against model definition.

---

### Pitfall 5: Not Testing UUID in URL

**Problem**: Tests use `pk` in URLs when ViewSet uses `lookup_field='uuid'`.

**Solution**: Always use UUID in test URLs:
```python
response = self.client.get(f'/api/cards/{card.uuid}/')  # ✅ Correct
```

---

## Summary

These diagnosis API patterns ensure:

1. ✅ **UUID Compatibility**: Custom actions accept `uuid=None` parameter
2. ✅ **Serializer Validation**: SlugRelatedField for UUID relationships
3. ✅ **Test Consistency**: Choice values match model definitions
4. ✅ **Comprehensive Coverage**: All CRUD + custom actions tested
5. ✅ **User Isolation**: QuerySet filtering by authenticated user

**Result**: Production-ready diagnosis API with UUID lookups (20/20 tests passing).

---

## Related Patterns

- **ViewSets**: See `architecture/viewsets.md` for permission patterns
- **Testing**: See `testing/integration-tests.md` for test strategies
- **API Design**: See `api/rest-framework.md` for DRF best practices

---

**Last Reviewed**: November 13, 2025
**Pattern Count**: 6 diagnosis & UUID patterns
**Status**: ✅ Production-validated (20/20 tests passing)
**Test Coverage**: CRUD + custom actions + user isolation
