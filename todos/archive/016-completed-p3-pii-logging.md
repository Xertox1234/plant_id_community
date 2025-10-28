---
status: resolved
priority: p3
issue_id: "016"
tags: [security, gdpr, privacy, logging]
dependencies: []
resolved_date: 2025-10-27
---

# Remove PII from Logs

**CVSS**: 4.7 (GDPR Concern)

## Problem

Logs contain usernames, emails, IP addresses (PII under GDPR).

## Solution

Hash/pseudonymize usernames, never log emails:
```python
def log_safe_username(username):
    hash_suffix = hashlib.sha256(username.encode()).hexdigest()[:8]
    return f"{username[:3]}***{hash_suffix}"
```

**Effort**: 2 hours
