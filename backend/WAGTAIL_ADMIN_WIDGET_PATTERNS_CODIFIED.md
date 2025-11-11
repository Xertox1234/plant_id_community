# Wagtail Admin Widget Patterns - Codified

**Created:** November 9, 2025
**Context:** Fixing Wagtail BlogPostPage publish_date field to use proper date picker widget
**Issue:** Plain text input instead of calendar widget, CSP blocking admin JavaScript
**Files:** `apps/blog/models.py`, `plant_community_backend/settings.py`

---

## Table of Contents

1. [Pattern 1: Wagtail AdminDateInput Widget Configuration](#pattern-1-wagtail-admindateinput-widget-configuration)
2. [Pattern 2: CSP Compatibility with Wagtail Admin](#pattern-2-csp-compatibility-with-wagtail-admin)
3. [Pattern 3: Conditional Middleware for Development vs Production](#pattern-3-conditional-middleware-for-development-vs-production)
4. [Pattern 4: Debugging Blank Admin Widgets](#pattern-4-debugging-blank-admin-widgets)
5. [Pattern 5: Widget Import Patterns](#pattern-5-widget-import-patterns)
6. [Pattern 6: Custom Widget Attributes](#pattern-6-custom-widget-attributes)

---

## Pattern 1: Wagtail AdminDateInput Widget Configuration

### ❌ WRONG - No Widget Specified

```python
from wagtail.admin.panels import FieldPanel

class BlogPostPage(Page):
    publish_date = models.DateField(
        help_text="Date to publish this post"
    )

    content_panels = [
        FieldPanel('publish_date'),  # ❌ No widget - renders as plain text input
    ]
```

**Problem:**
- Renders as plain `<input type="text">` without date picker
- Users must type dates manually (poor UX)
- No visual calendar widget
- No date format validation

**Symptom:**
User sees a text input field that says "Sunday, nove..." when typing, instead of a calendar popup.

---

### ✅ CORRECT - AdminDateInput Widget with Placeholder

```python
from wagtail.admin.panels import FieldPanel
from wagtail.admin import widgets

class BlogPostPage(Page):
    publish_date = models.DateField(
        help_text="Date to publish this post"
    )

    # Define widget as class variable (Wagtail 7+ pattern)
    date_widget = widgets.AdminDateInput(attrs={'placeholder': 'YYYY-MM-DD'})

    content_panels = [
        FieldPanel('publish_date', widget=date_widget),  # ✅ Proper date picker
    ]
```

**Why This Works:**
1. `widgets.AdminDateInput()` provides Wagtail's built-in date picker
2. Widget defined as class variable (not inline instantiation)
3. Placeholder guides users on expected format
4. Renders with calendar popup and date validation

**Result:**
- Calendar icon appears next to field
- Click icon → calendar popup opens
- Click date → auto-fills field in YYYY-MM-DD format
- Proper date validation

---

### 📋 Implementation Checklist

When adding date/time widgets to Wagtail models:

- [ ] Import `from wagtail.admin import widgets` (NOT `from wagtail.admin.widgets import AdminDateInput`)
- [ ] Define widget as class variable before `content_panels`
- [ ] Use `widgets.AdminDateInput()` for DateField
- [ ] Use `widgets.AdminDateTimeInput()` for DateTimeField
- [ ] Use `widgets.AdminTimeInput()` for TimeField
- [ ] Add helpful placeholder with `attrs={'placeholder': 'YYYY-MM-DD'}`
- [ ] Test in Wagtail admin to verify calendar popup appears
- [ ] Check browser console for CSP errors if widget is blank

---

## Pattern 2: CSP Compatibility with Wagtail Admin

### ❌ WRONG - Strict CSP Blocks Wagtail Admin Widgets

```python
# settings.py
MIDDLEWARE = [
    # ... other middleware ...
    'csp.middleware.CSPMiddleware',  # ❌ Blocks Wagtail admin widgets
]

CONTENT_SECURITY_POLICY = {
    'DIRECTIVES': {
        'default-src': ("'self'",),
        'script-src': ("'self'",),  # ❌ Too strict - blocks inline scripts
        'style-src': ("'self'",),   # ❌ Blocks inline styles
    }
}
```

**Problem:**
- Wagtail admin widgets (date picker, image chooser, etc.) use inline JavaScript
- Strict CSP blocks inline scripts with `script-src 'self'`
- Widget modals appear blank or don't load
- Browser console shows CSP violation errors:
  ```
  Refused to execute inline script because it violates the following
  Content Security Policy directive: "script-src 'self'"
  ```

**Symptoms:**
1. Date picker modal opens but is completely blank
2. Image chooser doesn't load
3. StreamField blocks don't render properly
4. Console full of CSP violation errors

---

### ✅ CORRECT - Conditional CSP for Development

```python
# settings.py
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'apps.core.security.SecurityMiddleware',
    'apps.core.middleware.RateLimitMonitoringMiddleware',
    'apps.core.middleware.SecurityMetricsMiddleware',
    'apps.core.middleware.PermissionsPolicyMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # CSP middleware NOT added here in base MIDDLEWARE list
    'wagtail.contrib.redirects.middleware.RedirectMiddleware',
    'apps.blog.middleware.BlogViewTrackingMiddleware',
]

# ✅ Add CSP middleware only in production
if not DEBUG:
    MIDDLEWARE.insert(
        MIDDLEWARE.index('django.middleware.clickjacking.XFrameOptionsMiddleware') + 1,
        'csp.middleware.CSPMiddleware'
    )
```

**Why This Works:**
1. **Development (DEBUG=True):** CSP disabled → Wagtail admin works perfectly
2. **Production (DEBUG=False):** CSP enabled → Security enforced
3. Developers can use all Wagtail features without CSP interference
4. Production maintains strict security posture

---

### 🔒 Production CSP Configuration

```python
# settings.py
if not DEBUG:
    # Strict CSP in production with nonces (Issue #145 fix)
    CONTENT_SECURITY_POLICY = {
        'DIRECTIVES': {
            'base-uri': ("'self'",),
            'connect-src': (
                "'self'",
                "https://api.plant.id",
                "https://my-api.plantnet.org",
            ),
            'default-src': ("'self'",),
            'font-src': ("'self'", "data:", "https://fonts.gstatic.com"),
            'form-action': ("'self'",),
            'frame-ancestors': ("'none'",),
            'img-src': ("'self'", "data:", "https:", "blob:"),
            'media-src': ("'self'",),
            'object-src': ("'none'",),
            'script-src': ("'self'",),  # Nonces will be added dynamically
            'style-src': ("'self'",),
            'worker-src': ("'self'", "blob:")
        }
    }
else:
    # Development - CSP disabled via middleware conditional
    pass
```

**Alternative: Report-Only Mode for Development**

If you want CSP warnings without blocking:

```python
if DEBUG:
    # Report violations but don't block (useful for debugging)
    CONTENT_SECURITY_POLICY_REPORT_ONLY = {
        'DIRECTIVES': {
            'default-src': ("'self'",),
            'script-src': ("'self'", "'unsafe-inline'", "'unsafe-eval'"),
            'style-src': ("'self'", "'unsafe-inline'"),
        }
    }
    # Still need to add middleware for report-only mode
    MIDDLEWARE.insert(
        MIDDLEWARE.index('django.middleware.clickjacking.XFrameOptionsMiddleware') + 1,
        'csp.middleware.CSPMiddleware'
    )
```

---

## Pattern 3: Conditional Middleware for Development vs Production

### ❌ WRONG - Hardcoded Middleware List

```python
MIDDLEWARE = [
    # ... other middleware ...
    'csp.middleware.CSPMiddleware',  # ❌ Always enabled
    'debug_toolbar.middleware.DebugToolbarMiddleware',  # ❌ In production too!
]
```

**Problems:**
1. Debug toolbar exposed in production
2. CSP breaks Wagtail admin in development
3. No flexibility for environment-specific needs

---

### ✅ CORRECT - Conditional Middleware Configuration

```python
# Base middleware list (always enabled)
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'apps.core.security.SecurityMiddleware',
    'apps.core.middleware.RateLimitMonitoringMiddleware',
    'apps.core.middleware.SecurityMetricsMiddleware',
    'apps.core.middleware.PermissionsPolicyMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'wagtail.contrib.redirects.middleware.RedirectMiddleware',
    'apps.blog.middleware.BlogViewTrackingMiddleware',
]

# ✅ Conditional: Add CSP only in production
if not DEBUG:
    MIDDLEWARE.insert(
        MIDDLEWARE.index('django.middleware.clickjacking.XFrameOptionsMiddleware') + 1,
        'csp.middleware.CSPMiddleware'
    )

# ✅ Conditional: Add request ID tracking if available
if _HAS_REQUEST_ID:
    MIDDLEWARE.append('request_id.middleware.RequestIdMiddleware')

# ✅ Conditional: Add debug toolbar only in development
if DEBUG:
    MIDDLEWARE.append('debug_toolbar.middleware.DebugToolbarMiddleware')
```

**Pattern Benefits:**
1. **Environment-Specific:** Different middleware for dev/prod
2. **Security:** CSP enforced only where needed
3. **Developer Experience:** No CSP blocking admin in development
4. **Flexibility:** Easy to add conditional middleware

---

### 🎯 Middleware Insertion Patterns

**Append to End (Order Not Critical):**
```python
if DEBUG:
    MIDDLEWARE.append('debug_toolbar.middleware.DebugToolbarMiddleware')
```

**Insert at Specific Position (Order Matters):**
```python
if not DEBUG:
    # Insert CSP right after XFrameOptionsMiddleware
    MIDDLEWARE.insert(
        MIDDLEWARE.index('django.middleware.clickjacking.XFrameOptionsMiddleware') + 1,
        'csp.middleware.CSPMiddleware'
    )
```

**Prepend to Beginning (High Priority):**
```python
if ENABLE_LOGGING:
    MIDDLEWARE.insert(0, 'apps.core.middleware.RequestLoggingMiddleware')
```

---

## Pattern 4: Debugging Blank Admin Widgets

### 🔍 Diagnostic Steps

When Wagtail admin widgets appear blank or don't load:

**Step 1: Check Browser Console**

```javascript
// Look for CSP violation errors
Refused to execute inline script because it violates the following
Content Security Policy directive: "script-src 'self'"

// Or missing resource errors
Failed to load resource: net::ERR_BLOCKED_BY_CLIENT
```

**Step 2: Inspect HTML**

```bash
# Check if widget is rendering
document.querySelector('input[name="publish_date"]')
# Should show: <input type="text" ...> not <input type="date" ...>

# Check for CSP headers
fetch(window.location.href).then(r => r.headers.get('Content-Security-Policy'))
```

**Step 3: Check Django Settings**

```python
# In Django shell or settings
python manage.py shell

>>> from django.conf import settings
>>> settings.DEBUG
True

>>> 'csp.middleware.CSPMiddleware' in settings.MIDDLEWARE
False  # ✅ Good in development

>>> settings.CONTENT_SECURITY_POLICY
# Should not be defined in development
```

**Step 4: Verify Widget Configuration**

```python
# In models.py
from wagtail.admin import widgets

# ✅ Correct import
date_widget = widgets.AdminDateInput(attrs={'placeholder': 'YYYY-MM-DD'})

# ❌ Wrong import patterns to avoid:
# from wagtail.admin.widgets import AdminDateInput  # ❌
# from django.forms import DateInput  # ❌ Django widget, not Wagtail
```

---

### 🐛 Common Issues and Fixes

**Issue 1: Widget Renders as Plain Text Input**

```python
# ❌ Problem
FieldPanel('publish_date')  # No widget specified

# ✅ Solution
date_widget = widgets.AdminDateInput(attrs={'placeholder': 'YYYY-MM-DD'})
FieldPanel('publish_date', widget=date_widget)
```

**Issue 2: Blank Modal/Popup**

```python
# ❌ Problem - CSP blocking JavaScript
MIDDLEWARE = [
    'csp.middleware.CSPMiddleware',  # Always enabled
]

# ✅ Solution - Conditional CSP
if not DEBUG:
    MIDDLEWARE.insert(
        MIDDLEWARE.index('django.middleware.clickjacking.XFrameOptionsMiddleware') + 1,
        'csp.middleware.CSPMiddleware'
    )
```

**Issue 3: Widget Instantiation Error**

```python
# ❌ Problem - Inline instantiation in panels
content_panels = [
    FieldPanel('publish_date', widget=widgets.AdminDateInput()),  # Can fail
]

# ✅ Solution - Class variable
date_widget = widgets.AdminDateInput(attrs={'placeholder': 'YYYY-MM-DD'})
content_panels = [
    FieldPanel('publish_date', widget=date_widget),
]
```

**Issue 4: Import Errors**

```python
# ❌ Wrong import patterns
from wagtail.admin.widgets import AdminDateInput  # ❌ Direct import
date_widget = AdminDateInput()  # ❌

from django.forms.widgets import DateInput  # ❌ Django widget
date_widget = DateInput()  # ❌ Not a Wagtail widget

# ✅ Correct import pattern
from wagtail.admin import widgets  # ✅ Import module
date_widget = widgets.AdminDateInput()  # ✅ Access via module
```

---

## Pattern 5: Widget Import Patterns

### ❌ WRONG - Direct Widget Imports

```python
# ❌ Don't do this
from wagtail.admin.widgets import AdminDateInput, AdminDateTimeInput

date_widget = AdminDateInput()
datetime_widget = AdminDateTimeInput()
```

**Problems:**
1. More verbose imports
2. Harder to see all widgets at a glance
3. Inconsistent with Wagtail documentation
4. May break in future Wagtail versions

---

### ✅ CORRECT - Module Import Pattern

```python
# ✅ Recommended pattern (Wagtail 7+)
from wagtail.admin import widgets

class BlogPostPage(Page):
    publish_date = models.DateField()
    publish_time = models.TimeField()
    last_updated = models.DateTimeField()

    # Define all widgets as class variables
    date_widget = widgets.AdminDateInput(attrs={'placeholder': 'YYYY-MM-DD'})
    time_widget = widgets.AdminTimeInput(attrs={'placeholder': 'HH:MM:SS'})
    datetime_widget = widgets.AdminDateTimeInput(attrs={'placeholder': 'YYYY-MM-DD HH:MM:SS'})

    content_panels = [
        FieldPanel('publish_date', widget=date_widget),
        FieldPanel('publish_time', widget=time_widget),
        FieldPanel('last_updated', widget=datetime_widget),
    ]
```

**Benefits:**
1. Single import line
2. All widgets accessed via `widgets.WidgetName()`
3. Consistent with Wagtail docs
4. Future-proof

---

### 📦 Available Wagtail Admin Widgets

```python
from wagtail.admin import widgets

# Date/Time Widgets
widgets.AdminDateInput()         # Calendar picker for DateField
widgets.AdminTimeInput()         # Time picker for TimeField
widgets.AdminDateTimeInput()     # Combined date+time picker

# Text Widgets
widgets.AdminAutoHeightTextInput()  # Auto-expanding text input
widgets.AdminTagWidget()            # Tag input with autocomplete

# Choice Widgets
widgets.AdminRadioSelect()       # Radio buttons
widgets.AdminCheckboxSelectMultiple()  # Checkboxes

# File Widgets
widgets.AdminFileWidget()        # File upload

# Custom Widgets (use sparingly)
widgets.AdminChooser()           # Generic chooser pattern
```

---

## Pattern 6: Custom Widget Attributes

### 🎨 Adding Placeholder Text

```python
from wagtail.admin import widgets

# ✅ Date with placeholder
date_widget = widgets.AdminDateInput(attrs={'placeholder': 'YYYY-MM-DD'})

# ✅ DateTime with placeholder and custom class
datetime_widget = widgets.AdminDateTimeInput(attrs={
    'placeholder': 'YYYY-MM-DD HH:MM:SS',
    'class': 'custom-datetime-input'
})

# ✅ Time with placeholder
time_widget = widgets.AdminTimeInput(attrs={'placeholder': 'HH:MM:SS'})
```

---

### 🔧 Adding CSS Classes

```python
# ✅ Custom CSS class for styling
date_widget = widgets.AdminDateInput(attrs={
    'placeholder': 'YYYY-MM-DD',
    'class': 'datepicker-large',
})

# ✅ Multiple classes
date_widget = widgets.AdminDateInput(attrs={
    'placeholder': 'YYYY-MM-DD',
    'class': 'datepicker-large required-field',
})
```

---

### 🎯 Adding Data Attributes

```python
# ✅ Data attributes for JavaScript integration
date_widget = widgets.AdminDateInput(attrs={
    'placeholder': 'YYYY-MM-DD',
    'data-min-date': '2024-01-01',
    'data-max-date': '2024-12-31',
    'data-highlight-today': 'true',
})
```

---

### 📋 Complete Example with Multiple Attributes

```python
from wagtail.admin import widgets
from django.db import models
from wagtail.models import Page
from wagtail.admin.panels import FieldPanel

class EventPage(Page):
    event_date = models.DateField(
        help_text="When is the event taking place?"
    )

    event_time = models.TimeField(
        help_text="What time does it start?"
    )

    registration_deadline = models.DateTimeField(
        help_text="Last moment to register"
    )

    # Custom widget configurations
    event_date_widget = widgets.AdminDateInput(attrs={
        'placeholder': 'YYYY-MM-DD',
        'class': 'event-datepicker',
        'data-min-date': 'today',  # JavaScript can use this
        'aria-label': 'Event date',
    })

    event_time_widget = widgets.AdminTimeInput(attrs={
        'placeholder': 'HH:MM',
        'class': 'event-timepicker',
        'aria-label': 'Event start time',
    })

    deadline_widget = widgets.AdminDateTimeInput(attrs={
        'placeholder': 'YYYY-MM-DD HH:MM',
        'class': 'deadline-picker',
        'data-highlight-deadlines': 'true',
        'aria-label': 'Registration deadline',
    })

    content_panels = Page.content_panels + [
        FieldPanel('event_date', widget=event_date_widget),
        FieldPanel('event_time', widget=event_time_widget),
        FieldPanel('registration_deadline', widget=deadline_widget),
    ]
```

---

## 🎓 Best Practices Summary

### ✅ DO

1. **Always use `widgets.AdminDateInput()` for DateField**
   - Provides proper calendar picker
   - Better UX than text input
   - Built-in validation

2. **Define widgets as class variables**
   ```python
   date_widget = widgets.AdminDateInput(attrs={'placeholder': 'YYYY-MM-DD'})
   content_panels = [FieldPanel('publish_date', widget=date_widget)]
   ```

3. **Import widgets module, not individual widgets**
   ```python
   from wagtail.admin import widgets  # ✅
   # NOT: from wagtail.admin.widgets import AdminDateInput  # ❌
   ```

4. **Disable CSP in development**
   ```python
   if not DEBUG:
       MIDDLEWARE.insert(index, 'csp.middleware.CSPMiddleware')
   ```

5. **Add helpful placeholders**
   ```python
   attrs={'placeholder': 'YYYY-MM-DD'}
   ```

6. **Test in Wagtail admin after adding widgets**
   - Navigate to admin page
   - Check if calendar popup appears
   - Verify date validation works

---

### ❌ DON'T

1. **Don't omit widgets for date fields**
   ```python
   FieldPanel('publish_date')  # ❌ Renders as text input
   ```

2. **Don't enable CSP in development**
   ```python
   MIDDLEWARE = [
       'csp.middleware.CSPMiddleware',  # ❌ Breaks Wagtail admin
   ]
   ```

3. **Don't use Django widgets for Wagtail**
   ```python
   from django.forms.widgets import DateInput  # ❌ Not a Wagtail widget
   ```

4. **Don't instantiate widgets inline in panels**
   ```python
   content_panels = [
       FieldPanel('date', widget=widgets.AdminDateInput()),  # ❌ Anti-pattern
   ]
   ```

5. **Don't ignore browser console errors**
   - CSP violations indicate blocking
   - Fix CSP configuration before debugging widget code

6. **Don't forget to restart Django after middleware changes**
   ```bash
   # Middleware changes require restart
   python manage.py runserver
   ```

---

## 🔧 Troubleshooting Checklist

When date picker widget doesn't work:

- [ ] **Import Check:** Using `from wagtail.admin import widgets`?
- [ ] **Widget Definition:** Defined as class variable before `content_panels`?
- [ ] **Widget Application:** Applied via `FieldPanel('field', widget=date_widget)`?
- [ ] **CSP Check:** CSP middleware disabled in development?
- [ ] **Browser Console:** Any CSP violation errors?
- [ ] **Django Restart:** Restarted server after middleware changes?
- [ ] **Browser Refresh:** Hard refresh (Cmd+Shift+R or Ctrl+Shift+F5)?
- [ ] **Widget Rendering:** HTML shows proper widget class names?
- [ ] **JavaScript Loading:** No 404 errors for admin JS files?
- [ ] **Modal Visibility:** Clicking calendar icon opens popup?

---

## 📚 Related Documentation

- **Wagtail Panels Reference:** https://docs.wagtail.org/en/stable/reference/panels.html
- **Wagtail Admin Widgets:** https://docs.wagtail.org/en/stable/extending/forms.html
- **Django CSP Middleware:** https://django-csp.readthedocs.io/
- **Content Security Policy:** https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP

---

## 📝 Commit Message Template

```
fix(wagtail): Add [widget type] to [model].[field]

**Problem:**
The [field] field was showing [current behavior] instead of [expected behavior].

**Solution:**
1. Added Wagtail's [WidgetName] widget to the [field] field
2. [Any CSP or middleware changes]

**Changes:**
- apps/[app]/models.py:
  - Import widgets from wagtail.admin
  - Create [widget_name] with [WidgetType] and [attributes]
  - Apply widget to [field] FieldPanel

[Any settings.py changes]

**Testing:**
- Navigate to [admin URL]
- [Expected behavior]

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

---

## 🎯 Quick Reference

| Field Type | Wagtail Widget | Django Widget (❌) |
|-----------|---------------|-------------------|
| DateField | `widgets.AdminDateInput()` | ~~`DateInput()`~~ |
| TimeField | `widgets.AdminTimeInput()` | ~~`TimeInput()`~~ |
| DateTimeField | `widgets.AdminDateTimeInput()` | ~~`DateTimeInput()`~~ |
| CharField (tags) | `widgets.AdminTagWidget()` | ~~`TextInput()`~~ |
| FileField | `widgets.AdminFileWidget()` | ~~`FileInput()`~~ |

**Always use Wagtail widgets for Wagtail admin pages!**

---

**End of WAGTAIL_ADMIN_WIDGET_PATTERNS_CODIFIED.md**
