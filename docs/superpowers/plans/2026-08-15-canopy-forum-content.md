# Canopy Forum Content & Artifact Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Populate the forum with the five Canopy boards and a believable demo world, add the three small read endpoints the landing page needs, and rebuild the forum landing + topbar to match the approved Canopy artifact (event hero, chips, "Your season", rail modules, ⌘K palette) with honest zero-states for streak/presence.

**Architecture:** Backend work lands in two places — the reusable `wagtail_forum` package gets a `ForumProfile.title` field and three read endpoints (`me/stats/`, `topics/recent/`, `users/experts/`); the host app `apps/forum_host` gets the `seed_demo_content` command plus its content module and committed image assets. The web side extends `forumTones` into a board identity map, rebuilds `CategoryListPage`'s hero/chips/stats/rail, and mounts a `CommandPalette` in `AppShell`.

**Tech Stack:** Django 6 / DRF / Wagtail 7 (package: `backend/packages/wagtail_forum/`), React 19 + TypeScript + Tailwind 4 + Vitest 4 + Playwright.

**Spec:** `docs/superpowers/specs/2026-08-15-canopy-forum-content-design.md` (binding; conflicts resolve against it). Parent: `docs/superpowers/specs/2026-08-13-canopy-design.md`.

**Branch:** `feat/canopy-forum-content` off `main` — ONLY after PR #537 has merged. Verify with `git log --oneline origin/main -1` that the squash of #537 is present before branching.

