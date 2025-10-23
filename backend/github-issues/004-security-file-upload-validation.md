# security: Add multi-layer file upload validation to prevent malicious files

## Overview

⚠️ **HIGH** - File upload validation relies solely on the `Content-Type` HTTP header, which can be easily spoofed by attackers to upload malicious files (executables, scripts) disguised as images, potentially leading to Remote Code Execution (RCE).

**Severity:** HIGH (CVSS 6.4 - MEDIUM-HIGH)
**Category:** Security / CWE-434 (Unrestricted File Upload)
**Impact:** Malicious file upload, potential XSS, code injection, RCE if files processed
**Timeline:** Fix within 7 days

## Problem Statement / Motivation

**Current State:**
```python
# File: /backend/apps/plant_identification/api/simple_views.py:91-96
allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
if image_file.content_type not in allowed_types:
    return Response({...}, status=status.HTTP_400_BAD_REQUEST)
```

**Attack Scenario:**
```bash
# Attacker uploads malicious executable with spoofed Content-Type
curl -X POST /api/v1/plant-identification/identify/ \
  -F "image=@malicious.exe;type=image/jpeg"
# Content-Type: image/jpeg (spoofed)
# Actual file: Windows executable (4D 5A magic bytes)
```

**Vulnerability:**
1. Attacker uploads `malicious.exe` renamed to `malicious.jpg`
2. Sets `Content-Type: image/jpeg` in HTTP request
3. Validation checks only the **header** (easily spoofed)
4. File passes validation and is processed by Plant.id/PlantNet APIs
5. If file is stored/served without proper headers, potential XSS or RCE

**CVSS 3.1 Score: 6.4 (MEDIUM)**
```
Vector: CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:L/I:L/A:N
- Attack Vector: Network (N)
- Attack Complexity: Low (L) - Easy to spoof headers
- Privileges Required: Low (L) - Requires authentication
- User Interaction: None (N)
- Scope: Unchanged (U)
- Confidentiality: Low (L) - Info disclosure possible
- Integrity: Low (L) - Can upload malicious files
- Availability: None (N)
```

**Real-World Examples:**
- 2019: WordPress file upload vulnerability (CVE-2019-8943) - PHP code execution
- 2020: Joomla directory traversal via file upload (CVE-2020-10238)
- 2021: Drupal file validation bypass (CVE-2020-13671)

**Why This Matters:**
- Content-Type header is **client-controlled** and completely untrusted
- File extensions can be renamed (malicious.exe → malicious.jpg)
- Magic bytes reveal true file type regardless of name/header
- OWASP lists unrestricted file upload as high-risk vulnerability

## Proposed Solution

**Multi-Layer Defense in Depth Approach:**

### Layer 1: Content-Type Header Check (Fast but Spoofable)
- First line of defense, reject obviously wrong types
- Fast check before reading file contents
- Don't rely on this alone!

### Layer 2: File Magic Bytes Verification (Reliable)
- Read first 2048 bytes to detect actual file type
- Uses `python-magic` library (libmagic wrapper)
- Cannot be spoofed by renaming or header manipulation

### Layer 3: PIL Image Verification (Ensures Valid Image)
- Try to open file with Pillow (PIL)
- Call `img.verify()` to ensure complete, valid image
- Catches corrupted or incomplete images

**Implementation:**

