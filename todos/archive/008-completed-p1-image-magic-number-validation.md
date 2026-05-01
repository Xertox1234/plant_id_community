---
status: pending
priority: p1
issue_id: "008"
tags: [code-review, security, file-upload, django, forum]
dependencies: []
---

# File Upload - Missing Image Content Validation

## Problem Statement

File upload validation includes extension and MIME type checks but does NOT validate actual file contents (magic number validation), allowing potential upload of malicious files disguised as images.

**Location:** `backend/apps/forum/viewsets/post_viewset.py:298-327`

## Findings

- Discovered during security audit by Security Sentinel agent
- **Current Validation:**
  ```python
  # ✅ Extension check (client can rename files)
  file_extension = image_file.name.split('.')[-1].lower()
  if file_extension not in ALLOWED_IMAGE_EXTENSIONS:
      return Response({"error": "Invalid file type"}, status=400)

  # ✅ MIME type check (defense in depth)
  if image_file.content_type not in ALLOWED_IMAGE_MIME_TYPES:
      return Response({"error": "Invalid MIME type"}, status=400)

  # ❌ MISSING: Magic number validation
  ```
- **Exploitation Scenario:**
  ```bash
  # Attacker uploads PHP shell disguised as image
  $ echo '<?php system($_GET["cmd"]); ?>' > shell.jpg
  $ file shell.jpg  # Still identifies as text, not image
  $ curl -X POST -F "image=@shell.jpg" /api/forum/posts/123/upload_image/
  # If server misconfigured, PHP code could execute
  ```
- **Risk Factors:**
  - ✅ Mitigated: Files stored in `/media/` (not in web root)
  - ✅ Mitigated: Django doesn't execute uploaded files by default
  - ❌ Concern: Image processing libraries (Pillow) could have vulnerabilities

## Proposed Solutions

### Option 1: Pillow Image Verification (RECOMMENDED)
```python
from PIL import Image
from io import BytesIO

# Add after MIME type validation:
try:
    # Validate image can be opened and is valid format
    image = Image.open(image_file)
    image.verify()  # Verify it's actually an image

    # Check image dimensions (prevent decompression bombs)
    MAX_IMAGE_PIXELS = 178956970  # ~178 million pixels (default limit)
    if image.width * image.height > MAX_IMAGE_PIXELS:
        return Response(
            {"error": f"Image too large: {image.width}x{image.height} pixels"},
            status=400
        )

    # Re-open for processing (verify() closes the file)
    image_file.seek(0)
    image = Image.open(image_file)

    # Additional validation: ensure format matches extension
    if image.format.lower() not in ['jpeg', 'png', 'gif', 'webp']:
        return Response(
            {"error": f"Invalid image format: {image.format}"},
            status=400
        )

except Exception as e:
    logger.warning(f"[SECURITY] Invalid image file rejected: {e}")
    return Response(
        {"error": "File is not a valid image"},
        status=400
    )
```

- **Pros**: Industry standard validation, detects non-image files, prevents decompression bombs
- **Cons**: Slightly slower upload processing (~100-200ms per image)
- **Effort**: 2 hours (implementation + tests + error handling)
- **Risk**: Low (Pillow is well-tested, widely used)

### Option 2: Magic Number (File Signature) Validation
```python
import imghdr

# Simple magic number check
def validate_image_signature(file):
    """Validate file is actually an image by checking magic number."""
    file.seek(0)
    image_type = imghdr.what(file)
    file.seek(0)

    if image_type not in ['jpeg', 'png', 'gif', 'webp']:
        return False
    return True

if not validate_image_signature(image_file):
    return Response({"error": "Invalid image file"}, status=400)
```

- **Pros**: Fast, lightweight, checks file signature
- **Cons**: Doesn't validate full image structure (Pillow is better)
- **Effort**: 1 hour
- **Risk**: Low

## Recommended Action

**Implement Option 1** - Use Pillow Image.verify() for comprehensive validation.

Add to constants.py:
```python
# Image validation constants
MAX_IMAGE_PIXELS = 178956970  # ~178 million pixels (prevent decompression bombs)
MAX_IMAGE_DIMENSION = 10000  # Max width or height in pixels
```

## Technical Details

- **Affected Files**:
  - `backend/apps/forum/viewsets/post_viewset.py` (upload_image action)
  - `backend/apps/forum/constants.py` (add MAX_IMAGE_PIXELS)
  - `backend/apps/forum/tests/test_attachment.py` (add tests)
- **Related Components**: Attachment model, image upload API
- **Dependencies**: Pillow (already installed)
- **Performance Impact**: +100-200ms per upload (acceptable)

## Resources

- Security Sentinel audit report (Nov 3, 2025)
- CWE-434: Unrestricted Upload of File with Dangerous Type
- CVSS Score: 6.5 (Medium)
- Pillow Image.verify(): https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.verify
- OWASP File Upload Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html

## Acceptance Criteria

- [ ] Image.verify() added to upload_image action
- [ ] Decompression bomb protection implemented
- [ ] Image format validation matches extension
- [ ] Tests verify rejection of non-image files
- [ ] Tests verify rejection of decompression bombs
- [ ] Error messages are user-friendly
- [ ] Logging includes security prefix: [SECURITY]
- [ ] Code review approved

## Work Log

### 2025-11-03 - Code Review Discovery
**By:** Claude Code Review System
**Actions:**
- Discovered during comprehensive security audit
- Analyzed by Security Sentinel agent
- Categorized as P1 (security defense-in-depth)

**Learnings:**
- Extension + MIME checks are not sufficient
- Magic number/content validation is required
- Decompression bombs are real attack vector
- Pillow Image.verify() is industry standard

## Notes

Source: Code review performed on November 3, 2025
Review command: /compounding-engineering:review audit code base
Agent: Security Sentinel
Defense-in-depth: Extension (client-side) → MIME (header) → Content (magic number)
All three layers should be validated for production security
