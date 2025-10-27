---
status: ready
priority: p3
issue_id: "021"
tags: [data-integrity, validation]
dependencies: []
---

# Add Confidence Score Validators

## Problem

No bounds checking on confidence_score FloatField - API could return 1.5 or -0.1.

## Solution

```python
from django.core.validators import MinValueValidator, MaxValueValidator

confidence_score = models.FloatField(
    validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
)
```

**Effort**: 15 minutes
