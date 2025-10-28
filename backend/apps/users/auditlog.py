"""
Audit log registration for users app models.

Registers sensitive models for audit trail tracking to comply with:
- GDPR Article 30 (records of processing activities)
- SOC 2 audit trail requirements
- Security monitoring and unauthorized access detection
"""

from auditlog.registry import auditlog
from .models import User, UserPlantCollection, ActivityLog


# Register User model for comprehensive audit tracking
# Tracks: create, update, delete operations on user accounts
# Captures: email access, profile changes, permission modifications
auditlog.register(
    User,
    include_fields=[
        'username', 'email', 'first_name', 'last_name', 'is_active',
        'is_staff', 'is_superuser', 'bio', 'location', 'hardiness_zone',
        'profile_visibility', 'show_email', 'trust_level'
    ],
    exclude_fields=['password', 'last_login'],  # Never log passwords
    m2m_fields=['groups', 'user_permissions', 'following'],  # Track permission changes
)

# Register UserPlantCollection for data access tracking
# Tracks: collection creation, modification, deletion
auditlog.register(
    UserPlantCollection,
    include_fields=['name', 'description', 'is_public'],
)

# Register ActivityLog for meta-tracking (audit the audit)
# Helps detect tampering or unauthorized modifications to activity logs
auditlog.register(
    ActivityLog,
    include_fields=['activity_type', 'description', 'is_public'],
)
