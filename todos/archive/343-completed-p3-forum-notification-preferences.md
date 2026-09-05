---
status: completed
priority: p3
issue_id: "343"
tags: [forum, notifications, backend, package, web]
dependencies: []
---

# Per-channel notification preferences (in-app / push / email per verb)

## Problem

Forum notifications fire on four verbs (REPLY, MENTION, SOLUTION,
MODERATION) across in-app, FCM push, and (partially) email — but the only
user control is a single `forum_notifications` flag. There is no preference
UI; `SettingsPage.tsx:1-13` even lists "Email notifications preferences" as
planned. Users can't opt out of push for replies while keeping mention
pushes, which is how notification fatigue starts.

## Findings

- `apps/forum_host/tasks.py:1-465` — push fires for `reply_added`/`mention`
  (tray) and `moderation_decided`/`answer_accepted` (data-only); the only
  gate besides `ForumProfile.fcm_token` is the global flag (2026-09-04
  backend catalog §6.2).
- `AppShell.tsx:284` + `NotificationBell.tsx` — in-app bell is mature; no
  settings route exists for channels.
- `web/src/pages/.../SettingsPage.tsx:1-13` — placeholder text already
  promises this feature.

## Recommended Action

1. **Package (`wagtail_forum`):** add a per-user preference model — either
   a JSONField on `ForumProfile` or (cleaner for auditability) a
   `ForumNotificationPreference` row keyed by `(profile, verb, channel)`.
   Defaults via `get_setting("NOTIFICATION_DEFAULTS", ...)` in `conf.py`;
   hosts can change defaults without a migration. Modest matrix: verbs
   {reply, mention, solution, moderation} x channels {in_app?, push, email}
   — decide whether in-app is toggleable at all (Discourse: in-app always
   on; recommend same).
2. Package gates its own fan-out (`wagtail_forum/notifications.py`) and
   exposes prefs read/write on `me/profile/` (fits existing
   `MeProfileView`, `api/views.py:1572-1761`).
3. **Host:** `apps/forum_host/notifications.py` push/email enqueue steps
   check the preference before `transaction.on_commit` enqueue.
4. **Web:** settings section replacing the placeholder; save via
   `PATCH /me/profile/`.
5. Relationship to todo 340 (digest): digest frequency is intentionally a
   separate profile field — don't conflate "which events notify me" with
   "which cadence batches them".

## Technical Details

- Existing gates: `wagtail_forum/api/notifications.py:1-142` (visibility
  filtering), `ForumProfile.fcm_token`, `is_firebase_available()`.
- Package/host split: package owns model + serializer + in-app gating; host
  owns push/email wiring only.
- Email send path being gated: `NotificationService.send_forum_reply_notification`
  via `apps/forum_host/tasks.py:279-362`.

## Acceptance Criteria

- [x] Preference model + API in `wagtail_forum` with package tests
      (defaults applied when no row exists; unknown verb/channel rejected)
- [x] Push/email fan-out respects preferences (host tests)
- [x] Web settings UI replaces the "planned" placeholder; changes persist
- [x] No change to default behavior for existing users beyond current state

## Work Log

### 2026-09-04 - Filed

- Surfaced by the 2026-09-04 forum competitive assessment (smaller-misses
  item: notification preference UI listed as planned in `SettingsPage`).

### 2026-09-05 - Started by completing-todos skill (run 2026-09-05-1142)

- Picked up by automated workflow.

### 2026-09-05 - Package + host implemented (run 2026-09-05-1142)

Decisions:

- **Storage: a sparse JSON overrides map on `ForumProfile`**
  (`notification_preferences`, migration 0035), not a per-(verb, channel)
  row model. Only cells the member changed are stored; the effective matrix
  is `NOTIFICATION_DEFAULTS` (conf, README row) deep-merged with the
  overrides at read time (`preferences.resolve_preferences`), so a host
  default change reaches every untouched cell without a migration. The row
  model's auditability was not worth 10 rows per member for a 5×2 matrix.