```python
# File: /backend/apps/plant_identification/utils/file_validation.py (NEW)

from PIL import Image
import magic
from rest_framework.exceptions import ValidationError
from typing import BinaryIO

def validate_image_file(image_file: BinaryIO) -> bool:
    """
    Validate image file using three layers of security.

    Defense-in-depth approach:
    1. Content-Type header check (fast, first line of defense)
    2. File magic bytes verification (reliable, cannot be spoofed)
    3. PIL image open and verify (ensures complete valid image)

    Args:
        image_file: Django UploadedFile object

    Raises:
        ValidationError: If file is not a valid image

    Returns:
        True if all validation layers pass

    Examples:
        >>> validate_image_file(request.FILES['image'])
        True  # Valid JPEG image

        >>> validate_image_file(malicious_exe)
        ValidationError: File content does not match declared type
    """
    allowed_content_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
    allowed_magic_types = ['image/jpeg', 'image/png', 'image/webp']

    # Layer 1: Check Content-Type header (fast but spoofable)
    if image_file.content_type not in allowed_content_types:
        raise ValidationError(
            f"Invalid Content-Type: {image_file.content_type}. "
            f"Allowed types: {', '.join(allowed_content_types)}"
        )

    # Layer 2: Verify file magic bytes (more reliable)
    image_file.seek(0)
    file_header = image_file.read(2048)  # Read first 2KB for magic detection
    image_file.seek(0)  # Reset file pointer for later processing

    mime = magic.from_buffer(file_header, mime=True)
    if mime not in allowed_magic_types:
        raise ValidationError(
            f"File content does not match declared type. "
            f"Detected: {mime}, Expected: {image_file.content_type}. "
            f"File may be renamed or have spoofed Content-Type header."
        )

    # Layer 3: Try to open with PIL (ensures it's a complete, valid image)
    try:
        image_file.seek(0)
        img = Image.open(image_file)
        img.verify()  # Verify it's a complete image without loading entire file
        image_file.seek(0)  # Reset for later processing
    except Exception as e:
        raise ValidationError(
            f"Invalid or corrupted image file: {str(e)}. "
            f"File may be incomplete, corrupted, or not a valid image."
        )

    return True
```

**Usage in Views:**

```python
# File: /backend/apps/plant_identification/api/simple_views.py

from apps.plant_identification.utils.file_validation import validate_image_file

@api_view(['POST'])
@permission_classes([IsAuthenticatedForIdentification])
def identify_plant(request):
    """Identify plant from uploaded image."""
    image_file = request.FILES.get('image')

    if not image_file:
        return Response({
            'success': False,
            'error': 'No image file provided'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Multi-layer validation (Content-Type + magic bytes + PIL)
    try:
        validate_image_file(image_file)
    except ValidationError as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

    # Proceed with plant identification...
    service = CombinedPlantIdentificationService()
    try:
        results = service.identify_plant(image_file, user=request.user)
        return Response(results, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Plant identification failed: {e}")
        return Response({
            'success': False,
            'error': 'Plant identification failed'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
```

## Technical Considerations

**Dependencies:**
```bash
# requirements.txt
python-magic==0.4.27  # File magic byte detection
Pillow==10.1.0        # Already installed for image processing
```

**System Libraries:**
```bash
# macOS (Homebrew)
brew install libmagic

# Ubuntu/Debian
sudo apt-get install libmagic1

# Alpine Linux (Docker)
apk add libmagic
```

**Magic Bytes Reference:**
- JPEG: `FF D8 FF` (255 216 255)
- PNG: `89 50 4E 47` (137 80 78 71)
- WebP: `52 49 46 46` (RIFF)
- Windows EXE: `4D 5A` (77 90)
- Linux ELF: `7F 45 4C 46` (127 69 76 70)

**Performance Impact:**
- Magic byte detection: ~1-2ms (reads first 2KB only)
- PIL verification: ~5-10ms (verifies without loading entire image)
- Total overhead: ~6-12ms per upload (negligible vs. API call 2-9 seconds)

**Security Hardening (Future):**
- Re-encode images to strip metadata/EXIF data
- Limit image dimensions to prevent decompression bombs
- Scan for embedded code in image formats (XBM, XPM vulnerabilities)

## Acceptance Criteria

**Code Changes:**
- [ ] Create `/backend/apps/plant_identification/utils/file_validation.py`
- [ ] Implement `validate_image_file()` with three layers
- [ ] Add `python-magic` to requirements.txt
- [ ] Update all file upload endpoints to use new validator
- [ ] Document system dependency (libmagic) in README.md

**Validation Layers:**
- [ ] Layer 1: Content-Type header validation
- [ ] Layer 2: Magic byte detection with python-magic
- [ ] Layer 3: PIL image verification
- [ ] Clear error messages for each validation failure type

**Testing:**
- [ ] Test valid images pass all layers
  ```python
  def test_valid_jpeg():
      with open('tests/fixtures/plant.jpg', 'rb') as f:
          result = validate_image_file(f)
          assert result is True
  ```

