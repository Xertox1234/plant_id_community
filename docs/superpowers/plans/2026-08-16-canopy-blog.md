# Canopy PR 3 — Blog & Seed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Canopy blog surface (list rebuild + detail from stub) and the `seed_demo_blog` command so the deployed `/blog` matches the Canopy artifact's blog screen and the forum rail's FromTheBlogModule lights up.

**Architecture:** Backend gets a new guarded, idempotent management command in `apps/blog` (catalogue module + committed WEBP covers) wired into `seed_demo_content` as a single prod entry point; guard logic is extracted into shared helpers in `apps/forum_host/seed_content.py`. Frontend rebuilds `BlogCard`/`BlogListPage` and builds `BlogDetailPage` on the PR-1 Canopy primitives, with an `article` variant added to the shared `StreamFieldRenderer`. No blog API changes.

**Tech Stack:** Django 5 / Wagtail (pages, images, renditions), pytest-django, React 19 + TypeScript, Tailwind 4 semantic tokens (`--gt-*`), Vitest.

**Spec:** `docs/superpowers/specs/2026-08-16-canopy-blog-design.md` (advisor-hardened + empirically probed; §12 lists verified facts — cite, don't re-derive).

## Global Constraints

- Brand: user-visible copy says **Houseplant MD**; "Canopy" names only the design language.
- Locked copy verbatim (spec §7 hero, §4 titles): eyebrow `The blog · new posts weekly`; headline `Do less to your plants.`; subcopy `Guides, experiments, and honest failures from the community garden. This month: why most houseplants are killed by kindness.`; CTAs `Read the latest` / `All topics →`; post titles `Variegation isn't magic, it's mutation` and `Your fiddle leaf isn't dying, it's adjusting`.
- New CSS/classes use `--gt-*` semantic tokens only — never raw `--canopy-*` references.
- Never render a red cross on a white/light ground (Geneva-emblem constraint, binding).
- All animation gated by `prefers-reduced-motion` (the `canopy-float` utility already is).
- Demo accounts: unusable password AND `@demo.houseplant-md.com` email; the real-user guard has **no override flag**; skip-not-overwrite everywhere (existing rows are never modified; author names fill-if-blank only).
- **No blog API changes** (no serializer/viewset/model-API edits; `BlogPostPage.save()`'s existing auto-compute is used as-is).
- Backend page-creating tests: run with `--create-db` locally (Wagtail root-truncation gotcha); never run two pytest invocations concurrently.
- Edit-time formatter strips imports unused at format time — add an import in the same edit as its first usage. The pre-commit formatter can abort a commit while output looks successful — verify each commit landed with `git log -1`.
- Commits end with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`. Never push to `main`; work rides `feat/canopy-blog`.

## File Map

| File | Role |
|---|---|
| `backend/apps/blog/seed_assets/*.webp` | 6 committed cover images (Task 1) |
| `backend/apps/forum_host/seed_content.py` | + shared guard helpers `real_users_queryset()`, `is_demo_account()`, `ensure_demo_user()` (Task 2) |
| `backend/apps/forum_host/management/commands/seed_demo_content.py` | refactored to use the shared helpers (Task 2); calls `seed_demo_blog` (Task 5) |
| `backend/apps/blog/seed_content.py` | CATEGORIES / AUTHOR_NAMES / POSTS catalogue (Task 3) |
| `backend/apps/blog/management/commands/seed_demo_blog.py` | the guarded, idempotent blog seed (Task 4) |
| `backend/apps/blog/tests/test_seed_demo_blog.py` | seed tests (Tasks 4–5) |
| `backend/apps/blog/management/commands/create_demo_blog_posts.py` | **deleted** (Task 5) |
| `web/src/types/blog.ts` | author/image/related types corrected to probed shapes (Task 6) |
| `web/src/components/BlogCard.tsx` + test | Canopy rebuild, compact variant for rails (Task 6) |
| `web/src/pages/BlogListPage.tsx` + test | hero + chips/search toolbar + grid + rail rebuild (Task 7) |
| `web/src/components/StreamFieldRenderer.tsx` + test | `variant="article"` + token restyle of block visuals (Task 8) |
| `web/src/pages/BlogDetailPage.tsx` + test | full detail build (Task 9) |
| `web/src/services/blogService.ts` | `fetchRelatedPosts()` stub deleted (Task 9) |
| `web/public/illustrations/thumb-*.webp` | deleted after reference grep (Task 1) |

Task order: 1 → 2 → 3 → 4 → 5 (backend done) → 6 → 7 → 8 → 9 → 10. Task 1 is controller-executed (Runware MCP access). Tasks 6–9 depend on nothing in 2–5 at build time (the web consumes the live API contract, already probed), but keep the order — the seeded world is what Task 10's visual pass photographs.

---

### Task 1: Seed assets (controller-executed — Runware MCP)

**Files:**

- Create: `backend/apps/blog/seed_assets/cover-kindness.webp`, `cover-mites.webp`, `cover-pruning.webp`, `cover-jungle.webp` (Runware-generated)
- Move: `web/public/illustrations/thumb-monstera.webp` → `backend/apps/blog/seed_assets/cover-variegation.webp`; `web/public/illustrations/thumb-fig.webp` → `backend/apps/blog/seed_assets/cover-fiddle.webp`

**Interfaces:**

- Produces: the six asset filenames Task 3's catalogue references verbatim in its `cover` keys.

- [ ] **Step 1: Reference grep before moving anything** (spec §6 — don't break a static reference)

Run: `grep -rn "thumb-monstera\|thumb-fig" web/src web/index.html web/public 2>/dev/null`
Expected: no hits outside `web/public/illustrations/` itself. If a hit appears, stop and re-point it before the move.

- [ ] **Step 2: Move the two committed thumbs into the backend**

```bash
mkdir -p backend/apps/blog/seed_assets
git mv web/public/illustrations/thumb-monstera.webp backend/apps/blog/seed_assets/cover-variegation.webp
git mv web/public/illustrations/thumb-fig.webp backend/apps/blog/seed_assets/cover-fiddle.webp
```

- [ ] **Step 3: Generate the four new covers via Runware** (moody botanical photo style matching the existing committed covers; WEBP, target ≤120 KB each, landscape ~1200×800 so the fill-800x400 rendition crops well)

| File | Prompt intent |
|---|---|
| `cover-kindness.webp` | Overwatered pothos in a terracotta pot on a windowsill, saucer full of water, yellowing lower leaf, moody soft window light, shallow depth of field, photo |
| `cover-mites.webp` | Macro photo of the underside of a houseplant leaf with fine stippling damage and faint webbing, dramatic side light, photo |
| `cover-pruning.webp` | Bypass pruners mid-cut on a leggy ficus branch, hands in frame, warm indoor light, wood table, photo |
| `cover-jungle.webp` | Small apartment balcony densely layered with potted plants on vertical shelves, golden hour, cozy, photo |

- [ ] **Step 4: Verify formats and sizes**

Run: `file backend/apps/blog/seed_assets/*.webp && du -h backend/apps/blog/seed_assets/*.webp`
Expected: all `Web/P image`, each ≤120 KB (re-generate or re-encode any that exceed it).

- [ ] **Step 5: Commit** (then verify it landed — formatter-abort trap)

```bash
git add backend/apps/blog/seed_assets web/public/illustrations
git commit -m "assets(blog): six seed covers — two thumbs relocated, four Runware-generated

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
git log -1 --stat
```

---

### Task 2: Shared demo-guard helpers (forum_host)

**Files:**

- Modify: `backend/apps/forum_host/seed_content.py` (append three functions at the end, after the data constants)
- Modify: `backend/apps/forum_host/management/commands/seed_demo_content.py:62-73` (census block) and `:96-146` (`_seed_users`)
- Test: `backend/apps/forum_host/tests/test_seed_demo_content.py` (existing suite is the regression net — no new tests needed; it already covers every guard path)

**Interfaces:**

- Produces: `real_users_queryset() -> QuerySet[User]`, `is_demo_account(user) -> bool`, `ensure_demo_user(spec: dict, stdout=None) -> User` in `apps.forum_host.seed_content`. Task 4's command imports all three names (`ensure_demo_user` indirectly needs `USERS`, already exported).
- Consumes: existing `USERS`, `DEMO_EMAIL_DOMAIN` constants in the same module.

- [ ] **Step 1: Append the helpers to `apps/forum_host/seed_content.py`**

```python
# ---------------------------------------------------------------------------
# Shared guard helpers — single source for the demo-account shape, used by
# BOTH seed commands (seed_demo_content and apps.blog's seed_demo_blog).
# Duplicated guard blocks drift (spec §5 / kimi-challenge); keep it here.
# Django imports live inside the functions so importing the catalogue data
# stays settings-free.
# ---------------------------------------------------------------------------


def real_users_queryset():
    """Every account that is neither demo-shaped nor a superuser.

    Guard layer 2's census: any row here means a live community — the seeds
    abort unconditionally (no override flag, by design)."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    demo_usernames = {u["username"] for u in USERS}
    return User.objects.exclude(
        username__in=demo_usernames,
        email__iendswith=f"@{DEMO_EMAIL_DOMAIN}",
    ).exclude(is_superuser=True)


def is_demo_account(user):
    """True when the account has the demo shape: unusable password AND the
    demo email domain. The census excuses superusers by design (the Railway
    admin must not block seeding), so this per-account check is what stops
    get_or_create from adopting a real account — superuser included — that
    happens to sit on a demo username."""
    return user.has_usable_password() is False and user.email.lower().endswith(
        f"@{DEMO_EMAIL_DOMAIN}".lower()
    )


def ensure_demo_user(spec, stdout=None):
    """Get-or-create ONE demo user (with ForumProfile fields) from a USERS
    spec. Never adopts or modifies a real account. Appointed trust survives
    signal recounts (signals.py takes max(current, earned))."""
    from django.contrib.auth import get_user_model
    from django.core.management.base import CommandError
    from wagtail_forum.models import ForumProfile

    User = get_user_model()
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
        profile.trust_level = spec["trust_level"]
        profile.save(
            update_fields=["display_name", "title", "bio", "trust_level"]
        )
        if stdout:
            stdout.write(f"Created demo user {spec['username']}.")
    elif not is_demo_account(user):
        raise CommandError(
            f"Refusing to seed demo user '{spec['username']}' "
            "— an account with that username already exists "
            "and is not a demo account (email ending in "
            f"@{DEMO_EMAIL_DOMAIN} with no usable password). "
            "This seed never adopts or modifies a real "
            "account, superuser or not."
        )
    return user
```

- [ ] **Step 2: Refactor `seed_demo_content.py` to call them**

In the imports, extend the existing `from apps.forum_host.seed_content import ...` line to also import `ensure_demo_user` and `real_users_queryset` (drop `USERS` from the command's imports **only if** it becomes unused — it is still used for `demo_usernames` in tests, check with grep; the command itself no longer needs it after this refactor, and the formatter will strip it, which is correct here).

Replace the census block in `handle()` (currently builds `demo_usernames` + `real_users` inline):

```python
        # Guard layer 2 (cannot be overridden): any real user = abort. Census
        # semantics live in seed_content.real_users_queryset — shared with
        # apps.blog's seed_demo_blog so the two guards cannot drift.
        real_users = real_users_queryset()
        if real_users.exists():
            raise CommandError(
                f"{real_users.count()} real user account(s) exist — refusing to "
                "seed demo content into a live community. This guard has no "
                "override flag by design (spec §5)."
            )
```

Replace `_seed_users` in full (the per-user body moved to `ensure_demo_user`; the atomic wrapper and its rationale stay):

```python
    def _seed_users(self):
        users = {}
        # Atomic across the whole spec list: a mid-loop adoption refusal must
        # roll back any demo users this same call already created, not leave a
        # partially-seeded user set behind (spec-consistent with the "seed
        # aborts with no content created" contract for guard failures).
        with transaction.atomic():
            for spec in USERS:
                users[spec["username"]] = ensure_demo_user(spec, self.stdout)
        return users
```

(Keep the `User = get_user_model()` line only where still used; the formatter will flag dead imports — remove `get_user_model` from the command imports if nothing else uses it.)

- [ ] **Step 3: Run the existing forum seed suite — it is the regression net**

Run: `cd backend && source venv/bin/activate && pytest apps/forum_host/tests/test_seed_demo_content.py -v --create-db`
Expected: all 12 tests PASS (guard trips, adoption refusal, idempotency, world shape — all unchanged behavior).

- [ ] **Step 4: Commit (verify with `git log -1`)**

```bash
git add backend/apps/forum_host/seed_content.py backend/apps/forum_host/management/commands/seed_demo_content.py
git commit -m "refactor(seed): extract shared demo-guard helpers into forum_host.seed_content

real_users_queryset / is_demo_account / ensure_demo_user become the single
source both seed commands call (spec §5 — duplicated guard blocks drift).
Behavior unchanged; existing seed suite is the regression net.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Blog catalogue module (`apps/blog/seed_content.py`)

**Files:**

- Create: `backend/apps/blog/seed_content.py`

**Interfaces:**

- Produces: `CATEGORIES: list[dict]` (`name`, `slug`, `description`), `AUTHOR_NAMES: dict[str, tuple[str, str]]` (username → (first, last)), `POSTS: list[dict]` (`slug`, `title`, `category`, `author`, `age_days`, `view_count`, `cover`, `introduction`, `blocks`). Task 4's command imports all three. `blocks` entries are `("heading", str)`, `("paragraph", "<p>…</p>")`, or `("quote", {"quote_text": str, "attribution": str})` — the exact python-native tuple shapes `create_demo_blog_posts.py` proved this Wagtail version accepts at `BlogPostPage(content_blocks=...)` construction.
- Consumes: nothing (pure data module; no Django imports).

This is a data-only module. Copy is final — locked titles verbatim (Global Constraints); bodies are real ~450–700-word articles so `save()`'s auto-computed reading times are honest 2–4 min values. View counts are non-monotonic with age so the popular ranking feels organic (top-5 = all but `small-space-jungle`).

- [ ] **Step 1: Write the module** (single step — data only, verified by Task 4's tests)

```python
"""Canopy demo blog catalogue (PR 3, spec §3–§4).

Data only — no Django imports, so the catalogue is importable settings-free.
Consumed by management/commands/seed_demo_blog.py. Post bodies are final,
authored copy: reading_time auto-computes from these at save() (~200 wpm),
so their length is the honesty contract for the "N min read" meta line.

blocks tuple shapes (proven by the retired create_demo_blog_posts command):
("heading", str) · ("paragraph", "<p>html</p>") ·
("quote", {"quote_text": str, "attribution": str})
"""

CATEGORIES = [
    {
        "name": "Care",
        "slug": "care",
        "description": "Watering, light, and the daily habits that keep plants alive.",
    },
    {
        "name": "Propagation",
        "slug": "propagation",
        "description": "Cuttings, divisions, and making more plants from the ones you have.",
    },
    {
        "name": "Pests & diseases",
        "slug": "pests-diseases",
        "description": "Spotting trouble early and treating it without panic.",
    },
    {
        "name": "Design",
        "slug": "design",
        "description": "Shaping plants and spaces — pruning, styling, and small-space jungles.",
    },
]

# username -> (first_name, last_name). MUST equal the ForumProfile
# display_name cast split (spec §5: the same person never appears under two
# names across forum and blog). Applied fill-if-blank only.
AUTHOR_NAMES = {
    "june_park": ("June", "Park"),
    "iris_delgado": ("Iris", "Delgado"),
    "sam_whitaker": ("Sam", "Whitaker"),
    "theo_brandt": ("Theo", "Brandt"),
}

POSTS = [
    {
        # The hero's "This month" feature (spec §4 #1) — newest post,
        # "Read the latest" CTA target.
        "slug": "killed-by-kindness",
        "title": "Killed by kindness",
        "category": "care",
        "author": "june_park",
        "age_days": 3,
        "view_count": 340,
        "cover": "cover-kindness.webp",
        "introduction": (
            "<p>Most houseplants don't die of neglect. They die of attention — "
            "specifically, the watering can. Here's what actually happens below "
            "the soil line, and the one habit that prevents it.</p>"
        ),
        "blocks": [
            (
                "paragraph",
                "<p>When a plant looks unhappy, the instinct is to do something, "
                "and the easiest something is water. So the droopy pothos gets a "
                "drink, and the yellowing philodendron gets a drink, and a week "
                "later both look worse, so they get another. In the clinic side "
                "of this community, the pattern behind dead houseplants is "
                "overwhelmingly this one: kindness, applied weekly, until the "
                "roots drown.</p>",
            ),
            ("heading", "What overwatering actually is"),
            (
                "paragraph",
                "<p>Overwatering isn't about the amount you pour — it's about "
                "oxygen. Roots respire. In soil that never dries, the air "
                "pockets stay flooded, the roots suffocate, and opportunistic "
                "fungi like <i>Pythium</i> and <i>Phytophthora</i> move into "
                "the dying tissue. That's root rot: not a disease your plant "
                "caught, but a condition you scheduled.</p>",
            ),
            (
                "paragraph",
                "<p>The cruel part is the symptom. A plant with rotting roots "
                "can't move water, so it wilts — and a wilting plant looks "
                "thirsty. If you answer the wilt with more water, you complete "
                "the loop. This is why \"how often should I water?\" is the "
                "wrong question. The calendar doesn't know what your soil is "
                "doing.</p>",
            ),
            (
                "quote",
                {
                    "quote_text": (
                        "The plant isn't thirsty on Tuesdays. It's thirsty "
                        "when the soil is dry — and only then."
                    ),
                    "attribution": "Every pathologist, eventually",
                },
            ),
            ("heading", "The one habit that fixes it"),
            (
                "paragraph",
                "<p>Check, then water. Push a finger two knuckles into the "
                "soil, or lift the pot and learn its dry weight. If the top "
                "few centimetres are damp, walk away — whatever the schedule "
                "says. Most common houseplants (pothos, monstera, snake "
                "plants, ZZs) would rather sit slightly dry for a week than "
                "sit wet for a day.</p>",
            ),
            (
                "paragraph",
                "<p>If you suspect rot already: tip the plant out. Healthy "
                "roots are firm and pale; rotten ones are brown, soft, and "
                "slide apart when pulled. Cut everything mushy back to clean "
                "tissue with sterilised scissors, repot into fresh, "
                "fast-draining mix in a pot with a real drainage hole, and "
                "water once. Then — this is the hard part — leave it alone. "
                "Recovery looks like nothing happening for a month. Doing "
                "less is the treatment.</p>",
            ),
        ],
    },
    {
        # Locked title (artifact card #1).
        "slug": "variegation-isnt-magic",
        "title": "Variegation isn't magic, it's mutation",
        "category": "propagation",
        "author": "iris_delgado",
        "age_days": 10,
        "view_count": 210,
        "cover": "cover-variegation.webp",
        "introduction": (
            "<p>Those white-splashed monstera leaves that cost more than your "
            "rent aren't a different species — they're a genetic accident that "
            "has to be carefully carried from cutting to cutting. Here's how it "
            "works and what that means when you propagate.</p>"
        ),
        "blocks": [
            (
                "paragraph",
                "<p>A variegated monstera is a chimera: two genetically "
                "different tissues growing side by side in one plant. The "
                "white sectors carry a mutation that stops chlorophyll "
                "production; the green sectors don't. The pattern you're "
                "paying for is the boundary between them, drawn fresh in "
                "every new leaf.</p>",
            ),
            ("heading", "Why the price tag"),
            (
                "paragraph",
                "<p>White tissue doesn't photosynthesise. A heavily variegated "
                "plant is running on half an engine, so it grows slowly — and "
                "slow growth means slow propagation, and slow propagation "
                "means scarcity. You can't tissue-culture your way out of it "
                "reliably either: chimeral variegation often doesn't survive "
                "the process, which is why lab-grown \"albo\" batches keep "
                "disappointing people.</p>",
            ),
            ("heading", "Propagating without losing the pattern"),
            (
                "paragraph",
                "<p>The variegation lives in the meristem layers at each node. "
                "When you take a cutting, choose a node whose surrounding stem "
                "shows both colours — a balanced marbling on the stem is the "
                "best predictor that the new growth point inherits both "
                "tissues. A cutting from an all-green stretch of stem will "
                "grow an all-green plant, no matter how white the leaf above "
                "it was.</p>",
            ),
            (
                "paragraph",
                "<p>Reversion runs both ways. A plant can drift green (the "
                "faster tissue simply outcompetes the white) or drift white "
                "until it can't feed itself. You steer with the pruning "
                "shears: cut back to a node behind the drift and let a "
                "better-balanced growth point take over. And when you're "
                "buying: look at the newest leaf and the stem, not the "
                "prettiest old leaf — the newest growth tells you where the "
                "plant is going, the old leaf only tells you where it's "
                "been.</p>",
            ),
        ],
    },
    {
        # Locked title (artifact card #2).
        "slug": "fiddle-leaf-adjusting",
        "title": "Your fiddle leaf isn't dying, it's adjusting",
        "category": "care",
        "author": "sam_whitaker",
        "age_days": 17,
        "view_count": 290,
        "cover": "cover-fiddle.webp",
        "introduction": (
            "<p>You brought it home, gave it the perfect corner, and it dropped "
            "three leaves in a week. Before you diagnose disease or drown it in "
            "fixes — this is probably just what a ficus does when its world "
            "changes.</p>"
        ),
        "blocks": [
            (
                "paragraph",
                "<p><i>Ficus lyrata</i> has a reputation for drama, and it's "
                "earned — but the drama is mostly one behaviour: when "
                "conditions change, it sheds. A move across the room, a new "
                "home, a season flipping the light angle, a draft from a "
                "winter window. The tree doesn't know it was an upgrade. It "
                "just knows the light budget changed, and it balances the "
                "books by dropping the leaves it can no longer afford.</p>",
            ),
            ("heading", "Normal shedding vs. actual trouble"),
            (
                "paragraph",
                "<p>Adjustment loss looks like this: lower or interior leaves "
                "going first, browning from the edge inward, over two to six "
                "weeks after a change, while the top of the plant keeps "
                "pushing new growth. Trouble looks different: brown spots "
                "with yellow halos spreading across many leaves at once "
                "(bacterial), sudden all-over drop (cold shock), or mushy "
                "stems (rot). If the newest growth is healthy, you're almost "
                "certainly watching acclimation, not decline.</p>",
            ),
            (
                "paragraph",
                "<p>The worst response is to keep changing things. New spot, "
                "then another new spot, then extra water, then fertiliser to "
                "\"help\" — every intervention resets the clock. Pick the "
                "brightest spot you can offer (fiddles want more light than "
                "almost any care card admits — within a metre of a bright "
                "window), and then commit to it.</p>",
            ),
            ("heading", "The six-week rule"),
            (
                "paragraph",
                "<p>After any move: six weeks of boring consistency. Water "
                "when the top few centimetres dry out, don't feed, don't "
                "repot, don't rotate it daily. Count the dropped leaves if it "
                "helps — a healthy adjusting fiddle usually stops shedding "
                "inside a month and answers with a flush of new leaves at the "
                "top. That new growth is the tree's signature on the new "
                "lease.</p>",
            ),
        ],
    },
    {
        "slug": "spider-mites-early",
        "title": "Spider mites move in before you notice",
        "category": "pests-diseases",
        "author": "june_park",
        "age_days": 24,
        "view_count": 150,
        "cover": "cover-mites.webp",
        "introduction": (
            "<p>By the time you see webbing, the colony is weeks old. The real "
            "detection window is earlier — and it's on the side of the leaf you "
            "never look at.</p>"
        ),
        "blocks": [
            (
                "paragraph",
                "<p>Spider mites are not insects — they're arachnids the size "
                "of a full stop, and they feed by puncturing individual leaf "
                "cells and drinking the contents. Each puncture leaves a pale "
                "pinprick. Scattered across a leaf, those pinpricks read as a "
                "dull, dusty, faded look long before any webbing appears. "
                "That stippling is your early warning, and it's visible weeks "
                "ahead of the cobwebs.</p>",
            ),
            ("heading", "The thirty-second weekly check"),
            (
                "paragraph",
                "<p>Once a week, flip a leaf on your most susceptible plants "
                "— calatheas, alocasias, palms, ivy, anything already stressed "
                "— and look at the underside against the light. Fine pale "
                "speckling on top, gritty dust that moves underneath: mites. "
                "A sheet of white paper held under a tapped leaf works too; "
                "the dust that walks is your answer.</p>",
            ),
            (
                "paragraph",
                "<p>Mites explode in warm, dry air — a radiator season "
                "special. A generation completes in under a week at room "
                "temperature, which is why an infestation that \"appeared "
                "overnight\" didn't. It compounded, quietly, on the underside "
                "of the leaves.</p>",
            ),
            ("heading", "Treatment that actually sticks"),
            (
                "paragraph",
                "<p>Quarantine the plant first. Then physically knock the "
                "population down: a genuinely thorough shower, top and "
                "underside of every leaf. Follow with insecticidal soap or "
                "horticultural oil, coating the leaf undersides — contact "
                "treatments only kill what they touch. Repeat every five to "
                "seven days for three rounds; eggs survive the first pass, so "
                "one treatment is a pause, not a cure. And keep the humidity "
                "up afterwards — dry air is an invitation to reinfest.</p>",
            ),
        ],
    },
    {
        "slug": "prune-like-you-mean-it",
        "title": "Prune like you mean it",
        "category": "design",
        "author": "theo_brandt",
        "age_days": 31,
        "view_count": 120,
        "cover": "cover-pruning.webp",
        "introduction": (
            "<p>Timid pruning makes leggy plants. An arborist's case for cutting "
            "deeper than feels safe — and where exactly to make the cut.</p>"
        ),
        "blocks": [
            (
                "paragraph",
                "<p>I prune trees for a living, and the mistake I see indoors "
                "is the same one I see in orchards: people trim the tips and "
                "call it shaping. Tip-trimming a leggy pothos or a stretched "
                "ficus just relocates the legginess. If you want a fuller "
                "plant, the cut has to go deeper — because new growth comes "
                "from where you cut, not where you wish.</p>",
            ),
            ("heading", "Where growth actually comes from"),
            (
                "paragraph",
                "<p>Every leaf meets the stem at a node, and at every node "
                "sits a dormant bud. Apical dominance — hormones from the "
                "growing tip — keeps those buds asleep. Remove the tip and "
                "the nearest buds below wake up, usually two or three of "
                "them. That's the whole trick: one cut above a node trades "
                "one growth point for several. Cut a centimetre above the "
                "node, angled away from the bud; stubs die back, and cuts "
                "made mid-internode leave a dead straw that invites rot.</p>",
            ),
            (
                "paragraph",
                "<p>So prune for the plant you want in six months, not the "
                "plant you have. A leggy pothos can lose half its length and "
                "answer with branches at every remaining node. A "
                "single-stalk ficus can be topped at the height where you "
                "want it to fork. Vigorous growers — pothos, philodendron, "
                "tradescantia, ficus — shrug off a hard cutback in growing "
                "season and hand you a pile of propagation material as "
                "change.</p>",
            ),
            (
                "quote",
                {
                    "quote_text": (
                        "A timid cut is a decision to make the same cut "
                        "again in three months."
                    ),
                    "attribution": "Theo Brandt",
                },
            ),
            (
                "paragraph",
                "<p>Timing matters less indoors than outside, but the rule of "
                "thumb holds: prune hard at the start of active growth "
                "(spring into summer) so the response is fast, and keep "
                "winter cuts to maintenance. Sharp, clean tools; wipe the "
                "blades between plants. Then put the shears down and let the "
                "plant answer.</p>",
            ),
        ],
    },
    {
        "slug": "small-space-jungle",
        "title": "A jungle in forty square feet",
        "category": "design",
        "author": "sam_whitaker",
        "age_days": 38,
        "view_count": 80,
        "cover": "cover-jungle.webp",
        "introduction": (
            "<p>You don't need a conservatory. A balcony, one good wall, and "
            "some vertical thinking will hold more plants than you can "
            "water in an evening — here's the layout maths.</p>"
        ),
        "blocks": [
            (
                "paragraph",
                "<p>My entire growing space is a balcony you can cross in two "
                "steps, and it holds about sixty plants comfortably. The "
                "trick isn't miniature plants — it's that a jungle is "
                "measured in layers, not floor area. Floor, shelf, rail, and "
                "hanging: four storeys of growing space stacked over the "
                "same forty square feet.</p>",
            ),
            ("heading", "Layer by light, not by looks"),
            (
                "paragraph",
                "<p>Every shelf is its own microclimate. The top shelf near "
                "the glass gets triple the light of the floor in the corner "
                "— so the sun-hungry things (herbs, succulents, flowering "
                "plants) live high, and the shade-tolerant crowd (pothos, "
                "ferns, ZZ) furnishes the dim lower levels they'd choose in "
                "a forest anyway. When a plant sulks, the first move is one "
                "shelf up or down, not a new pot.</p>",
            ),
            (
                "paragraph",
                "<p>Grouping is free humidity. Plants transpire, and a dense "
                "cluster raises the local humidity a few points over the "
                "room — the difference between crispy calathea edges and "
                "none. Cluster the humidity-lovers on one shelf with a tray "
                "of damp pebbles under them, and let the succulents keep "
                "their airy corner.</p>",
            ),
            ("heading", "Edit like a curator"),
            (
                "paragraph",
                "<p>The failure mode of a small jungle isn't running out of "
                "space — it's keeping plants you don't love because space "
                "opened up. Forty square feet forces the good habit: every "
                "plant earns its spot each season. Propagate the favourites, "
                "gift the rest, and the jungle stays dense, healthy, and "
                "yours. A small collection you can water in twenty minutes "
                "beats a sprawling one you resent.</p>",
            ),
        ],
    },
]
```

- [ ] **Step 2: Sanity-import the module**

Run: `cd backend && source venv/bin/activate && python -c "from apps.blog.seed_content import CATEGORIES, AUTHOR_NAMES, POSTS; assert len(CATEGORIES)==4 and len(POSTS)==6 and set(AUTHOR_NAMES) == {p['author'] for p in POSTS}; print('catalogue ok')"`
Expected: `catalogue ok`

- [ ] **Step 3: Commit (verify with `git log -1`)**

```bash
git add backend/apps/blog/seed_content.py
git commit -m "feat(blog): Canopy demo blog catalogue — 4 categories, 6 authored posts

Data-only module (spec §3–§4). Locked artifact titles verbatim; bodies are
real ~450–700-word articles so save()'s auto-computed reading times are
honest. View counts drive the popular ranking (no BlogPostView rows).

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: `seed_demo_blog` command + tests

**Files:**

- Create: `backend/apps/blog/management/commands/seed_demo_blog.py`
- Test: `backend/apps/blog/tests/test_seed_demo_blog.py`

**Interfaces:**

- Consumes: Task 2's `real_users_queryset`, `ensure_demo_user`, and `USERS` from `apps.forum_host.seed_content`; Task 3's `CATEGORIES`, `AUTHOR_NAMES`, `POSTS`; Task 1's asset files.
- Produces: management command `seed_demo_blog` with a `--confirm` kwarg (`call_command("seed_demo_blog", confirm=True)`) — Task 5 wires it into `seed_demo_content`.

- [ ] **Step 1: Write the failing tests** — `backend/apps/blog/tests/test_seed_demo_blog.py`:

```python
"""Tests for `manage.py seed_demo_blog` (Canopy PR 3, spec §5).

Page-creating (BlogIndexPage/BlogPostPage are Wagtail pages) — run locally
with --create-db on a partial re-run (backend/CLAUDE.md stale-test-DB gotcha).
"""

from datetime import timedelta

import pytest
from apps.blog.models import BlogCategory, BlogIndexPage, BlogPostPage
from apps.blog.seed_content import AUTHOR_NAMES, CATEGORIES, POSTS
from apps.forum_host.seed_content import DEMO_EMAIL_DOMAIN
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from django.utils import timezone
from wagtail.images import get_image_model
from wagtail.models import Site

User = get_user_model()

EXPECTED_COVERS = {f"Seed: {p['cover']}" for p in POSTS}


def _world_counts():
    return (
        User.objects.count(),
        BlogCategory.objects.count(),
        BlogPostPage.objects.count(),
        get_image_model().objects.count(),
    )


@override_settings(DEBUG=False)
@pytest.mark.django_db
def test_refuses_without_confirm_when_not_debug():
    with pytest.raises(CommandError, match="--confirm"):
        call_command("seed_demo_blog")


@override_settings(DEBUG=False)
@pytest.mark.django_db
def test_confirm_seeds_when_not_debug():
    call_command("seed_demo_blog", confirm=True)
    assert BlogPostPage.objects.count() == len(POSTS)


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_refuses_when_real_users_exist_even_with_confirm():
    User.objects.create_user(username="alice", password="x")
    with pytest.raises(CommandError, match="real user"):
        call_command("seed_demo_blog", confirm=True)


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_superuser_does_not_trip_the_guard():
    User.objects.create_superuser(
        username="admin", email="admin@example.com", password="x"
    )
    call_command("seed_demo_blog")
    assert BlogPostPage.objects.count() == len(POSTS)


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_refuses_to_adopt_a_real_account_on_an_author_username():
    # Same adoption hole the forum seed closed: a real superuser sitting on a
    # demo username sails past the census (superusers are excused by design)
    # and must be refused at the per-account check, leaving nothing created.
    real_admin = User.objects.create_superuser(
        username="june_park", email="june@realcompany.com", password="x"
    )
    with pytest.raises(CommandError, match="june_park"):
        call_command("seed_demo_blog")

    real_admin.refresh_from_db()
    assert real_admin.email == "june@realcompany.com"
    assert real_admin.has_usable_password() is True
    assert real_admin.first_name == ""  # names never touched on a refusal
    assert BlogPostPage.objects.count() == 0


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_author_names_set_only_when_blank():
    # Fill-if-blank (spec §5): a demo-shaped account whose name was manually
    # customised keeps the custom name; a blank one gets the cast name.
    custom = User.objects.create_user(
        username="iris_delgado",
        email=f"iris_delgado@{DEMO_EMAIL_DOMAIN}",
        first_name="Custom",
        last_name="Name",
    )
    custom.set_unusable_password()
    custom.save()

    call_command("seed_demo_blog")

    custom.refresh_from_db()
    assert (custom.first_name, custom.last_name) == ("Custom", "Name")
    for username, (first, last) in AUTHOR_NAMES.items():
        if username == "iris_delgado":
            continue
        user = User.objects.get(username=username)
        assert (user.first_name, user.last_name) == (first, last)


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_run_twice_is_idempotent():
    call_command("seed_demo_blog")
    counts_1 = _world_counts()
    published_1 = dict(BlogPostPage.objects.values_list("slug", "first_published_at"))

    call_command("seed_demo_blog")
    counts_2 = _world_counts()
    published_2 = dict(BlogPostPage.objects.values_list("slug", "first_published_at"))

    assert counts_1 == counts_2
    assert published_1 == published_2


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_reuses_an_existing_blog_index():
    site_root = Site.objects.get(is_default_site=True).root_page
    index = site_root.add_child(instance=BlogIndexPage(title="Blog", slug="blog"))
    index.save_revision().publish()

    call_command("seed_demo_blog")

    assert BlogIndexPage.objects.count() == 1
    assert BlogPostPage.objects.first().get_parent().pk == index.pk


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_world_shape():
    call_command("seed_demo_blog")

    assert BlogPostPage.objects.count() == len(POSTS)
    assert BlogCategory.objects.count() == len(CATEGORIES)

    # Routable tree (audit H1 analogue): the index must live under the Site's
    # root_page or every post URL is None and nothing is ever served.
    site_root = Site.objects.get(is_default_site=True).root_page
    index = BlogIndexPage.objects.get()
    assert index.is_descendant_of(site_root)
    assert index.get_url() is not None

    now = timezone.now()
    for spec in POSTS:
        post = BlogPostPage.objects.get(slug=spec["slug"])
        assert post.live is True
        assert post.author.username == spec["author"]
        assert [c.slug for c in post.categories.all()] == [spec["category"]]
        assert post.view_count == spec["view_count"]
        assert post.featured_image is not None
        assert post.featured_image.title == f"Seed: {spec['cover']}"
        # Back-dating (publish-fields lesson, LEARNINGS 2026-08-15): the
        # curated age must land on first/last_published_at, not just the
        # child-table publish_date.
        expected = now - timedelta(days=spec["age_days"])
        assert abs(post.first_published_at - expected) < timedelta(minutes=5)
        assert abs(post.last_published_at - expected) < timedelta(minutes=5)
        assert post.publish_date == expected.date()
        # Honesty contract: reading_time is auto-computed at save() from the
        # real body — assert PRESENCE and plausibility, not a pinned value
        # (DRF-SkipField lesson: a silently-absent value must fail loudly).
        assert post.reading_time is not None
        assert post.reading_time >= 2

    seeded_images = get_image_model().objects.filter(title__startswith="Seed: ")
    # cover-variegation / cover-fiddle names must not collide with forum
    # seed titles; in THIS suite only blog covers exist.
    assert {img.title for img in seeded_images} == EXPECTED_COVERS

    # Popular ordering is deterministic from seeded view_counts alone
    # (spec §12: the endpoint never excludes zero-view posts).
    ordered = list(
        BlogPostPage.objects.order_by("-view_count").values_list("slug", flat=True)
    )
    assert ordered == [
        "killed-by-kindness",
        "fiddle-leaf-adjusting",
        "variegation-isnt-magic",
        "spider-mites-early",
        "prune-like-you-mean-it",
        "small-space-jungle",
    ]
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && source venv/bin/activate && pytest apps/blog/tests/test_seed_demo_blog.py -v --create-db`
Expected: every test FAILS with `Unknown command: 'seed_demo_blog'`.

- [ ] **Step 3: Write the command** — `backend/apps/blog/management/commands/seed_demo_blog.py`:

```python
from datetime import timedelta
from pathlib import Path

from apps.blog.models import BlogCategory, BlogIndexPage, BlogPostPage
from apps.blog.seed_content import AUTHOR_NAMES, CATEGORIES, POSTS
from apps.forum_host.seed_content import (
    USERS,
    ensure_demo_user,
    real_users_queryset,
)
from django.core.files.images import ImageFile
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from wagtail.images import get_image_model
from wagtail.models import Collection, Page, Site

ASSET_DIR = Path(__file__).resolve().parent.parent.parent / "seed_assets"
IMAGE_COLLECTION_NAME = "Blog images"


class Command(BaseCommand):
    help = (
        "Idempotently seed the Canopy demo blog: BlogIndexPage, 4 categories, "
        "6 posts with committed cover images. Skip-not-overwrite: existing "
        "rows are never modified. Safe to re-run."
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
        # Census semantics are shared with seed_demo_content via
        # forum_host.seed_content.real_users_queryset (spec §5 — one source).
        real_users = real_users_queryset()
        if real_users.exists():
            raise CommandError(
                f"{real_users.count()} real user account(s) exist — refusing to "
                "seed demo content into a live community. This guard has no "
                "override flag by design (spec §5)."
            )

        index = self._ensure_index()
        categories = self._seed_categories()
        authors = self._ensure_authors()
        created = [
            spec
            for spec in POSTS
            if self._seed_post(spec, index, categories, authors)
        ]
        self.stdout.write(
            self.style.SUCCESS(
                f"Blog seed complete: {len(created)} post(s) created, "
                f"{len(POSTS) - len(created)} already present."
            )
        )
        if created:
            # The forum half may have skipped (and not refreshed) — refresh
            # here so search reflects the seeded posts.
            call_command("update_index", verbosity=0)

    # -- page tree ----------------------------------------------------------

    def _ensure_index(self):
        # Must live under the Site's root_page (the routable tree), NOT the
        # depth-1 treebeard root — same audit-H1 constraint seed_default_forum
        # documents: a page attached there has url None and is never served.
        try:
            site_root = Site.objects.get(is_default_site=True).root_page
        except Site.DoesNotExist:
            raise CommandError(
                "No default Wagtail Site found. Run migrations before seeding."
            )
        except Site.MultipleObjectsReturned:
            raise CommandError(
                "Multiple default Wagtail Sites found; fix is_default_site "
                "flags before seeding."
            )

        index = BlogIndexPage.objects.first()
        if index is None:
            index = site_root.add_child(
                instance=BlogIndexPage(title="Blog", slug="blog")
            )
            index.save_revision().publish()
            self.stdout.write(self.style.SUCCESS("Created BlogIndexPage 'blog'."))
        elif not index.is_descendant_of(site_root):
            index.move(site_root, pos="last-child")
            index = BlogIndexPage.objects.get(pk=index.pk)
            if not index.revisions.exists():
                index.save_revision().publish()
            self.stdout.write(
                self.style.SUCCESS("Moved BlogIndexPage under the site root page.")
            )
        return index

    # -- categories / authors ----------------------------------------------

    def _seed_categories(self):
        categories = {}
        for spec in CATEGORIES:
            category, created = BlogCategory.objects.get_or_create(
                slug=spec["slug"],
                defaults={
                    "name": spec["name"],
                    "description": spec["description"],
                },
            )
            if created:
                self.stdout.write(f"Created category {spec['slug']}.")
            categories[spec["slug"]] = category
        return categories

    def _ensure_authors(self):
        specs = {u["username"]: u for u in USERS}
        authors = {}
        # Atomic like the forum seed's user pass: an adoption refusal must
        # roll back any demo users this call created.
        with transaction.atomic():
            for username, (first, last) in AUTHOR_NAMES.items():
                user = ensure_demo_user(specs[username], self.stdout)
                # Fill-if-blank ONLY (spec §5): the blog author line reads
                # User.get_full_name(); a manually customised name wins.
                if not user.first_name and not user.last_name:
                    user.first_name = first
                    user.last_name = last
                    user.save(update_fields=["first_name", "last_name"])
                authors[username] = user
        return authors

    # -- posts ---------------------------------------------------------------

    def _seed_post(self, spec, index, categories, authors):
        """Create one post. Post-granular idempotency: if the slug exists
        anywhere, skip ENTIRELY (manual edits always win). Returns True when
        created."""
        if BlogPostPage.objects.filter(slug=spec["slug"]).exists():
            return False

        published_at = timezone.now() - timedelta(days=spec["age_days"])
        with transaction.atomic():
            post = index.add_child(
                instance=BlogPostPage(
                    title=spec["title"],
                    slug=spec["slug"],
                    author=authors[spec["author"]],
                    publish_date=published_at.date(),
                    introduction=spec["introduction"],
                    content_blocks=spec["blocks"],
                    featured_image=self._get_image(spec["cover"]),
                    view_count=spec["view_count"],
                )
            )
            post.categories.add(categories[spec["category"]])
            # reading_time auto-computes in BlogPostPage.save() when unset —
            # the stored value derives from the real body (spec §9).
            post.save_revision().publish()
            # Back-date LAST (publish-fields lesson): first/last_published_at
            # live on the wagtailcore.Page PARENT table — MTI means a
            # BlogPostPage-queryset .update() cannot touch them (spec §12).
            Page.objects.filter(pk=post.pk).update(
                first_published_at=published_at,
                last_published_at=published_at,
            )
        self.stdout.write(f"Created blog post {spec['slug']}.")
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
                collection=self._get_collection(),
            )

    def _get_collection(self):
        # Management-command context: single caller, no concurrent first-use
        # race — the forum's select_for_update dance (wagtail_forum/
        # collections.py) is unnecessary here.
        root = Collection.get_first_root_node()
        existing = root.get_children().filter(name=IMAGE_COLLECTION_NAME).first()
        if existing is not None:
            return existing
        return root.add_child(name=IMAGE_COLLECTION_NAME)
```

- [ ] **Step 4: Run the suite to verify it passes**

Run: `pytest apps/blog/tests/test_seed_demo_blog.py -v --create-db`
Expected: all 9 tests PASS.

- [ ] **Step 5: Commit (verify with `git log -1`)**

```bash
git add backend/apps/blog/management/commands/seed_demo_blog.py backend/apps/blog/tests/test_seed_demo_blog.py
git commit -m "feat(blog): seed_demo_blog — guarded, idempotent Canopy demo blog seed

Two-layer guard shared with the forum seed (census helper + per-account
non-adoption), fill-if-blank author names, routable-tree index, per-post
atomicity, Page-table back-dating (MTI), covers from committed seed_assets.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Single-entry integration + retire the old command

**Files:**

- Modify: `backend/apps/forum_host/management/commands/seed_demo_content.py` (end of `handle()`)
- Delete: `backend/apps/blog/management/commands/create_demo_blog_posts.py`
- Test: `backend/apps/blog/tests/test_seed_demo_blog.py` (append one test)

**Interfaces:**

- Consumes: Task 4's `seed_demo_blog` command.
- Produces: the prod runbook stays ONE `seed_demo_content --confirm` run (forum half skips idempotently, blog half seeds).

- [ ] **Step 1: Write the failing integration test** (append to `test_seed_demo_blog.py`):

```python
@override_settings(DEBUG=False)
@pytest.mark.django_db
def test_seed_demo_content_seeds_the_blog_and_forwards_confirm():
    # The single-entry prod runbook (spec §2.1): one seed_demo_content
    # --confirm run must ALSO seed the blog — which requires the parent to
    # forward confirm=..., or the inner layer-1 guard aborts in production.
    call_command("seed_demo_content", confirm=True)
    assert BlogPostPage.objects.count() == len(POSTS)
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest apps/blog/tests/test_seed_demo_blog.py::test_seed_demo_content_seeds_the_blog_and_forwards_confirm -v --create-db`
Expected: FAIL — `assert 0 == 6` (forum command never calls the blog seed yet).

- [ ] **Step 3: Wire the call** — in `seed_demo_content.py`'s `handle()`, after the existing `update_index` block at the end:

```python
        if created:
            # Content changed under the search index's feet (timestamps moved
            # post-publish); refresh so search reflects the seeded world.
            call_command("update_index", verbosity=0)
        # Blog half of the demo world (spec 2026-08-16 §5): one prod entry
        # point. --confirm MUST forward — in production the blog command's
        # own layer-1 guard would otherwise abort this single-entry runbook.
        call_command("seed_demo_blog", confirm=options["confirm"])
```

(The first three lines already exist — only the comment + `seed_demo_blog` call are new.)

- [ ] **Step 4: Delete the obsolete command** (off-brand copy; creates a real-shaped `demo@plantcommunity.com` author that would permanently trip the guard):

```bash
git rm backend/apps/blog/management/commands/create_demo_blog_posts.py
grep -rn "create_demo_blog_posts" backend --include="*.py" --include="*.md"
```

Expected grep: no remaining references (if docs mention it, update them in this commit).

- [ ] **Step 5: Amend the forum suite's image assertions** — `seed_demo_content` now ALSO creates the 6 blog covers, so `apps/forum_host/tests/test_seed_demo_content.py::test_world_shape`'s `title__startswith("Seed: ")` filter over-matches. Narrow it to the forum's own assets (all forum assets are `post-*.webp`; blog covers are `cover-*.webp`):

In `test_world_shape`, replace:

```python
    seeded_images = get_image_model().objects.filter(title__startswith="Seed: ")
```

with:

```python
    # "Seed: post-*" = the forum's own assets; seed_demo_content now also
    # seeds the blog (PR 3), whose covers are "Seed: cover-*" and asserted
    # in apps/blog/tests/test_seed_demo_blog.py.
    seeded_images = get_image_model().objects.filter(title__startswith="Seed: post-")
```

(The `EXPECTED_IMAGE_ASSETS` set and both assertions after the filter are already `post-*`-only and stay unchanged.)

- [ ] **Step 6: Run both seed suites + the full backend suite**

Run: `pytest apps/blog/tests/test_seed_demo_blog.py apps/forum_host/tests/test_seed_demo_content.py -v --create-db`
Expected: all PASS (the forum suite proves the appended call didn't break forum-only expectations — its idempotency test now also exercises blog idempotency transitively).
Then: `pytest --create-db` (FULL suite — spec §10 requires it, not the blog subset).
Expected: entire suite green (~1490 tests, 8 skips).

- [ ] **Step 7: Commit (verify with `git log -1`; `git rm` from Step 4 is already staged)**

```bash
git add backend/apps/forum_host/management/commands/seed_demo_content.py backend/apps/forum_host/tests/test_seed_demo_content.py backend/apps/blog/tests/test_seed_demo_blog.py
git commit -m "feat(seed): seed_demo_content seeds the blog too; retire create_demo_blog_posts

One prod entry point (spec §2.1): the forum command forwards --confirm to
seed_demo_blog. The obsolete create_demo_blog_posts command is deleted —
off-brand copy, and its demo@plantcommunity.com author would trip the
real-user guard forever after.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Types + BlogCard rebuild

**Files:**

- Modify: `web/src/types/blog.ts` (`BlogPostAuthor`, `BlogPostImage`, `BlogPost`, new `RelatedPostSummary`)
- Rewrite: `web/src/components/BlogCard.tsx`
- Rewrite test: `web/src/components/BlogCard.test.tsx`

**Interfaces:**

- Consumes: probed API shapes (spec §12): `author = {id, username, first_name, last_name, display_name}`, `featured_image` = fill-800x400 rendition `{url, width, height, alt}`, `featured_image_thumb` = fill-300x200, `excerpt`, `reading_time`.
- Produces: `BlogCard` with props `{ post: BlogPost; compact?: boolean }` (compact = rail rows; the old `showImage` prop is retired). `RelatedPostSummary` type for Task 9. Task 7 renders `<BlogCard post={p} />` in the grid and `<BlogCard post={p} compact />` in the rail.

- [ ] **Step 1: Update the types** in `web/src/types/blog.ts` — replace the `BlogPostAuthor` and `BlogPostImage` interfaces and the `related_posts` line, add `RelatedPostSummary`:

```ts
export interface BlogPostAuthor {
  id?: number;
  username?: string;
  first_name?: string;
  last_name?: string;
  /** Server-computed: get_full_name() or username. Preferred display string. */
  display_name?: string;
}

/**
 * Wagtail ImageRenditionField payload (probed 2026-08-16):
 * featured_image = fill-800x400, featured_image_thumb = fill-300x200.
 */
export interface BlogPostImage {
  url: string;
  width?: number;
  height?: number;
  alt?: string;
}

/** Item shape of the detail response's server-computed related_posts. */
export interface RelatedPostSummary {
  id: number;
  title: string;
  slug: string;
  url?: string | null;
  published_date?: string | null;
  excerpt?: string;
  featured_image?: { url: string } | null;
}
```

In `BlogPost`, change/add these members (rest unchanged):

```ts
  featured_image?: BlogPostImage;
  featured_image_thumb?: BlogPostImage;
  reading_time?: number | null;
  related_posts?: RelatedPostSummary[];
```

Run: `cd web && npx tsc --noEmit` — expected: errors ONLY in `BlogCard.tsx` (it reads the removed `featured_image.thumbnail` / `title` members) — those confirm the rebuild target; no errors elsewhere.

- [ ] **Step 2: Write the failing BlogCard tests** — replace `web/src/components/BlogCard.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import BlogCard from './BlogCard';
import type { BlogPost } from '@/types';

const post: BlogPost = {
  id: 1,
  meta: {
    type: 'blog.BlogPostPage',
    detail_url: '',
    html_url: '',
    slug: 'killed-by-kindness',
    first_published_at: '2026-08-13T09:00:00Z',
  },
  slug: 'killed-by-kindness',
  title: 'Killed by kindness',
  excerpt: 'Most houseplants don’t die of neglect.',
  content_blocks: [],
  featured_image: { url: '/media/cover-800.webp', width: 800, height: 400, alt: '' },
  featured_image_thumb: { url: '/media/cover-300.webp', width: 300, height: 200, alt: '' },
  publish_date: '2026-08-13',
  author: { id: 2, username: 'june_park', display_name: 'June Park' },
  categories: [{ id: 1, name: 'Care', slug: 'care' }],
  reading_time: 3,
};

function renderCard(p: BlogPost, compact = false) {
  return render(
    <MemoryRouter>
      <BlogCard post={p} compact={compact} />
    </MemoryRouter>
  );
}

describe('BlogCard', () => {
  it('links to the post detail page', () => {
    renderCard(post);
    expect(screen.getByRole('link')).toHaveAttribute('href', '/blog/killed-by-kindness');
  });

  it('renders title, category label, excerpt, and the meta line', () => {
    renderCard(post);
    expect(screen.getByText('Killed by kindness')).toBeInTheDocument();
    expect(screen.getByText('Care')).toBeInTheDocument();
    expect(screen.getByText(/die of neglect/)).toBeInTheDocument();
    // Meta line: "N min read · Author" (artifact card format). Key-PRESENCE
    // discipline: assert the whole joined string so a silently-missing
    // reading_time or author fails loudly.
    expect(screen.getByText('3 min read · June Park')).toBeInTheDocument();
  });

  it('uses the 800x400 rendition for the grid cover', () => {
    renderCard(post);
    expect(screen.getByRole('img')).toHaveAttribute('src', '/media/cover-800.webp');
  });

  it('omits the meta segments that are absent instead of printing blanks', () => {
    renderCard({ ...post, reading_time: null, author: undefined });
    expect(screen.queryByText(/min read/)).not.toBeInTheDocument();
    expect(screen.queryByText(/·/)).not.toBeInTheDocument();
  });

  it('renders without a cover when no image exists', () => {
    renderCard({ ...post, featured_image: undefined, featured_image_thumb: undefined });
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
    expect(screen.getByText('Killed by kindness')).toBeInTheDocument();
  });

  it('compact variant renders the 300x200 thumb and meta, no excerpt', () => {
    renderCard(post, true);
    expect(screen.getByRole('img')).toHaveAttribute('src', '/media/cover-300.webp');
    expect(screen.getByText('3 min read · June Park')).toBeInTheDocument();
    expect(screen.queryByText(/die of neglect/)).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run to verify failure**

Run: `cd web && npx vitest run src/components/BlogCard.test.tsx`
Expected: FAIL (old card renders `first_name last_name`, thumbnail URL, no meta line).

- [ ] **Step 4: Rewrite `web/src/components/BlogCard.tsx`**

```tsx
import { memo } from 'react';
import { Link } from 'react-router-dom';
import Card from './ui/Card';
import { stripHtml } from '../utils/sanitize';
import type { BlogPost } from '@/types';

/**
 * BlogCard — Canopy blog post card (PR 3).
 *
 * Grid variant: cover (fill-800x400 rendition), category label, title,
 * excerpt, and the artifact's meta line ("N min read · Author").
 * Compact variant: thumb + title + meta, for rail modules.
 *
 * Card `interactive` + a DIRECT child <Link> is load-bearing: the row focus
 * outline rides `.canopy-interactive:has(> a:focus-visible)` (PR 2).
 */

interface BlogCardProps {
  post: BlogPost;
  compact?: boolean;
}

function metaLine(post: BlogPost): string {
  const parts: string[] = [];
  if (post.reading_time) parts.push(`${post.reading_time} min read`);
  if (post.author?.display_name) parts.push(post.author.display_name);
  return parts.join(' · ');
}

function excerptText(post: BlogPost): string {
  if (post.excerpt) return post.excerpt;
  if (post.introduction) return stripHtml(post.introduction);
  return '';
}

function BlogCard({ post, compact = false }: BlogCardProps) {
  const meta = metaLine(post);

  if (compact) {
    const thumb = post.featured_image_thumb?.url ?? post.featured_image?.url;
    return (
      <Link
        to={`/blog/${post.slug}`}
        className="group flex items-center gap-3 rounded-sm p-1.5 transition-colors hover:bg-surface-2/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-secondary"
      >
        {thumb && (
          <img
            src={thumb}
            alt=""
            width={48}
            height={48}
            className="h-12 w-12 shrink-0 rounded-sm object-cover"
          />
        )}
        <span className="flex min-w-0 flex-col gap-0.5">
          <span className="truncate text-[13px] font-medium text-ink transition-colors group-hover:text-primary">
            {post.title}
          </span>
          {meta && <span className="font-mono text-[11px] text-ink-3">{meta}</span>}
        </span>
      </Link>
    );
  }

  const cover = post.featured_image?.url ?? post.featured_image_thumb?.url;
  const category = post.categories?.[0];
  const excerpt = excerptText(post);

  return (
    <Card interactive className="overflow-hidden">
      <Link
        to={`/blog/${post.slug}`}
        className="group flex h-full flex-col focus:outline-none"
      >
        {cover && (
          <img
            src={cover}
            alt={post.featured_image?.alt || ''}
            width={800}
            height={400}
            className="aspect-[2/1] w-full object-cover"
          />
        )}
        <span className="flex flex-1 flex-col gap-2.5 p-5">
          {category && (
            <span className="self-start rounded-pill border border-line bg-surface-2/60 px-2.5 py-0.5 font-mono text-[11px] uppercase tracking-[0.14em] text-ink-2">
              {category.name}
            </span>
          )}
          <span className="text-[17px] font-semibold leading-snug text-ink transition-colors group-hover:text-primary">
            {post.title}
          </span>
          {excerpt && (
            <span className="line-clamp-2 text-[13.5px] leading-relaxed text-ink-2">
              {excerpt}
            </span>
          )}
          {meta && (
            <span className="mt-auto pt-1 font-mono text-[11.5px] text-ink-3">{meta}</span>
          )}
        </span>
      </Link>
    </Card>
  );
}

export default memo(BlogCard);
```

- [ ] **Step 5: Run tests + typecheck**

Run: `npx vitest run src/components/BlogCard.test.tsx && npx tsc --noEmit`
Expected: 6 PASS; **tsc now fails only in `BlogListPage.tsx`** (it passes the retired `showImage` prop) — that's Task 7's target and the reason Tasks 6+7 commit checkpoints are ordered back-to-back; if anything else fails, fix it here.

- [ ] **Step 6: Commit (verify with `git log -1`)** — commit is safe with the known BlogListPage tsc failure only if your gate tolerates it; otherwise fold this commit into Task 7's. Default: commit here, note the pending Task-7 fix in the message.

```bash
git add web/src/types/blog.ts web/src/components/BlogCard.tsx web/src/components/BlogCard.test.tsx
git commit -m "feat(web/blog): Canopy BlogCard + probed API types

Card interactive + direct Link child (focus-outline contract), grid and
compact variants, artifact meta line. Types match the 2026-08-16 probe
(display_name author, rendition images, RelatedPostSummary). BlogListPage
still passes the retired showImage prop — rebuilt next commit.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: BlogListPage rebuild

**Files:**

- Rewrite: `web/src/pages/BlogListPage.tsx`
- Create test: `web/src/pages/BlogListPage.test.tsx` (none exists today)

**Interfaces:**

- Consumes: Task 6's `BlogCard`; primitives `HeroCard { eyebrow?, title, description?, actions?, art? }`, `Chip { active?, ...button }`, `Pagination { page, onPageChange, hasPrevious, hasNext, totalPages? }`, `ButtonLink { to, variant?, size? }`, `Button { variant? }`, `RailSlot` (portal), `RailModule { icon, title }`; services `fetchBlogPosts`, `fetchPopularPosts`, `fetchCategories`.
- Produces: the `/blog` route page. Locked hero copy (Global Constraints). URL params: `?page=`, `?search=`, `?category=` (existing plumbing, order param retired).

- [ ] **Step 1: Write the failing tests** — `web/src/pages/BlogListPage.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import BlogListPage from './BlogListPage';
import { fetchBlogPosts, fetchPopularPosts, fetchCategories } from '../services/blogService';
import type { BlogPost } from '@/types';

vi.mock('../services/blogService', () => ({
  fetchBlogPosts: vi.fn(),
  fetchPopularPosts: vi.fn(),
  fetchCategories: vi.fn(),
}));

const mockFetchPosts = vi.mocked(fetchBlogPosts);
const mockFetchPopular = vi.mocked(fetchPopularPosts);
const mockFetchCategories = vi.mocked(fetchCategories);

function post(slug: string, title: string): BlogPost {
  return {
    id: Math.random(),
    meta: { type: 'blog.BlogPostPage', detail_url: '', html_url: '', slug, first_published_at: '' },
    slug,
    title,
    content_blocks: [],
    author: { display_name: 'June Park' },
    reading_time: 3,
    categories: [{ id: 1, name: 'Care', slug: 'care' }],
  };
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/blog']}>
      <BlogListPage />
    </MemoryRouter>
  );
}

beforeEach(() => {
  // Block bodies, not implicit returns — Vitest 4 registers an implicit
  // return as teardown (docs/rules/testing.md).
  mockFetchPosts.mockResolvedValue({
    items: [post('killed-by-kindness', 'Killed by kindness')],
    meta: { total_count: 1 },
  });
  mockFetchPopular.mockResolvedValue([post('fiddle-leaf-adjusting', 'Your fiddle leaf isn’t dying, it’s adjusting')]);
  mockFetchCategories.mockResolvedValue([
    { id: 1, name: 'Care', slug: 'care' },
    { id: 2, name: 'Design', slug: 'design' },
  ]);
});

describe('BlogListPage', () => {
  it('renders the locked Canopy hero copy', async () => {
    renderPage();
    expect(await screen.findByText('Do less to your plants.')).toBeInTheDocument();
    expect(screen.getByText('The blog · new posts weekly')).toBeInTheDocument();
    expect(screen.getByText(/killed by kindness\./)).toBeInTheDocument();
    // "Read the latest" is a Button until the limit-1 latest fetch resolves,
    // then a link — assert by text here; the link form is the next test.
    expect(screen.getByText('Read the latest')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'All topics →' })).toBeInTheDocument();
  });

  it('deep-links "Read the latest" to the newest post', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByRole('link', { name: 'Read the latest' })).toHaveAttribute(
        'href',
        '/blog/killed-by-kindness'
      );
    });
  });

  it('renders category chips and filters on click', async () => {
    renderPage();
    const chip = await screen.findByRole('button', { name: 'Care' });
    await userEvent.click(chip);
    await waitFor(() => {
      expect(mockFetchPosts).toHaveBeenCalledWith(
        expect.objectContaining({ category: 'care', page: 1 })
      );
    });
  });

  it('submits the search field into the query', async () => {
    renderPage();
    const input = await screen.findByRole('searchbox', { name: /search articles/i });
    await userEvent.type(input, 'mites{Enter}');
    await waitFor(() => {
      expect(mockFetchPosts).toHaveBeenCalledWith(
        expect.objectContaining({ search: 'mites', page: 1 })
      );
    });
  });

  it('renders the grid cards', async () => {
    renderPage();
    expect(await screen.findByText('Killed by kindness')).toBeInTheDocument();
  });

  it('shows an empty state with a clear-filters action when nothing matches', async () => {
    mockFetchPosts.mockResolvedValue({ items: [], meta: { total_count: 0 } });
    renderPage();
    expect(await screen.findByText(/No articles found/)).toBeInTheDocument();
  });
});
```

Note: `RailSlot` portals into `#app-rail` and renders `null` when the target
(or the xl media query) is absent — as in these tests. The rail's content is
therefore NOT asserted here; the compact card it hosts is covered by Task 6's
tests.