- **In-app is always on** (Discourse precedent) — not a preference; the
  package's `create_notifications` is unchanged. Channels are `push` and
  `email`; verbs `reply`, `mention`, `quote`, `solution`, `moderation`.
- **Defaults ARE the pre-343 behaviour** (push on everywhere; email on for
  replies only, which is the only email arm that exists), pinned by
  `test_defaults_are_the_pre_343_behaviour_and_fully_resolved_on_read` — a
  member with no overrides notices nothing (AC4).
- **API: resolved on read, partial on write.** `me/profile/` returns the
  full matrix; PATCH accepts a partial `{verb: {channel: bool}}` merged in
  `MeProfileSerializer.update`; unknown verb/channel or non-bool → 400
  (`NotificationPreferencesField`).
- **Gated inside the host tasks**, not before the enqueue: the push tasks
  already hold the profile row per recipient and the email batch does one
  bulk fetch, so the request thread pays nothing. `wants_channel` maps
  fan-out event names to verbs; an unmapped event is NOT gated (a future
  event can't be silently dropped by an old row). `forum_notifications`
  stays the master switch above the matrix.

Evidence:

```text
$ pytest test_notification_preferences.py (pkg + host) test_profiles.py test_tasks.py test_signals.py → 102 passed
$ manage.py makemigrations --check → No changes detected; manage.py check → no issues
$ mutation checks (single push gate, batch push gate, email gate, merge-on-PATCH) → each 1+ failed, guards restored via cp
```

Full backend suite with the preference gates (alone, `--create-db`):

```text
2220 passed, 8 skipped, 5 warnings in 406.75s (0:06:46)
```

### 2026-09-05 - Review round 1 (cross-cutting): 6 findings — all repaired

- **MEDIUM Wagtail snippet form exposed the raw JSON (and the FCM token) as
  admin inputs**, bypassing `validate_preferences` → `ForumProfileViewSet.
  exclude_form_fields = ["fcm_token", "notification_preferences"]`; admin
  test asserts neither input renders while `bio` still does (mutation:
  removing the exclusion fails it).
- **MEDIUM master switch unpinned** → test: `forum_notifications=False` with
  an explicit `push: True` override sends nothing through both push tasks.
- **LOW** both-recipients-opted-out batch → zero sends, no exception (test);
  PATCH `{}` is a 200 no-op and stored junk survives an unrelated PATCH
  harmlessly while reads stay resolved (test); the profile PATCH schema
  description now lists the preference 400s; `NOTIFICATION_VERBS` stays a
  literal (host tasks import the module before the registry is ready) but a
  drift test pins it to `NotificationVerb.values` + `moderation`.

```text
$ pytest test_notification_preferences.py (pkg+host) test_admin.py test_docs.py → 44 passed
```

### 2026-09-05 - Review round 1 (django-drf): 3 findings — all repaired, contract narrowed

- **MEDIUM inert cells:** the 5×2 matrix offered `email` for mention / quote /
  solution / moderation although only `reply_added` has an email arm, and
  `moderation_decided` has no in-app row at all (its push is a tray-silent
  client sync signal) — so "in-app always on" was false for it and turning
  its push off would have broken the client's silent refresh. **Decision:**
  the contract is now `NOTIFICATION_MATRIX` — exactly the cells with a
  delivery path: `reply` {push, email}, `mention` {push}, `quote` {push},
  `solution` {push}. Moderation is not a preference and stays ungated. The
  resolved matrix's keys tell clients which cells exist; a PATCH for an
  unwired cell is a 400 ("Email is not available for mention."). This
  deviates from the todo's suggested verb list on purpose (recorded).
- **MEDIUM literal-True fallback drifted from the package defaults** → a cell
  the host's `NOTIFICATION_DEFAULTS` omits falls back to the package's own
  `DEFAULTS["NOTIFICATION_DEFAULTS"]` cell (one source of truth); test pins
  a partial host override; mutation (literal True) fails it.
- **LOW merge against a junk-valued stored verb untested** → unit test
  `merge_preferences({"reply": "oops"}, …)` + the API-level junk PATCH.
- Also: `test_preference_verbs_track_notification_verbs` now pins equality
  with `NotificationVerb.values`; `_notification_content` docstring lists
  `answer_accepted` among the tray events (it has copy).

```text
$ pytest test_notification_preferences.py (pkg+host) test_admin.py test_docs.py test_profiles.py test_tasks.py test_notification_copy.py → 112 passed
$ mutation checks (package-default fallback → literal True; unwired-cell rejection removed) → each 1 failed, restored via cp
```

Full backend suite after the round-1 repairs (alone, `--create-db`):

```text
2227 passed, 8 skipped, 5 warnings in 286.34s (0:04:46)
```

Mutation re-check after the narrowed matrix: the unwired-cell rejection →
1 failed; the package-default fallback was EQUIVALENT to a literal True (every
package default is True today) until the test patched the package default
itself — now `row.get(channel, True)` fails it. Guards restored via cp.

### 2026-09-05 - Review round 1 (web): react-typescript 6 findings — 5 repaired, 1 documented; contract change applied

- **HIGH deploy skew** (web and backend ship on separate pipelines; an
  older backend omits the field and an unguarded index took the whole page
  down) → `notification_preferences` optional; a missing/non-object matrix
  is the load-error branch with Retry. Mutation (unguarded) → 1 failed.
- **Contract narrowed** per the backend round: only wired cells exist
  (`reply` push+email; `mention`/`quote`/`solution` push); the grid renders
  a checkbox only for keys the server sent, "—" + sr-only "Not available"
  otherwise; no moderation row. Mutation (unconditional email checkbox) → 3 failed.
- **MEDIUM tests coupled to sibling render order** → both sections are
  named exports tested standalone; digest tests restored to their pre-343
  form; one page-level smoke test.
- **LOW** optimistic flip now functional `setProfile`; refocus only when
  focus is on the body or inside the section (test: focus left alone after
  moving away mid-save) — same guard applied to the digest select; caption
  and `scope` assertions added; global disable kept and documented with the
  per-cell-pending upgrade path.

```text
$ npm run type-check → exit 0; eslint + prettier clean
$ npx vitest run → Test Files  96 passed (96)
      Tests  1236 passed (1236)
```

### 2026-09-05 - Acceptance criteria flipped (evidence)

- AC1 (model + API, defaults applied without a row, unknown verb/channel
  rejected): `test_defaults_are_the_pre_343_behaviour_and_fully_resolved_on_read`,
  `test_partial_patch_merges_and_stores_only_the_overrides`,
  `test_unknown_verb_channel_or_non_boolean_is_a_400` (7 cases).
- AC2 (push/email fan-out honours preferences, host tests):
  `apps/forum_host/tests/test_notification_preferences.py` — single and
  batch push per verb, email gate, master switch, both-opted-out, no-profile defaults.
- AC3 (web settings UI replaces the placeholder; changes persist):
  `SettingsPage.test.tsx` "notification preferences" — toggling a cell PATCHes
  exactly that cell and the response is rendered; the file header no longer
  says "planned".
- AC4 (no change to default behaviour): defaults equal the pre-343 matrix,
  pinned by test; the full backend suite (2227) passed with every existing
  fan-out test untouched.

### 2026-09-05 - Completed by completing-todos skill (run 2026-09-05-1142)

- Verification: all 4 acceptance criteria passed (backend 2227, web 1236 passed (1236)).
- Review: 3 reviewers, 15 findings (1 high web, 5 medium) — all actionable findings repaired in one round.
- Codified: `docs/rules/{api,celery,react}.md`, `backend/docs/patterns/domain/forum.md`,
  `web/docs/patterns/react-typescript.md`, django reviewer checklist.
