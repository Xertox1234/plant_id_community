"""
Single source of truth for Cloudflare R2 object-storage configuration (todo 321).

Imported by BOTH sides of the R2 integration so a var rename or a Cache-Control
change lands in one place instead of drifting across files held together only by
"must match settings.py" comments:

- ``plant_community_backend/settings.py`` — the ``STORAGES`` block and
  ``validate_environment()``'s fail-fast check.
- ``apps/core/management/commands/sync_media_to_r2.py`` — the one-time migration
  copy, which talks to R2's S3-compatible API via boto3 directly.

Why this module lives in the project package rather than ``apps/core/constants.py``
(both were on the table in todo 321): apps read settings, not the reverse, and
``settings.py`` has no app-level import today — making it import ``apps.*`` would
invert that direction for the first time. Both would resolve at runtime (anything
that can import ``plant_community_backend.settings`` has ``backend/`` on
``sys.path``, so ``apps`` is reachable too), but ``apps.core.constants`` is only
*safe* this early while ``apps/__init__.py`` and ``apps/core/__init__.py`` stay
empty — a model import or app-config added to either later would break settings
load itself, with an `AppRegistryNotReady` that points nowhere near the cause.
``apps/core/constants.py`` is also docstring-scoped to security constants and had
exactly one importer repo-wide.

Deliberately has NO imports — not Django, not decouple. It is read at settings
import time, before any app registry exists, and the sync command imports it while
``USE_R2`` may be off.

When adding or renaming a var here, also update the operator-facing docs, which
carry the list as prose on purpose: ``backend/.env.example``,
``backend/docs/deployment/railway.md``,
``backend/docs/patterns/security/secret-management.md``, and the root
``CLAUDE.md`` env-var table.
"""

# Vars sync_media_to_r2 needs for its direct boto3 calls.
R2_BOTO3_REQUIRED_VARS = (
    "R2_BUCKET_NAME",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_ENDPOINT_URL",
)

# Vars that only feed Django's URL generation (S3Storage.url() builds media URLs
# from `custom_domain`). The sync command never builds a URL, which is why it
# requires the boto3 set above and not this one.
R2_URL_ONLY_VARS = ("R2_CUSTOM_DOMAIN",)

# Everything validate_environment() demands when USE_R2 is on. Composed from the
# two sets above rather than sliced out of one flat tuple: a slice like
# SHARED[:4] is index-dependent, so inserting a var in the wrong position later
# would silently change what the sync command requires — the exact drift this
# module exists to prevent. Composing forces a new var to declare which set it
# joins. Order is cosmetic, not load-bearing — it only sets the sequence missing
# vars are reported in (validate_environment() emits one message per missing var
# regardless of position).
R2_REQUIRED_VARS = R2_BOTO3_REQUIRED_VARS + R2_URL_ONLY_VARS

# Cache-Control stamped on every object, whether written by S3Storage (new
# uploads) or copied up by sync_media_to_r2. Paired with file_overwrite=False in
# settings.py so a same-name re-upload gets a new key rather than silently
# replacing bytes at a URL the CDN was told to cache for a year.
#
# This VALUE's only independent check is the hardcoded string in
# test_sync_media_to_r2.py's test_upload_sets_cache_control_and_content_type.
# test_r2_storage.py compares STORAGES against this constant, which pins that
# settings.py reads it — not that it is right. Don't "de-duplicate" that test
# literal into an import of this name, or the last real anchor disappears.
R2_CACHE_CONTROL = "public, max-age=31536000, immutable"

# R2 has no regions, but both boto3 and django-storages require the field set.
R2_REGION_NAME = "auto"