- [ ] **Step 2: Run to verify failure**

Run: `npx vitest run src/pages/BlogListPage.test.tsx`
Expected: FAIL (old page has no hero, different copy/roles).

- [ ] **Step 3: Rewrite `web/src/pages/BlogListPage.tsx`**

```tsx
import { useEffect, useRef, useState, useCallback, FormEvent } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Flame, Search } from 'lucide-react';
import HeroCard from '../components/ui/HeroCard';
import Chip from '../components/ui/Chip';
import Button from '../components/ui/Button';
import ButtonLink from '../components/ui/ButtonLink';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import { Pagination } from '../components/ui/Pagination';
import RailSlot from '../components/layout/RailSlot';
import RailModule from '../components/ui/RailModule';
import BlogCard from '../components/BlogCard';
import PageMeta from '../components/PageMeta';
import { fetchBlogPosts, fetchPopularPosts, fetchCategories } from '../services/blogService';
import { logger } from '../utils/logger';
import type { BlogPost, BlogCategory } from '@/types';

const POSTS_PER_PAGE = 8; // 2-col grid → even pages

/**
 * BlogListPage — Canopy blog index (PR 3, spec §7).
 *
 * Locked hero copy (artifact parity) → chips + search toolbar → 2-col card
 * grid → Pagination. Rail: popular posts. Sort dropdown and category
 * sidebar retired (spec §2.2); search kept — no regressions.
 */
export default function BlogListPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [posts, setPosts] = useState<BlogPost[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [categories, setCategories] = useState<BlogCategory[]>([]);
  const [popular, setPopular] = useState<BlogPost[]>([]);
  const [latestSlug, setLatestSlug] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const gridRef = useRef<HTMLDivElement>(null);

  const page = parseInt(searchParams.get('page') || '1');
  const search = searchParams.get('search') || '';
  const category = searchParams.get('category') || '';

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        setLoading(true);
        setError(null);
        const { items, meta } = await fetchBlogPosts({
          page,
          limit: POSTS_PER_PAGE,
          search,
          category,
        });
        if (cancelled) return;
        setPosts(items);
        setTotalCount(meta.total_count);
      } catch (err) {
        if (cancelled) return;
        logger.error('Error loading blog posts', {
          component: 'BlogListPage',
          error: err,
          context: { page, search, category },
        });
        setError(err instanceof Error ? err.message : 'Failed to load blog posts');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [page, search, category]);

  useEffect(() => {
    let cancelled = false;
    const loadOnce = async () => {
      try {
        const [latest, popularPosts, cats] = await Promise.all([
          fetchBlogPosts({ page: 1, limit: 1 }),
          fetchPopularPosts({ limit: 5, days: 30 }),
          fetchCategories(),
        ]);
        if (cancelled) return;
        setLatestSlug(latest.items[0]?.slug ?? null);
        setPopular(popularPosts);
        setCategories(cats);
      } catch (err) {
        if (cancelled) return;
        // Rail/hero garnish only — the grid is the page; log and continue.
        logger.error('Error loading blog sidebar data', {
          component: 'BlogListPage',
          error: err,
        });
      }
    };
    loadOnce();
    return () => {
      cancelled = true;
    };
  }, []);

  const scrollToGrid = useCallback(() => {
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    gridRef.current?.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth' });
  }, []);

  const setParam = useCallback(
    (mutate: (params: URLSearchParams) => void) => {
      const next = new URLSearchParams(searchParams);
      mutate(next);
      next.delete('page'); // any filter change resets to page 1
      setSearchParams(next);
    },
    [searchParams, setSearchParams]
  );

  const handleCategory = useCallback(
    (slug: string) => {
      setParam((p) => {
        if (slug) p.set('category', slug);
        else p.delete('category');
      });
    },
    [setParam]
  );

  const handleSearch = useCallback(
    (e: FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      const value = (new FormData(e.currentTarget).get('search') as string).trim();
      setParam((p) => {
        if (value) p.set('search', value);
        else p.delete('search');
      });
    },
    [setParam]
  );

  const clearFilters = useCallback(() => {
    setSearchParams({});
    scrollToGrid();
  }, [setSearchParams, scrollToGrid]);

  const handlePageChange = useCallback(
    (newPage: number) => {
      const next = new URLSearchParams(searchParams);
      next.set('page', newPage.toString());
      setSearchParams(next);
      window.scrollTo({
        top: 0,
        behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches
          ? 'auto'
          : 'smooth',
      });
    },
    [searchParams, setSearchParams]
  );

  const totalPages = Math.max(1, Math.ceil(totalCount / POSTS_PER_PAGE));
  const hasFilters = Boolean(search || category);

  return (
    <div className="flex flex-col gap-8">
      <PageMeta
        title="Blog — Houseplant MD"
        description="Guides, experiments, and honest failures from the community garden."
      />

      {/* HeroCard's title renders as an h2 by design — the page still needs
          its own h1 for the document outline. */}
      <h1 className="sr-only">Blog</h1>
      <HeroCard
        eyebrow="The blog · new posts weekly"
        title="Do less to your plants."
        description="Guides, experiments, and honest failures from the community garden. This month: why most houseplants are killed by kindness."
        actions={
          <>
            {latestSlug ? (
              <ButtonLink to={`/blog/${latestSlug}`}>Read the latest</ButtonLink>
            ) : (
              <Button onClick={scrollToGrid}>Read the latest</Button>
            )}
            <Button variant="ghost" onClick={clearFilters}>
              All topics →
            </Button>
          </>
        }
        art={
          <img
            src="/illustrations/hero-blog.webp"
            alt=""
            width={280}
            height={280}
            className="canopy-float w-[200px] md:w-[260px]"
          />
        }
      />

      {/* Toolbar: category chips + search (spec §2.2 — search kept). */}
      <div
        ref={gridRef}
        className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between"
      >
        <div className="flex flex-wrap gap-2">
          <Chip active={!category} onClick={() => handleCategory('')}>
            All
          </Chip>
          {categories.map((cat) => (
            <Chip
              key={cat.id}
              active={category === cat.slug}
              onClick={() => handleCategory(cat.slug)}
            >
              {cat.name}
            </Chip>
          ))}
        </div>
        <form onSubmit={handleSearch} className="relative md:w-64" role="search">
          <Search
            aria-hidden="true"
            className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-3"
          />
          <input
            key={search}
            type="search"
            name="search"
            defaultValue={search}
            aria-label="Search articles"
            placeholder="Search articles…"
            className="w-full rounded-pill border border-line bg-surface-2/60 py-2 pl-10 pr-4 text-[13px] text-ink placeholder:text-ink-3 transition-colors hover:bg-surface-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-secondary"
          />
        </form>
      </div>

      {/* Active-search count + clear (spec §7). */}
      {hasFilters && !loading && !error && (
        <div className="flex items-center gap-3 font-mono text-[12px] text-ink-3">
          <span>
            {totalCount} {totalCount === 1 ? 'article' : 'articles'}
            {search && <> for “{search}”</>}
          </span>
          <button
            type="button"
            onClick={clearFilters}
            className="text-ink-2 underline underline-offset-2 transition-colors hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-secondary"
          >
            Clear filters
          </button>
        </div>
      )}

      {loading && (
        <div className="flex justify-center py-16">
          <LoadingSpinner />
        </div>
      )}

      {error && (
        <div className="rounded-md border border-error/30 bg-error/10 p-6 text-center text-[13.5px] text-error">
          Couldn’t load the blog — {error}
        </div>
      )}

      {!loading && !error && posts.length === 0 && (
        <div className="canopy-card rounded-md p-10 text-center">
          <p className="text-[15px] font-semibold text-ink">No articles found</p>
          <p className="mt-1 text-[13.5px] text-ink-2">
            Try a different search, or browse every topic.
          </p>
          {hasFilters && (
            <Button variant="outline" className="mt-4" onClick={clearFilters}>
              Clear filters
            </Button>
          )}
        </div>
      )}

      {!loading && !error && posts.length > 0 && (
        <>
          <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
            {posts.map((p) => (
              <BlogCard key={p.id} post={p} />
            ))}
          </div>
          {totalPages > 1 && (
            <Pagination
              page={page}
              onPageChange={handlePageChange}
              hasPrevious={page > 1}
              hasNext={page < totalPages}
              totalPages={totalPages}
            />
          )}
        </>
      )}

      {popular.length > 0 && (
        <RailSlot>
          <RailModule icon={<Flame />} title="Popular this month">
            <div className="flex flex-col gap-1.5">
              {popular.map((p) => (
                <BlogCard key={p.id} post={p} compact />
              ))}
            </div>
          </RailModule>
        </RailSlot>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run tests + typecheck + full web suite**

Run: `npx vitest run src/pages/BlogListPage.test.tsx && npx tsc --noEmit && npx vitest run`
Expected: new tests PASS; tsc clean (the Task-6 `showImage` failure is gone); full suite green.

- [ ] **Step 5: Commit (verify with `git log -1`)**

```bash
git add web/src/pages/BlogListPage.tsx web/src/pages/BlogListPage.test.tsx
git commit -m "feat(web/blog): Canopy blog index — locked hero, chips+search toolbar, card grid, popular rail

