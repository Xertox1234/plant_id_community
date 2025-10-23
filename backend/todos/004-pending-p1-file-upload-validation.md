---
status: pending
priority: p1
issue_id: "004"
tags: [security, file-upload, validation, rce]
dependencies: []
---

# Add File Upload Validation with Magic Bytes (CRITICAL)

## Problem Statement

File type validation relies on Content-Type header which can be spoofed by attackers:

```python
# simple_views.py:91-96
allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
if image_file.content_type not in allowed_types:
    return Response({...}, status=status.HTTP_400_BAD_REQUEST)
```

**Impact:**
- Content-Type header can be spoofed by attacker
- Malicious files (executables, scripts) can be uploaded with fake Content-Type
- Potential RCE (Remote Code Execution) if files are processed without validation
- Exploitability: HIGH

**Proof of Concept:**
```bash
# Attacker uploads malicious file with spoofed Content-Type
curl -X POST /api/plant-identification/identify/ \
  -H "Content-Type: multipart/form-data" \
  -F "image=@malicious.exe;type=image/jpeg"
```

## Findings

- Discovered during security audit by security-sentinel agent
- Location: `/backend/apps/plant_identification/api/simple_views.py:91-96`
- Severity: HIGH (OWASP A03:2021 - Injection)
- Similar vulnerability in all file upload endpoints

## Proposed Solutions

### Option 1: Multi-Layer Validation (RECOMMENDED)
- **Pros**: Defense in depth, catches all attack vectors
- **Cons**: Additional dependency (python-magic)
- **Effort**: Medium (1 hour)
- **Risk**: Low (standard security practice)

**Implementation:**
```python
# 1. Install dependency
# requirements.txt
python-magic==0.4.27

# 2. Create validation utility
# apps/plant_identification/utils/file_validation.py

from PIL import Image
import magic
from rest_framework.exceptions import ValidationError

def validate_image_file(image_file):
    """
    Validate image file using multiple methods for security.

    Performs three layers of validation:
    1. Content-Type header check (first line of defense)
    2. File magic bytes verification (more reliable)
    3. PIL image open and verify (ensures complete valid image)

    Args:
        image_file: Django UploadedFile object

    Raises:
        ValidationError: If file is not a valid image

    Returns:
        True if validation passes
    """
    allowed_content_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
    allowed_magic_types = ['image/jpeg', 'image/png', 'image/webp']

    # Layer 1: Check Content-Type header (fast but spoofable)
    if image_file.content_type not in allowed_content_types:
        raise ValidationError(
            f"Invalid Content-Type: {image_file.content_type}. "
            f"Allowed: {', '.join(allowed_content_types)}"
        )

    # Layer 2: Verify file magic bytes (more reliable)
    image_file.seek(0)
    file_header = image_file.read(2048)  # Read first 2KB for magic detection
    image_file.seek(0)  # Reset for later processing

    mime = magic.from_buffer(file_header, mime=True)
    if mime not in allowed_magic_types:
        raise ValidationError(
            f"File content does not match declared type. "
            f"Detected: {mime}, Expected: {image_file.content_type}"
        )

    # Layer 3: Try to open with PIL (ensures it's a complete, valid image)
    try:
        img = Image.open(image_file)
        img.verify()  # Verify it's a complete image
        image_file.seek(0)  # Reset for later processing
    except Exception as e:
        raise ValidationError(f"Invalid or corrupted image file: {str(e)}")

    return True

# 3. Use in views
# apps/plant_identification/api/simple_views.py

from apps.plant_identification.utils.file_validation import validate_image_file

@api_view(['POST'])
def identify_plant(request):
    image_file = request.FILES.get('image')

    # Validate file before processing
    try:
        validate_image_file(image_file)
    except ValidationError as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

    # Proceed with identification...
```

### Option 2: Extension Validation Only (NOT RECOMMENDED)
- **Pros**: Simple, no dependencies
- **Cons**: Easy to bypass (rename malicious.exe to malicious.jpg)
- **Effort**: Small (15 minutes)
- **Risk**: HIGH (insufficient protection)

## Recommended Action

**Implement Option 1** - Multi-layer validation with python-magic

## Technical Details

- **Affected Files**:
  - `/backend/apps/plant_identification/api/simple_views.py:91-96`
  - `/backend/requirements.txt` (add python-magic)
  - NEW: `/backend/apps/plant_identification/utils/file_validation.py`

- **Related Components**:
  - All file upload endpoints
  - Image processing pipeline
  - External API integrations (Plant.id, PlantNet)

- **System Dependencies**:
  ```bash
  # macOS
  brew install libmagic

  # Ubuntu/Debian
  sudo apt-get install libmagic1

  # Python package
  pip install python-magic
  ```

- **Database Changes**: No

## Resources

- Security audit report: `/backend/docs/development/SECURITY_AUDIT_REPORT.md`
- Agent report: security-sentinel (Finding #9)
- OWASP File Upload: https://owasp.org/www-community/vulnerabilities/Unrestricted_File_Upload
- python-magic docs: https://github.com/ahupp/python-magic

## Acceptance Criteria

- [ ] python-magic dependency added to requirements.txt
- [ ] libmagic system library installed and documented
- [ ] file_validation.py utility created with validate_image_file()
- [ ] Three-layer validation implemented (Content-Type, magic bytes, PIL verify)
- [ ] All file upload endpoints use new validation
- [ ] Clear error messages for each validation failure type
- [ ] Tests verify:
  - [ ] Valid images pass validation
  - [ ] Spoofed Content-Type rejected (malicious.exe with type=image/jpeg)
  - [ ] Corrupted images rejected
  - [ ] Non-image files rejected
- [ ] Documentation updated with system dependency requirements

## Work Log

### 2025-10-22 - Code Review Discovery
**By:** security-sentinel agent
**Actions:**
- Discovered file upload validation vulnerability during security audit
- Analyzed attack vectors (Content-Type spoofing)
- Categorized as CRITICAL/HIGH priority (potential RCE)

**Learnings:**
- Never trust Content-Type header alone
- Defense in depth: Multiple validation layers
- Use magic bytes for file type detection
- Verify files can be opened by intended library (PIL for images)
- Document system dependencies (libmagic)

## Notes

**Urgency:** CRITICAL - Fix before production deployment
**Deployment:** Requires libmagic system library installation
**Testing:**
```bash
# Test with actual malicious file
cp /bin/ls malicious_executable.jpg
curl -X POST http://localhost:8000/api/v1/plant-identification/identify/ \
  -F "image=@malicious_executable.jpg"
# Should be rejected with "File content does not match declared type"
```

**Attack Scenario:**
1. Attacker uploads malicious.exe renamed to malicious.jpg
2. Sets Content-Type: image/jpeg in HTTP request
3. Without magic byte validation, file passes Content-Type check
4. If file is processed/executed, RCE achieved

**Defense:**
Magic bytes detect actual file type regardless of name/header:
- JPEG: `FF D8 FF`
- PNG: `89 50 4E 47`
- Executable: `4D 5A` (Windows) or `7F 45 4C 46` (Linux ELF)
