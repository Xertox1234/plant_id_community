# Forum Phase 2 — "Make It Safe" Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the forum API so it is safe to put online — close the verified gaps (no rate limiting, unbounded pagination, spoofable image upload, no server-side HTML sanitization) plus whatever a `security-reviewer` pass surfaces, without redesigning the API.

**Architecture:** Apply the repo's existing security patterns to the forum's hand-rolled DRF views: `django-ratelimit` decorators (function views) / `method_decorator` (class views) with limits in a new `apps/forum_integration/constants.py`; clamp manual pagination; add the 4-layer file-upload validation; sanitize stored HTML server-side with `nh3` and constrain `content_format`; remove dead permission-bypassing code.

**Tech Stack:** Django 5 + DRF, django-machina, `django-ratelimit==4.1.0` (already a dep), `nh3` (to add), PIL/Pillow (already used by ImageKit `ProcessedImageField`), pytest / Django test runner (real DB, no mocks).

**Spec:** `docs/superpowers/specs/2026-05-25-forum-modernization-hardening-design.md`
**Depends on:** Phase 1 (a working forum to verify against). Backend hardening itself is independent of the Phase 1 frontend changes.

---

## Verified state (read directly — `api_views.py`, `serializers.py`)

| Concern | Where | Status |
|---|---|---|
| No rate limiting | entire `api_views.py` (grep `ratelimit` → none) | **gap** |
| Unbounded `page_size` | `all_topics_list` (`api_views.py:74`); `TopicDetailView` manual posts pagination | **gap** (DRF `ListAPIView`s are fine — fixed `PAGE_SIZE=20`, no client override) |
| Image upload validation | `PostImageUploadView` (`api_views.py:689–709`) — size + client `content_type` only | **gap** (partially mitigated: `ForumPostImage.image` is an ImageKit `ProcessedImageField`, so non-images fail during processing — but make it explicit + reject early) |
| Server-side HTML sanitization | `CreateTopicSerializer.create` / `CreatePostSerializer.create` store `content` raw on `Post.content` | **gap** |
| `content_format` unconstrained | `serializers.py:334` (topic), `:417` (post) — plain `CharField` | **gap** |
| AI-assist cost abuse | `forum_ai_assist` (`api_views.py:298`) — `IsAuthenticated`, unthrottled | **gap** |
| Attachment trust enforcement | `PostImageUploadView` (`api_views.py:645`) uses `PermissionHandler.can_attach_files()` | **already correct** |
| Trust-level reporting | primary path `api_views.py:1085` correct; `except` fallback `:1096` reports `is_staff` | **minor** |
| Topic/reply per-forum perms | `CreateTopicView`, `PostCreateView` — `IsAuthenticated` only (no `can_start_new_topics`/`can_reply_to_topics`) | **verify** (default perms grant these to all authed users → fine for public forums) |
| Ownership checks (edit/delete) | `api_views.py:389,419,660` | **already correct** |
| Search SQL wildcard escaping | `forum_search` via `escape_search_query` (`api_views.py:242`) | **already correct** |
| Dead permission-bypass code | server-rendered `views.py` + `*_simple.html`; gutted `apps/forum` | **remove** |

**Existing patterns to reuse:**

- Rate limiting: `@ratelimit(key=..., rate=RATE_LIMITS[...]["..."], method=..., block=True)` (`apps/users/views.py:88–93`); limits dict in `apps/plant_identification/constants.py`. 429 conversion + logging already handled centrally in `apps/core/exceptions.py`.
- CBV rate limiting via `method_decorator` — precedent in `apps/blog/api_views.py`, `apps/garden/viewsets.py`.
- File upload 4-layer validation: `docs/patterns/security/file-upload.md` (extension → MIME → size → PIL magic number).
- Constants convention: every app has `apps/<app>/constants.py` — `forum_integration` currently lacks one (create it).

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `backend/requirements.txt` | Modify | Add `nh3` |
| `backend/apps/forum_integration/constants.py` | Create | Rate limits, page-size cap, image-validation constants (no magic numbers) |
| `backend/apps/forum_integration/sanitization.py` | Create | `sanitize_forum_html()` (nh3 allowlist mirroring React `SANITIZE_PRESETS.FORUM`) |
| `backend/apps/forum_integration/serializers.py` | Modify | Sanitize `content` on write; `content_format` → `ChoiceField` |
| `backend/apps/forum_integration/api_views.py` | Modify | Rate-limit decorators; pagination clamps; 4-layer image validation; reporting-fallback fix |
| `backend/apps/forum_integration/management/commands/sanitize_forum_content.py` | Create | One-time backfill of existing `Post.content` |
| `backend/apps/forum_integration/views.py` + `templates/forum_integration/*_simple.html` | Delete | Dead permission-bypass server-rendered code |
| `backend/apps/forum/` | Delete | Gutted stub |
| `backend/apps/forum_integration/tests/test_security.py` | Create | Security regression suite |