Sort dropdown and category sidebar retired (spec §2.2); search kept on the
toolbar with existing ?search= plumbing. Read-the-latest deep-links via a
limit-1 latest fetch with scroll fallback.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: StreamFieldRenderer Canopy pass

**Files:**

- Modify: `web/src/components/StreamFieldRenderer.tsx`
- Modify test: `web/src/components/StreamFieldRenderer.test.tsx` (update any assertion pinned to a changed class; behavior assertions stay)

**Interfaces:**

- Consumes: nothing new.
- Produces: `StreamFieldRenderer` gains `variant?: 'inline' | 'article'` (default `'inline'` — the current wrapper, so **forum PostCard rendering is unchanged**). Task 9 passes `variant="article"`.

Scope discipline: the renderer is SHARED with forum posts (`mentionHighlight` path). The variant only changes the wrapper; block restyles below are token-consistent and apply to both consumers (forum bodies contain only paragraph/image/quote, so heading/code/spotlight/cta restyles are blog-only in practice).

- [ ] **Step 1: Add the variant prop + wrapper**

Replace the `StreamFieldRendererProps` interface and the main component's wrapper:

```tsx
interface StreamFieldRendererProps {
  blocks?: StreamFieldBlockType[] | null;
  /** Forum posts only: style @username mentions in paragraph blocks. */
  mentionHighlight?: boolean;
  /**
   * 'inline' (default): current compact rendering — forum posts, previews.
   * 'article': blog detail — reading measure + roomier block rhythm.
   */
  variant?: 'inline' | 'article';
}
```