- [ ] Test spoofed Content-Type rejected
  ```python
  def test_spoofed_content_type():
      # Upload malicious.exe with Content-Type: image/jpeg
      with pytest.raises(ValidationError, match="does not match declared type"):
          validate_image_file(malicious_file)
  ```

- [ ] Test corrupted images rejected
  ```python
  def test_corrupted_image():
      with pytest.raises(ValidationError, match="Invalid or corrupted"):
          validate_image_file(corrupted_jpeg)
  ```

- [ ] Test non-image files rejected
  ```python
  def test_pdf_file():
      with pytest.raises(ValidationError, match="File content does not match"):
          validate_image_file(pdf_file)
  ```

- [ ] Integration test with actual endpoint
  ```bash
  # Create malicious file disguised as JPEG
  cp /bin/ls malicious.jpg

  curl -X POST /api/v1/plant-identification/identify/ \
    -H "Authorization: Bearer $TOKEN" \
    -F "image=@malicious.jpg"

  # Expected: 400 Bad Request with "File content does not match" error
  ```

**Documentation:**
- [ ] System dependency documented in README.md
- [ ] Installation instructions for libmagic (macOS, Ubuntu, Docker)
- [ ] Security audit documentation updated
- [ ] File upload security best practices documented

## Success Metrics

**Immediate (Within 7 days):**
- ✅ Zero malicious file uploads possible (validated by security testing)
- ✅ No legitimate image uploads rejected (false positive rate < 0.1%)
- ✅ File upload latency increase < 20ms (acceptable overhead)

**Long-term (Within 30 days):**
- 📋 Security scanning in CI/CD (bandit, safety)
- 📋 Automated security testing with fuzzing
- 📋 OWASP File Upload Cheat Sheet compliance verified

## Dependencies & Risks

**Dependencies:**
- python-magic Python package
- libmagic system library (platform-specific installation)
- Pillow (already installed)

**Risks:**
- **Medium:** libmagic system library must be installed on all environments
  - **Mitigation:** Add to Dockerfile, deployment docs, CI/CD setup
  - **Mitigation:** Fallback gracefully if libmagic not available (log error, use Content-Type only)

- **Low:** Performance overhead from validation
  - **Mitigation:** Magic byte check only reads first 2KB (fast)
  - **Mitigation:** PIL verify doesn't load entire image (fast)
  - **Mitigation:** Total overhead ~10ms vs. 2-9s API call (0.1-0.5%)

- **Low:** False positives rejecting valid images
  - **Mitigation:** Three-layer approach reduces false positives
  - **Mitigation:** Comprehensive testing with real-world images
  - **Mitigation:** Clear error messages guide users to resolution

## References & Research

### Internal References
- **Code Review Finding:** security-sentinel agent (Finding #9)
- **Security Audit:** `/backend/docs/development/SECURITY_AUDIT_REPORT.md`
- **File Upload Endpoint:** `/backend/apps/plant_identification/api/simple_views.py:91-96`
- **Image Processing:** `/backend/apps/plant_identification/services/plant_id_service.py`

### External References
- **OWASP File Upload Cheat Sheet:** https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html
- **python-magic Documentation:** https://github.com/ahupp/python-magic
- **Pillow Security:** https://pillow.readthedocs.io/en/stable/releasenotes/index.html#security-issues
- **CWE-434 Unrestricted File Upload:** https://cwe.mitre.org/data/definitions/434.html
- **OWASP Top 10 A03:2021 Injection:** https://owasp.org/Top10/A03_2021-Injection/

### Related CVEs
- **CVE-2019-8943:** WordPress file upload vulnerability (PHP code execution)
- **CVE-2020-10238:** Joomla directory traversal via file upload
- **CVE-2020-13671:** Drupal file validation bypass

### Related Work
- **Issue #001:** Rotate exposed API keys (security hardening)
- **Issue #002:** Fix insecure SECRET_KEY (security hardening)
- **Git commit:** b4819df (Week 3 Quick Wins implementation)

---

**Created:** 2025-10-22
**Priority:** ⚠️ HIGH
**Assignee:** @williamtower
**Labels:** `priority: high`, `type: security`, `area: backend`, `week-3`, `code-review`
**Estimated Effort:** 1 hour (implementation) + 30 minutes (testing) + 30 minutes (docs)
