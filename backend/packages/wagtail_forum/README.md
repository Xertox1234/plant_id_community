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
- [Previews](#previews)
- [Mounting the API](#mounting-the-api)
- [Settings](#settings)
- [Signals](#signals)
- [Spam backends](#spam-backends)
- [List envelopes](#list-envelopes)
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

Add the app to `INSTALLED_APPS`. It relies on Wagtail's snippets, images, and
search apps plus `django-taggit` (topic tags), so all four must be present:

```python
INSTALLED_APPS = [
    # ...
    "wagtail.snippets",
    "wagtail.images",
    "wagtail.search",
    "taggit",
    # ...
    "wagtail_forum",
]
```

(`modelcluster` is deliberately absent from this list: it is a Wagtail-core
prerequisite every Wagtail host already installs, and no forum model uses it —
`Topic.tags` is a plain `TaggableManager`, not `ClusterTaggableManager`.)

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
The two page templates extend a shared `wagtail_forum/base.html` skeleton that
also renders `{% wagtailuserbar %}`, so an editor landing on "View live" has a
route back to the admin. Hosts may override any of the three templates under
`templates/wagtail_forum/`.

Board visibility is enforced through Wagtail: a board with a `PageViewRestriction`
(or any descendant of a restricted ancestor) is invisible to the entire API.

## Previews

`Post` previews through Wagtail's built-in `PreviewableMixin` with a
server-rendered template (`admin/post_preview.html`) — deliberately **not**
through a headless-preview library, even in a host (like this repo) whose blog
previews through the SPA via `wagtail_headless_preview`. Three reasons: the
preview pane renders draft StreamField content for moderators with zero
SPA work; the package stays free of an extra dependency; and headless preview
targets Pages, while `Post` is a snippet, so its support there would need
verifying first. Revisit only if moderators need previews in the real SPA
rendering (todo 299 records the costed alternative).

## Mounting the API

```python
# urls.py
urlpatterns = [
    path("api/forum/", include("wagtail_forum.api.urls")),
]
```

Routes: boards, topics (list/detail/create), posts (list/create/edit/delete),
reactions, reports, image upload, profiles (`me` + public), search, delta `sync`,
user mention search, notifications (list/unread-count/mark-read), recent topics,
community experts, and the landing-page event hero.

The package ships **no authentication and no throttling** by design — see
[Rate limiting](#rate-limiting).

### Wagtail API v2

The page types are deliberately **not** registered with Wagtail API v2 and
declare no `api_fields`. The DRF API above is the sole content contract:
`ForumIndex.intro` is delivered — expanded and nh3-sanitized — inside the
board-list envelope, and `ForumBoard.description` inside each board object.
Declaring `api_fields` would open a second delivery path that serves rich text
in raw DB form (v2 does not run `expand_db_html`) and bypasses the sanitizer.
A host's generic `pages` endpoint still lists the forum pages with base `Page`
fields only; that is the intended exposure.

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

#### Alt text (M7)

`POST /forum/images/` accepts an optional **`alt`** multipart part alongside
`image`. It is stripped, truncated to 255 chars, and stored on Wagtail's own
`Image.description` field; `serialize_image_for_api` returns it as `alt`.

Three consequences worth knowing before changing this:

- **`alt` never falls back to `title`.** `title` is the upload filename, and
  filename-as-alt is an accessibility anti-pattern — a screen reader announcing
  `IMG_2481.jpg` is worse than announcing nothing. An image uploaded without
  `alt` serves `alt: ""`, which is the correct markup for a decorative image.
  Images uploaded before M7 therefore serve `""` rather than their filename.
- **Alt is per-image, not per-usage.** The body block value stays a bare image
  `int`, so re-embedding one upload in a second post reuses the first post's alt.
  Accepted: forum uploads are effectively single-use, and per-usage alt would
  mean a StreamField `int` → `dict` data migration across every post *and*
  revision.
- **There is no alt PATCH endpoint.** Alt is captured at upload time only;
  correcting it means uploading the image again. `alt` is also deliberately
  excluded from the idempotency fingerprint, so a same-key retry carrying
  corrected alt replays the original response (including the original alt)
  rather than 422-ing.

### Reads, caching, and sync

| Setting | Default | Purpose |
|---|---|---|
| `WAGTAILFORUM_VIEW_COUNT_DEDUP_SECONDS` | `900` (15 min) | Window in which repeat topic-detail GETs from the same user/IP count as one view. |
| `WAGTAILFORUM_TOPIC_READ_DEDUP_SECONDS` | `900` (15 min) | Read-marker dedup window. Deliberately **separate** from the view-count window — they gate unrelated concerns and only happen to share a default. |
| `WAGTAILFORUM_PUBLIC_READ_CACHE_SECONDS` | `60` | Shared-cache TTL for **anonymous** board list, topic list, search, recent topics, experts rails, and the event hero only, so a CDN can offload public reads. Authenticated responses are always `private, no-store`. Topic detail and post list are never shared-cached (view counting; moderated-away content must stop serving immediately). Tradeoff: a just-removed topic can linger in the anon-cached *list* for up to this TTL. |
| `WAGTAILFORUM_RECENT_TOPICS_DEFAULT_LIMIT` | `5` | Default row count for `GET topics/recent/` (the landing "Active now" rail) when `?limit=` is omitted. |
| `WAGTAILFORUM_RECENT_TOPICS_MAX_LIMIT` | `20` | Cap on `?limit=` for `GET topics/recent/`. Bounded because each row may resolve a thumbnail rendition. |
| `WAGTAILFORUM_EXPERTS_LIMIT` | `4` | Max row count for `GET users/experts/` (the "Community experts" / "Experts online" landing rail). |
| `WAGTAILFORUM_EXPERTS_MIN_TRUST_LEVEL` | `3` | Minimum trust level to appear in `GET users/experts/`. (3 = TrustLevel.REGULAR) |
| `WAGTAILFORUM_PRESENCE_TOUCH_THROTTLE_SECONDS` | `300` (5 min) | Max frequency of the `ForumProfile.last_seen` write on an authenticated forum request — cache-gated (`cache.add`), so a burst of requests from one user costs one write, not one per request. |
| `WAGTAILFORUM_PRESENCE_ONLINE_WINDOW_SECONDS` | `900` (15 min) | Freshness `last_seen` must be within for `GET users/experts/`'s `online` field to report `true`. Deliberately separate from the throttle above — same "unrelated concerns, same default coincidentally" reasoning as the dedup pair above. |
| `WAGTAILFORUM_SEARCH_MAX_TERMS` | `50` | Max whitespace-separated terms `SearchView` passes to the search backend. A many-term query recurses Wagtail's search-query AND-tree construction (one nesting level per term) into a `RecursionError`/500; excess terms are truncated, not rejected with 400. |
| `WAGTAILFORUM_SEARCH_MAX_QUERY_CHARS` | `500` | Max characters of `?q=` `SearchView` will process, applied before the term-count cap. Mirrors `SIMILAR_QUERY_MAX_CHARS` on the semantic-search path. |
| `WAGTAILFORUM_SYNC_TOMBSTONE_RETENTION_DAYS` | `30` | How long `TopicDeletedLog` tombstones are kept. A client that has not synced within this window must do a full resync. See [Management commands](#management-commands). |
| `WAGTAILFORUM_UNREAD_LAUNCH_AT` | `"2026-07-16T00:00:00Z"` | Last-resort "unread" baseline for a user with no `TopicRead` **and** no `ForumProfile` row. Bounds the initial unread flood to topics active since launch. A real `ForumProfile.read_watermark_at` always wins once one exists. Must be an ISO-8601 datetime **with** a timezone offset; a malformed value raises loudly rather than silently degrading. |
| `WAGTAILFORUM_MENTION_MAX_PER_POST` | `10` | Max distinct `@mentions` resolved per post — bounds parse cost and notification fan-out on a mass-mention post. |
| `WAGTAILFORUM_TOPIC_MAX_TAGS` | `5` | Max tags accepted per topic on create. `taggit` creates a `Tag` row per unseen name, so an unbounded list is a cheap write-amplification vector against the shared tag table. |
| `WAGTAILFORUM_TOPIC_TAG_MAX_LENGTH` | `50` | Max characters per tag (must stay `<=` taggit's `Tag.name` max_length of 100). Tags are normalized on write — trimmed, inner whitespace collapsed, lowercased, de-duplicated — so `?tag=` matches one canonical spelling. |
| `WAGTAILFORUM_TOPIC_IDENTIFICATION_MAX_CANDIDATES` | `3` | Max suggested species in a topic's identification snapshot. See [Identification attachment](#identification-attachment) — the snapshot is caller-supplied, so this bounds how much unverified text one create can park on a topic. |
| `WAGTAILFORUM_TOPIC_IDENTIFICATION_NAME_MAX_LENGTH` | `200` | Max characters per candidate `name` / `scientific_name`. Inner whitespace is collapsed on write, so a "name" of 200 newlines can't pass the length check. |
| `WAGTAILFORUM_TOPIC_IDENTIFICATION_PROVIDER_MAX_LENGTH` | `50` | Max characters for the snapshot's `provider` label. Must stay `<=` the model column's `max_length` (50). |

## Identification attachment

A topic may carry **one** `ForumIdentificationAttachment` — a snapshot of a
plant-ID result the author attached when composing (audit M6). It is what makes
a help-identify topic answerable without a round trip: the photo and the app's
own suggestions arrive with the question.

**It is a snapshot, not a reference.** No FK into the host's identification
domain, and not a StreamField body block:

- Purging private identification history (GDPR) must never blank out or break
  public forum content.
- A plain model migrates normally; a body block would need a StreamField data
  migration across every stored body.
- It hangs off the *topic*, so it survives the opening post being edited,
  redacted, or replaced.

**Every field is caller-supplied.** This package does not import the host's
identification app, and there is no server-side record to resolve — the composer
sends the snapshot it received and the row records *what the author says the app
told them*. The write bounds above are the defence; a host's UI should label the
card as the author's attached app result, not a verified determination.

Write it by nesting an `identification` object in the topic-create payload:

```json
{
  "title": "Is this a monstera or a philodendron?",
  "slug": "is-this-a-monstera-or-a-philodendron",
  "body": [{"type": "paragraph", "value": "<p>App wasn't sure.</p>"}],
  "identification": {
    "image_id": 42,
    "provider": "plant_id",
    "candidates": [
      {"name": "Swiss cheese plant", "scientific_name": "Monstera deliciosa", "confidence": 0.82}
    ]
  }
}
```

`image_id` is optional and must be an image the caller uploaded into the forum
image collection (`POST /forum/images/`) — the same IDOR rule as avatars and
inline post images. The FK is `SET_NULL`, so a deleted photo leaves the
candidates readable and the card falls back to text-only.

**Read side: topic detail only.** `GET /forum/topics/{id}/` returns
`identification` as `{image, provider, candidates, created_at}` or `null`. The
topic list and both search hit-builders deliberately do **not** carry it — the
card renders above the opening post and nowhere else. The model's
`identification_result_id` is never serialized out: it is an internal
correlation handle pointing into private history.

## Signals

Four signals are public API for hosts (push notifications, analytics, email).
They live in `wagtail_forum.signals`.

| Signal | Fired when | kwargs |
|---|---|---|
| `topic_created` | A topic is published for the **first** time | `sender=Topic`, `topic=<Topic>`, `post=<opening Post or None>` |
| `reply_added` | A non-opening post is published for the **first** time | `sender=Post`, `topic=<Topic>`, `post=<Post>` |
| `moderation_decided` | A create or edit finishes routing | `sender=type(obj)`, `obj=<Topic or Post>`, `status="published"` or `"pending"` |
| `solution_marked` | A post is accepted as a topic's answer | `sender=Topic`, `topic=<Topic>`, `post=<accepted Post>`, `actor=<User who accepted>` |

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
- **`solution_marked` fires on accept only, never on clear**, and not on a
  re-accept of the post that is already the answer — so a receiver may treat it
  as "this answer was newly accepted" without deduplicating. It is fired from
  the API view (inside `transaction.on_commit`) rather than from a model
  signal, because only the request knows the `actor`. `post.author` may be
  `None` if that account was since deleted.
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

## List envelopes

The forum API ships **five** list-collection shapes. They are not converging:
each one carries information the cursor envelope cannot express, and the audit
that raised this (M40) asked for one documented contract *or* a documented
divergence. This is the divergence, stated deliberately.

| Endpoint(s) | Envelope | Why not cursor |
|---|---|---|
| topic list, post list, notification list | `{results, next, previous}` (DRF `CursorPagination`) | — this is the default; use it for any new collection. |
| `GET boards/` | `{results, intro}` — flat, no cursor | Boards are a handful of Wagtail pages rendered as one nav tree. `pagination_class = None`; a `next` that is always `null` would imply paging that does not exist. `intro` is the `ForumIndex` welcome copy (expanded + sanitized HTML, `""` when unset) — it belongs to the same screen as the boards and is always fetched with them, so it rides the envelope instead of costing a second round-trip. Media embeds and images are stripped *before* expansion, never after: expanding one would fire Wagtail's untimed oEmbed `requests.get` (or generate a rendition) on this public, CDN-fronted endpoint, and sanitizing only the output would discard the result while still paying for it. |
| `GET search/` | `{topics, posts, topics_has_more, posts_has_more, page}` | **Two** independently-paged result sets in one response. A cursor envelope has one `results`; splitting search into two round-trips would double the query cost of every keystroke. Offset-paged (not keyset) because the ordering is relevance, which a concurrent write reshuffles — so `page` is echoed back and clients dedup by id when appending. |
| `GET sync/` | `{topics, deleted, has_more, next_since, next_since_id}` | A delta poll, not a page. `deleted` carries tombstones (ids to evict) that no `results` list can represent, and the cursor is a compound `(updated_at, id)` the client persists across sessions — DRF's opaque cursor is per-response and not resumable days later. |
| `GET topics/recent/`, `GET users/experts/` | `{results}` — bare, no cursor, no `intro` | Fixed-size landing-rail snapshots (`?limit=`/`RECENT_TOPICS_MAX_LIMIT`, `EXPERTS_LIMIT`), not incrementally paged — there is no `next` page to request, and neither carries a sibling field like `intro` to justify the flat envelope's extra key. |

A host may add sections to these: the plant_id reference host appends a premium
`semantic` array to the search payload (`apps/forum_host/semantic_search.py`).
Additive only — a host must not change a shipped key's meaning.

### Section items are lighter than list items, on purpose

Search items are **not** `TopicListSerializer` / `PostSerializer` payloads, and
enriching them is a non-goal:

- The **post** item is `{id, topic_id, topic_title, topic_slug, board_id,
  board_slug, excerpt}`. `excerpt` is a plain-text slice built from the
  StreamField's `raw_data` (`plain_text_excerpt`), precisely so search does not
  resolve every hit's body. Serializing the full body per hit re-introduces the
  per-post image bulk-fetch that helper exists to avoid — the cost lands on the
  forum's most-hit anonymous, CDN-cached endpoint.
- Neither search item carries an `author`. Search ranks text, and adding one
  would mean joining the whole `author__wagtail_forum_profile__avatar` chain for
  two result sets per query. Clients render the `[deleted]`-style sentinel
  (`web/src/services/forumMappers.ts`).
- Topic items **do** carry `reply_count`, `view_count`, `last_post_at` and
  `is_pinned` — the board-list metadata a result row displays. `is_pinned` is
  there because a pinned topic is pinned wherever it surfaces, not because
  search is pinned-first: search order is relevance, always.

A client that needs the full object follows the id to `topics/<id>/` or
`topics/<id>/posts/`.

### Versioning

These shapes are **not** negotiated per request — every forum view opts out of
DRF request versioning (`api/versioning.py`, one shared mixin). A breaking
response change is therefore a package version bump plus a coordinated client
update, never a new `/v2/` path.

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

Paging is backend-independent and is described under
[List envelopes](#list-envelopes): each section returns up to `SearchView.PAGE_SIZE`
(20) results per page with an honest `*_has_more` flag, and `?page=` is bounded at
`MAX_PAGE` (50) to cap the SQL OFFSET — so roughly the first 1,000 hits per
section are reachable. (An earlier revision of this section claimed results were
"capped at 50 with no pagination and no `has_more` flag"; that predates the
paging work and was wrong.)

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