Run backend commands from `backend/` with the venv active. Test DB after migration-affecting changes: `python manage.py test apps.forum_integration --noinput`.

---

## Task 0: Audit-first — run `security-reviewer`

- [x] **Step 1: Run the forum security review**

Invoked on 2026-05-26. Files reviewed: `api_views.py`, `serializers.py`, `models.py`, `forumService.ts`, `web/src/pages/forum/`, `web/src/components/forum/`.

- [x] **Step 2: Triage**

**CONFIRMED known gaps (all covered by existing tasks):**

- No rate limiting → Task 5
- Unbounded `page_size` in `all_topics_list` → Task 6. *Correction: `TopicDetailView` hardcodes 10 (not vulnerable).*
- Image upload: size + client content-type only → Task 7
- No server-side sanitization; `content_format` unconstrained → Tasks 2–3

**NEW HIGH findings:**

- [H1] `ForumCategoryListView`, `ForumTopicsListView`, `TopicDetailView`, `PostListView`, `TopicsFeedView`, `forum_search`, `PostImageListView`, `TopicMarkViewedView` — all bypass `PermissionHandler.can_read_forum()`. Private/restricted forums would leak to any caller. → Covered by Task 8 (verify if restricted forums exist; if yes, enforce). If all forums public (expected): document and close.
- [H2] `CreateTopicView` (line 169), `CreatePostView` (line 202), `PostCreateView` (line 350) — bypass `can_start_new_topics`/`can_reply_to_topics`; `CreatePostView`/`PostCreateView` also don't check `topic.status == TOPIC_LOCKED`. → Covered by Task 8.
- [H3] **NEW — IDOR on `UserTopicsListView`/`UserWatchedTopicsListView`** (`api_views.py:1254–1285`, `1293–1336`): `user_id` from URL is never validated against `request.user`. Any authenticated user can read any other user's topic/watched-topic history. → **Added to Task 10 (per-endpoint audit).**

**MEDIUM (out of scope, convert to todos):**

- M1: `all_topics_list:121`, `forum_ai_assist:327`, `PostReactionView:561`, `user_trust_level:1102` — `str(e)` returned in 500 responses.
- M2: `api_views.py:716` — `original_filename` stored/returned unsanitized from client.

**CLEARED (no issue):** CSRF wiring correct, SQL injection in search handled by `escape_search_query`, ownership checks on edit/delete correct, mass assignment not possible, frontend XSS covered by `sanitizeHtml`.

- [x] **Step 3: Commit the triage notes** (append to this plan; no code yet)

```bash
git add docs/superpowers/plans/2026-05-25-forum-phase2-security.md
git commit -m "docs(forum): record Phase 2 security-reviewer triage"
```

---

## Task 1: Forum constants module

**Files:**

- Create: `backend/apps/forum_integration/constants.py`

- [ ] **Step 1: Write the constants**

```python
# backend/apps/forum_integration/constants.py
"""Forum configuration constants (no magic numbers elsewhere)."""

# --- Rate limits (django-ratelimit `rate` strings) ---
# Keyed by authenticated user where possible; IP for anonymous-readable endpoints.
FORUM_RATE_LIMITS = {
    "create_topic": "10/h",
    "create_post": "30/h",
    "update_post": "30/h",
    "delete_post": "30/h",
    "react": "60/m",
    "upload_image": "20/h",
    "search": "30/m",
    "ai_assist": "20/d",  # per-user daily cap — direct cost vector
}

# --- Pagination ---
FORUM_MAX_PAGE_SIZE = 100
FORUM_DEFAULT_PAGE_SIZE = 25

# --- Image upload validation ---
FORUM_IMAGE_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
FORUM_IMAGE_ALLOWED_CONTENT_TYPES = ["image/jpeg", "image/png", "image/gif", "image/webp"]
FORUM_IMAGE_ALLOWED_EXTENSIONS = [".jpg", ".jpeg", ".png", ".gif", ".webp"]
# PIL format names corresponding to the allowed types
FORUM_IMAGE_ALLOWED_PIL_FORMATS = ["JPEG", "PNG", "GIF", "WEBP"]
FORUM_IMAGE_MAX_PER_POST = 6
```

