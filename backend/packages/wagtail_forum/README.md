# wagtail-forum

A reusable, Wagtail-native community forum. Boards are Wagtail Pages; topics and
posts are feature-rich snippets (moderation workflow, revisions, locking, search).
A headless DRF API is optional (`pip install wagtail-forum[api]`).

The core imports nothing host-specific and uses `settings.AUTH_USER_MODEL`.

## Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Bootstrap: workflow and moderator group](#bootstrap-workflow-and-moderator-group)
- [Creating the page tree](#creating-the-page-tree)
- [Mounting the API](#mounting-the-api)
- [Settings](#settings)
- [Signals](#signals)
- [Spam backends](#spam-backends)
- [Error envelope](#error-envelope)
- [Idempotency](#idempotency)
- [Rate limiting](#rate-limiting)
- [Search backend](#search-backend)
- [Management commands](#management-commands)
- [Internationalization](#internationalization)

## Requirements

- Python >= 3.11
- Django >= 4.2
- Wagtail >= 7.0
- For the API extra: `djangorestframework>=3.14`, `nh3>=0.2`

## Installation

```bash
pip install wagtail-forum          # core (Wagtail pages + snippets + admin)
pip install wagtail-forum[api]     # + the headless DRF API
```

Add the app to `INSTALLED_APPS`. It relies on Wagtail's snippets and images apps,
so both must be present:

```python
INSTALLED_APPS = [
    # ...
    "wagtail.snippets",
    "wagtail.images",
    "wagtail.search",
    "modelcluster",
    "taggit",
    # ...
    "wagtail_forum",
]
```

Then migrate:

```bash
python manage.py migrate wagtail_forum
```

`WagtailForumAppConfig.ready()` imports `wagtail_forum.signals`, which registers
the counter/trust receivers. Nothing else is auto-wired — the bootstrap below is
deliberately host-owned.

## Bootstrap: workflow and moderator group

Two things are **not** created by migrations and must be bootstrapped by the host:

1. **The moderation workflow.** Untrusted content fails *closed* — if no workflow
   is assigned to Topic/Post, an untrusted post stays a draft rather than
   publishing unscreened. A forum without this bootstrap accepts posts that never
   become visible.
2. **A moderator group.** Moderators need Wagtail admin access plus change/publish
   permissions on the forum snippets.

The package ships the workflow half as `wagtail_forum.workflow.ensure_default_workflow()`
— idempotent, and it will not override a workflow a host has already assigned to
Topic/Post. The group half is a host pattern, because group naming and permission
scope are site policy.

Wire both from a `post_migrate` receiver in your own app (this is exactly what the
reference host does in `apps/forum_host/bootstrap.py`):

```python
# myhost/bootstrap.py
from django.db.models.signals import post_migrate


def ensure_forum_bootstrap(sender, **kwargs):
    # Guard on your own app label: by the time YOUR post_migrate fires,
    # wagtail_forum is fully migrated and its Permission rows exist.
    if getattr(sender, "label", None) != "myhost":
        return

    from django.contrib.auth.models import Group, Permission
    from wagtail_forum.workflow import ensure_default_workflow

    ensure_default_workflow()

    group, _ = Group.objects.get_or_create(name="Forum Moderators")
    perms = Permission.objects.filter(
        content_type__app_label="wagtail_forum",
        content_type__model__in=["topic", "post"],
        codename__in=[
            "view_topic", "change_topic", "delete_topic", "publish_topic",
            "view_post", "change_post", "delete_post", "publish_post",
        ],
    ) | Permission.objects.filter(
        # Without access_admin a moderator-only user cannot log into the CMS.
        content_type__app_label="wagtailadmin",
        codename="access_admin",
    )
    # add(), not set(): this runs on EVERY post_migrate, and set() would strip
    # permissions an admin granted the group by hand.
    group.permissions.add(*perms)


def connect():
    post_migrate.connect(
        ensure_forum_bootstrap, dispatch_uid="myhost.ensure_forum_bootstrap"
    )
```

Call `connect()` from your app config's `ready()`, and list your app **after**
`wagtail_forum` in `INSTALLED_APPS` so the permission rows exist when it runs.

## Creating the page tree

Boards live in the Wagtail page tree so a host can place the forum wherever it
likes:

- `ForumIndex` — the root forum node. Allowed child: `ForumBoard`.
- `ForumBoard` — one board/category. No children.

Create a `ForumIndex` under your site root in the Wagtail admin, then add
`ForumBoard` children. Both render a minimal server-side fallback template so
"View live", sitemaps, and crawlers do not 500; the DRF API is the intended UI.

Board visibility is enforced through Wagtail: a board with a `PageViewRestriction`
(or any descendant of a restricted ancestor) is invisible to the entire API.

## Mounting the API

```python
# urls.py
urlpatterns = [
    path("api/forum/", include("wagtail_forum.api.urls")),
]
```

Routes: boards, topics (list/detail/create), posts (list/create/edit/delete),
reactions, reports, image upload, profiles (`me` + public), search, delta `sync`,
user mention search, and notifications (list/unread-count/mark-read).

The package ships **no authentication and no throttling** by design — see
[Rate limiting](#rate-limiting).

## Settings

Every setting is read via `wagtail_forum.conf.get_setting(name)`, which looks up
`WAGTAILFORUM_<NAME>` in Django settings and falls back to the package default.
Values are deep-copied on read, so mutating a returned list/dict cannot poison
later reads.

### Moderation and trust

| Setting | Default | Purpose |
|---|---|---|
| `WAGTAILFORUM_SPAM_BACKEND` | `"wagtail_forum.spam.heuristic.HeuristicSpamBackend"` | Dotted path to the spam backend (see [Spam backends](#spam-backends)). |
| `WAGTAILFORUM_TRUST_AUTOPUBLISH_LEVEL` | `2` (`TrustLevel.MEMBER`) | Minimum author trust level that publishes without moderation. |
| `WAGTAILFORUM_TRUST_THRESHOLDS` | `{1: 1, 2: 5, 3: 50, 4: 200}` | `trust_level -> minimum visible post_count`. Trust is re-derived in **both** directions, so trust funded by posts later removed as spam is revoked. Keys may be strings (JSON/env-friendly). |
| `WAGTAILFORUM_SPAM_MAX_LINKS` | `3` | Heuristic backend: max `http(s)://` occurrences before rejection. |
| `WAGTAILFORUM_SPAM_BANNED_WORDS` | `[]` | Heuristic backend: case-insensitive substring blocklist. |
| `WAGTAILFORUM_REPORT_AUTO_HIDE_THRESHOLD` | `3` | Distinct open reports on one post before it is auto-unpublished pending review. |

Trust levels are `TrustLevel` in `wagtail_forum.models.profiles`:
`NEW=0`, `BASIC=1`, `MEMBER=2`, `REGULAR=3`, `LEADER=4`.

### Inline image uploads

Uploads land in a dedicated Wagtail collection, and a post body may only reference
images from that collection **that the author uploaded** — collection membership
alone is not sufficient.

| Setting | Default | Purpose |
|---|---|---|
| `WAGTAILFORUM_IMAGE_ALLOWED_EXTENSIONS` | `["jpg", "jpeg", "png", "gif", "webp"]` | Layer 1: extension allowlist. |
| `WAGTAILFORUM_IMAGE_ALLOWED_MIME_TYPES` | `["image/jpeg", "image/png", "image/gif", "image/webp"]` | Layer 2: declared content-type allowlist. |
| `WAGTAILFORUM_IMAGE_MAX_SIZE_BYTES` | `10485760` (10 MB) | Layer 3: size cap (DoS guard). |
| `WAGTAILFORUM_IMAGE_MAX_PIXELS` | `100000000` | Layer 4: PIL decompression-bomb threshold. |
| `WAGTAILFORUM_IMAGE_MAX_WIDTH` | `5000` | Layer 4: max pixel width. |
| `WAGTAILFORUM_IMAGE_MAX_HEIGHT` | `5000` | Layer 4: max pixel height. |
| `WAGTAILFORUM_IMAGE_COLLECTION_NAME` | `"Forum Images"` | Collection name, created lazily and idempotently under root. |

### Reads, caching, and sync

| Setting | Default | Purpose |
|---|---|---|
| `WAGTAILFORUM_VIEW_COUNT_DEDUP_SECONDS` | `900` (15 min) | Window in which repeat topic-detail GETs from the same user/IP count as one view. |
| `WAGTAILFORUM_TOPIC_READ_DEDUP_SECONDS` | `900` (15 min) | Read-marker dedup window. Deliberately **separate** from the view-count window — they gate unrelated concerns and only happen to share a default. |
| `WAGTAILFORUM_PUBLIC_READ_CACHE_SECONDS` | `60` | Shared-cache TTL for **anonymous** board list, topic list, and search only, so a CDN can offload public reads. Authenticated responses are always `private, no-store`. Topic detail and post list are never shared-cached (view counting; moderated-away content must stop serving immediately). Tradeoff: a just-removed topic can linger in the anon-cached *list* for up to this TTL. |
| `WAGTAILFORUM_SYNC_TOMBSTONE_RETENTION_DAYS` | `30` | How long `TopicDeletedLog` tombstones are kept. A client that has not synced within this window must do a full resync. See [Management commands](#management-commands). |
| `WAGTAILFORUM_UNREAD_LAUNCH_AT` | `"2026-07-16T00:00:00Z"` | Last-resort "unread" baseline for a user with no `TopicRead` **and** no `ForumProfile` row. Bounds the initial unread flood to topics active since launch. A real `ForumProfile.read_watermark_at` always wins once one exists. Must be an ISO-8601 datetime **with** a timezone offset; a malformed value raises loudly rather than silently degrading. |
| `WAGTAILFORUM_MENTION_MAX_PER_POST` | `10` | Max distinct `@mentions` resolved per post — bounds parse cost and notification fan-out on a mass-mention post. |

## Signals

Three signals are public API for hosts (push notifications, analytics, email).
They live in `wagtail_forum.signals`.

| Signal | Fired when | kwargs |
|---|---|---|
| `topic_created` | A topic is published for the **first** time | `sender=Topic`, `topic=<Topic>`, `post=<opening Post or None>` |
| `reply_added` | A non-opening post is published for the **first** time | `sender=Post`, `topic=<Topic>`, `post=<Post>` |
| `moderation_decided` | A create or edit finishes routing | `sender=type(obj)`, `obj=<Topic or Post>`, `status="published"` or `"pending"` |

```python
from django.dispatch import receiver
from wagtail_forum.signals import reply_added


@receiver(reply_added)
def push_on_reply(sender, topic, post, **kwargs):
    ...
```

Contract notes:

- **First publish only.** A moderator edit-republish does not re-fire
  `topic_created`/`reply_added`.
- **`post` may be `None`** on `topic_created` for an admin-created topic that has
  no opening post yet.
- **Fired synchronously inside the publish transaction.** A receiver that hands
  off to async work (Celery, FCM) should wrap it in `transaction.on_commit()`
  itself — and register that hook only after the write it depends on succeeded.
- **Receiver exceptions are swallowed.** Signals are dispatched with
  `send_robust()` and failures are logged to the `wagtail_forum` logger, so
  third-party receiver code cannot abort a publish or corrupt the denormalized
  counters.

## Spam backends

Screening is pluggable. Point `WAGTAILFORUM_SPAM_BACKEND` at any dotted path
resolving to a class with a no-argument constructor and a `check()` method:

```python
from wagtail_forum.spam.base import SpamBackend, SpamResult


class MySpamBackend(SpamBackend):
    def check(self, obj) -> SpamResult:
        # obj is a Topic or a Post.
        text = self.extract_text(obj)   # title + opening-post topic title + body
        if is_bad(text):
            return SpamResult(False, "why it was rejected")
        return SpamResult(True)
```

- `SpamResult(is_clean: bool, reason: str = "")`.
- `extract_text(obj)` flattens title + StreamField body into one string. For an
  opening post it also folds in the topic title — the topic's own workflow is
  never started, so title spam would otherwise publish unscreened.
- A backend that **raises** leaves the content as a draft (fail closed) and still
  fires `moderation_decided` with `status="pending"`.

The shipped default, `HeuristicSpamBackend`, rejects on link count
(`SPAM_MAX_LINKS`) and a case-insensitive word blocklist (`SPAM_BANNED_WORDS`).
Its `check_text()` is split out so a composite backend (e.g. one that also calls
an LLM) can flatten a large body once and screen the same string twice.

## Error envelope

Every API error path raises a DRF `APIException` (never a hand-built
`Response({"detail": ...})`), so all errors flow through one exception handler
and share a single envelope:

```json
{
  "error": true,
  "message": "Idempotency-Key was already used with a different payload.",
  "code": "unprocessable",
  "status_code": 422,
  "errors": {"body": ["This field is required."]}
}
```

`errors` carries field-level validation errors, or `{"detail": "<message>"}` for
a non-field error; it is absent when the exception has no detail.

**This envelope is host-owned.** Without registering a handler you get bare DRF
responses (`{"detail": ...}`) — a silently different contract. Register the
shipped reference handler:

```python
REST_FRAMEWORK = {
    "EXCEPTION_HANDLER": (
        "wagtail_forum.api.exception_handler.forum_exception_handler"
    ),
}
```

A host may substitute its own compatible handler — the plant_id reference host
uses `apps.core.exceptions.custom_exception_handler`, which emits the identical
core envelope plus an optional `request_id` and a 429 branch for its rate limiter.

## Idempotency

Every unsafe write (`topic`/`reply`/`image` create, `post` edit, `reaction`
toggle, `report`) honours an `Idempotency-Key` request header: a retry with the
same key replays the original response (original status code) instead of
repeating the side effect; reuse with a different body returns `422`; a same-key
twin still in-flight returns `409`. Keys are scoped per (endpoint, user) and
cached for 24h. See `api/idempotency.py`.

## Rate limiting

The package ships no throttling by design — auth and rate limits are the host's
responsibility. Wrap the API views (see `apps/forum_host/api.py` in the
reference host: `method_decorator(ratelimit(...))` subclasses mounted in place
of `wagtail_forum.api.urls`, with a route-parity test against this package).

Note that host subclassing means package-only tests exercise the *unwrapped*
view class; test new read-view behaviour through your own mount too.

## Search backend

`/search/` delegates to `wagtail.search.backends.get_search_backend()`, so the
quality of forum search is entirely the host's backend choice.

- **PostgreSQL** — with `django.contrib.postgres` in `INSTALLED_APPS`, Wagtail's
  default backend resolves to `PostgresSearchBackend`: real full-text search with
  `ts_rank` ranking and GIN indexes applied by Wagtail's own migrations. No extra
  configuration needed.
- **Elasticsearch / OpenSearch** — configure `WAGTAILSEARCH_BACKENDS` as usual.
- **SQLite or an unknown vendor** — the database fallback degrades to an
  unindexed `icontains` scan over topic titles. Fine for development, not for
  production traffic.

Known limitation on all backends: results are capped at 50 with no pagination and
no `has_more` flag.

## Management commands

```bash
python manage.py prune_forum_tombstones [--days N]
```

Deletes `TopicDeletedLog` rows older than the retention window
(`WAGTAILFORUM_SYNC_TOMBSTONE_RETENTION_DAYS`, default 30; `--days` overrides).

**This must be scheduled** (cron, Celery beat, or a platform cron service) or the
tombstone table grows unboundedly. Tombstones let delta-sync clients evict
deleted topics without a full resync, so the retention window is also the maximum
time a client may be offline before it needs one.

## Internationalization

User- and admin-facing strings are wrapped in `gettext_lazy`: Wagtail admin menu
labels and the search area, model choice labels (trust levels, report reasons and
statuses, reaction types, notification verbs), and every DRF error message raised
by the API.

The package ships an extracted source catalog at
`wagtail_forum/locale/en/LC_MESSAGES/django.po`. To add a language:

```bash
cd <site-packages>/wagtail_forum        # or the package source tree
django-admin makemessages -l de
# translate django.po, then:
django-admin compilemessages -l de
```

The committed `en` catalog is an extraction **snapshot**, not a translation
(every `msgstr` is empty, so English resolves to the msgid either way). Re-run
`makemessages` after adding a translatable string to keep it current.

Compiled `.mo` files are not committed — Django reads the compiled catalog, not
the `.po` — so `compilemessages` must run as part of your build or deploy step.
A build that skips it ships the catalogs **inert**: every locale silently falls
back to the msgid, with no error to notice.

The reference host wires this into its image build (`backend/Dockerfile`), and a
reusing host needs the same two pieces:

1. **`gettext` in the image** — it provides `msgfmt`. `gettext-base` is *not*
   enough; it omits `msgfmt` and `compilemessages` fails with "Can't find
   msgfmt".
2. **`python manage.py compilemessages`** as a build step. It walks the tree
   from the working directory collecting `locale/` dirs, so running it from the
   project root picks up this package's catalog automatically — no
   `LOCALE_PATHS` entry needed. Run it *before* `collectstatic` so the walk does
   not traverse the collected static tree.

Today this compiles only the `en` snapshot, which is a no-op at runtime — the
point is that the pipeline is live, so adding `locale/de/` is the only step
required to get real translations.

Two deliberate omissions:

- **Developer-facing strings are not translated** — logger calls,
  `ImproperlyConfigured` messages, and management-command help text, following
  Django's own convention.
- **Persisted strings are not translated either**, deliberately: the workflow
  and task names (`"Forum moderation"`, `"Spam check"`) are `get_or_create`
  lookup keys, so translating them would create a duplicate workflow row per
  locale; and a `SpamResult.reason` is stored as a Wagtail workflow rejection
  comment, where rendering it in whichever locale happened to be active at
  write time would corrupt the moderation audit trail.
- **`TranslatableMixin` is not applied to Topic/Post.** Forum content is
  user-generated, so it needs *interface* translation, not *content* translation;
  adopting the mixin would add `locale`/`translation_key` fields and a
  `unique_together(translation_key, locale)` constraint interacting with the
  existing slug and opening-post constraints, plus migrations on live tables —
  cost with no current consumer. Note that `ForumIndex`/`ForumBoard` are Wagtail
  `Page` subclasses and therefore *already* carry `locale`/`translation_key`, so
  board structure is translatable today. Revisit if a host adopts
  wagtail-localize and genuinely needs per-locale topic content.

## Development

```bash
# From the host project (the package is tested inside a host that provides settings)
pytest packages/wagtail_forum apps/forum_host --create-db
```

Use `--create-db`: the suite creates Wagtail pages, and a reused test database
whose page tree was truncated by an earlier `TransactionTestCase` fails with
`Page.DoesNotExist`.

`tests/test_reusability.py` asserts the package never imports the host's `apps.*`
namespace. `tests/test_docs.py` asserts this README documents every setting in
`conf.DEFAULTS` and every public signal — add both when you add either.
