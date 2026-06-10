# Flutter (mobile) — binding rules

Compact checklist auto-injected before edits. Long-form:
`plant_community_mobile/docs/patterns/flutter-patterns.md`, `.../riverpod.md`.

- **Riverpod 3.x `Notifier`/`AsyncNotifier`** — not the legacy `StateNotifier`.
- **Cancel `StreamSubscription`s** in the provider's `ref.onDispose` /
  `dispose()` — uncancelled streams leak and fire after disposal.
- **Material 3** — use `Color.withValues(alpha: ...)`, not the deprecated
  `withOpacity()`.
- **Check dark mode** — read `Theme.of(context).brightness`; never hardcode
  light-only colors.
- **Secrets in `flutter_secure_storage`**, never `SharedPreferences`.
- `go_router` redirects guard on auth state; gate debug-only routes with
  `kDebugMode`.
- Null safety: no `!` force-unwrap on values that can genuinely be null.
- **Never retry `429` (rate limit) on non-idempotent requests** — retrying a
  rate-limited POST/PATCH can create duplicate records. Exclude 429 from the retry
  predicate and surface it to the UI as a rate-limit error.
- **Regenerate codegen after editing any `@riverpod`/`@freezed`/`part '*.g.dart'`
  source** — run `flutter pub run build_runner build --delete-conflicting-outputs`
  and commit the updated `.g.dart`. Riverpod embeds a source-content hash
  (`_$xHash`), so *any* edit (even deleting an unrelated method) makes it stale. CI's
  "Ensure generated code is committed" gate (`build_runner` + `git diff
  --exit-code`) blocks the merge; local `flutter analyze`/`test` will NOT catch it.