```tsx
export default function StreamFieldRenderer({
  blocks,
  mentionHighlight,
  variant = 'inline',
}: StreamFieldRendererProps) {
  if (!blocks || blocks.length === 0) {
    return null;
  }

  const wrapper =
    variant === 'article'
      ? 'mx-auto w-full max-w-[70ch] text-[15px]'
      : 'prose prose-lg max-w-none';

  return (
    <div className={wrapper}>
      {blocks.map((block, index) => (
        <StreamFieldBlock
          key={block.id || index}
          block={block}
          mentionHighlight={mentionHighlight}
        />
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Token-restyle the block visuals** (same file; behavior, sanitization presets, and the quote-block security comment/branching are UNTOUCHED — class strings only):

- `heading`: `<h2 className="mt-9 mb-3.5 text-[24px] font-semibold leading-snug text-balance text-ink">`
- `paragraph` (className only): `"mb-4 leading-relaxed text-ink-2"`
- `image` (className only): `"my-5 mx-auto h-auto max-w-full rounded-md"`
- `quote` (blockquote className only): `"my-8 rounded-r-md border-l-2 border-secondary bg-surface-2/50 py-4 pl-6 pr-4 italic text-ink-2"` — inner text div classes stay (`text-xl mb-2` → `"mb-2 text-[17px]"`), attribution footer stays.
- `code` (pre className only): `"my-6 overflow-x-auto rounded-md border border-line bg-surface-2/60 p-4 font-mono text-[13px] text-ink"`
- `plant_spotlight` (outer div className only): `"my-8 rounded-md border border-line bg-surface-2/50 p-6"`; the 🌿 emoji in the h3 is removed (Canopy retired emoji chrome — PR #535/#537 precedent): `<h3 className="mb-3 text-[19px] font-semibold text-ink">{plantName}</h3>`; the care-level `<p>` keeps its svg but className becomes `"mt-4 flex items-center text-sm font-semibold text-ok"` (`text-leaf` → `text-ok`: leaf is a legacy re-pointed accent, ok is the semantic).
- `call_to_action` (outer div className only): `"canopy-card my-8 rounded-md p-8 text-center"`; h3 → `"mb-2 text-[19px] font-semibold text-ink"`; description className → `"mb-6 text-ink-2"`; all three `buttonClasses` variants → keep the structure but re-token: secondary `"inline-block rounded-pill border border-line bg-surface-2/60 px-6 py-2.5 text-[13.5px] font-semibold text-ink-2 transition-colors hover:bg-surface-2 hover:text-ink"`, outline the same as secondary, default/primary `"canopy-cta inline-block rounded-pill px-6 py-2.5 text-[13.5px] font-semibold"`.
- `default` (unsupported) block: classes stay (already token-based).

- [ ] **Step 3: Run the renderer + forum-consumer suites**

Run: `npx vitest run src/components/StreamFieldRenderer.test.tsx src/components/forum/PostCard.test.tsx`
Expected: behavior tests PASS; any assertion pinned to an old class string fails — update those assertions to the new classes (assert semantics like role/text where possible instead of classes). PostCard suite green proves the forum path is untouched.

- [ ] **Step 4: Full web suite + typecheck**

Run: `npx vitest run && npx tsc --noEmit`
Expected: green.

- [ ] **Step 5: Commit (verify with `git log -1`)**

```bash
git add web/src/components/StreamFieldRenderer.tsx web/src/components/StreamFieldRenderer.test.tsx
git commit -m "feat(web/blog): StreamFieldRenderer article variant + Canopy token restyle

