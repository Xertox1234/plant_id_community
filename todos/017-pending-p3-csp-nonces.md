---
status: ready
priority: p3
issue_id: "017"
tags: [security, csp]
dependencies: []
---

# Add CSP Nonces to Templates

**CVSS**: 3.7 (Low)

## Problem

CSP config has nonces but templates don't use them.

## Solution

```django
{% load csp %}
<script nonce="{{ request.csp_nonce }}">
    // Inline script
</script>
```

**Effort**: 1 hour
