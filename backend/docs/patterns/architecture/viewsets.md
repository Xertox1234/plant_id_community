# Django REST Framework ViewSet Patterns

**Last Updated**: November 13, 2025
**Consolidated From**: CLAUDE.md, Issue #131 documentation
**Status**: ✅ Production-Tested
**Security Impact**: CRITICAL

---

## Table of Contents

1. [ViewSet Permission Override Bug](#viewset-permission-override-bug)
2. [Correct get_permissions() Pattern](#correct-get_permissions-pattern)
3. [Security Implications](#security-implications)
4. [Testing Permission Integration](#testing-permission-integration)
5. [Common Pitfalls](#common-pitfalls)

---

## ViewSet Permission Override Bug

### The Problem

**Issue #131** (November 6, 2025): ViewSet's `get_permissions()` method overrides `@action`-level `permission_classes`, causing custom action permissions to be silently ignored.

**Security Impact**: HIGH - Permission checks can be bypassed, allowing unauthorized users to access restricted actions.

### How the Bug Manifests

When you override `get_permissions()` in a ViewSet, it's called for EVERY action. If you don't explicitly handle custom actions, DRF ignores the `permission_classes` specified in `@action` decorators.

**The Inheritance Chain**:
1. Request comes in for custom action (e.g., `upload_image`)
2. DRF calls `self.get_permissions()`
3. Your `get_permissions()` returns default permissions (e.g., `IsAuthenticatedOrReadOnly`)
4. `@action` decorator's `permission_classes` are NEVER checked!

**Real-World Example from Issue #131**:

```python
# apps/forum/viewsets/post_viewset.py (BEFORE FIX)

class PostViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_permissions(self):
        """
        ❌ BUG: This method is called for ALL actions,
        including custom @action methods!
        """
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsAuthorOrModerator()]
        return [IsAuthenticatedOrReadOnly()]  # ❌ Applies to upload_image too!

    @action(
        detail=True,
        methods=['POST'],
        permission_classes=[CanUploadImages, IsAuthorOrModerator]  # ❌ IGNORED!
    )
    def upload_image(self, request, pk=None):
        """
        Intended: Only BASIC+ trust level users can upload images
        Reality: ALL authenticated users can upload (permission bypass!)
        """
        # Implementation...
```

**What Happened**:
- NEW users (trust level 0) could upload images
- `CanUploadImages` permission was NEVER checked
- Trust level restrictions were completely bypassed
- Security vulnerability discovered in 14 passing tests

---

## Correct get_permissions() Pattern

### Pattern: Delegate to super() for Custom Actions

**Anti-Pattern** ❌:
```python
class MyViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_permissions(self):
        # ❌ BAD - Custom actions not handled
        if self.action in ['update', 'destroy']:
            return [IsAuthorOrModerator()]
        return [IsAuthenticatedOrReadOnly()]  # ❌ Overrides @action permissions!

    @action(detail=True, methods=['POST'], permission_classes=[CustomPermission])
    def custom_action(self, request, pk=None):
        # CustomPermission is NEVER checked!
        pass
```

**Correct Pattern** ✅:
```python
class MyViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_permissions(self):
        """
        Dynamic permissions based on action.

        CRITICAL: For custom actions with their own permission_classes,
        call super().get_permissions() to respect @action-level permissions.
        """
        # ✅ Let custom actions use their own permission_classes
        if self.action in ['custom_action', 'another_custom_action']:
            return super().get_permissions()  # ✅ Uses @action permissions

        # Standard action permissions
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsAuthorOrModerator()]

        return [IsAuthenticatedOrReadOnly()]

    @action(detail=True, methods=['POST'], permission_classes=[CustomPermission])
    def custom_action(self, request, pk=None):
        # ✅ CustomPermission is properly enforced
        pass
```

### Real-World Implementation

**Location**: `apps/forum/viewsets/post_viewset.py:183-202` (AFTER FIX)

```python
class PostViewSet(viewsets.ModelViewSet):
    """
    ViewSet for forum posts with dynamic permissions.
    """
    queryset = Post.objects.all()
    serializer_class = PostSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_permissions(self) -> List[BasePermission]:
        """
        Dynamic permissions based on action.

        Returns:
            - IsAuthorOrModerator for update/delete
            - IsAuthenticatedOrReadOnly for list/retrieve/create
            - Action-level permissions for custom actions (upload_image, delete_image, etc.)
        """
        # ✅ For custom actions with their own permission_classes in @action decorator,
        # use super().get_permissions() to respect action-level permissions
        if self.action in ['upload_image', 'delete_image', 'flag_post']:
            return super().get_permissions()

        # Standard CRUD permissions
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsAuthorOrModerator()]

        return [IsAuthenticatedOrReadOnly()]

    @action(
        detail=True,
        methods=['POST'],
        permission_classes=[CanUploadImages, IsAuthorOrModerator]  # ✅ Now enforced!
    )
    @method_decorator(ratelimit(key='user', rate='10/h', method='POST', block=True))
    def upload_image(self, request: Request, pk=None) -> Response:
        """
        Upload an image attachment to a post.

        Permissions:
        - CanUploadImages: Requires BASIC trust level or higher
        - IsAuthorOrModerator: Must be post author or moderator
        """
        # Implementation...
```

**Key Points**:
- ✅ List custom actions explicitly in `get_permissions()`
- ✅ Call `super().get_permissions()` for those actions
- ✅ Standard CRUD actions handled normally
- ✅ Security vulnerability fixed

---

## Security Implications

### Why This Matters

**Permission Bypass Vulnerability**:
1. **Trust Level Bypass**: NEW users could upload images (requires BASIC+)
2. **Authorization Bypass**: Non-authors could perform restricted actions
3. **Silent Failure**: No error, no warning - permissions just ignored
4. **Production Risk**: Could be exploited in production if not caught

**Impact of Issue #131**:
- **Severity**: HIGH (permission bypass)
- **Affected Actions**: All custom actions with `@action` permissions
- **Tests Passing**: 14/18 (false sense of security)
- **Root Cause**: ViewSet inheritance behavior not understood

### How to Detect This Bug

**Symptoms**:
- Tests pass but feature doesn't work as expected
- Users can perform actions they shouldn't
- Permission classes in `@action` decorators seem to be ignored
- Logs show permission checks skipped

**Testing for This Bug**:
```python
def test_new_user_cannot_upload_image(self):
    """
    Verify NEW users cannot upload images (requires BASIC trust level).

    This test FAILED before Issue #131 fix because get_permissions()
    was returning IsAuthenticatedOrReadOnly instead of CanUploadImages.
    """
    # Create NEW user (trust level 0)
    user = User.objects.create_user(username='newuser', password='password')
    self.assertEqual(user.profile.trust_level, 'new')

    post = Post.objects.create(author=user, content='Test', thread=self.thread)
    self.client.login(username='newuser', password='password')

    # Try to upload image
    image = SimpleUploadedFile("test.jpg", b"file_content", content_type="image/jpeg")
    response = self.client.post(
        f'/api/v1/forum/posts/{post.id}/upload_image/',
        {'image': image},
        format='multipart'
    )

    # Should return 403 (permission denied)
    self.assertEqual(response.status_code, 403)
    self.assertIn('trust level', response.json()['message'].lower())
```

---

## Testing Permission Integration

### Integration Test Pattern

**Test Coverage Required**:
1. ✅ Standard CRUD permissions (list, retrieve, create, update, delete)
2. ✅ Custom action permissions (upload_image, delete_image, flag_post)
3. ✅ Permission class combinations (multiple permissions with AND logic)
4. ✅ Trust level integration
5. ✅ Staff/superuser bypass behavior

**Example Test Suite**:
```python
# apps/forum/tests/test_post_viewset_permissions.py

class PostViewSetPermissionTests(TestCase):
    """
    Integration tests for PostViewSet permissions.

    These tests verify that get_permissions() correctly delegates to
    action-level permission_classes for custom actions.
    """

    def test_upload_image_requires_basic_trust_level(self):
        """NEW users cannot upload images (requires BASIC+)."""
        user = self._create_user_with_trust_level('new')
        post = Post.objects.create(author=user, content='Test', thread=self.thread)
        self.client.login(username=user.username, password='password')

        response = self._upload_image(post.id)

        # Verify 403 response with trust level message
        self.assertEqual(response.status_code, 403)
        self.assertIn('BASIC trust level', response.json()['message'])

    def test_basic_user_can_upload_image(self):
        """BASIC users can upload images."""
        user = self._create_user_with_trust_level('basic')
        post = Post.objects.create(author=user, content='Test', thread=self.thread)
        self.client.login(username=user.username, password='password')

        response = self._upload_image(post.id)

        # Verify 201 response with attachment data
        self.assertEqual(response.status_code, 201)
        self.assertIn('image', response.json())

    def test_staff_bypasses_trust_level_check(self):
        """Staff users bypass trust level requirements."""
        user = self._create_user_with_trust_level('new')
        user.is_staff = True
        user.save()

        post = Post.objects.create(author=user, content='Test', thread=self.thread)
        self.client.login(username=user.username, password='password')

        response = self._upload_image(post.id)

        # Staff bypasses trust level check
        self.assertEqual(response.status_code, 201)

    def test_non_author_cannot_upload_to_others_post(self):
        """Non-authors cannot upload images to others' posts."""
        author = self._create_user_with_trust_level('basic')
        other_user = self._create_user_with_trust_level('basic')

        post = Post.objects.create(author=author, content='Test', thread=self.thread)
        self.client.login(username=other_user.username, password='password')

        response = self._upload_image(post.id)

        # Verify 403 response (not post author)
        self.assertEqual(response.status_code, 403)

    def test_moderator_can_upload_to_any_post(self):
        """Moderators can upload images to any post."""
        author = self._create_user_with_trust_level('basic')
        moderator = self._create_user_with_trust_level('expert')  # EXPERT = moderator

        post = Post.objects.create(author=author, content='Test', thread=self.thread)
        self.client.login(username=moderator.username, password='password')

        response = self._upload_image(post.id)

        # Moderator can upload to any post
        self.assertEqual(response.status_code, 201)

    # Helper methods
    def _create_user_with_trust_level(self, level: str) -> User:
        """Create user with specific trust level."""
        user = User.objects.create_user(username=f'user_{level}', password='password')
        profile = user.profile
        profile.trust_level = level
        if level in ['basic', 'trusted', 'veteran', 'expert']:
            user.date_joined = timezone.now() - timedelta(days=30)
            profile.post_count = 50
        profile.save()
        user.save()
        return user

    def _upload_image(self, post_id: int) -> Response:
        """Helper to upload image to post."""
        image = SimpleUploadedFile("test.jpg", b"file_content", content_type="image/jpeg")
        return self.client.post(
            f'/api/v1/forum/posts/{post_id}/upload_image/',
            {'image': image},
            format='multipart'
        )
```

**Test Results**:
- **Before Fix**: 14/18 passing (4 trust level tests failing)
- **After Fix**: 17/17 passing (1 skipped for time-based rate limiting)

---

## Common Pitfalls

### Pitfall 1: Forgetting to List Custom Actions

**Problem**:
```python
def get_permissions(self):
    # ❌ BAD - upload_image not listed
    if self.action in ['delete_image']:
        return super().get_permissions()

    if self.action in ['update', 'destroy']:
        return [IsAuthorOrModerator()]

    return [IsAuthenticatedOrReadOnly()]  # ❌ Overrides upload_image!

@action(detail=True, methods=['POST'], permission_classes=[CanUploadImages])
def upload_image(self, request, pk=None):
    # CanUploadImages is NEVER checked!
    pass
```

**Solution**: List ALL custom actions that have `permission_classes` in `@action` decorator.

---

### Pitfall 2: Using Placeholder None

**Problem**:
```python
def get_permissions(self):
    if self.action in ['upload_image']:
        return None  # ❌ Returns None, not action permissions!

    return [IsAuthenticatedOrReadOnly()]
```

**Why This Fails**: Returning `None` doesn't delegate to action permissions - it just returns `None`, which DRF treats as "no permissions" (allows everything).

**Solution**: Use `super().get_permissions()` to properly delegate.

---

### Pitfall 3: Inconsistent Action Names

**Problem**:
```python
def get_permissions(self):
    # ❌ BAD - typo in action name
    if self.action in ['upload_images']:  # Wrong!
        return super().get_permissions()

    return [IsAuthenticatedOrReadOnly()]

@action(detail=True, methods=['POST'], permission_classes=[CanUploadImages])
def upload_image(self, request, pk=None):  # Correct name
    # CanUploadImages is NEVER checked!
    pass
```

**Why This Fails**: Action name mismatch - `'upload_images'` != `'upload_image'`.

**Solution**: Double-check action names match exactly (use constants if many actions).

---

### Pitfall 4: Missing super() Call

**Problem**:
```python
def get_permissions(self):
    if self.action in ['upload_image']:
        return [CanUploadImages()]  # ❌ Hardcoded, ignores IsAuthorOrModerator!

    return [IsAuthenticatedOrReadOnly()]

@action(
    detail=True,
    methods=['POST'],
    permission_classes=[CanUploadImages, IsAuthorOrModerator]  # Both required!
)
def upload_image(self, request, pk=None):
    pass
```

**Why This Fails**: Only returns `CanUploadImages`, but `@action` decorator specifies BOTH `CanUploadImages` AND `IsAuthorOrModerator`.

**Solution**: Use `super().get_permissions()` to get ALL permissions from decorator.

---

### Pitfall 5: Testing Only Happy Path

**Problem**: Tests that only verify successful actions will miss permission bugs.

```python
def test_user_can_upload_image(self):
    """❌ BAD - Only tests success case."""
    user = self._create_basic_user()
    post = Post.objects.create(author=user, content='Test', thread=self.thread)
    self.client.login(username=user.username, password='password')

    response = self._upload_image(post.id)

    # This passes even if permission check is broken!
    self.assertEqual(response.status_code, 201)
```

**Solution**: Test BOTH success AND failure cases.

```python
def test_new_user_cannot_upload_image(self):
    """✅ GOOD - Tests permission denial."""
    user = self._create_new_user()  # Trust level: NEW
    post = Post.objects.create(author=user, content='Test', thread=self.thread)
    self.client.login(username=user.username, password='password')

    response = self._upload_image(post.id)

    # Verifies permission check is actually enforced
    self.assertEqual(response.status_code, 403)
    self.assertIn('trust level', response.json()['message'].lower())
```

---

## Deployment Checklist

### Pre-Deployment Verification

**Code Review**:
- [ ] All custom actions listed in `get_permissions()`
- [ ] `super().get_permissions()` used for custom actions
- [ ] Action names match exactly (no typos)
- [ ] Standard CRUD actions handled correctly
- [ ] Documentation updated with permission requirements

**Testing**:
- [ ] Integration tests cover all custom actions
- [ ] Tests verify permission denial (not just success)
- [ ] Trust level integration tested
- [ ] Staff/superuser bypass tested
- [ ] Multiple permission combinations tested

**Security**:
- [ ] Permission bypass vulnerability fixed
- [ ] All tests passing (no skipped permission tests)
- [ ] OpenAPI schema documents permission requirements
- [ ] Error messages include actionable guidance

---

## Summary

**The Critical Pattern**:
```python
def get_permissions(self):
    # ✅ ALWAYS list custom actions with @action permission_classes
    if self.action in ['upload_image', 'delete_image', 'flag_post']:
        return super().get_permissions()  # Respects @action permissions

    # Handle standard CRUD actions
    if self.action in ['update', 'partial_update', 'destroy']:
        return [IsAuthorOrModerator()]

    return [IsAuthenticatedOrReadOnly()]
```

**Key Takeaways**:
1. ✅ `get_permissions()` is called for EVERY action
2. ✅ `@action` decorator permissions are ignored unless explicitly delegated
3. ✅ Use `super().get_permissions()` to respect action-level permissions
4. ✅ List ALL custom actions that have `permission_classes`
5. ✅ Test permission denial, not just success

**Security Impact**: Fixing this pattern prevents permission bypass vulnerabilities and ensures trust level restrictions are properly enforced.

---

## Related Patterns

- **Rate Limiting**: See `rate-limiting.md` for rate limit + permission integration
- **Input Validation**: See `security/input-validation.md` for request validation
- **Authentication**: See `security/authentication.md` for auth patterns

---

**Last Reviewed**: November 13, 2025
**Pattern Count**: 1 critical ViewSet pattern
**Status**: ✅ Production-validated
**Issue Reference**: #131 (November 6, 2025)