- [ ] **Step 2: Commit**

```bash
git add backend/apps/forum_integration/constants.py
git commit -m "feat(forum): add forum constants (rate limits, pagination, image rules)"
```

---

## Task 2: nh3 sanitizer utility

**Files:**

- Modify: `backend/requirements.txt`
- Create: `backend/apps/forum_integration/sanitization.py`
- Test: `backend/apps/forum_integration/tests/test_sanitization.py`

- [ ] **Step 1: Add the dependency**

Add to `backend/requirements.txt` (keep alphabetical near `bleach`):

```text
nh3==0.2.18
```

Install: `cd backend && pip install nh3==0.2.18`

- [ ] **Step 2: Write the failing test**

```python
# backend/apps/forum_integration/tests/test_sanitization.py
from django.test import SimpleTestCase
from apps.forum_integration.sanitization import sanitize_forum_html


class SanitizeForumHtmlTests(SimpleTestCase):
    def test_strips_script_tags(self):
        dirty = '<p>hi</p><script>alert(1)</script>'
        clean = sanitize_forum_html(dirty)
        self.assertNotIn('<script', clean)
        self.assertIn('<p>hi</p>', clean)

    def test_strips_event_handlers_and_js_urls(self):
        self.assertNotIn('onerror', sanitize_forum_html('<img src=x onerror=alert(1)>'))
        self.assertNotIn('javascript:', sanitize_forum_html('<a href="javascript:alert(1)">x</a>'))

    def test_keeps_allowed_formatting(self):
        html = '<p><strong>bold</strong> <em>i</em> <a href="https://x.com">link</a></p>'
        clean = sanitize_forum_html(html)
        self.assertIn('<strong>bold</strong>', clean)
        self.assertIn('href="https://x.com"', clean)
```

- [ ] **Step 3: Write the implementation**

The allowlist is a **deliberate translation** of the React `SANITIZE_PRESETS.FORUM` preset (`web/src/utils/sanitize.ts`, ~line 146). Open that preset and reconcile the tag/attribute sets before finalizing (parity is the goal — see Step 5).

```python
# backend/apps/forum_integration/sanitization.py
"""Authoritative server-side HTML sanitization for forum content (nh3)."""
import nh3

# Mirror of web SANITIZE_PRESETS.FORUM — reconcile with web/src/utils/sanitize.ts.
ALLOWED_TAGS = {
    "p", "br", "span", "div",
    "strong", "b", "em", "i", "u", "s", "strike",
    "ul", "ol", "li",
    "blockquote", "code", "pre",
    "h1", "h2", "h3", "h4",
    "a", "img",
}
ALLOWED_ATTRIBUTES = {
    "a": {"href", "title", "rel", "target"},
    "img": {"src", "alt", "title", "width", "height"},
    "span": {"class"},
    "code": {"class"},
    "pre": {"class"},
}
ALLOWED_URL_SCHEMES = {"http", "https", "mailto"}


def sanitize_forum_html(html: str) -> str:
    """Return an XSS-safe subset of `html`. Authoritative — apply on every write."""
    if not html:
        return html
    return nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=ALLOWED_URL_SCHEMES,
        link_rel="noopener noreferrer nofollow",
    )
```

- [ ] **Step 4: Run the test**

Run: `cd backend && python manage.py test apps.forum_integration.tests.test_sanitization --noinput`
Expected: PASS.

- [ ] **Step 5: Parity check vs. the React preset**

Open `web/src/utils/sanitize.ts` `SANITIZE_PRESETS.FORUM`. Confirm `ALLOWED_TAGS`/`ALLOWED_ATTRIBUTES` here are a superset-or-equal of what the editor (TipTap) can emit and not narrower than the client allowlist (otherwise server strips content the client kept). Adjust and re-run the test. Document any intentional divergence in a code comment.

- [ ] **Step 6: Commit**

```bash
git add backend/requirements.txt backend/apps/forum_integration/sanitization.py backend/apps/forum_integration/tests/test_sanitization.py
git commit -m "feat(forum): add nh3 server-side HTML sanitizer for forum content"
```