variant='article' adds the reading measure for the blog detail page;
default 'inline' wrapper is byte-identical so forum PostCard rendering is
unchanged. Block visuals re-tokened (quote/code/spotlight/CTA); emoji
chrome removed per Canopy precedent.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 9: BlogDetailPage build

**Files:**

- Rewrite: `web/src/pages/BlogDetailPage.tsx` (currently a stub)
- Create test: `web/src/pages/BlogDetailPage.test.tsx`
- Modify: `web/src/services/blogService.ts` (delete the `fetchRelatedPosts` stub + its docstring)

**Interfaces:**

- Consumes: `fetchBlogPost(slug: string): Promise<BlogPost>`; Task 6's `RelatedPostSummary` (shape: `{id, title, slug, url, published_date, excerpt, featured_image}` — spec §8); Task 8's `variant="article"`; `NotFoundPage` (its stable headline: `This leaf is not in our records.`).
- Produces: the `/blog/:slug` route page.

- [ ] **Step 1: Write the failing tests** — `web/src/pages/BlogDetailPage.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import BlogDetailPage from './BlogDetailPage';
import { fetchBlogPost } from '../services/blogService';
import type { BlogPost } from '@/types';

vi.mock('../services/blogService', () => ({
  fetchBlogPost: vi.fn(),
}));

const mockFetchPost = vi.mocked(fetchBlogPost);

const post: BlogPost = {
  id: 1,
  meta: {
    type: 'blog.BlogPostPage',
    detail_url: '',
    html_url: '',
    slug: 'killed-by-kindness',
    first_published_at: '2026-08-13T09:00:00Z',
  },
  slug: 'killed-by-kindness',
  title: 'Killed by kindness',
  introduction: '<p>Most houseplants don’t die of neglect.</p>',
  content_blocks: [
    { type: 'heading', value: 'What overwatering actually is' },
    { type: 'paragraph', value: '<p>Roots respire.</p>' },
  ],
  featured_image: { url: '/media/cover-800.webp', width: 800, height: 400, alt: 'Overwatered pothos' },
  publish_date: '2026-08-13',
  author: { id: 2, username: 'june_park', display_name: 'June Park' },
  categories: [{ id: 1, name: 'Care', slug: 'care' }],
  reading_time: 3,
  related_posts: [
    {
      id: 2,
      title: 'Your fiddle leaf isn’t dying, it’s adjusting',
      slug: 'fiddle-leaf-adjusting',
      excerpt: 'Before you diagnose disease…',
      featured_image: { url: '/media/fiddle-300.webp' },
    },
  ],
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/blog/killed-by-kindness']}>
      <Routes>
        <Route path="/blog/:slug" element={<BlogDetailPage />} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  mockFetchPost.mockResolvedValue(post);
});

describe('BlogDetailPage', () => {
  it('renders headline, eyebrow, author line, and cover', async () => {
    renderPage();
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Killed by kindness' })
    ).toBeInTheDocument();
    expect(screen.getByText('Care')).toBeInTheDocument();
    expect(screen.getByText(/August 13, 2026/)).toBeInTheDocument();
    // Key-presence discipline: the full joined line, so a silently-null
    // reading_time or author fails loudly.
    expect(screen.getByText('By June Park · 3 min read')).toBeInTheDocument();
    expect(screen.getByAltText('Overwatered pothos')).toHaveAttribute(
      'src',
      '/media/cover-800.webp'
    );
  });

  it('renders the StreamField body', async () => {
    renderPage();
    expect(
      await screen.findByRole('heading', { name: 'What overwatering actually is' })
    ).toBeInTheDocument();
    expect(screen.getByText('Roots respire.')).toBeInTheDocument();
  });

  it('renders the related-posts strip with links', async () => {
    renderPage();
    expect(await screen.findByText('More from the blog')).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: /fiddle leaf/i })
    ).toHaveAttribute('href', '/blog/fiddle-leaf-adjusting');
  });

  it('hides the related strip when the server sends none', async () => {
    mockFetchPost.mockResolvedValue({ ...post, related_posts: [] });
    renderPage();
    await screen.findByRole('heading', { level: 1, name: 'Killed by kindness' });
    expect(screen.queryByText('More from the blog')).not.toBeInTheDocument();
  });

  it('renders the 404 page for an unknown slug', async () => {
    mockFetchPost.mockRejectedValue(new Error('Blog post not found'));
    renderPage();
    expect(
      await screen.findByText('This leaf is not in our records.')
    ).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `npx vitest run src/pages/BlogDetailPage.test.tsx`
Expected: FAIL (stub renders "implementation coming soon").

- [ ] **Step 3: Rewrite `web/src/pages/BlogDetailPage.tsx`**

```tsx
import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import Card from '../components/ui/Card';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import StreamFieldRenderer from '../components/StreamFieldRenderer';
import PageMeta from '../components/PageMeta';
import NotFoundPage from './NotFoundPage';
import { fetchBlogPost } from '../services/blogService';
import { stripHtml } from '../utils/sanitize';
import { logger } from '../utils/logger';
import type { BlogPost } from '@/types';

