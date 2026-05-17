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