---

## Task 3: Sanitize on write + constrain `content_format`

**Files:**

- Modify: `backend/apps/forum_integration/serializers.py`

- [ ] **Step 1: Constrain `content_format` (both write serializers)**

Replace the plain `CharField` at `serializers.py:334` (CreateTopicSerializer) and `:417` (CreatePostSerializer):

```python
    content_format = serializers.ChoiceField(
        choices=["plain", "draftail", "html"],
        required=False,
        write_only=True,
        default="plain",
    )
```

(Serializer-level only — **no model migration**, per the spec's Option-C scope. The model field stays as-is.)

- [ ] **Step 2: Sanitize `content` on write**

In `CreateTopicSerializer.create` (around `serializers.py:355`) and `CreatePostSerializer.create` (around `:436`), sanitize the post content before persisting. Add the import at top:

```python
from .sanitization import sanitize_forum_html
```

In `CreateTopicSerializer.create`, after `content = validated_data.pop("content")`:

```python
        content = sanitize_forum_html(content)
```

In `CreatePostSerializer.create`, the content is in `validated_data["content"]`; sanitize before the `Post.objects.create(...)`:

```python
        if "content" in validated_data:
            validated_data["content"] = sanitize_forum_html(validated_data["content"])
```

Also sanitize on update: `PostUpdateView` uses `CreatePostSerializer`; its `update` path runs `perform_update` which writes `validated_data["content"]`. Add a `validate_content` method to `CreatePostSerializer` so both create and update are covered uniformly:

```python
    def validate_content(self, value):
        return sanitize_forum_html(value)
```

If you add `validate_content`, you can drop the inline sanitize in `create` (DRF runs field validators before `create`/`update`). Do the same `validate_content` on `CreateTopicSerializer`.

- [ ] **Step 3: Write the test**

```python
# add to backend/apps/forum_integration/tests/test_security.py (created in Task 11)
def test_create_post_sanitizes_stored_html(self):
    # ...authenticate, POST a reply with '<p>ok</p><script>alert(1)</script>'
    # assert the persisted Post.content has no '<script'
```

- [ ] **Step 4: Run tests + commit**

Run: `cd backend && python manage.py test apps.forum_integration --noinput`

```bash
git add backend/apps/forum_integration/serializers.py
git commit -m "feat(forum): sanitize post content server-side and constrain content_format"
```

---

## Task 4: Legacy content backfill command

**Ordering requirement (from spec):** this ships in the **same release** as Task 3 and is **run as a required deploy step**, so no window exists where new content is sanitized but legacy rows are not.

**Files:**

- Create: `backend/apps/forum_integration/management/commands/sanitize_forum_content.py`

- [ ] **Step 1: Write the command**

```python
# backend/apps/forum_integration/management/commands/sanitize_forum_content.py
"""One-time backfill: re-sanitize all existing forum post content."""
from django.core.management.base import BaseCommand
from machina.apps.forum_conversation.models import Post
from apps.forum_integration.sanitization import sanitize_forum_html


class Command(BaseCommand):
    help = "Sanitize existing Post.content with the forum HTML allowlist."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Report changes without saving.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        changed = 0
        scanned = 0
        for post in Post.objects.all().iterator():
            scanned += 1
            cleaned = sanitize_forum_html(post.content or "")
            if cleaned != (post.content or ""):
                changed += 1
                if not dry_run:
                    post.content = cleaned
                    post.save(update_fields=["content"])
        verb = "would change" if dry_run else "changed"
        self.stdout.write(self.style.SUCCESS(f"[forum] scanned {scanned}, {verb} {changed} posts"))
```

- [ ] **Step 2: Test the command (real DB)**

```python
# add to test_security.py
def test_backfill_neutralizes_existing_malicious_content(self):
    # create a Post with content '<script>alert(1)</script>' directly,
    # call call_command('sanitize_forum_content'),
    # reload and assert no '<script' remains
```

- [ ] **Step 3: Run + commit**

Run: `cd backend && python manage.py test apps.forum_integration.tests.test_security --noinput`

```bash
git add backend/apps/forum_integration/management/commands/sanitize_forum_content.py backend/apps/forum_integration/tests/test_security.py
git commit -m "feat(forum): add one-time content sanitization backfill command"
```

---

## Task 5: Rate limiting

`django-ratelimit` raises `Ratelimited` (→ 429 via `apps/core/exceptions.py`). Function views use the bare decorator; class views use `method_decorator` on the handler method.

**Files:**

- Modify: `backend/apps/forum_integration/api_views.py`

- [ ] **Step 1: Add imports**

```python
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from .constants import FORUM_RATE_LIMITS, FORUM_MAX_PAGE_SIZE, FORUM_DEFAULT_PAGE_SIZE
```

- [ ] **Step 2: Decorate the function-based views**

`forum_search` (anonymous-readable → key by IP) and `forum_ai_assist` (authed, cost vector → key by user, daily):

```python
@api_view(["GET"])
@permission_classes([permissions.AllowAny])
@ratelimit(key="ip", rate=FORUM_RATE_LIMITS["search"], method="GET", block=True)
def forum_search(request):
    ...

@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
@ratelimit(key="user", rate=FORUM_RATE_LIMITS["ai_assist"], method="POST", block=True)
def forum_ai_assist(request):
    ...
```

- [ ] **Step 3: Decorate the class-based write views**

Apply `method_decorator` to the relevant handler. Examples:

```python
@method_decorator(
    ratelimit(key="user", rate=FORUM_RATE_LIMITS["create_topic"], method="POST", block=True),
    name="create",
)
class CreateTopicView(generics.CreateAPIView):
    ...

@method_decorator(
    ratelimit(key="user", rate=FORUM_RATE_LIMITS["create_post"], method="POST", block=True),
    name="create",
)
class PostCreateView(generics.CreateAPIView):
    ...
```

Apply equivalently to: `CreatePostView` (legacy `create`), `PostUpdateView` (`name="update"`, rate `update_post`), `PostDeleteView` (`name="destroy"`, rate `delete_post`), `PostReactionView` (`name="post"`, rate `react`), `PostImageUploadView` (`name="post"`, rate `upload_image`).

- [ ] **Step 4: Verify 429 wiring**

Confirm `apps/core/exceptions.py` is the configured `EXCEPTION_HANDLER` (it is — `REST_FRAMEWORK` in settings). No change needed; it converts `Ratelimited` → 429 and logs `"429 Rate Limit Exceeded"`.

- [ ] **Step 5: Test (one representative limit) + commit**

```python
# test_security.py — hammer create_post past its limit, assert a 429 appears
```

Run: `cd backend && python manage.py test apps.forum_integration.tests.test_security --noinput`

```bash
git add backend/apps/forum_integration/api_views.py
git commit -m "feat(forum): rate-limit forum write/search/AI endpoints"
```

> Note: rate-limit tests need the cache backend active. Use the real Redis/local-memory cache the test settings configure; do not mock it.

---

## Task 6: Pagination caps

**Files:**

- Modify: `backend/apps/forum_integration/api_views.py`

- [ ] **Step 1: Clamp `all_topics_list`**

Replace `page_size = int(request.GET.get("page_size", 25))` (`api_views.py:74`) with a clamped read:

```python
        page_size = min(
            max(1, int(request.GET.get("page_size", FORUM_DEFAULT_PAGE_SIZE))),
            FORUM_MAX_PAGE_SIZE,
        )
```

- [ ] **Step 2: Clamp `TopicDetailView` posts pagination**

In `TopicDetailView.retrieve` (the manual posts `Paginator`, ~`api_views.py:147`), apply the same clamp to any client-supplied page size. If it currently hardcodes 10, leave the size fixed but ensure no client override exceeds `FORUM_MAX_PAGE_SIZE`.

- [ ] **Step 3: Test + commit**

```python
# test_security.py — GET /topics/?page_size=100000 returns <= FORUM_MAX_PAGE_SIZE results
```

```bash
git add backend/apps/forum_integration/api_views.py
git commit -m "fix(forum): cap page_size on manual-pagination endpoints (DoS)"
```

---

## Task 7: 4-layer image upload validation

Reference `docs/patterns/security/file-upload.md`. Add **extension allowlist** and **PIL magic-number verification** to the existing size + MIME checks in `PostImageUploadView` (`api_views.py:696–709`).

**Files:**

- Modify: `backend/apps/forum_integration/api_views.py`

- [ ] **Step 1: Add imports + constants**

```python
import os
from PIL import Image, UnidentifiedImageError
from .constants import (
    FORUM_IMAGE_MAX_BYTES,
    FORUM_IMAGE_ALLOWED_CONTENT_TYPES,
    FORUM_IMAGE_ALLOWED_EXTENSIONS,
    FORUM_IMAGE_ALLOWED_PIL_FORMATS,
    FORUM_IMAGE_MAX_PER_POST,
)
```

- [ ] **Step 2: Replace the per-file validation block** (the `for i, uploaded_file ...` loop body, `api_views.py:696–709`)

```python
        for i, uploaded_file in enumerate(uploaded_files):
            # Layer 1: extension allowlist
            ext = os.path.splitext(uploaded_file.name)[1].lower()
            if ext not in FORUM_IMAGE_ALLOWED_EXTENSIONS:
                errors.append(f"File {uploaded_file.name} has an unsupported extension.")
                continue
            # Layer 2: declared MIME (cheap reject; not trusted alone)
            if uploaded_file.content_type not in FORUM_IMAGE_ALLOWED_CONTENT_TYPES:
                errors.append(f"File {uploaded_file.name} is not a supported image type.")
                continue
            # Layer 3: size
            if uploaded_file.size > FORUM_IMAGE_MAX_BYTES:
                errors.append(f"File {uploaded_file.name} is too large. Maximum size is 5MB.")
                continue
            # Layer 4: magic number — verify real image bytes with PIL
            try:
                uploaded_file.seek(0)
                with Image.open(uploaded_file) as im:
                    im.verify()
                    if im.format not in FORUM_IMAGE_ALLOWED_PIL_FORMATS:
                        errors.append(f"File {uploaded_file.name} content is not an allowed image.")
                        continue
                uploaded_file.seek(0)  # reset for storage
            except (UnidentifiedImageError, OSError):
                errors.append(f"File {uploaded_file.name} is not a valid image.")
                continue
            # ... existing ForumPostImage.objects.create(...) block unchanged ...
```

Also swap the hardcoded `max_size`/`allowed_types`/`> 6` checks above the loop to the constants (`FORUM_IMAGE_MAX_PER_POST`, etc.).

- [ ] **Step 3: Test + commit**

```python
# test_security.py:
# - upload a .txt renamed to .jpg with image/jpeg content_type → rejected (PIL layer)
# - upload an oversized file → rejected
# - upload a real small PNG → accepted
```

Run: `cd backend && python manage.py test apps.forum_integration.tests.test_security --noinput`

```bash
git add backend/apps/forum_integration/api_views.py
git commit -m "feat(forum): add 4-layer image upload validation (extension+MIME+size+PIL)"
```

---

## Task 8: Forum-level authz verify + reporting-fallback fix

- [ ] **Step 1: Determine the forum visibility model**

Check whether any `Forum` is configured with non-default (restricted) permissions (Wagtail/machina admin, or `forum_permission` rows). If **all forums are public** (the expected state), the `IsAuthenticated` gates on create/reply are functionally equivalent to machina's defaults — **document this and stop here for create/reply**.

- [ ] **Step 2: (Only if restricted forums exist) enforce per-forum create/reply perms**

In `CreateTopicView`/`PostCreateView`, before saving, check `PermissionHandler().can_start_new_topics(forum, user)` / `can_reply_to_topics(topic.forum, user)` and return 403 otherwise — mirroring the existing `can_attach_files` check in `PostImageUploadView` (`api_views.py:645`). **Time-box: 1 day.** If machina config proves heavy, keep `IsAuthenticated`, document, and file a follow-up todo.

- [ ] **Step 3: Fix the trust-level reporting fallback (minor)**

In `user_trust_level` (`api_views.py:1096`), the `except` fallback reports `"can_attach_files": user.is_staff`. Leave the value but add a comment that this is a degraded fallback only hit when the handler raises; optionally log a warning so the real failure is visible. No behavior change to enforcement.

- [ ] **Step 4: Commit**

```bash
git add backend/apps/forum_integration/api_views.py
git commit -m "chore(forum): verify forum-level authz; annotate trust-level fallback"
```

---

## Task 9: Remove dead permission-bypass code

These server-rendered views skip permission checks "for debugging" and are commented out of `urls.py` — delete them. Also delete the gutted `apps/forum` stub.

**Files:**

- Delete: `backend/apps/forum_integration/views.py`
- Delete: `backend/apps/forum_integration/templates/forum_integration/*_simple.html`
- Delete: `backend/apps/forum/`

- [ ] **Step 1: Confirm nothing imports them**

```bash
cd backend && grep -rn "forum_integration.views\|_simple.html\|apps.forum\b" --include='*.py' apps/ plant_community_backend/ | grep -v forum_integration.api_views
```

Expected: only the already-commented-out lines in `plant_community_backend/urls.py`. Remove those comment lines too.

- [ ] **Step 2: Delete + verify the app still boots**

```bash
cd backend
git rm backend/apps/forum_integration/views.py 2>/dev/null || git rm apps/forum_integration/views.py
git rm apps/forum_integration/templates/forum_integration/*_simple.html
git rm -r apps/forum
python manage.py check
```

Expected: `System check identified no issues`. (Confirm `apps.forum` is not in `INSTALLED_APPS` — it isn't.)

- [ ] **Step 3: Commit**

```bash
git add -A backend/apps/forum_integration backend/apps/forum backend/plant_community_backend/urls.py
git commit -m "chore(forum): remove dead permission-bypass views, simple templates, gutted app"
```

---

## Task 10: Per-endpoint authorization audit

- [ ] **Step 1: Enumerate and confirm**

For every entry in `api_urls.py`, confirm in `api_views.py`:

- `AllowAny` only on read-only endpoints (`categories`, `topics`, `posts` list/detail, `reactions` GET, `images` GET, `search`, `stats`).
- Every write requires `IsAuthenticated` **and** an ownership/staff or machina-permission check (create/update/delete post, update topic, upload/delete image).

Record the table in this plan as evidence (endpoint → permission → ownership check). Fix any gaps found as their own commit.

- [ ] **Step 2: Commit (if any fixes)**

```bash
git add backend/apps/forum_integration/api_views.py
git commit -m "fix(forum): close per-endpoint authorization gaps from audit"
```

---

## Task 11: Security regression suite

**Files:**

- Create: `backend/apps/forum_integration/tests/test_security.py`

- [ ] **Step 1: Assemble the suite** (gathering the assertions referenced in Tasks 3–7)

Cover, against a **real DB** (no mocks, per repo rule), using authenticated requests where needed:

- Stored-XSS payload is sanitized on create **and** update (no `<script>` persisted).
- `content_format` outside `{plain,draftail,html}` is rejected (400).
- `?page_size=100000` returns `<= FORUM_MAX_PAGE_SIZE` items.
- Spoofed-MIME / non-image upload rejected; oversized upload rejected; valid PNG accepted.
- Hitting a rate-limited endpoint past its limit yields **429** (use the configured cache).
- Non-owner edit/delete is forbidden (403).
- The backfill command neutralizes a pre-existing malicious `Post.content`.

- [ ] **Step 2: Run the full forum suite**

Run: `cd backend && python manage.py test apps.forum_integration --noinput`
Expected: all green.

- [ ] **Step 3: Commit**

```bash
git add backend/apps/forum_integration/tests/test_security.py
git commit -m "test(forum): add security regression suite (xss, rate-limit, upload, authz)"
```

---

## Self-Review (completed during authoring)

- **Spec coverage:** rate limiting (T5), pagination caps (T6), 4-layer image validation (T7), server-side sanitization + content_format (T3) + legacy backfill (T4), forum-level authz/trust fallback (T8), dead-code removal (T9), audit-first (T0) + per-endpoint audit (T10), regression tests (T11). Registration precondition is verified in Phase-1/launch checklist, not here.
- **Corrected scope:** attachment trust enforcement is **already wired** (`api_views.py:645`) — Phase 2 only fixes the reporting fallback (T8), not the enforcement. The spec was corrected accordingly.
- **No model migration:** `content_format` is constrained at the serializer; image/sanitization changes touch views/serializers only.
- **Placeholders:** the `security-reviewer` findings (T0) and the visibility-model check (T8.1) are runtime determinations, not placeholders — each has a defined action and fallback.

## Definition of Done (Phase 2)

- `security-reviewer` CRITICAL/HIGH findings resolved or converted to todos.
- All gaps in the verified-state table closed (or explicitly deferred with a todo).
- `python manage.py test apps.forum_integration --noinput` green, including the new security suite.
- Backfill command run as part of the deploy (same release as sanitize-on-write).
- No dead permission-bypass code remains.

## Finding Status

- [x] #M1 str(e) leaked in 500 responses → todo 097 (completed 2026-05-26)
- [x] #M2 original_filename unsanitized → todo 098 (completed 2026-05-26)