/**
 * BlogDetailPage — Canopy blog article (PR 3, spec §8).
 *
 * Eyebrow (category · date) → display headline → author line → cover →
 * StreamField body at reading measure → "More from the blog" strip from the
 * server-computed related_posts. Rail deliberately empty: the RailSlot is
 * unused, so the shell widens the reading column (spec §9).
 */

function formatDate(value?: string): string | null {
  if (!value) return null;
  // publish_date is a date-only string; bare new Date('YYYY-MM-DD') parses
  // as UTC midnight and renders the PREVIOUS day in negative-offset
  // timezones — anchor it to local midnight instead.
  const date = value.length === 10 ? new Date(`${value}T00:00:00`) : new Date(value);
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}

export default function BlogDetailPage() {
  const { slug } = useParams<{ slug: string }>();
  const [post, setPost] = useState<BlogPost | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!slug) return;
    let cancelled = false;
    const load = async () => {
      try {
        setLoading(true);
        setError(null);
        setNotFound(false);
        const data = await fetchBlogPost(slug);
        if (!cancelled) setPost(data);
      } catch (err) {
        if (cancelled) return;
        if (err instanceof Error && /not found/i.test(err.message)) {
          setNotFound(true);
        } else {
          logger.error('Error loading blog post', {
            component: 'BlogDetailPage',
            error: err,
            context: { slug },
          });
          setError(err instanceof Error ? err.message : 'Failed to load this article');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [slug]);

  if (notFound) return <NotFoundPage />;

  if (loading) {
    return (
      <div className="flex justify-center py-24">
        <LoadingSpinner />
      </div>
    );
  }

  if (error || !post) {
    return (
      <div className="mx-auto max-w-[70ch] rounded-md border border-error/30 bg-error/10 p-6 text-center text-[13.5px] text-error">
        Couldn’t load this article{error ? ` — ${error}` : ''}
      </div>
    );
  }

  const category = post.categories?.[0];
  const date = formatDate(post.publish_date);
  const authorLine = [
    post.author?.display_name && `By ${post.author.display_name}`,
    post.reading_time && `${post.reading_time} min read`,
  ]
    .filter(Boolean)
    .join(' · ');
  const related = post.related_posts ?? [];

  return (
    <article className="flex flex-col gap-8">
      <PageMeta
        title={`${post.title} — Houseplant MD`}
        description={post.introduction ? stripHtml(post.introduction) : undefined}
        og={{ title: post.title, type: 'article' }}
      />

      <header className="mx-auto flex w-full max-w-[70ch] flex-col items-start gap-3.5">
        <div className="flex flex-wrap items-center gap-3">
          {category && (
            <span className="rounded-pill border border-line bg-surface-2/60 px-2.5 py-0.5 font-mono text-[11px] uppercase tracking-[0.14em] text-ink-2">
              {category.name}
            </span>
          )}
          {date && <span className="font-mono text-[12px] text-ink-3">{date}</span>}
        </div>
        <h1 className="gt-h1 text-balance md:text-[38px]">{post.title}</h1>
        {authorLine && <p className="font-mono text-[12.5px] text-ink-3">{authorLine}</p>}
      </header>

      {post.featured_image?.url && (
        <Card className="mx-auto w-full max-w-[860px] overflow-hidden p-0">
          <img
            src={post.featured_image.url}
            alt={post.featured_image.alt || ''}
            width={post.featured_image.width || 800}
            height={post.featured_image.height || 400}
            className="aspect-[2/1] w-full object-cover"
          />
        </Card>
      )}

      {post.introduction && (
        <div className="mx-auto w-full max-w-[70ch]">
          <StreamFieldRenderer
            blocks={[{ type: 'paragraph', value: post.introduction }]}
            variant="article"
          />
        </div>
      )}

      <StreamFieldRenderer blocks={post.content_blocks} variant="article" />

      {related.length > 0 && (
        <aside className="mx-auto w-full max-w-[860px] border-t border-line pt-8">
          <h2 className="mb-4 text-[17px] font-semibold text-ink">More from the blog</h2>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            {related.slice(0, 3).map((rp) => (
              <Card key={rp.id} interactive className="overflow-hidden">
                <Link to={`/blog/${rp.slug}`} className="group flex h-full flex-col focus:outline-none">
                  {rp.featured_image?.url && (
                    <img
                      src={rp.featured_image.url}
                      alt=""
                      className="aspect-[2/1] w-full object-cover"
                    />
                  )}
                  <span className="flex flex-1 flex-col gap-1.5 p-4">
                    <span className="text-[14px] font-semibold leading-snug text-ink transition-colors group-hover:text-primary">
                      {rp.title}
                    </span>
                    {rp.excerpt && (
                      <span className="line-clamp-2 text-[12.5px] text-ink-2">{rp.excerpt}</span>
                    )}
                  </span>
                </Link>
              </Card>
            ))}
          </div>
        </aside>
      )}
    </article>
  );
}
```

Note the introduction is rendered through the article-variant renderer as a lead paragraph (sanitized HTML — it is RichTextField HTML, never `dangerouslySetInnerHTML` raw).

- [ ] **Step 4: Delete the `fetchRelatedPosts` stub** from `web/src/services/blogService.ts` (the whole function + its docstring — spec §8: dead, misleading residue), then:

Run: `grep -rn "fetchRelatedPosts" web/src`
Expected: no hits.

- [ ] **Step 5: Run tests + full suite + typecheck + build**

Run: `npx vitest run src/pages/BlogDetailPage.test.tsx && npx vitest run && npx tsc --noEmit && npm run build`
Expected: all green.

- [ ] **Step 6: Commit (verify with `git log -1`)**

```bash
git add web/src/pages/BlogDetailPage.tsx web/src/pages/BlogDetailPage.test.tsx web/src/services/blogService.ts
git commit -m "feat(web/blog): Canopy blog article page

Category/date eyebrow, display headline, honest author line, cover Card,
article-variant StreamField body, related strip from the server-computed
related_posts. Empty rail widens the reading column. fetchRelatedPosts
stub (always-empty, stale docstring) deleted.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 10: Gates + seeded visual pass

**Files:** none created — verification only.

- [ ] **Step 1: Backend full suite**

Run: `cd backend && source venv/bin/activate && pytest --create-db`
Expected: entire suite green (~1495 tests incl. the 10 new seed tests, 8 skips). Never run two pytest invocations concurrently.

- [ ] **Step 2: Web gates**

Run: `cd web && npx vitest run && npx tsc --noEmit && npm run build`
Expected: all green (~900 tests).

- [ ] **Step 3: Seeded visual pass (controller-supervised)** — seed a scratch world and screenshot for the user's artifact judgment (spec §10 acceptance):

```bash
cd backend && source venv/bin/activate
python manage.py migrate  # dev DB
python manage.py seed_demo_content  # DEBUG=True locally — no --confirm needed
python manage.py runserver  # + web: npm run dev
```

Screenshot `/blog` (hero + grid + rail, both themes) and one article (`/blog/killed-by-kindness` — body, quote block, related strip), plus `/forum` to confirm the FromTheBlogModule now lists posts. **Caveat (codified):** if a scratch server is used instead of the dev DB, it MUST get its own `REDIS_URL` db index or it serves dev's cached rendition paths.
Expected: user judges against the Canopy artifact's blog screen; the meta lines show the honest 2–4 min reading times (spec §9 deviation, pre-approved).

- [ ] **Step 4: Buffer** — address whatever the visual pass or final review surfaces before the PR opens.

## Post-merge (not in this plan's tasks)

User-supervised Railway seed session, runbook unchanged:
`railway ssh --service plant_id_community "python manage.py seed_demo_content --confirm"` — forum half skips idempotently, blog half seeds. Verify live `/blog` + a rendition URL returns `200 image/webp` (media volume + serve() route already in place, PR #539).
