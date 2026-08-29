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
- **Firebase-emulator integration tests** (`integration_test/`): adopt the
  native `[DEFAULT]` app — `Firebase.initializeApp()` with NO options (passing
  options throws `[core/duplicate-app]`) and run the emulator with the same
  `--project` as the native `projectId`. Gate on
  `String.fromEnvironment('FIRESTORE_EMULATOR_HOST')` — `Platform.environment`
  is invisible on-device; an unset define is a clean skip. Mount the service
  provider BEFORE `useFirestoreEmulator()` (its `build()` assigns
  `_firestore.settings`, which would clobber the emulator host and send traffic
  to prod). Give `testWidgets` an overall `timeout:` — per-step `.timeout()`s
  don't cover init/sign-in, so an unreachable emulator hangs forever. Reference:
  `integration_test/firestore_emulator_roundtrip_test.dart` +
  `scripts/run_firestore_emulator_test.sh`; details in
  `docs/FIRESTORE_PATTERNS.md` Pattern 10.
- **Epoch-guard async lifecycle services** (anything a sign-out must cancel):
  capture `_epoch` at method entry, re-check after EVERY `await` — including
  `subscription.cancel()` — and bump it in `detach()`. A stale continuation
  otherwise re-registers state after logout (confirmed empirically, todo 253
  slice 6). And never suppress an interceptor side effect with a boolean flag
  around an awaited call — a timed-out request keeps running after the flag
  resets; put the opt-out ON THE REQUEST (`Options(extra: {...})`, checked in
  the interceptor). See `plant_community_mobile/docs/patterns/flutter-patterns.md`.
- **Widget/route tests: every provider the mounted screen reads must succeed.**
  Riverpod 3.x `FutureProvider`/`AsyncNotifier` auto-retry on error with a
  backoff `Timer`; a fetch that keeps throwing reschedules that timer forever and
  fails the test with `A Timer is still pending even after the widget tree was
  disposed`. Give the fake API a fixture for each method the screen calls — don't
  rely on an error state settling. (`docs/LEARNINGS.md` 2026-07-25.)
- **Idempotent mobile writes: one `Idempotency-Key` per action, rotated on
  content change.** Reuse the key across retries of the *same* payload so the
  server replays; regenerate it when the composed content changes, or an
  edit-then-retry wedges a permanent `422` ("used with a different payload").
  See `plant_community_mobile/docs/patterns/riverpod.md` → Idempotent Write Actions.
- **Moving fixed-width chrome (avatar, badge, icon) into a `Flexible`/`Expanded`
  cell that sits beside a `Spacer()` is a LAYOUT change, not a rendering
  change.** `Spacer()` claims half the row's slack regardless of what the
  flex child needs, so adding chrome to a shared widget can silently overflow
  every call site that already had one. Budget it in pixels and add a
  narrow-viewport (≤375pt) test — the default 800×600 test surface will not
  catch this. See `plant_community_mobile/docs/patterns/flutter-patterns.md`
  → Shared-Widget Consolidation.
- **When assigning `TextEditingController.value` directly** (a hand-rolled
  toolbar/transform, not IME input), always set `composing: TextRange.empty`
  on the result. `copyWith` carries a stale composing range through
  unchanged; a structural mutation that shortens the text can leave it
  pointing past the new text's end, tripping the controller's own assert
  during ordinary IME typing (Gboard keeps a composing region on the
  in-progress word).
- **`GlobalKey`/`Scrollable.ensureVisible` only reaches a child a lazy list
  has already built.** `ListView.builder`/`.separated` only build the
  viewport + cache extent (~250px default) — a `GlobalKey` assigned in
  `itemBuilder` for a not-yet-built item is never attached, so
  `key.currentContext` is `null` and any scroll-to-it attempt silently
  no-ops. This is not a deep-link mechanism for anything below the fold;
  reaching an off-screen item needs index/`ScrollController`-based
  scrolling instead.
- **After editing ANY `@riverpod`-annotated function's BODY** — not just
  when adding a new provider — re-run `build_runner` and `git diff
  --exit-code` the specific `.g.dart` file(s) whose source changed, even if
  a regen already ran earlier in the same session for an unrelated
  addition. The embedded content hash changes on any body edit; a stale
  hash is invisible to local `flutter test`/`flutter analyze` and to a
  read-only code review (which cannot run the mutating regen+diff check
  itself) — only a fresh-checkout CI regen catches it, after push. Treat
  `flutter pub run build_runner build --delete-conflicting-outputs && git
  diff --exit-code -- lib test` as its own explicit pre-push step, not
  something "run flutter test" already covers.