**Plan-time verification corrections to the spec** (verified against code, the spec's own "plan verifies" clauses):

- `ForumIdentificationAttachment` is **topic-level** (OneToOne on `Topic`), not post-level. `identifications_shared` therefore counts attachments on topics the user authored.
- Counters/trust fire on Wagtail's `published` signal — the seed publishes posts via `save_revision().publish()` (mirrors `wagtail_forum/tests/test_counters.py`), never bulk-creates.
- Appointed trust survives recounts (`signals.py` `_refresh_profile` takes `max(current, earned)` when current > earned) — the seed may assign trust levels before creating content.
- Public caching reuses the package's existing `PublicForumReadCacheMixin` (`PUBLIC_READ_CACHE_SECONDS = 60`) — no new cache machinery.
- `users/search/` is `IsAuthenticated` → the palette's People section is auth-only.

## Global Constraints

Copied from the spec + repo rules; every task's requirements include these.

- **Backend:** new endpoints use `UnversionedForumAPIMixin`, `@extend_schema`, the package error shape; all tunables in `conf.py` `DEFAULTS` (package) or module-level constants (host command) — no magic numbers inline. `users/experts/` must be routed BEFORE `users/<str:username>/`. The recent-topics endpoint owns its shape (dict-building like `PublicProfileView`) — it must NOT use `TopicListSerializer` (three-hit-builder rule, todo 273). Nothing FKs into plant-ID history — identification content is snapshot data only. Raw SQL never uses f-strings for identifiers (no raw SQL is expected).
- **Seed:** idempotent by natural keys (users: username; boards: slug; topics: slug-per-board; topic-granular skip for posts/reactions/solutions/images). Two-layer guard: `DEBUG=False` requires `--confirm`; any real (non-demo, non-superuser) account aborts regardless of flags. Demo users: `set_unusable_password()`, `<username>@demo.houseplant-md.com`. Timestamps spread post-hoc via `queryset.update()`; content creation goes through normal ORM + `save_revision().publish()`.
- **Web:** CSS values use `--gt-*` semantic tokens, never raw `--canopy-*` in property positions; rules that must beat a utility go UNLAYERED. Router imports from `'react-router-dom'`. Tap targets ≥44px (`min-h-11`). `PageMeta` titles end `· Houseplant MD`. Debounce timers in `useRef`. Async effects carry race guards (`ignore` flag or request epoch). No fabricated data: streak and presence are zero-states exactly as specced.
- **Tests:** Vitest hooks use block bodies — never `beforeEach(() => mock.mockReset())` (teardown-replay); mock values set in `beforeEach` (repo `restoreMocks: true` wipes factory-chained values). Playwright forum locators scoped to `#main-content` (and exclude the hero CTAs where the board list is the target); run Playwright via `./node_modules/.bin/playwright`, NEVER `npx playwright` (rtk mangles args). RailSlot portals are null in jsdom — rail modules get module-level tests. Backend: page-creating suites need `--create-db` on partial re-runs; never run two pytest invocations concurrently.
- **Commits:** web files get `npx prettier --write` before staging; commit trailer `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`; after any hook-gated commit verify HEAD moved (`git log --oneline -1`) — markdownlint/formatters abort commits after modifying files (re-add + re-commit).
- **Honesty ledger (spec §9):** streak card = zero-state ("—" / "Coming soon"), experts module = "Community experts" with NO dots and NO online claim, no progress bars anywhere, `me/stats` are all-time and sublabels must not claim a season.

---

### Task 1: Seed image assets (CONTROLLER-EXECUTED — Runware MCP)

The controller runs this task directly (subagents have no image-generation access).

**Files:**

- Create: `backend/apps/forum_host/seed_assets/post-monstera-albo.webp`
- Create: `backend/apps/forum_host/seed_assets/post-fiddle-leaf.webp`
- Create: `backend/apps/forum_host/seed_assets/post-hosta-damage.webp`
- Create: `backend/apps/forum_host/seed_assets/post-mealybugs.webp`
- Create: `backend/apps/forum_host/seed_assets/post-balcony-before.webp`
- Create: `backend/apps/forum_host/seed_assets/post-balcony-after.webp`
- Create: `backend/apps/forum_host/seed_assets/post-pothos-years.webp`
- Create: `backend/apps/forum_host/seed_assets/post-orchid-bloom.webp`

**Interfaces:** Produces: the eight asset filenames above, referenced verbatim by Task 7's content module.

- [ ] **Step 1: Generate** — one Runware image per prompt below. Style prefix for ALL: "candid smartphone photo, natural indoor light, realistic, slightly imperfect framing, no text, no watermark". These masquerade as user uploads — NOT glossy hero art.
  - monstera-albo: "monstera albo borsigiana leaf, half white variegation, potted plant on a wooden table by a window"
  - fiddle-leaf: "fiddle leaf fig in a living room corner, three dropped brown-edged leaves on the floor beside the pot"
  - hosta-damage: "hosta plant in a garden bed, leaves with many irregular chewed holes, evening light"
  - mealybugs: "extreme close-up of a jade plant stem joint with white cottony mealybug clusters"
  - balcony-before: "small empty city balcony with bare concrete floor and two empty railing planters, overcast day"
  - balcony-after: "small city balcony crowded with lush potted plants, a trellis with climbing vine and warm string lights, dusk"
  - pothos-years: "very long golden pothos vines cascading two meters from a high shelf in a bright room"
  - orchid-bloom: "phalaenopsis orchid with one fresh flower spike blooming on a kitchen windowsill, supermarket plastic pot"
- [ ] **Step 2: Convert + bound** — download each, convert to WEBP ≤120KB, longest edge 1200px: `sips -Z 1200 <in> --out tmp.png && cwebp -q 78 tmp.png -o <name>.webp` (or Pillow via `backend/venv/bin/python` if cwebp is absent). Verify with `ls -la`.
- [ ] **Step 3: Commit** — `git add backend/apps/forum_host/seed_assets/ && git commit -m "feat(canopy-content): commit seed image assets (Runware, WEBP)"`. Verify HEAD moved.

---

### Task 2: Deferral todo files (streak+badges, presence)

**Files:**

- Create: `todos/NNN-pending-p3-forum-day-streak-badges.md` (NNN = next free id)
- Create: `todos/MMM-pending-p3-forum-experts-presence.md` (MMM = NNN+1)

**Interfaces:** Produces: the two todo ids, referenced by code comments in Tasks 8 and 9. Record both ids in the SDD ledger immediately.

- [ ] **Step 1: Determine ids** — `ls todos/*.md | tail -3` AND `ls todos/archive/*.md 2>/dev/null | tail -3`; next id = highest seen anywhere + 1 (todo 299 exists in the archive; expect 300/301 — verify, don't assume).
- [ ] **Step 2: Write both files** following `todos/TEMPLATE.md` (status `pending`, priority `p3`, required sections, filename matches frontmatter). Content:
  - **Day streak + badges:** Problem: the Canopy artifact's "Your season" shows a day streak and badge progress ("16 to your Botanist badge"); PR 2.5 ships the streak card as a zero-state and omits progress bars. Findings: spec §9 (`docs/superpowers/specs/2026-08-15-canopy-forum-content-design.md`); zero-state card in `web/src/pages/forum/CategoryListPage.tsx`; `StatCard` already supports `progress` (`web/src/components/ui/StatCard.tsx`). Recommended action: per-user daily-activity tracking (an activity-date table updated on post publish), streak computation, badge definitions + thresholds + award logic, then replace the zero-state and restore progress bars. Acceptance criteria: streak card shows a real number that increments with next-day activity and resets after a gap; at least one badge with visible progress; zero-state code comment removed.
  - **Experts presence:** Problem: the artifact's rail is "Experts online" with live dots; PR 2.5 ships "Community experts" with no presence claim. Findings: `ForumProfile.last_seen` exists and is currently null-by-default (`backend/packages/wagtail_forum/wagtail_forum/models/profiles.py:45`); experts endpoint at `users/experts/` (Task 6 of this plan). Recommended action: throttled `last_seen` touch on authenticated forum API requests (e.g. once per 5 min per user), `online = last_seen within 15 min` flag on the experts payload, module renamed back to "Experts online" with dots driven by the flag. Acceptance criteria: dot appears only for a user active in the last 15 min; no per-request write amplification (throttled touch); module title switches with the data.
- [ ] **Step 3: Commit** — `git add todos/ && git commit -m "todos: file streak+badges and experts-presence deferrals (canopy PR 2.5)"`.

---

### Task 3: `ForumProfile.title` + author serialization

**Files:**

- Modify: `backend/packages/wagtail_forum/wagtail_forum/models/profiles.py`
- Create: `backend/packages/wagtail_forum/wagtail_forum/migrations/0020_forumprofile_title.py` (via makemigrations)
- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/serializers.py`
- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/views.py` (PublicProfileView payload + schema)
- Test: `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_profile_title.py`

**Interfaces:**

- Produces: `ForumProfile.title: CharField(max_length=80, blank=True, default="")`; every `serialize_forum_author()` payload gains `"title": str` (empty string when no profile/title); `PublicProfileView` payload gains `"title"`.
- Consumed by: Task 6 (experts endpoint), Task 7 (seed sets titles), Task 9 (web renders titles).

- [ ] **Step 1: Add the field** — in `profiles.py`, after `signature`:

```python
    # Forum "user title" (cf. Discourse): a role label shown beside the name
    # ("Head moderator", "Master gardener"). Admin-set only — deliberately NOT
    # member-editable via MeProfileSerializer; it reads as an endorsement.
    title = models.CharField(max_length=80, blank=True, default="")
```

- [ ] **Step 2: Migration** — `backend/venv/bin/python backend/manage.py makemigrations wagtail_forum` (run from `backend/`); confirm it creates `0020_*` adding only `title`.
- [ ] **Step 3: Serialize** — in `serializers.py`:
  - `_deleted_author()` dict gains `"title": ""`.
  - `serialize_forum_author` return dict gains `"title": (profile.title if profile else "")`.
  - `AUTHOR_SCHEMA` properties gain `"title": {"type": "string"}` (locate `AUTHOR_SCHEMA` near line 120; it is the schema the `@extend_schema_field(AUTHOR_SCHEMA)` decorators reference).
  - `MeProfileSerializer`: add `title` to `fields` with `read_only_fields` membership (member must NOT be able to PATCH it — verify the serializer's existing read-only mechanism and follow it).
- [ ] **Step 4: Public profile** — in `views.py` `PublicProfileView`: add `"title"` to the payload dict (profile.title or `""`) and to `PUBLIC_PROFILE_SCHEMA` properties.
- [ ] **Step 5: Tests** — `test_profile_title.py`:

```python
import pytest
from django.contrib.auth import get_user_model
from wagtail_forum.api.serializers import serialize_forum_author
from wagtail_forum.models import ForumProfile

User = get_user_model()


@pytest.mark.django_db
def test_author_payload_carries_title():
    user = User.objects.create_user(username="iris")
    profile = ForumProfile.for_user(user)
    profile.title = "Head moderator"
    profile.save(update_fields=["title"])
    assert serialize_forum_author(user)["title"] == "Head moderator"


@pytest.mark.django_db
def test_author_payload_title_defaults_empty():
    user = User.objects.create_user(username="noprofile")
    # No profile row at all → empty title, no crash.
    assert serialize_forum_author(user)["title"] == ""


@pytest.mark.django_db
def test_me_profile_cannot_patch_title(client_or_apiclient_fixture_per_existing_suite):
    # Follow the existing MeProfileView PATCH test in tests/api/ for fixture
    # style: PATCH {"title": "Grand Wizard"} as an authenticated user, expect
    # 200 with title unchanged ("" in the response), and DB value unchanged.
    ...
```

Replace the third test's placeholder fixture with the exact client fixture used by the existing `MeProfileView` tests (read one before writing — `grep -rn "me/profile" backend/packages/wagtail_forum/wagtail_forum/tests/api/ | head`). The assertion set (200, response title unchanged, DB unchanged) is required.

- [ ] **Step 6: Run** — from `backend/`: `venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_profile_title.py -v` → all pass. Then the package's serializer-adjacent suites: `venv/bin/python -m pytest packages/wagtail_forum -k "profile or author" -q`.
- [ ] **Step 7: Commit** — `feat(canopy-content): ForumProfile.title + author payload title`.

---

### Task 4: `GET me/stats/` endpoint

**Files:**

- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/views.py`
- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/urls.py`
- Test: `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_me_stats.py`

**Interfaces:**

- Produces: `GET <forum-api>/me/stats/` → `{"posts": int, "solutions_accepted": int, "identifications_shared": int}`, `IsAuthenticated` (anon → 401/403 per the package's existing auth-failure shape — assert whichever the existing `me/profile/` tests assert).
- Consumed by: Task 9's `fetchMyStats`.

- [ ] **Step 1: View** — in `views.py`, after `MeProfileView`:

```python
ME_STATS_SCHEMA = {
    "type": "object",
    "properties": {
        "posts": {"type": "integer"},
        "solutions_accepted": {"type": "integer"},
        "identifications_shared": {"type": "integer"},
    },
}


class MeStatsView(UnversionedForumAPIMixin, APIView):
    """All-time forum stats for the requesting user ("Your season" cards).

    All-time by design (spec §9): no season windowing, and the client's card
    sublabels must not claim one. Three cheap reads — the denormalized
    profile.post_count plus two indexed COUNTs — so no caching.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: ME_STATS_SCHEMA},
        description="All-time forum stats for the requesting user.",
    )
    def get(self, request):
        from ..models import ForumIdentificationAttachment, ForumProfile

        profile = ForumProfile.for_user(request.user)
        return Response(
            {
                "posts": profile.post_count,
                "solutions_accepted": Topic.objects.filter(
                    solved_post__author=request.user, live=True
                ).count(),
                # Topic-level attachments (OneToOne on Topic — spec corrected
                # at plan time): attachments the user shared on their topics.
                "identifications_shared": ForumIdentificationAttachment.objects.filter(
                    topic__author=request.user, topic__live=True
                ).count(),
            }
        )
```

(`Topic`, `APIView`, `Response`, `IsAuthenticated`, `extend_schema` are already imported in `views.py` — verify, don't re-import.)

- [ ] **Step 2: Route** — in `urls.py`, directly after the `me/profile/` line: `path("me/stats/", MeStatsView.as_view(), name="me-stats"),` (+ import).
- [ ] **Step 3: Tests** — `test_me_stats.py`, following the fixture style of the existing `tests/api/` suites: (a) anonymous GET → the same status the anon `me/profile/` test asserts; (b) fresh authenticated user → `{"posts": 0, "solutions_accepted": 0, "identifications_shared": 0}`; (c) full path: build a board+topic (author=other), publish an opening post + one reply by the requesting user (`save_revision().publish()`), set `topic.solved_post` to the user's reply, create a `ForumIdentificationAttachment` on a topic authored BY the user → expect `{"posts": 1 or 2 per what published posts the user authored, "solutions_accepted": 1, "identifications_shared": 1}` — compute the exact expected `posts` from what you created and assert it precisely; (d) another user's solved topic does NOT count.
- [ ] **Step 4: Run** — `venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_me_stats.py -v` → pass.
- [ ] **Step 5: Commit** — `feat(canopy-content): me/stats endpoint`.

---

### Task 5: `GET topics/recent/` endpoint

**Files:**

- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/views.py`
- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/urls.py`
- Modify: `backend/packages/wagtail_forum/wagtail_forum/conf.py`
- Test: `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_recent_topics.py`

**Interfaces:**

- Produces: `GET <forum-api>/topics/recent/?limit=N` (public, anon-cacheable) →

```json
{ "results": [ { "id": 1, "slug": "s", "title": "t",
  "board": {"id": 2, "name": "Show & tell", "slug": "show-tell"},
  "reply_count": 3, "last_post_at": "…", "is_pinned": false,
  "thumbnail_url": null } ] }
```

- Consumed by: Task 9 (`fetchRecentTopics` — hero detection + Active-now rail).

- [ ] **Step 1: conf** — add to `DEFAULTS` in `conf.py`:

```python
    # topics/recent/ ("Active now" rail): default and cap for ?limit=. Capped
    # because each row may resolve a thumbnail rendition.
    "RECENT_TOPICS_DEFAULT_LIMIT": 5,
    "RECENT_TOPICS_MAX_LIMIT": 20,
```

- [ ] **Step 2: View** — in `views.py` (near `SearchView`; reuse `_visible_boards()`):

```python
RECENT_TOPICS_SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "slug": {"type": "string"},
                    "title": {"type": "string"},
                    "board": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "name": {"type": "string"},
                            "slug": {"type": "string"},
                        },
                    },
                    "reply_count": {"type": "integer"},
                    "last_post_at": {
                        "type": "string", "format": "date-time", "nullable": True,
                    },
                    "is_pinned": {"type": "boolean"},
                    "thumbnail_url": {"type": "string", "nullable": True},
                },
            },
        }
    },
}


class RecentTopicsView(UnversionedForumAPIMixin, PublicForumReadCacheMixin, APIView):
    """Cross-board latest topics for the landing rail ("Active now").

    Owns its shape as lightweight dicts (same pattern as PublicProfileView) —
    deliberately NOT TopicListSerializer, so this never becomes a fourth hit
    builder (todo 273). Thumbnails resolve batched from the opening posts'
    first image block (StreamField raw_data — never iterate the StreamValue,
    which fires per-object image fetches; docs/LEARNINGS.md 2026-06-25), with
    the topic's identification-attachment image as fallback.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        responses={200: RECENT_TOPICS_SCHEMA},
        description=(
            "Latest live topics across all visible boards, most recent "
            "activity first. ?limit= defaults to RECENT_TOPICS_DEFAULT_LIMIT, "
            "capped at RECENT_TOPICS_MAX_LIMIT."
        ),
    )
    def get(self, request):
        from ..models import ForumIdentificationAttachment, Post

        try:
            limit = int(request.query_params.get("limit", ""))
        except ValueError:
            limit = get_setting("RECENT_TOPICS_DEFAULT_LIMIT")
        limit = max(1, min(limit, get_setting("RECENT_TOPICS_MAX_LIMIT")))

        topics = list(
            Topic.objects.filter(
                board__in=_visible_boards(), live=True, last_post_at__isnull=False
            )
            .select_related("board")
            .order_by("-last_post_at")[:limit]
        )
        topic_ids = [t.pk for t in topics]

        # First image block id per topic, from opening posts' raw stream data.
        image_id_by_topic = {}
        for post in Post.objects.filter(
            topic_id__in=topic_ids, is_opening_post=True, live=True
        ).only("topic_id", "body"):
            for block in post.body.raw_data:
                if block.get("type") == "image" and block.get("value"):
                    image_id_by_topic[post.topic_id] = block["value"]
                    break
        for att in ForumIdentificationAttachment.objects.filter(
            topic_id__in=topic_ids, image_id__isnull=False
        ).only("topic_id", "image_id"):
            image_id_by_topic.setdefault(att.topic_id, att.image_id)

        from wagtail.images import get_image_model

        images = get_image_model().objects.in_bulk(set(image_id_by_topic.values()))

        def thumb(topic):
            image = images.get(image_id_by_topic.get(topic.pk))
            if image is None:
                return None
            url = image.get_rendition("fill-80x80").url
            return request.build_absolute_uri(url)

        return Response(
            {
                "results": [
                    {
                        "id": t.pk,
                        "slug": t.slug,
                        "title": t.title,
                        "board": {
                            "id": t.board_id,
                            "name": t.board.title,
                            "slug": t.board.slug,
                        },
                        "reply_count": t.reply_count,
                        "last_post_at": t.last_post_at,
                        "is_pinned": t.is_pinned,
                        "thumbnail_url": thumb(t),
                    }
                    for t in topics
                ]
            }
        )
```

(`get_setting`, `AllowAny` — verify existing imports in `views.py`; `AllowAny` is already imported for `PublicProfileView`.) `last_post_at` in the dict is a datetime — DRF's `Response` JSON encoder serializes it ISO-8601, same as `PublicProfileView`'s dict timestamps.

- [ ] **Step 3: Route** — `path("topics/recent/", RecentTopicsView.as_view(), name="topics-recent"),` placed BEFORE `topics/<int:topic_id>/` (literal-over-capture, same rule the file already documents for `users/search/`).
- [ ] **Step 4: Tests** — `test_recent_topics.py`: (a) empty forum → `{"results": []}`; (b) topics across two boards return newest-activity-first with correct board objects and reply counts; (c) `limit` respected and capped at the max setting; (d) a topic whose opening post carries an image block → `thumbnail_url` is a non-null absolute URL; a topic with neither image → null; (e) non-live topic excluded; (f) **query-count pin**: with 5 topics, wrap the GET in `django_assert_num_queries` (or the suite's existing pin idiom) and document WHY the count is N in the docstring (topics + opening posts + attachments + in_bulk + per-thumbnail rendition lookups + cache-mixin queries — count empirically, explain each).
- [ ] **Step 5: Run** — targeted pytest → pass.
- [ ] **Step 6: Commit** — `feat(canopy-content): cross-board topics/recent endpoint`.

---

### Task 6: `GET users/experts/` endpoint

**Files:**

- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/views.py`
- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/urls.py`
- Modify: `backend/packages/wagtail_forum/wagtail_forum/conf.py`
- Test: `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_experts.py`

**Interfaces:**

- Produces: `GET <forum-api>/users/experts/` (public, anon-cacheable) → `{"results": [{"username", "display_name", "avatar", "trust_level", "title"}]}` — each row IS `serialize_forum_author()` output (which carries `title` after Task 3).
- Consumed by: Task 9's `fetchExperts` (Community experts rail).

- [ ] **Step 1: conf** —

```python
    # users/experts/ ("Community experts" rail): row cap and minimum trust.
    "EXPERTS_LIMIT": 4,
    "EXPERTS_MIN_TRUST_LEVEL": 3,  # TrustLevel.REGULAR
```

- [ ] **Step 2: View** —

```python
EXPERTS_SCHEMA = {
    "type": "object",
    "properties": {
        "results": {"type": "array", "items": AUTHOR_SCHEMA},
    },
}


class ExpertsView(UnversionedForumAPIMixin, PublicForumReadCacheMixin, APIView):
    """Highest-trust active members for the landing rail.

    No presence data — deliberately (spec §9): the client renders these as
    "Community experts" with no online claim until the presence todo wires
    ForumProfile.last_seen.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        responses={200: EXPERTS_SCHEMA},
        description="Up to EXPERTS_LIMIT members at or above EXPERTS_MIN_TRUST_LEVEL, highest trust then post count first.",
    )
    def get(self, request):
        from ..models import ForumProfile

        profiles = (
            ForumProfile.objects.filter(
                trust_level__gte=get_setting("EXPERTS_MIN_TRUST_LEVEL"),
                user__is_active=True,
            )
            .select_related("user", "avatar")
            .order_by("-trust_level", "-post_count")[: get_setting("EXPERTS_LIMIT")]
        )
        return Response(
            {"results": [serialize_forum_author(p.user, request) for p in profiles]}
        )
```

(`serialize_forum_author` and `AUTHOR_SCHEMA` are importable from `.serializers` — check how `views.py` already imports from there and extend that import.)

- [ ] **Step 3: Route** — `path("users/experts/", ExpertsView.as_view(), name="users-experts"),` — MUST sit before `users/<str:username>/` and after/beside `users/search/`; extend the existing ordering comment to name both literals.
- [ ] **Step 4: Tests** — (a) empty → `{"results": []}`; (b) profiles at trust 4/4/3/2/0 → returns the three ≥3 in `-trust_level, -post_count` order with `title` present in each row; (c) inactive user excluded; (d) a fifth qualifying profile is cut by the limit; (e) route sanity: GET `users/experts/` resolves to this view, NOT PublicProfileView (assert a 200 with `results` key — a username-capture would 404).
- [ ] **Step 5: Run** — targeted pytest → pass.
- [ ] **Step 6: Commit** — `feat(canopy-content): users/experts endpoint`.

---

### Task 7: `seed_demo_content` command + content catalogue

**Files:**

- Create: `backend/apps/forum_host/management/commands/seed_demo_content.py`
- Create: `backend/apps/forum_host/seed_content.py`
- Test: `backend/apps/forum_host/tests/test_seed_demo_content.py` (create `tests/__init__.py` beside it if the app has no tests package — check first)

**Interfaces:**

- Consumes: Task 1's asset filenames; Task 3's `ForumProfile.title`.
- Produces: the seeded world (5 boards, 8 users, 16 topics) that Tasks 9–12 render and screenshot.

- [ ] **Step 1: Content module** — `backend/apps/forum_host/seed_content.py`. This file is DATA ONLY (no Django imports), so the command stays readable and the catalogue is testable. Structure, verbatim:

```python
"""Demo-world catalogue for `manage.py seed_demo_content`.

Spec: docs/superpowers/specs/2026-08-15-canopy-forum-content-design.md §3–§5.
Pure data — the command owns all ORM work. Reply `age_hours` = hours before
NOW the reply landed (strictly decreasing per topic, all < the topic's age).
"""

BOARDS = [
    {
        "title": "Plant identification",
        "slug": "plant-identification",
        "description": "Post a photo, get a name. Most plants are identified within the hour.",
    },
    {
        "title": "Care & problems",
        "slug": "care-problems",
        "description": "Yellow leaves, root rot, repotting panic — bring it here.",
    },
    {
        "title": "Pests & diseases",
        "slug": "pests-diseases",
        "description": "Spot it early. Bugs, blight, and mystery spots, diagnosed together.",
    },
    {
        "title": "Garden design",
        "slug": "garden-design",
        "description": "Beds, borders, and balcony jungles. Show your plans and steal ideas.",
    },
    {
        "title": "Show & tell",
        "slug": "show-tell",
        "description": "New growth, first blooms, full shelfies. Brag freely.",
    },
]

DEMO_EMAIL_DOMAIN = "demo.houseplant-md.com"

USERS = [
    {"username": "iris_delgado", "display_name": "Iris Delgado", "title": "Head moderator", "trust_level": 4,
     "bio": "Keeping the canopy tidy since day one. Aroid collector, moss wall apologist."},
    {"username": "sam_whitaker", "display_name": "Sam Whitaker", "title": "Master gardener", "trust_level": 4,
     "bio": "Thirty years of vegetable beds and one very opinionated greenhouse."},
    {"username": "june_park", "display_name": "June Park", "title": "Plant pathologist", "trust_level": 3,
     "bio": "I look at spots on leaves so you don't have to. Fungus is usually the answer."},
    {"username": "theo_brandt", "display_name": "Theo Brandt", "title": "Arborist", "trust_level": 3,
     "bio": "Trees mostly, houseplants reluctantly, bonsai never again."},
    {"username": "maya_okafor", "display_name": "Maya Okafor", "title": "Balcony gardener", "trust_level": 2,
     "bio": "Twelve square meters, forty-one pots, zero regrets."},
    {"username": "priya_nair", "display_name": "Priya Nair", "title": "", "trust_level": 2,
     "bio": "Slowly turning a rental kitchen into a propagation lab."},
    {"username": "marcus_webb", "display_name": "Marcus Webb", "title": "", "trust_level": 1,
     "bio": "New-ish. I water too much and I'm working on it."},
    {"username": "lena_fischer", "display_name": "Lena Fischer", "title": "", "trust_level": 0,
     "bio": "Just got my first monstera. Be gentle."},
]

# Topic dict shape:
#   board, slug, title, author, age_days (float), pinned (bool),
#   opening: {"paragraphs": [str, ...], "image": asset-name-or-None}
#   identification: None | {"provider", "candidates": [...]}
#   replies: [{"author", "age_hours", "paragraphs": [...],
#              "image": asset-or-None, "solution": bool,
#              "reactions": {type: [usernames]}}, ...]
# Only keys that differ from the defaults need to appear in replies
# (the command reads them with .get()).

TOPICS = [ ... ]  # ← full catalogue below; paste verbatim
```

The full `TOPICS` list (paste into the module verbatim — it IS the deliverable; author, ages, images, solutions, and reactions per spec §5's table):

```python
TOPICS = [
    {
        "board": "plant-identification", "slug": "monstera-albo-variegation",
        "title": "Monstera albo — is this variegation stable?",
        "author": "maya_okafor", "age_days": 2.0, "pinned": False,
        "opening": {"paragraphs": [
            "Picked this up in a trade last weekend and the seller swore the sectoral variegation is stable. Two of the newer leaves are almost half white though, and I've read that's actually a bad sign?",
            "Photo attached — the newest leaf is the one on the right. Should I cut back to the last balanced leaf or let it run?",
        ], "image": "post-monstera-albo.webp"},
        "identification": None,
        "replies": [
            {"author": "sam_whitaker", "age_hours": 44,
             "paragraphs": ["Half-white leaves look spectacular and photosynthesize terribly. The plant is spending sugar it isn't making. I'd let one ride and watch the next node."]},
            {"author": "lena_fischer", "age_hours": 41,
             "paragraphs": ["No advice, just… wow. That leaf is unreal."]},
            {"author": "iris_delgado", "age_hours": 38,
             "paragraphs": ["Agree with Sam — stability in albos is a spectrum, not a yes/no. The node the leaf came from matters more than the leaf itself. If the petiole shows a good mix of green and white, you're fine."],
             "reactions": {"helpful": ["maya_okafor", "lena_fischer", "marcus_webb"]}},
            {"author": "maya_okafor", "age_hours": 36,
             "paragraphs": ["Petiole is marbled, roughly 60/40 green. That's reassuring, thank you both."]},
            {"author": "theo_brandt", "age_hours": 30,
             "paragraphs": ["One more thing — keep it out of harsh afternoon sun. White tissue scorches first and a scorched half-white leaf is a sad, expensive thing."]},
            {"author": "priya_nair", "age_hours": 26,
             "paragraphs": ["Following this thread because I have the exact same question about a mint monstera cutting."]},
            {"author": "sam_whitaker", "age_hours": 22,
             "paragraphs": ["Mint is a different beast, Priya — even less stable. Start a thread with a photo of yours and we'll take a look."]},
            {"author": "marcus_webb", "age_hours": 18,
             "paragraphs": ["How much would a plant like this even cost? Asking for my very worried wallet."]},
            {"author": "maya_okafor", "age_hours": 14,
             "paragraphs": ["More than I'll admit in public, Marcus."],
             "reactions": {"like": ["lena_fischer", "priya_nair"]}},
            {"author": "june_park", "age_hours": 9,
             "paragraphs": ["Late to this, but chiming in on the health side: variegated tissue is also more prone to fungal spotting when it stays wet. Water at the base, not over the leaves."]},
            {"author": "maya_okafor", "age_hours": 5,
             "paragraphs": ["Noted — it lives away from the mister now. This community is faster than the plant shop's own staff."]},
            {"author": "iris_delgado", "age_hours": 1.5,
             "paragraphs": ["That's the idea. Post an update when the next leaf unfurls — genuinely curious how it lands."]},
        ],
    },
    {
        "board": "plant-identification", "slug": "estate-sale-trailing-plant",
        "title": "Found this trailing thing at an estate sale — hoya or dischidia?",
        "author": "lena_fischer", "age_days": 6, "pinned": False,
        "opening": {"paragraphs": [
            "Grabbed a hanging basket of this for two dollars. Leaves are small, thick, and slightly fuzzy, growing in opposite pairs along thin stems. The tag just says 'assorted foliage'.",
            "It reminds me of the hoyas I see here but the leaves feel thinner. How do I tell hoya and dischidia apart without flowers?",
        ], "image": None},
        "identification": None,
        "replies": [
            {"author": "priya_nair", "age_hours": 130,
             "paragraphs": ["Estate sales are the best plant shops. Check the sap — hoyas usually bleed white latex when you nick a stem, dischidia much less so."]},
            {"author": "sam_whitaker", "age_hours": 120,
             "paragraphs": ["Priya's sap test is the classic. Also look at the roots along the stem: dischidia throws adventitious roots at nearly every node because it climbs ant trees in habitat. Hoya does it too but far less eagerly. Fuzzy small opposite leaves plus eager rooting says dischidia to me — likely Dischidia hirsuta or a relative."],
             "solution": True,
             "reactions": {"helpful": ["lena_fischer", "maya_okafor"], "thanks": ["lena_fischer"]}},
            {"author": "lena_fischer", "age_hours": 110,
             "paragraphs": ["Nicked a stem — barely any sap, and there are little roots at almost every node. Dischidia it is. Two dollars!"]},
            {"author": "iris_delgado", "age_hours": 100,
             "paragraphs": ["Marking Sam's answer as the solution. Nice ID without a flower in sight."]},
            {"author": "marcus_webb", "age_hours": 60,
             "paragraphs": ["I would have confidently called that a string of nickels and been wrong. Good thread."]},
            {"author": "lena_fischer", "age_hours": 30,
             "paragraphs": ["Update: it perked up after a soak and it's ALREADY growing. Estate sale of the year."]},
        ],
    },
    {
        "board": "plant-identification", "slug": "fuzzy-leaves-purple-undersides",
        "title": "ID please: fuzzy leaves, purple undersides",
        "author": "marcus_webb", "age_days": 9, "pinned": False,
        "opening": {"paragraphs": [
            "Office plant swap mystery. Soft fuzzy leaves, green on top, deep purple underneath, stems are slightly succulent. It's growing fast under a basic desk lamp.",
        ], "image": None},
        "identification": None,
        "replies": [
            {"author": "june_park", "age_hours": 210,
             "paragraphs": ["Purple velvet plant — Gynura aurantiaca. The fuzz plus purple underside combination is hard to mistake. Fair warning: its flowers smell genuinely bad, most people pinch the buds."],
             "solution": True,
             "reactions": {"helpful": ["marcus_webb", "priya_nair"]}},
            {"author": "marcus_webb", "age_hours": 200,
             "paragraphs": ["That's it exactly, photos online match perfectly. Pinching buds as instructed."]},
            {"author": "maya_okafor", "age_hours": 180,
             "paragraphs": ["Gynura gets leggy fast in low light — the desk lamp is why it's sprinting. Cuttings root in water in about a week if you want to thicken the pot."]},
            {"author": "marcus_webb", "age_hours": 150,
             "paragraphs": ["Took three cuttings tonight. This is how it starts, isn't it."]},
            {"author": "iris_delgado", "age_hours": 140,
             "paragraphs": ["It is. Welcome."],
             "reactions": {"like": ["marcus_webb", "lena_fischer", "priya_nair"]}},
        ],
    },
    {
        "board": "plant-identification", "slug": "tree-bark-peels-like-paper",
        "title": "What tree is this? Bark peels like paper",
        "author": "priya_nair", "age_days": 12, "pinned": False,
        "opening": {"paragraphs": [
            "From my building's courtyard. Small tree, maybe four meters, and the bark peels off in thin coppery curls you can see light through. Leaves are in threes with toothed edges.",
            "The app gave me two suggestions (attached) — does the confidence look right to people who know trees?",
        ], "image": None},
        "identification": {
            "provider": "plant_id",
            "candidates": [
                {"name": "Paperbark maple", "scientific_name": "Acer griseum", "confidence": 0.91},
                {"name": "River birch", "scientific_name": "Betula nigra", "confidence": 0.42},
            ],
        },
        "replies": [
            {"author": "theo_brandt", "age_hours": 280,
             "paragraphs": ["The app nailed it — Acer griseum, paperbark maple. Trifoliate leaves plus that cinnamon exfoliating bark is a giveaway combination; river birch peels too but its leaves are single, not in threes."],
             "solution": True,
             "reactions": {"helpful": ["priya_nair", "sam_whitaker", "marcus_webb"]}},
            {"author": "sam_whitaker", "age_hours": 270,
             "paragraphs": ["Lucky courtyard. One of the best small trees there is — autumn color is going to be worth a photo for Show & tell."]},
            {"author": "priya_nair", "age_hours": 250,
             "paragraphs": ["Accepted Theo's answer. I walk past this tree every day and never looked twice until this week."]},
            {"author": "june_park", "age_hours": 220,
             "paragraphs": ["Paperbarks are also refreshingly pest-free, if anyone's shopping for a courtyard tree."]},
            {"author": "lena_fischer", "age_hours": 190,
             "paragraphs": ["The bark description alone made me google it. Gorgeous tree."]},
            {"author": "theo_brandt", "age_hours": 100,
             "paragraphs": ["If the building manager ever threatens to 'tidy' the peeling bark — that's the whole point of the tree. Defend it."]},
            {"author": "priya_nair", "age_hours": 60,
             "paragraphs": ["Formally appointing myself its guardian."]},
        ],
    },
    {
        "board": "care-problems", "slug": "fiddle-leaf-dropped-leaves-move",
        "title": "Fiddle leaf dropped 3 leaves after the move",
        "author": "marcus_webb", "age_days": 1.2, "pinned": False,
        "opening": {"paragraphs": [
            "Moved apartments on Saturday. By Tuesday my fiddle had dropped three lower leaves — full leaves, not brown-edged ones. It went from a south window to an east window.",
            "Is this normal adjustment or the beginning of the end? Photo of the crime scene attached.",
        ], "image": "post-fiddle-leaf.webp"},
        "identification": None,
        "replies": [
            {"author": "sam_whitaker", "age_hours": 26,
             "paragraphs": ["Normal. Ficus lyrata treats any change of address as a personal insult. Three lower leaves after a light change is protest, not decline — watch the top growth, not the floor."],
             "reactions": {"helpful": ["marcus_webb", "lena_fischer"]}},
            {"author": "iris_delgado", "age_hours": 24,
             "paragraphs": ["Seconding Sam. The mistake people make NOW is compensating — more water, fertilizer, moving it again. Don't. Park it, water when the top two inches are dry, and ignore it for a month."]},
            {"author": "marcus_webb", "age_hours": 22,
             "paragraphs": ["I was literally holding the watering can when this notification came in. Putting it down."],
             "reactions": {"like": ["iris_delgado", "sam_whitaker", "maya_okafor", "priya_nair"]}},
            {"author": "june_park", "age_hours": 18,
             "paragraphs": ["One check worth doing once: lift it and look at drainage holes. If the move cracked the root ball and it's sitting in a saucer of water, that's a different conversation."]},
            {"author": "marcus_webb", "age_hours": 15,
             "paragraphs": ["Checked — drains fine, no standing water. It's protest then."]},
            {"author": "maya_okafor", "age_hours": 10,
             "paragraphs": ["Mine dropped five when I moved and grew seven that summer. They're drama, not fragile."]},
            {"author": "lena_fischer", "age_hours": 6,
             "paragraphs": ["Saving this whole thread for the day I inevitably buy one."]},
            {"author": "sam_whitaker", "age_hours": 2,
             "paragraphs": ["Update us in four weeks, Marcus. I have money on new growth."]},
        ],
    },
    {
        "board": "care-problems", "slug": "pothos-yellow-halo-leaves",
        "title": "Yellow halo on pothos leaves — overwatering or light?",
        "author": "lena_fischer", "age_days": 4, "pinned": False,
        "opening": {"paragraphs": [
            "Several older leaves on my golden pothos have gone yellow from the edge inward, like a halo, while the veins stay green longer. It sits two meters from a west window and I water every Sunday, religiously.",
        ], "image": None},
        "identification": None,
        "replies": [
            {"author": "june_park", "age_hours": 90,
             "paragraphs": ["'Every Sunday, religiously' is the clue. Fixed-schedule watering plus edge-in yellowing on older leaves is the classic overwatering signature — roots suffocate, plant cannibalizes old leaves. Light two meters from a west window is fine.", "Switch from schedule to check: finger two knuckles into the soil, water only when dry at that depth."],
             "solution": True,
             "reactions": {"helpful": ["lena_fischer", "marcus_webb", "maya_okafor"], "thanks": ["lena_fischer"]}},
            {"author": "lena_fischer", "age_hours": 85,
             "paragraphs": ["Guilty. Sunday watering was the one habit I was proud of."]},
            {"author": "sam_whitaker", "age_hours": 80,
             "paragraphs": ["Schedules aren't bad — schedule the CHECK, not the watering. Sunday = knuckle test day."],
             "reactions": {"like": ["lena_fischer", "june_park"]}},
            {"author": "priya_nair", "age_hours": 70,
             "paragraphs": ["Also worth sliding it out of the pot once — if the soil smells swampy, repot into something chunkier and it resets the clock."]},
            {"author": "lena_fischer", "age_hours": 50,
             "paragraphs": ["Checked the roots: white and firm, soil smells like soil. Caught it early then. Accepting June's answer."]},
            {"author": "marcus_webb", "age_hours": 40,
             "paragraphs": ["The knuckle test has saved every plant I own. All four of them."]},
            {"author": "iris_delgado", "age_hours": 20,
             "paragraphs": ["Threads like this are exactly what this board is for — clear symptom, clear cause, caught early. Well done everyone."]},
            {"author": "lena_fischer", "age_hours": 8,
             "paragraphs": ["Week one of knuckle-test Sundays complete. The pothos and I are in therapy together."]},
            {"author": "june_park", "age_hours": 3,
             "paragraphs": ["Recovery arc begins. The halos won't re-green, but no NEW halos is the win to watch for."]},
        ],
    },
    {
        "board": "care-problems", "slug": "repotting-roots-circling",
        "title": "Repotting panic: roots circling the pot three times",
        "author": "maya_okafor", "age_days": 15, "pinned": False,
        "opening": {"paragraphs": [
            "Went to repot my rubber plant and the root ball is a solid spiral — roots circling the pot at least three full turns. Internet says everything from 'tease gently' to 'slice it with a knife'. Which is it?",
        ], "image": None},
        "identification": None,
        "replies": [
            {"author": "sam_whitaker", "age_hours": 350,
             "paragraphs": ["Both, in order. Tease what teases free, and where it's woven solid, three shallow vertical cuts spaced around the ball. Circling roots that stay circling will eventually girdle the plant — a clean cut heals, a spiral doesn't."],
             "reactions": {"helpful": ["maya_okafor", "marcus_webb"]}},
            {"author": "theo_brandt", "age_hours": 340,
             "paragraphs": ["What Sam said — we do exactly this with nursery trees, just with bigger knives. The fear is worse than the surgery."]},
            {"author": "maya_okafor", "age_hours": 320,
             "paragraphs": ["Did it. Three cuts, teased the rest, new pot two sizes up. My kitchen looks like a crime scene but the patient is stable."],
             "reactions": {"like": ["sam_whitaker", "lena_fischer", "iris_delgado"]}},
            {"author": "priya_nair", "age_hours": 250,
             "paragraphs": ["This thread convinced me to finally check my dracaena. Two turns. Caught it in time."]},
            {"author": "sam_whitaker", "age_hours": 150,
             "paragraphs": ["Two-week check-in, Maya?"]},
            {"author": "maya_okafor", "age_hours": 30,
             "paragraphs": ["Two new leaves and no sulking whatsoever. Surgery recommended, would slice again."]},
        ],
    },
    {
        "board": "care-problems", "slug": "calathea-folds-at-noon",
        "title": "My calathea folds up at noon, not night. Normal?",
        "author": "priya_nair", "age_days": 20, "pinned": False,
        "opening": {"paragraphs": [
            "I know calatheas fold their leaves at night — mine does that too. But lately it ALSO folds around midday, then relaxes by late afternoon. It's near a south window with a sheer curtain.",
        ], "image": None},
        "identification": None,
        "replies": [
            {"author": "june_park", "age_hours": 470,
             "paragraphs": ["Midday folding is light-avoidance — even through a sheer, noon sun can exceed what a forest-floor plant wants. It's protecting its leaf surface. Not damage, but it IS feedback: an east window or another meter of distance and it'll stop."],
             "reactions": {"helpful": ["priya_nair", "lena_fischer"]}},
            {"author": "priya_nair", "age_hours": 460,
             "paragraphs": ["That makes complete sense — it started when the days got longer. Moving it tonight."]},
            {"author": "maya_okafor", "age_hours": 440,
             "paragraphs": ["Calatheas: the only housemates who tell you EXACTLY what's wrong, in mime."],
             "reactions": {"like": ["priya_nair", "june_park", "marcus_webb"]}},
            {"author": "priya_nair", "age_hours": 200,
             "paragraphs": ["Moved to the east window: no more noon folding, still does its goodnight prayer. Case closed."]},
        ],
    },
    {
        "board": "pests-diseases", "slug": "hosta-leaves-eaten-overnight",
        "title": "What's eating my hosta leaves overnight?",
        "author": "maya_okafor", "age_days": 0.9, "pinned": False,
        "opening": {"paragraphs": [
            "Every morning there are new ragged holes in my hostas — sometimes half a leaf gone — and I never see a single culprit during the day. Photo of the damage attached. No slime trails that I can spot on the pavers.",
        ], "image": "post-hosta-damage.webp"},
        "identification": None,
        "replies": [
            {"author": "sam_whitaker", "age_hours": 20,
             "paragraphs": ["Overnight ragged holes on hosta is slugs until proven otherwise, trails or no trails — they hide in the mulch by day. Go out two hours after dark with a torch; you'll meet the perpetrators personally."],
             "reactions": {"helpful": ["maya_okafor"]}},
            {"author": "june_park", "age_hours": 18,
             "paragraphs": ["Sam's right. If the torch patrol comes up empty, look for earwigs — they do a raggedier, smaller-hole version of the same crime. But on hosta, bet slugs."]},
            {"author": "theo_brandt", "age_hours": 16,
             "paragraphs": ["Beer traps work but you have to commit to emptying them, which is a smell you don't forget. A copper tape ring around the pot cluster is lazier and pretty effective."]},
            {"author": "maya_okafor", "age_hours": 12,
             "paragraphs": ["Torch patrol report: SEVEN slugs, one personal-record specimen. I feel betrayed by how calm they were about being caught."],
             "reactions": {"like": ["sam_whitaker", "june_park", "lena_fischer", "priya_nair"]}},
            {"author": "lena_fischer", "age_hours": 10,
             "paragraphs": ["'One personal-record specimen' has me crying. Godspeed, hostas."]},
            {"author": "iris_delgado", "age_hours": 8,
             "paragraphs": ["Relocation two gardens away minimum, or they commute back. This is documented."]},
            {"author": "maya_okafor", "age_hours": 6,
             "paragraphs": ["They got a one-way trip to the park. Copper tape going on this weekend as border control."]},
            {"author": "marcus_webb", "age_hours": 4,
             "paragraphs": ["Reading this at midnight and now I want to go check my one outdoor pot with a torch."]},
            {"author": "sam_whitaker", "age_hours": 1,
             "paragraphs": ["Go. Report back. This board runs on torch patrols."]},
            {"author": "maya_okafor", "age_hours": 0.4,
             "paragraphs": ["Morning update: zero new holes. First clean night in two weeks."]},
        ],
    },
    {
        "board": "pests-diseases", "slug": "white-cotton-blobs-jade",
        "title": "Tiny white cotton blobs on jade stems",
        "author": "lena_fischer", "age_days": 7, "pinned": False,
        "opening": {"paragraphs": [
            "There are little white fuzzy blobs tucked into the joints of my jade plant, mostly where leaves meet stems. They wipe off but come back within days. Close-up attached — what am I fighting?",
        ], "image": "post-mealybugs.webp"},
        "identification": None,
        "replies": [
            {"author": "june_park", "age_hours": 160,
             "paragraphs": ["Mealybugs — the cottony tufts in stem joints are textbook. The ones you wipe are the visible fraction; eggs and crawlers hide in every crevice, which is why they 'come back'.", "Protocol: cotton bud dipped in 70% isopropyl on every blob, repeat every 4–5 days for three weeks, and isolate the plant from its neighbors today."],
             "solution": True,
             "reactions": {"helpful": ["lena_fischer", "maya_okafor", "marcus_webb"], "thanks": ["lena_fischer"]}},
            {"author": "lena_fischer", "age_hours": 150,
             "paragraphs": ["Quarantined and dabbed. It smells like a clinic in here, which feels thematically appropriate for this site."],
             "reactions": {"like": ["june_park", "iris_delgado"]}},
            {"author": "iris_delgado", "age_hours": 140,
             "paragraphs": ["The three-week commitment is the part people skip — one missed cycle and the survivors reboot the colony. Calendar reminders are your friend."]},
            {"author": "maya_okafor", "age_hours": 100,
             "paragraphs": ["Check the pot rim and the underside of the saucer too. I lost a round to mealies that were camping OUTSIDE the plant."]},
            {"author": "lena_fischer", "age_hours": 48,
             "paragraphs": ["Found two blobs under the rim. Maya, you just won me the war two weeks early."]},
            {"author": "june_park", "age_hours": 24,
             "paragraphs": ["Keep the isopropyl cycles going anyway — 'I see none' and 'there are none' are different claims. Accepting congratulations in week three."]},
            {"author": "lena_fischer", "age_hours": 12,
             "paragraphs": ["Understood, doctor. Marking your first reply as the solution so future jade owners find the protocol."]},
        ],
    },
    {
        "board": "pests-diseases", "slug": "brown-spots-yellow-rings-monstera",
        "title": "Brown spots with yellow rings spreading across my monstera",
        "author": "marcus_webb", "age_days": 3, "pinned": False,
        "opening": {"paragraphs": [
            "Started as one brown spot with a yellow halo on a middle leaf; a week later there are five spots across three leaves. The spots are dry in the center, almost papery. I mist most mornings because the flat is dry.",
        ], "image": None},
        "identification": None,
        "replies": [
            {"author": "june_park", "age_hours": 68,
             "paragraphs": ["Dry papery centers with yellow halos spreading leaf-to-leaf reads as a fungal leaf spot, and 'I mist most mornings' is very likely the engine — spores need leaf wetness, and misting delivers it daily.", "Stop misting entirely, remove the worst-affected leaf with clean scissors, and give it more airflow. Humidity for the flat: pebble tray or a humidifier, never the spray bottle."],
             "reactions": {"helpful": ["marcus_webb", "lena_fischer", "priya_nair"]}},
            {"author": "marcus_webb", "age_hours": 60,
             "paragraphs": ["The misting was supposed to be the HELPFUL thing I did. Stopped as of now, one leaf removed."]},
            {"author": "sam_whitaker", "age_hours": 50,
             "paragraphs": ["Misting is the most oversold habit in houseplants — it raises humidity for about eight minutes and leaf-wetness hours for fungi. You're not the first it's betrayed."],
             "reactions": {"like": ["marcus_webb", "june_park", "maya_okafor"]}},
            {"author": "priya_nair", "age_hours": 30,
             "paragraphs": ["Watch the remaining spots' EDGES: if they stop growing you've won; if the halos keep widening in a week, come back and June will probably prescribe a copper fungicide."]},
            {"author": "marcus_webb", "age_hours": 10,
             "paragraphs": ["Marked the spot edges on the leaf with tiny tape arrows so I can tell if they grow. Science corner."],
             "reactions": {"like": ["june_park", "priya_nair"]}},
        ],
    },
    {
        "board": "garden-design", "slug": "balcony-jungle-v2",
        "title": "Balcony jungle v2 — before and after",
        "author": "maya_okafor", "age_days": 18, "pinned": False,
        "opening": {"paragraphs": [
            "Two years ago this was a concrete rectangle with two sad railing planters (photo one). Version 2 is done: trellis wall, tiered plant stand, and the string lights that finally made it a room (photo two, taken last week).",
            "Total plant count is 41. Ask me anything, including 'how do you water all that' — the answer is 'slowly, with coffee'.",
        ], "image": "post-balcony-before.webp"},
        "identification": None,
        "replies": [
            {"author": "maya_okafor", "age_hours": 430,
             "paragraphs": ["And the after:"], "image": "post-balcony-after.webp",
             "reactions": {"love": ["lena_fischer", "priya_nair", "marcus_webb", "iris_delgado"], "like": ["sam_whitaker"]}},
            {"author": "priya_nair", "age_hours": 420,
             "paragraphs": ["The trellis wall is genius — is the vine a star jasmine? How's it handling wind up there?"]},
            {"author": "maya_okafor", "age_hours": 410,
             "paragraphs": ["Star jasmine, yes. Wind was THE design constraint: everything above railing height is either tied in or heavy-potted. Learned that the expensive way in v1."]},
            {"author": "sam_whitaker", "age_hours": 380,
             "paragraphs": ["Proper planning. One suggestion for v3: a rain gauge. Balconies live in a rain shadow and people chronically overestimate what storms deliver back there."],
             "reactions": {"helpful": ["maya_okafor"]}},
            {"author": "theo_brandt", "age_hours": 350,
             "paragraphs": ["41 plants on what looks like 12 square meters is excellent density without reading as clutter. The tiering does the work."]},
            {"author": "lena_fischer", "age_hours": 300,
             "paragraphs": ["Saving both photos as my aspiration board. The lights genuinely make it."]},
            {"author": "marcus_webb", "age_hours": 200,
             "paragraphs": ["How much of the budget was pots? I've realized pots are where plant money actually goes."]},
            {"author": "maya_okafor", "age_hours": 150,
             "paragraphs": ["Roughly 40% pots, and that's WITH two years of thrifting. Nobody warns you about this."]},
            {"author": "iris_delgado", "age_hours": 90,
             "paragraphs": ["This is the best before/after this board has had. Pinning a link to it in my mental highlight reel."]},
        ],
    },
    {
        "board": "garden-design", "slug": "north-facing-bed-what-thrives",
        "title": "North-facing bed: what actually thrives?",
        "author": "theo_brandt", "age_days": 25, "pinned": False,
        "opening": {"paragraphs": [
            "Asking for collective experience over catalog promises: a 4-meter bed against a north wall, maybe two hours of oblique morning sun in summer, decent soil. What has ACTUALLY thrived for you in that situation — not survived, thrived?",
        ], "image": None},
        "identification": None,
        "replies": [
            {"author": "sam_whitaker", "age_hours": 580,
             "paragraphs": ["Twenty years with a bed like that: hostas (obviously), Japanese forest grass, astilbe if it stays moist, and hellebores that outperform everything February through April. Ferns for structure — Dryopteris shrugs off the dry-shade months."],
             "reactions": {"helpful": ["theo_brandt", "maya_okafor", "priya_nair"]}},
            {"author": "june_park", "age_hours": 560,
             "paragraphs": ["Adding brunnera 'Jack Frost' — silver leaves that genuinely glow in shade, and slugs like it less than hostas. Disease pressure in north beds is mildew late summer; space generously."]},
            {"author": "theo_brandt", "age_hours": 540,
             "paragraphs": ["Hellebores were on the maybe list — 'outperforms everything Feb–April' promotes them to anchors. Keep them coming."]},
            {"author": "maya_okafor", "age_hours": 500,
             "paragraphs": ["Not a bed, but my north balcony corner: fuchsias flowered for five straight months in almost no direct sun. If the bed gets any morning light they'd earn a spot."]},
            {"author": "iris_delgado", "age_hours": 420,
             "paragraphs": ["Seconding forest grass — it does the 'movement' job ornamental grasses do, in shade nothing else tolerates."]},
            {"author": "theo_brandt", "age_hours": 380,
             "paragraphs": ["Plan drafted: hellebore + fern anchors, forest grass rhythm, brunnera edging, astilbe where the downspout keeps it damp, one experimental fuchsia. Planting report in autumn. Thanks all."],
             "reactions": {"like": ["sam_whitaker", "june_park", "maya_okafor"]}},
        ],
    },
    {
        "board": "show-tell", "slug": "three-years-same-pothos",
        "title": "Three years of the same pothos, one photo per year",
        "author": "priya_nair", "age_days": 11, "pinned": False,
        "opening": {"paragraphs": [
            "Year one: a four-leaf cutting in a jam jar. Year two: a respectable pot on the bookshelf. Year three, photographed this morning: it has claimed the entire shelf run and is negotiating for the curtain rail.",
            "Same plant, same window, mostly the same neglect. Time is the best fertilizer.",
        ], "image": "post-pothos-years.webp"},
        "identification": None,
        "replies": [
            {"author": "lena_fischer", "age_hours": 250,
             "paragraphs": ["'Negotiating for the curtain rail' — and winning, by the look of it. This is beautiful."],
             "reactions": {"love": ["priya_nair"]}},
            {"author": "marcus_webb", "age_hours": 240,
             "paragraphs": ["The jam jar origin story gives me hope for my cutting graveyard."]},
            {"author": "maya_okafor", "age_hours": 230,
             "paragraphs": ["Yearly photos of the same plant is such a good idea. Starting this tradition tonight with the rubber plant."],
             "reactions": {"like": ["priya_nair", "sam_whitaker"]}},
            {"author": "iris_delgado", "age_hours": 210,
             "paragraphs": ["Threads like this are why Show & tell exists. Three-year update thread or we riot."]},
            {"author": "priya_nair", "age_hours": 190,
             "paragraphs": ["Deal. See you all in year four when it owns the ceiling."]},
            {"author": "sam_whitaker", "age_hours": 120,
             "paragraphs": ["Time IS the best fertilizer. I'm having that engraved on something."],
             "reactions": {"like": ["priya_nair", "lena_fischer", "june_park"]}},
            {"author": "theo_brandt", "age_hours": 40,
             "paragraphs": ["Respect for 'mostly the same neglect' — honest plant keeping. It clearly works."]},
            {"author": "priya_nair", "age_hours": 15,
             "paragraphs": ["The secret ingredient is benign inattention and a good window."]},
        ],
    },
    {
        "board": "show-tell", "slug": "rescue-orchid-first-bloom",
        "title": "First bloom on the orchid I rescued from the grocery store",
        "author": "lena_fischer", "age_days": 5, "pinned": False,
        "opening": {"paragraphs": [
            "Eighteen months ago this phalaenopsis was on the grocery store clearance rack: two yellow leaves, rotted roots, one euro. Today it opened its first flower on a brand-new spike.",
            "Photo from the kitchen windowsill this morning. I may have said 'good morning' to it out loud.",
        ], "image": "post-orchid-bloom.webp"},
        "identification": None,
        "replies": [
            {"author": "maya_okafor", "age_hours": 110,
             "paragraphs": ["EIGHTEEN MONTHS of patience. This is the most satisfying kind of post — congratulations to you both."],
             "reactions": {"love": ["lena_fischer", "priya_nair"]}},
            {"author": "sam_whitaker", "age_hours": 100,
             "paragraphs": ["Clearance-rack rescues that rebloom are the true flex on this board. What did the root recovery look like?"]},
            {"author": "lena_fischer", "age_hours": 95,
             "paragraphs": ["Cut everything mushy, sphagnum + a clear cup for four months until new roots showed, then bark mix. Mostly I just didn't give up."]},
            {"author": "june_park", "age_hours": 80,
             "paragraphs": ["Textbook rescue protocol, executed with patience. The clear-cup trick deserves more fame."],
             "reactions": {"helpful": ["lena_fischer", "marcus_webb"]}},
            {"author": "iris_delgado", "age_hours": 60,
             "paragraphs": ["From the clinic's perspective: patient admitted critical, discharged blooming. Exactly what this community is for."],
             "reactions": {"like": ["lena_fischer", "maya_okafor", "sam_whitaker"]}},
            {"author": "marcus_webb", "age_hours": 30,
             "paragraphs": ["Checking every clearance rack in town this weekend. You've created a monster."]},
            {"author": "lena_fischer", "age_hours": 4,
             "paragraphs": ["Go forth and rescue. Second flower bud is already swelling — updates as they open."]},
        ],
    },
    {
        "board": "show-tell", "slug": "bloom-watch-2026",
        "title": "Bloom watch 2026: what's flowering at your place this August?",
        "author": "iris_delgado", "age_days": 10, "pinned": True,
        "opening": {"paragraphs": [
            "It's August, which means the community bloom watch is ON. Every year we track what's flowering, fruiting, and quietly failing across everyone's windowsills, balconies, and beds — one thread, all month.",
            "The rules are simple: post what's blooming (photos loved, not required), say roughly where you're growing it, and if something SHOULD be blooming but isn't, post that too — someone here will know why.",
            "I'll start: the moss wall is not blooming because it is moss, and I've made peace with that.",
        ], "image": None},
        "identification": None,
        "replies": [
            {"author": "maya_okafor", "age_hours": 235,
             "paragraphs": ["Balcony report: star jasmine second flush, one defiant dahlia in a pot that's too small for it, and the string lights (perennial, evergreen, zero water)."],
             "reactions": {"like": ["iris_delgado", "lena_fischer"]}},
            {"author": "sam_whitaker", "age_hours": 220,
             "paragraphs": ["Greenhouse: tomatoes fruiting on schedule, and the hoyas chose THIS week to all open at once — twelve umbels across three plants. The smell at 9pm is a event."],
             "reactions": {"love": ["priya_nair", "maya_okafor"]}},
            {"author": "priya_nair", "age_hours": 200,
             "paragraphs": ["Kitchen lab: hoya cutting from Sam's advice thread has its FIRST peduncle. Eighteen months from cutting to countdown."]},
            {"author": "sam_whitaker", "age_hours": 195,
             "paragraphs": ["Do not move it now, Priya. Not one centimeter. Peduncles hold grudges."],
             "reactions": {"helpful": ["priya_nair"], "like": ["lena_fischer"]}},
            {"author": "lena_fischer", "age_hours": 120,
             "paragraphs": ["My rescue orchid opened its first flower TODAY — full story in its own thread, but it counts for the watch. One euro plant, first bloom, eighteen months."],
             "reactions": {"love": ["iris_delgado", "maya_okafor"]}},
            {"author": "theo_brandt", "age_hours": 100,
             "paragraphs": ["Failing-quietly entry as requested: the courtyard hydrangea has produced exactly one (1) flower head. Suspect last winter's pruning enthusiasm. Accepting condolences and pruning-calendar corrections."]},
            {"author": "sam_whitaker", "age_hours": 90,
             "paragraphs": ["Theo — macrophylla blooms on old wood, so last summer's cuts took this year's flowers with them. Prune right after flowering, never in spring. Next August will forgive you."],
             "reactions": {"helpful": ["theo_brandt", "marcus_webb"]}},
            {"author": "marcus_webb", "age_hours": 70,
             "paragraphs": ["Nothing blooming at mine yet, but the purple velvet plant from my ID thread is growing like it's being paid. Does aggressive foliage count for the watch?"]},
            {"author": "iris_delgado", "age_hours": 65,
             "paragraphs": ["Foliage counts, Marcus. The watch honors all victories."],
             "reactions": {"like": ["marcus_webb", "lena_fischer"]}},
            {"author": "june_park", "age_hours": 20,
             "paragraphs": ["Pathologist's entry: the healthiest thing in my flat is a sweet potato that sprouted in the pantry and has been promoted to a vase. August delivers."],
             "reactions": {"love": ["iris_delgado", "priya_nair", "maya_okafor"]}},
            {"author": "iris_delgado", "age_hours": 1,
             "paragraphs": ["Week-two roundup: two first-ever blooms, one hoya event, one hydrangea diagnosis, one pantry promotion. Keep them coming — the watch runs all month."],
             "reactions": {"like": ["sam_whitaker", "lena_fischer"]}},
        ],
    },
]
```

- [ ] **Step 2: The command** — `seed_demo_content.py`:

```python
from datetime import timedelta
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.images import ImageFile
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from wagtail.images import get_image_model
from wagtail.rich_text import RichText

from wagtail_forum.collections import get_forum_image_collection
from wagtail_forum.models import (
    ForumBoard,
    ForumIdentificationAttachment,
    ForumIndex,
    ForumProfile,
    Post,
    Reaction,
    Topic,
)

from apps.forum_host.seed_content import BOARDS, DEMO_EMAIL_DOMAIN, TOPICS, USERS

ASSET_DIR = Path(__file__).resolve().parent.parent.parent / "seed_assets"
# The pre-Canopy starter board seed_default_forum creates; removed only if empty.
LEGACY_STARTER_SLUG = "general-discussion"


class Command(BaseCommand):
    help = (
        "Idempotently seed the Canopy demo world: 5 boards, 8 demo users, "
        "16 topics with replies/solutions/reactions/images. Skip-not-overwrite: "
        "existing rows are never modified. Safe to re-run."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Required when DEBUG=False (production).",
        )

    def handle(self, *args, **options):
        from django.conf import settings

        # Guard layer 1: production requires an explicit flag.
        if not settings.DEBUG and not options["confirm"]:
            raise CommandError(
                "DEBUG is False. Re-run with --confirm to seed demo content "
                "into this environment."
            )
        # Guard layer 2 (cannot be overridden): any real user = abort.
        User = get_user_model()
        demo_usernames = {u["username"] for u in USERS}
        real_users = User.objects.exclude(username__in=demo_usernames).exclude(
            is_superuser=True
        )
        if real_users.exists():
            raise CommandError(
                f"{real_users.count()} real user account(s) exist — refusing to "
                "seed demo content into a live community. This guard has no "
                "override flag by design (spec §5)."
            )

        # Prerequisites: ForumIndex + image collection (idempotent, tested).
        call_command("seed_default_forum")
        index = ForumIndex.objects.first()

        users = self._seed_users()
        boards = self._seed_boards(index)
        self._remove_empty_starter_board()
        created = [
            spec for spec in TOPICS if self._seed_topic(spec, boards, users)
        ]
        self.stdout.write(
            self.style.SUCCESS(
                f"Seed complete: {len(created)} topic(s) created, "
                f"{len(TOPICS) - len(created)} already present."
            )
        )
        if created:
            # Content changed under the search index's feet (timestamps moved
            # post-publish); refresh so search reflects the seeded world.
            call_command("update_index", verbosity=0)

    # -- users ---------------------------------------------------------------

    def _seed_users(self):
        User = get_user_model()
        users = {}
        for spec in USERS:
            user, created = User.objects.get_or_create(
                username=spec["username"],
                defaults={"email": f"{spec['username']}@{DEMO_EMAIL_DOMAIN}"},
            )
            if created:
                user.set_unusable_password()
                user.save(update_fields=["password"])
                profile = ForumProfile.for_user(user)
                profile.display_name = spec["display_name"]
                profile.title = spec["title"]
                profile.bio = spec["bio"]
                # Appointed trust: survives signal recounts (signals.py takes
                # max(current, earned) when current exceeds earned).
                profile.trust_level = spec["trust_level"]
                profile.save(
                    update_fields=["display_name", "title", "bio", "trust_level"]
                )
                self.stdout.write(f"Created demo user {spec['username']}.")
            users[spec["username"]] = user
        return users

    # -- boards --------------------------------------------------------------

    def _seed_boards(self, index):
        boards = {}
        for spec in BOARDS:
            board = ForumBoard.objects.filter(slug=spec["slug"]).first()
            if board is None:
                board = index.add_child(
                    instance=ForumBoard(
                        title=spec["title"],
                        slug=spec["slug"],
                        description=spec["description"],
                    )
                )
                board.save_revision().publish()
                self.stdout.write(f"Created board {spec['slug']}.")
            boards[spec["slug"]] = board
        return boards

    def _remove_empty_starter_board(self):
        starter = ForumBoard.objects.filter(slug=LEGACY_STARTER_SLUG).first()
        if starter is None:
            return
        if starter.topics.exists():
            self.stdout.write(
                f"Board '{LEGACY_STARTER_SLUG}' has topics — keeping it "
                "(spec §3: never delete content)."
            )
            return
        starter.delete()
        self.stdout.write(f"Removed empty starter board '{LEGACY_STARTER_SLUG}'.")

    # -- topics --------------------------------------------------------------

    def _seed_topic(self, spec, boards, users):
        """Create one topic + its world. Topic-granular idempotency: if the
        slug already exists on its board, skip ENTIRELY (spec §5 — manual
        edits always win). Returns True when created."""
        board = boards[spec["board"]]
        if Topic.objects.filter(board=board, slug=spec["slug"]).exists():
            return False

        now = timezone.now()
        with transaction.atomic():
            topic = Topic.objects.create(
                board=board,
                title=spec["title"],
                slug=spec["slug"],
                author=users[spec["author"]],
                is_pinned=spec["pinned"],
            )
            post_times = []

            def publish_post(author, paragraphs, image_name, opening, age_hours):
                body = [
                    ("paragraph", RichText(f"<p>{p}</p>")) for p in paragraphs
                ]
                if image_name:
                    body.append(("image", self._get_image(image_name)))
                post = Post.objects.create(
                    topic=topic,
                    author=author,
                    body=body,
                    is_opening_post=opening,
                )
                post.save_revision().publish()
                post_times.append((post.pk, now - timedelta(hours=age_hours)))
                return post

            opening_age = spec["age_days"] * 24
            publish_post(
                users[spec["author"]],
                spec["opening"]["paragraphs"],
                spec["opening"].get("image"),
                True,
                opening_age,
            )
            solution_post = None
            for reply in spec["replies"]:
                post = publish_post(
                    users[reply["author"]],
                    reply["paragraphs"],
                    reply.get("image"),
                    False,
                    reply["age_hours"],
                )
                if reply.get("solution"):
                    solution_post = post
                for rtype, names in reply.get("reactions", {}).items():
                    for name in names:
                        Reaction.objects.get_or_create(
                            post=post, user=users[name], reaction_type=rtype
                        )
                    Reaction.recount(post)

            if spec.get("identification"):
                ForumIdentificationAttachment.objects.create(
                    topic=topic,
                    provider=spec["identification"]["provider"],
                    candidates=spec["identification"]["candidates"],
                )

            newest = max(ts for _, ts in post_times)
            if solution_post is not None:
                topic.solved_post = solution_post
                topic.solved_at = newest
                topic.save(update_fields=["solved_post", "solved_at"])

            # Timestamp pass — LAST, via .update() so auto_now/auto_now_add and
            # signals don't overwrite the spread (spec §5).
            for pk, ts in post_times:
                Post.objects.filter(pk=pk).update(created_at=ts, updated_at=ts)
            Topic.objects.filter(pk=topic.pk).update(
                created_at=now - timedelta(hours=opening_age),
                updated_at=newest,
                last_post_at=newest,
            )
        self.stdout.write(f"Created topic {spec['slug']} on {spec['board']}.")
        return True

    # -- images --------------------------------------------------------------

    def _get_image(self, asset_name):
        Image = get_image_model()
        title = f"Seed: {asset_name}"
        existing = Image.objects.filter(title=title).first()
        if existing:
            return existing
        path = ASSET_DIR / asset_name
        if not path.exists():
            raise CommandError(f"Missing seed asset: {path}")
        with path.open("rb") as fh:
            return Image.objects.create(
                title=title,
                file=ImageFile(fh, name=asset_name),
                collection=get_forum_image_collection(),
            )
```

Implementer notes: verify `Reaction` is exported from `wagtail_forum.models` `__init__` (add the export if missing — `reports.py`/`__init__.py` shows the pattern); verify `update_index` is the correct command for the configured search backend (the DB backend needs no reindex — in that case keep the call, it is a cheap no-op, but confirm it doesn't error). If `RichText` inside a list literal fails StreamField validation, use the `[{"type": "paragraph", "value": ...}]` raw form instead — write ONE probe test first, don't guess.

- [ ] **Step 3: Tests** — `test_seed_demo_content.py` (pytest, `@pytest.mark.django_db`; page-creating — remember `--create-db` locally on partial re-runs):
  - `test_refuses_without_confirm_when_not_debug` — `settings.DEBUG=False` (override), expect `CommandError` mentioning `--confirm`.
  - `test_refuses_when_real_users_exist_even_with_confirm` — create `User(username="alice")`, run with `--confirm` and DEBUG=True → `CommandError` mentioning "real user".
  - `test_superuser_does_not_trip_the_guard` — only a superuser exists → seed succeeds.
  - `test_seeds_the_five_boards_and_removes_empty_starter` — after run: the five spec slugs exist, `general-discussion` gone; run `seed_default_forum` FIRST so the starter exists beforehand.
  - `test_keeps_starter_board_with_topics` — starter board given one topic pre-seed → still present after, six boards total.
  - `test_run_twice_is_idempotent` — run twice; capture `(User.count, ForumBoard.count, Topic.count, Post.count, Reaction.count, ForumIdentificationAttachment.count)` and every `Topic.updated_at` after run one → identical after run two.
  - `test_world_shape` — after one run: 16 topics; `bloom-watch-2026` is pinned; 4 topics solved with the spec'd solvers; the identification attachment exists on `tree-bark-peels-like-paper` with 2 candidates; every topic's `last_post_at` equals its newest post's `created_at`; post timestamps strictly increase within each topic; demo users have unusable passwords and the demo email domain; iris/sam trust_level == 4 (appointed trust survived recounts).
  - Asset-dependent tests: the seed opens real files — the eight assets are committed by Task 1, so tests may rely on them.
- [ ] **Step 4: Run** — from `backend/`: `venv/bin/python -m pytest apps/forum_host/tests/test_seed_demo_content.py -v --create-db` → all pass. Then run the command for real against the dev DB: `venv/bin/python manage.py seed_demo_content` and eyeball `/forum` in the SPA.
- [ ] **Step 5: Commit** — `feat(canopy-content): seed_demo_content command + demo world catalogue`.

---

### Task 8: Web — board identity map + landing chips

**Files:**

- Modify: `web/src/utils/forumTones.ts`
- Modify: `web/src/components/forum/CategoryCard.tsx`
- Modify: `web/src/pages/forum/CategoryListPage.tsx`
- Test: `web/src/utils/forumTones.test.ts` (create), update `web/src/pages/forum/CategoryListPage.test.tsx`

**Interfaces:**

- Produces: `boardIdentity(slug): { tone: TileTone; Icon: LucideIcon; chipLabel: string }` (named map for the five Canopy slugs, hash-tone + `Leaf` + full-name fallback for unknown slugs — `chipLabel` falls back to the board NAME passed by the caller, see signature below). `boardTone` keeps its signature but consults the map first.
- Consumed by: CategoryCard (tile), CategoryListPage (chips), Task 10's rail modules (icon tiles).

- [ ] **Step 1: Identity map** — extend `forumTones.ts`:

```ts
import type { LucideIcon } from 'lucide-react';
import { Bug, Camera, Droplet, LayoutDashboard, Leaf } from 'lucide-react';
import type { TileTone } from '../components/ui/Tile';
import { hashString } from './hashString';

const TONES: TileTone[] = ['sage', 'pollen', 'bloom', 'orchid'];

interface BoardIdentity {
  tone: TileTone;
  Icon: LucideIcon;
  chipLabel: string;
}

/**
 * Deliberate identities for the five Canopy boards (spec §3) — tone, icon,
 * and short chip label are design decisions, not derivations. Unknown slugs
 * fall back to the hash tone + Leaf so third-party boards still render.
 */
const BOARD_IDENTITY: Record<string, BoardIdentity> = {
  'plant-identification': { tone: 'sage', Icon: Leaf, chipLabel: 'Identification' },
  'care-problems': { tone: 'pollen', Icon: Droplet, chipLabel: 'Care' },
  'pests-diseases': { tone: 'bloom', Icon: Bug, chipLabel: 'Pests' },
  'garden-design': { tone: 'orchid', Icon: LayoutDashboard, chipLabel: 'Design' },
  'show-tell': { tone: 'sage', Icon: Camera, chipLabel: 'Show & tell' },
};

export function boardIdentity(slug: string, fallbackLabel = ''): BoardIdentity {
  return (
    BOARD_IDENTITY[slug] ?? {
      tone: TONES[hashString(slug) % TONES.length],
      Icon: Leaf,
      chipLabel: fallbackLabel || slug,
    }
  );
}

/** Deterministic accent tone per board slug (map first, hash fallback). */
export function boardTone(slug: string): TileTone {
  return boardIdentity(slug).tone;
}
```

- [ ] **Step 2: CategoryCard icon** — in the `Tile`, replace the bare `Leaf` fallback with the identity icon (keep the `category.icon` emoji branch — it wins when the CMS sets one):

```tsx
const { Icon } = boardIdentity(category.slug);
// … inside <Tile>:
{category.icon ? (
  <span className="text-xl leading-none">{category.icon}</span>
) : (
  <Icon className="h-5 w-5" />
)}
```

(import `boardIdentity` instead of `boardTone` and use `boardIdentity(category.slug).tone` for the Tile tone — one lookup.)

- [ ] **Step 3: Chips on the landing page** — in `CategoryListPage`, above the board list (after the stat cards), when `categories.length > 1`:

```tsx
const [activeBoard, setActiveBoard] = useState<string | null>(null);
const visibleCategories = activeBoard
  ? categories.filter((c) => c.slug === activeBoard)
  : categories;
```

```tsx
<div className="mt-6 flex flex-wrap items-center gap-2" role="group" aria-label="Filter boards">
  <Chip active={activeBoard === null} onClick={() => setActiveBoard(null)} className="min-h-11">
    All
  </Chip>
  {categories.map((c) => (
    <Chip
      key={c.slug}
      active={activeBoard === c.slug}
      onClick={() => setActiveBoard((prev) => (prev === c.slug ? null : c.slug))}
      className="min-h-11"
    >
      {boardIdentity(c.slug, c.name).chipLabel}
    </Chip>
  ))}
</div>
```

The board list maps `visibleCategories`. Import `Chip` from `../../components/ui/Chip`.

- [ ] **Step 4: Tests** — `forumTones.test.ts`: the five known slugs return their spec'd tone/chipLabel; an unknown slug returns a stable tone (same input → same output) and the fallback label. `CategoryListPage.test.tsx` additions: chips render one per board + All; clicking a chip filters the list to that board; clicking it again (or All) restores; chips absent with a single board.
- [ ] **Step 5: Run** — `npx vitest run src/utils/forumTones.test.ts src/pages/forum/CategoryListPage.test.tsx` → pass. `npx tsc --noEmit` → clean.
- [ ] **Step 6: Commit** — prettier the touched files, then `feat(canopy-content): board identity map + landing filter chips`.

---

### Task 9: Web — services, event hero, "Your season"

**Files:**

- Modify: `web/src/services/forumService.ts`
- Modify: `web/src/types/forum.ts`
- Modify: `web/src/pages/forum/CategoryListPage.tsx`
- Test: update `web/src/pages/forum/CategoryListPage.test.tsx`

**Interfaces:**

- Consumes: Tasks 4–6 endpoint shapes; `useAuth().isAuthenticated`.
- Produces: `fetchMyStats(): Promise<ForumMyStats>`, `fetchRecentTopics(limit?): Promise<RecentTopic[]>`, `fetchExperts(): Promise<ForumExpert[]>`, `recentTopicPath(t): string`; CategoryListPage renders the event hero + season cards. Task 10 consumes `fetchRecentTopics`/`fetchExperts` and `recentTopicPath`.

- [ ] **Step 1: Types** — in `types/forum.ts`:

```ts
/** GET me/stats/ — all-time counts ("Your season" cards). */
export interface ForumMyStats {
  posts: number;
  solutions_accepted: number;
  identifications_shared: number;
}

/** GET topics/recent/ row — the landing rail's "Active now" shape. */
export interface RecentTopic {
  id: number;
  slug: string;
  title: string;
  board: { id: number; name: string; slug: string };
  reply_count: number;
  last_post_at: string | null;
  is_pinned: boolean;
  thumbnail_url: string | null;
}

/** GET users/experts/ row — serialize_forum_author + title. */
export interface ForumExpert {
  username: string;
  display_name: string;
  avatar: string | null;
  trust_level: number | null;
  title: string;
}
```

Export them from `types/index.ts` following the existing re-export pattern.

- [ ] **Step 2: Service functions** — in `forumService.ts` (Search section is a fine neighborhood):

```ts
export async function fetchMyStats(): Promise<ForumMyStats> {
  return authenticatedFetch<ForumMyStats>(`${FORUM_BASE}/me/stats/`);
}

export async function fetchRecentTopics(limit = 5): Promise<RecentTopic[]> {
  const data = await authenticatedFetch<{ results: RecentTopic[] }>(
    `${FORUM_BASE}/topics/recent/?limit=${limit}`
  );
  return data.results || [];
}

export async function fetchExperts(): Promise<ForumExpert[]> {
  const data = await authenticatedFetch<{ results: ForumExpert[] }>(
    `${FORUM_BASE}/users/experts/`
  );
  return data.results || [];
}
```

- [ ] **Step 3: Topic path helper** — in `web/src/utils/forumUrls.ts`, add (mirroring the existing helpers' style and the backend's `Topic.get_absolute_url` format):

```ts
/** Path for a topics/recent row: /forum/{board.id}-{board.slug}/{id}-{slug}. */
export function recentTopicPath(topic: RecentTopic): string {
  return `/forum/${topic.board.id}-${topic.board.slug}/${topic.id}-${topic.slug}`;
}
```

(Read the existing `threadPath`/`categoryPath` first and match their exact format — if `categoryPath` produces a different id-slug separator, follow the file, not this plan.)

- [ ] **Step 4: CategoryListPage** — one `fetchRecentTopics(5)` call in the existing load effect (parallel with `fetchForumIndex` via `Promise.all`; the effect's `ignore` guard covers both). Failure of the recent call must NOT fail the page — catch it separately and default `[]`.
  - **Event hero**: `const bloomWatch = recentTopics.find((t) => t.is_pinned && t.slug.startsWith('bloom-watch'));`. When found, the HeroCard renders the artifact copy: eyebrow `"Community event"`, title `"The bloom watch is on."`, description `"Every August the community tracks what's flowering, fruiting, and quietly failing. Post yours, get it identified, and help a neighbor's garden along."`, actions: primary `<Link to={recentTopicPath(bloomWatch)}><Button variant="primary">Join the bloom watch</Button></Link>` + ghost `<Button variant="ghost" onClick={scrollToBoards}>Browse boards</Button>` where `scrollToBoards` focuses/scrolls the board-list container (`boardsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })` — plus `motion-reduce` note: pass `behavior: 'auto'` when `window.matchMedia('(prefers-reduced-motion: reduce)').matches`). When NOT found, keep the current "Ask the canopy" hero UNCHANGED. Same hero art both ways.
  - **Your season (authed)**: when `isAuthenticated`, fetch `fetchMyStats()` (own effect + ignore guard; failure hides the row, never errors the page). Replace the anonymous stat trio with FOUR cards; anonymous users keep the existing trio exactly as-is:

```tsx
<div className="mt-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
  <StatCard icon={<ScanSearch … />} value={myStats.identifications_shared} label="Identifications" sublabel="shared with the forum" tone="sage" />
  <StatCard icon={<MessagesSquare … />} value={myStats.posts} label="Posts" sublabel="all time" tone="pollen" />
  <StatCard icon={<Check … />} value={myStats.solutions_accepted} label="Solutions" sublabel="accepted answers" tone="bloom" />
  {/* Zero-state (spec §9): no fabricated streak number. Wire via todos/NNN
      (forum-day-streak-badges) — replace value/sublabel when real. */}
  <StatCard icon={<Flame … />} value="—" label="Day streak" sublabel="Coming soon" tone="orchid" />
</div>
```

Add a `rowhead`-style heading above it: `<h2 className="gt-h3 mt-8">Your season</h2>` (and `Boards` heading above the chips+list to mirror the artifact's rowheads — check the current markup and keep the document outline sane: the page h1 stays sr-only). Use the icons: `ScanSearch`, `MessagesSquare`, `Check`, `Flame` from lucide. No `progress` prop anywhere (spec §9). Replace `NNN` in the comment with Task 2's actual streak todo id.

- [ ] **Step 5: Tests** — CategoryListPage suite: (a) event hero renders (with `Join the bloom watch` linking to the topic path) when a pinned bloom-watch topic is in the mocked recent payload; (b) "Ask the canopy" hero when absent AND when `fetchRecentTopics` rejects; (c) authed + stats mock → four cards with real values and the `—` streak card with "Coming soon"; (d) anon → the original trio, no "Your season" heading; (e) stats fetch rejection → trio absent but page fine (no crash, hero + boards render). Mock modules with block-body hooks; set mock resolutions in `beforeEach`.
- [ ] **Step 6: Run** — targeted vitest + `npx tsc --noEmit` → clean.
- [ ] **Step 7: Commit** — `feat(canopy-content): event hero + Your season cards`.

---

### Task 10: Web — rail modules (Community experts, Active now topics)

**Files:**

- Create: `web/src/components/forum/rail/CommunityExpertsModule.tsx`
- Create: `web/src/components/forum/rail/ActiveNowModule.tsx`
- Modify: `web/src/pages/forum/CategoryListPage.tsx` (rail composition)
- Test: `web/src/components/forum/rail/CommunityExpertsModule.test.tsx`, `web/src/components/forum/rail/ActiveNowModule.test.tsx`

**Interfaces:**

- Consumes: `fetchExperts`, `fetchRecentTopics`, `recentTopicPath`, `specimenAvatar`, `boardIdentity`, `RailModule`, `Timestamp`.
- Produces: two self-hiding rail modules; CategoryListPage's rail becomes `CommunityExperts` + `ActiveNow` + `FromTheBlogModule` (the old board-based "Active now" block is REMOVED).

- [ ] **Step 1: CommunityExpertsModule** — prop-less, self-hiding (mirror `FromTheBlogModule`'s fetch/ignore/self-hide shape exactly):

```tsx
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Users } from 'lucide-react';
import RailModule from '../../ui/RailModule';
import { fetchExperts } from '../../../services/forumService';
import { specimenAvatar } from '../../../utils/forumAvatars';
import { logger } from '../../../utils/logger';
import type { ForumExpert } from '@/types';

/** Trust-level labels, mirroring the backend's TrustLevel choices. */
const TRUST_LABELS: Record<number, string> = {
  0: 'New member', 1: 'Member', 2: 'Member', 3: 'Regular', 4: 'Leader',
};

/**
 * Right-rail module: highest-trust community members.
 *
 * Deliberately "Community experts" with NO presence dots — the artifact's
 * "Experts online" needs real presence data (ForumProfile.last_seen wiring);
 * see todos/MMM-pending-p3-forum-experts-presence.md. No online claim is made
 * until then (spec §9).
 */
export default function CommunityExpertsModule() {
  const [experts, setExperts] = useState<ForumExpert[]>([]);

  useEffect(() => {
    let ignore = false;
    fetchExperts()
      .then((rows) => {
        if (!ignore) setExperts(rows);
      })
      .catch((err) => {
        logger.error('Error loading experts rail', {
          component: 'CommunityExpertsModule',
          error: err,
        });
      });
    return () => {
      ignore = true;
    };
  }, []);

  if (experts.length === 0) return null;

  return (
    <RailModule icon={<Users aria-hidden="true" />} title="Community experts">
      <ul className="flex flex-col gap-3">
        {experts.map((expert) => (
          <li key={expert.username}>
            <Link to={`/forum/users/${expert.username}`} className="group flex items-center gap-2.5">
              <img
                src={expert.avatar ?? specimenAvatar(expert.username)}
                alt=""
                className="h-[34px] w-[34px] rounded-[11px] object-cover"
              />
              <span className="min-w-0">
                <span className="block truncate text-[12.5px] font-semibold text-ink transition-colors group-hover:text-primary">
                  {expert.display_name}
                </span>
                <span className="gt-label block normal-case tracking-normal">
                  {expert.title || TRUST_LABELS[expert.trust_level ?? 0] || 'Member'}
                </span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </RailModule>
  );
}
```

(Verify the profile route — grep the router for the UserProfilePage path (`/forum/users/:username` vs something else) and use the real one. Replace `MMM` with Task 2's presence todo id.)

- [ ] **Step 2: ActiveNowModule** — same skeleton; renders topics:

```tsx
import { Zap } from 'lucide-react';
// … fetchRecentTopics(3), self-hide on empty/error.
{topics.map((t) => {
  const { Icon, tone } = boardIdentity(t.board.slug, t.board.name);
  return (
    <li key={t.id}>
      <Link to={recentTopicPath(t)} className="group flex items-start gap-2.5">
        {t.thumbnail_url ? (
          <img src={t.thumbnail_url} alt="" className="h-10 w-10 flex-none rounded-[10px] border border-line object-cover" />
        ) : (
          <Tile tone={tone} size="sm" aria-hidden="true"><Icon className="h-4 w-4" /></Tile>
        )}
        <span className="min-w-0">
          <span className="block text-[12.5px] leading-snug font-medium text-ink transition-colors group-hover:text-primary">{t.title}</span>
          <span className="gt-label mt-0.5 block normal-case tracking-normal">
            {t.reply_count} {t.reply_count === 1 ? 'reply' : 'replies'}
            {t.last_post_at && <> · <Timestamp iso={t.last_post_at} /></>}
          </span>
        </span>
      </Link>
    </li>
  );
})}
```

Module title "Active now", icon `Zap`. (Check `Timestamp`'s props — if it requires a `prefix`, omit it or pass empty per its interface; read the component first.)

- [ ] **Step 3: Compose the rail** — CategoryListPage's `RailSlot` becomes `<CommunityExpertsModule />`, `<ActiveNowModule />`, `<FromTheBlogModule />` in that order (artifact order). Delete the old board-based Active-now block and its now-unused `activeBoards` computation. If ActiveNowModule and the page would both call `fetchRecentTopics`, that is TWO calls — acceptable (60s server cache, different limits), but prefer passing the page's fetched rows down as an optional prop `topics?: RecentTopic[]` and only self-fetching when absent; implement the prop version.
- [ ] **Step 4: Tests** — module-level (RailSlot is null in jsdom, so render the modules DIRECTLY, not through the page): experts render with title fallback to trust label, self-hide on empty and on rejection, **no presence dot in the DOM** (assert absence of any element with a `bg-secondary`-ish dot class — assert on structure: each row has exactly the img + two text spans); ActiveNow renders thumbnail when present, icon tile when null, reply pluralization, self-hides on empty/error.
- [ ] **Step 5: Run** — targeted vitest + tsc → clean.
- [ ] **Step 6: Commit** — `feat(canopy-content): experts + active-now rail modules`.

---

### Task 11: Web — ⌘K command palette

**Files:**

- Create: `web/src/components/CommandPalette.tsx`
- Modify: `web/src/layouts/AppShell.tsx`
- Test: `web/src/components/CommandPalette.test.tsx`

**Interfaces:**

- Consumes: `searchForum` (topics), `searchForumUsers` (people; auth-gated), `fetchCategories`, `threadPath` (from forumUrls — read its exact signature for search-result threads; SearchPage already uses it), `useAuth`, `useNavigate` (from `react-router-dom`).
- Produces: `<CommandPalette open onClose />`; AppShell owns the open state, the Cmd/Ctrl+K listener, and the pill button.

- [ ] **Step 1: Component** — `CommandPalette.tsx`. Requirements (implement with the repo's existing idioms — the drawer in `AppShell` shows the dialog pattern):
  - Overlay `div` fixed inset-0 z-50, backdrop `bg-abyss/70` closes on click; panel: centered top-quarter, `w-full max-w-xl`, `canopy-card rounded-lg border border-line` with an `<input>` at top (`placeholder="Search plants, posts, people…"`, autofocused on open) and a scrollable results region below (`max-h-[60vh] overflow-y-auto`).
  - `role="dialog"` `aria-modal="true"` `aria-label="Search"`; Escape closes; focus is trapped (Tab cycles input ↔ results); on close, focus returns to the trigger (AppShell passes the trigger ref or relies on the button being the previously-focused element — implement focus return explicitly with a ref captured on open).
  - **Sections**, rendered as labeled groups (`gt-label` headings): (1) **Quick actions** — always: "Identify a plant" → `/identify`, "Start a thread" → `/forum/new-thread`, plus one row per board (from `fetchCategories()`, fetched once on first open, `boardIdentity` icon) → `categoryPath(board)`; (2) **Topics** — when query ≥2 chars: `searchForum({ q })`, top 5 `threads`, each row → its thread path, final row "Search everything for '…'" → `/forum/search?q=…`; (3) **People** — only when `isAuthenticated` and query ≥2 chars: `searchForumUsers(q)`, top 5, row → the profile route (same path as Task 10).
  - **Debounce ≥250ms via `useRef` timer** (CLAUDE.md gotcha — never `useState`), cleaned up on unmount.
  - **Stale-response epoch guard (spec §8)**: a `useRef(0)` epoch incremented per issued query; responses landing with a stale epoch are dropped. Same class as the PR #537 unread-badge fix.
  - Keyboard: ArrowUp/ArrowDown move an active row (roving `aria-selected` + `id` with `aria-activedescendant` on the input), Enter activates it (navigate + close). All rows are real `<Link>`s or buttons ≥44px tall (`min-h-11`).
  - Loading state: subtle "Searching…" line per pending section; error state: section shows "Search is unavailable right now" (never a raw error object; render `error.message` semantics per repo rule).
  - Motion: fade/scale ≤200ms, wrapped in a `motion-reduce:transition-none` class.
  - Navigation uses `useNavigate` from **`react-router-dom`**.
- [ ] **Step 2: AppShell wiring** —
  - State `paletteOpen`; global listener: `useEffect` keydown for `(e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k'` → `preventDefault()`, open (ignore when an `<input>`/`<textarea>`/contenteditable has focus EXCEPT the palette's own input; simplest: only guard against repeat-open).
  - The search pill `<Link to="/forum/search">` becomes a `<button type="button" onClick={() => setPaletteOpen(true)}>` with the SAME classes plus a trailing `<kbd className="ml-auto rounded-sm border border-line-2 px-1.5 py-0.5 font-mono text-[10.5px]">{isMac ? '⌘K' : 'Ctrl K'}</kbd>`; `isMac` from `navigator.platform`/`navigator.userAgent` sniff (`/Mac|iPhone|iPad/`), computed once at module level. Keep the pill's accessible name "Search plants, posts, people…".
  - Render `<CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />` inside the provider tree.
  - AppShell suite: existing tests must stay green — the pill changed from link to button; update any test that asserted the `/forum/search` link (check `AppShell.test.tsx` and fix assertions to the button + palette-open behavior).
- [ ] **Step 3: Tests** — `CommandPalette.test.tsx` (mock the three service fns; block-body hooks): opens with quick actions visible; typing ≥2 chars calls `searchForum` after debounce (use fake timers) and renders topic rows; People section absent when unauthenticated, present + populated when authed; Escape calls `onClose`; ArrowDown+Enter navigates (assert `useNavigate` mock); stale-epoch: resolve query A's promise AFTER query B's — only B's results render; section error renders the unavailable line. AppShell test: Ctrl+K opens the palette (fire keydown), pill click opens it.
- [ ] **Step 4: Run** — targeted vitest, then the FULL web suite (`npx vitest run`) + `npx tsc --noEmit` + `npm run build` → all clean.
- [ ] **Step 5: Commit** — `feat(canopy-content): command palette (Cmd/Ctrl+K) + topbar pill`.

---

### Task 12: E2E smoke, screenshots, full gates, PR

**Files:**

- Create: `web/e2e/command-palette.spec.ts`
- Modify: none expected (fixes only if gates fail)

**Interfaces:** Consumes everything; produces the verified branch + PR.

- [ ] **Step 1: Palette e2e** — `command-palette.spec.ts` (content-independent, runs anon):

```ts
import { test, expect } from '@playwright/test';

test('command palette opens with the keyboard and closes with Escape', async ({ page }) => {
  await page.goto('/');
  await page.keyboard.press('ControlOrMeta+KeyK');
  const dialog = page.getByRole('dialog', { name: 'Search' });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText('Identify a plant')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(dialog).not.toBeVisible();
});

test('topbar search pill opens the palette', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: /Search plants, posts, people/ }).click();
  await expect(page.getByRole('dialog', { name: 'Search' })).toBeVisible();
});
```

Run: `./node_modules/.bin/playwright test command-palette` (direct binary — NEVER `npx playwright`). Expect passes on installed browsers (chromium + Mobile Chrome locally; firefox/webkit binaries are absent on this machine — that is an environment gap, not a failure).

- [ ] **Step 2: Seed locally + screenshot sweep** — backend running with the dev DB seeded (Task 7 step 4 already ran it; re-run is a no-op). Playwright screenshot script or manual `page.screenshot` passes over `/forum` (anon + authed if a dev login exists) in BOTH modes (toggle `data-mode`), plus one board page and one seeded topic (the bloom-watch topic and the mealybugs solved topic are the money shots). Save under the session scratchpad; the controller reviews them against the artifact before the PR is opened.
- [ ] **Step 3: Full gates** —
  - Backend, from `backend/`: `venv/bin/python -m pytest` (FULL suite — Topic-adjacent surface changed; the three-hit-builder rule's blast radius demands it). Also `venv/bin/python manage.py spectacular --file /dev/null` (schema still valid with the three new endpoints) and `venv/bin/python manage.py check`.
  - Web, from `web/`: `npx vitest run` (full), `npx tsc --noEmit`, `npm run build`.
  - E2E: palette spec + the existing `theme` spec (regression: AppShell changed).
- [ ] **Step 4: PR** — push branch, open PR titled `forum(content): Canopy demo world + artifact parity (PR 2.5)`. Body: spec link, the three endpoints, seed summary (5 boards / 8 users / 16 topics / guards), zero-state decisions + their todo ids, the spec §9 honesty ledger verbatim, test counts, screenshot highlights, and the post-merge manual step: **run `python manage.py seed_demo_content --confirm` on Railway (user-supervised)**. `🤖 Generated with [Claude Code](https://claude.com/claude-code)` trailer. Do NOT arm auto-merge — user reviews first (repo convention).

---

## Execution notes for the controller

- Task order is the dependency order; Tasks 3→4→5→6 are independent of each other after 3 (4/5/6 touch the same `views.py`/`urls.py`/`conf.py` — run them SEQUENTIALLY, never in parallel).
- Task 1 (Runware) and Task 2 (todos) are controller/cheap work before the first backend dispatch; Task 8 can start any time after Task 2 (it needs no backend).
- The seed run on Railway is NOT a plan task — it is a post-merge manual step with the user.
- Model guidance per the SDD skill: Tasks 3, 4, 6 are cheap-tier (complete code above); Task 5, 8, 9, 10 mid-tier; Task 7 (seed + catalogue transcription + tests) and Task 11 (palette) mid-tier with careful review; final whole-branch review on the most capable model.

## After landing

- Run the seed on Railway with the user (`--confirm`), verify `/forum` on the deployed site against the artifact.
- PR 3 (blog + blog seed) proceeds per the parent spec; the streak/presence todos stay filed.
