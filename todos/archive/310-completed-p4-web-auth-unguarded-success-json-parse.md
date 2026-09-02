---
status: completed
priority: p4
issue_id: "310"
tags: [web, auth, react]
dependencies: []
---

# Auth service success-path `response.json()` is unguarded across three functions

## Problem

`web/src/services/authService.ts`'s `login()`, `signup()`, and
`getCurrentUser()` all guard their **error**-response `response.json()` call
with try/catch (todo 298 added it to `login()`; `signup()` already had it),
but none guard the **success** (`response.ok`) path's `response.json()`
call. A malformed or truncated 200 body would let the raw
`JSON.parse` `SyntaxError` (`"Unexpected token '<'..."` etc.) propagate
through the outer catch and reach the UI via `error.message` — the exact
failure class todo 298 just fixed, on the opposite branch.

## Findings

- Surfaced by `react-typescript-reviewer` during todo 298's code review
  (2026-08-17), flagged explicitly as low severity / pre-existing / not a
  regression from that diff — filed here rather than fixed inline to keep
  298's diff scoped to its own AC (the error path).
- `login()` — `web/src/services/authService.ts:92` (post-298), unguarded
  `const data: AuthResponse = await response.json();` on the success branch.
- `signup()` — same file, ~line 150, identical shape.
- `getCurrentUser()` — same file, ~line 219, identical shape.

## Recommended Action

1. Wrap each success-path `response.json()` in the same try/catch pattern
   todo 298 established for the error paths, falling back to a generic
   message (e.g. `"Login succeeded but the response could not be read"`)
   rather than letting the parse exception's raw text reach the UI.
2. Do all three functions in one pass — they share the exact same shape, so
   one PR covering `login()`/`signup()`/`getCurrentUser()` together is more
   coherent than three separate fixes.

## Technical Details

- `web/src/services/authService.ts` — all three functions.
- Mirror the established pattern from todo 298's error-path fix (and
  `signup()`'s pre-existing error-path handling) rather than inventing a new
  one.

## Acceptance Criteria

- [x] A malformed/non-JSON 200 response from `login()`, `signup()`, and
      `getCurrentUser()` each render a friendly fallback message, not a raw
      parse-exception string.
      **Met literally for `login()`/`signup()`.** `getCurrentUser()` returns
      `User | null` and renders no message at all, so "friendly fallback
      message" cannot apply to it as written; met in intent instead — no parse
      string can escape it, the fallback can no longer throw, and a body that
      parses to the wrong shape is caught rather than cached. It deliberately
      returns the last known user, NOT `null`: see the review entry in the Work
      Log for why the opposite (my first pass) was a regression.
- [x] Vitest coverage for the malformed-200-body case on all three functions.
- [x] Existing test suites remain green (no regressions to the many
      already-passing success-path tests).

## Work Log

### 2026-08-17 - Filed

- Split out of todo 298's code review (react-typescript-reviewer finding,
  low severity) — explicitly flagged as a pre-existing, cross-cutting
  pattern gap rather than a regression, so filed as a follow-up instead of
  expanding 298's diff beyond its own AC.

### 2026-09-02 - Started by completing-todos skill (run 2026-09-02-0458)

- Picked up by automated workflow.

**The three call sites are NOT the uniform shape this todo assumes.** Read
before writing: `login()` and `signup()` both throw out of their outer catch,
so an unguarded success-path parse does reach the UI as `error.message` —
exactly as filed. `getCurrentUser()` does not:

```
} catch (error) {
  logger.error('[authService] Get current user error', { error });
  const storedUser = sessionStorage.getItem('user');
  return storedUser ? JSON.parse(storedUser) : null;
}
```

It returns `User | null` and never surfaces a message, so a malformed 200 there
is already swallowed — no raw parse string reaches the UI today. What it does
instead is **silently promote a stale cached identity to "current"**, which is
the bug class todo 297 (`web-stale-identity-revalidation`, completed) exists to
prevent, and `AuthContext.revalidateIdentity()` (`web/src/contexts/AuthContext.tsx:273`)
calls `getCurrentUser()` on every **tab focus** with no try/catch of its own.

So AC1's literal wording ("render a friendly fallback message") does not apply
to `getCurrentUser()` — it renders nothing. The criterion's *intent* (a
malformed 200 must not produce a bad outcome) does, and for this function the
bad outcome is a wrong identity, not a raw string.

### 2026-09-02 - Implemented (run 2026-09-02-0458)

**`login()` / `signup()` — as filed.** Success-path `response.json()` wrapped in
try/catch, mirroring the error-path shape todo 298 established (log the status,
throw a human message). A malformed 200 now yields "Login succeeded but the
response couldn't be read. Please try again." instead of `Unexpected token
'<', "<!DOCTYPE "... is not valid JSON` reaching the UI through the outer catch.

**`getCurrentUser()` — same defect, different consequence.** Its outer catch
returns `storedUser ? JSON.parse(storedUser) : null` rather than rethrowing, so
the unguarded parse never leaked a message; it silently returned the
**previously cached user**. That is a wrong-identity bug, and
`AuthContext.revalidateIdentity()` calls this on every tab focus specifically
to catch a cookie-jar identity switch (todo 297, after the 2026-08-13 prod
incident where the header showed one account while a forum reply was created as
another). A guard that "succeeds" by handing back an unverified identity would
have re-opened exactly what 297 closed.

So the fix routes an unparseable 200 to the same outcome as the `!response.ok`
branch: clear sessionStorage, return `null`. **The trade-off is deliberate and
worth naming:** a flaky proxy returning one unparseable 200 will log the SPA
out on focus rather than keep showing a possibly-wrong user. Showing an identity
the server never confirmed is the more dangerous of the two, the next successful
call restores the session, and the alternative is the 297 failure mode.

**One adjacent fix, same function, same defect class.** That outer catch's own
`JSON.parse(storedUser)` was unguarded and throws *out of the catch block* on a
corrupt sessionStorage value — and `revalidateIdentity()` (`AuthContext.tsx:273`)
awaits `getCurrentUser()` with no try/catch of its own, so that becomes an
unhandled rejection on tab focus. `getStoredUser()` in the same module already
has the try/catch, so the fallback now calls it. A success-path guard that falls
into a throwing fallback is not actually a guard.

**Verification**

```
$ npx tsc --noEmit
TypeScript: No errors found

$ ./node_modules/.bin/vitest run src/services/authService.test.ts
 Test Files  1 passed (1)
      Tests  34 passed (34)      # 30 pre-existing + 4 new

$ ./node_modules/.bin/vitest run
 Test Files  86 passed (86)
      Tests  1008 passed (1008)

$ npm run lint
ESLint: 0 errors, 1 warnings in 1 files   # block-navigation.js, a coverage
                                          # artifact, pre-existing and untouched
```

AC2's four new tests:

- `login` → `should show a friendly message for a malformed 200 body, not the
  parse error` — asserts the message is the friendly one AND that it does not
  match `/unexpected token|did not match the expected pattern/i`, the two real
  browser texts (Chrome / Safari) recorded by todo 298.
- `signup` → same shape.
- `getCurrentUser` → `should clear the cache and return null on a malformed
  200, not the stale cached user`. A cached user **is** seeded in this test, so
  a regression back to the fallback path returns that user and fails — the
  assertion cannot pass vacuously.
- `getCurrentUser` → `should return null rather than throw when the
  sessionStorage fallback holds corrupt JSON`, pinning the adjacent fix.

**One assertion bug caught while writing them:** the first draft asserted
`expect(sessionStorageMock.setItem).not.toHaveBeenCalled()`, which failed —
`getOrCreateRequestId()` writes a request id to sessionStorage on every request
(`web/src/utils/requestId.ts:39`). Scoped to
`not.toHaveBeenCalledWith('user', expect.anything())`, which is what the tests
actually mean. Worth recording: the blanket form would have been a false
assertion about a different key.

AC3 — all 30 pre-existing `authService` tests pass untouched, including
`should fallback to sessionStorage on network error`, which pins that the
network-failure path (fetch rejecting) still returns the cached user. Only the
malformed-200 path changed behaviour.

### 2026-09-02 - Code review + repair (run 2026-09-02-0458)

Bundled `/code-review high`. Three findings, all real, all repaired. **The first
one invalidated my own reasoning above** — recorded rather than quietly
rewritten, because the wrong version is the instructive part.

**Finding 1 (MEDIUM) — repaired. My `return null` was a regression, not a fix.**
The entry above argued that returning the cached user on an unreadable 200
"silently promotes a stale identity", by analogy to todo 297. The reviewer
found the analogy is wrong and named the cost: `revalidateIdentity()` has two
callers beyond tab focus —
`web/src/pages/forum/NewThreadPage.tsx:267` and
`web/src/pages/forum/ThreadDetailPage.tsx:388` — which compute
`drifted = (current?.id ?? null) !== actingUserId` **after a write has already
succeeded**. Verified by reading both: `ThreadDetailPage.tsx:391` renders
literally *"Your session changed while replying — you were signed out."* when
`current?.username` is absent. So one unparseable body following a **successful**
reply would show that notice for a session that never changed, and
`setUser(null)` + `ProtectedLayout.tsx:43` would then really sign the user out.

The error in my reasoning: an unreadable body teaches us **nothing** about the
identity, which is not the same as learning the viewer is logged out. Returning
the cached user does not *promote* anything — the UI is already showing that
user, so it changes nothing and merely declines to update. Returning `null`
actively asserts a falsehood, and three call sites act on the assertion. The
297 failure mode needs a *server response naming a different user*; a body we
cannot read is not that.

Corrected: an unreadable 200 returns `getStoredUser()`. The guard's purpose is
now what it should always have been — make the case explicit, logged, and
incapable of throwing — not change the answer.

**Finding 2 (LOW/MEDIUM) — repaired, and it exposed a weak test.** The bare
`catch {}` could not honour the network-vs-malformed distinction the comment
claimed, since it also swallows a connection reset mid-body-read. Now moot:
both classes mean "couldn't confirm" and both return the last known user, so
the code and its comment finally agree. The sharper half of the finding was
about the *tests*: both mocks threw `new Error('Unexpected token …')`, not a
real `SyntaxError`, so the suite passed identically whether the catch was bare
or narrowed — the tests could not distinguish the two behaviours. All
malformed-body mocks now throw a real `SyntaxError`.

**Finding 3 (LOW/MEDIUM) — repaired.** The guard covered the parse but
`data.user` was dereferenced *outside* it, so a 200 that parses to the wrong
shape still escaped. Two concrete paths: body `null` → `TypeError: Cannot read
properties of null (reading 'user')`, which `AuthContext.toAuthError`
(`AuthContext.tsx:47`, `message = err.message` verbatim) puts straight on the
login form — the exact class this todo exists to close; body `{}` → nothing
throws, `login()` **resolves** with `user: undefined`, `sessionStorage` stores
the literal string `"undefined"`, `LoginPage.tsx:128` navigates on
`result.success`, and `ProtectedLayout` bounces straight back to `/login` with
no error shown — a silent login loop. Shape check (`if (!data?.user) throw`)
moved inside the guard in both functions, and the equivalent (`!data?.id`) in
`getCurrentUser`.

**Not a finding** (reviewer checked and dismissed): `getGoogleOAuthUrl`
(`authService.ts:375`) has the same unguarded success-path parse, but its only
caller (`GoogleSignInButton.tsx:59-62`) catches and substitutes a generic
message, so no raw parse text reaches the UI.

**Mutation-checked, not just green.** Each new guard was removed in turn to
confirm its tests actually bite:

```
# login shape check removed:
 FAIL  ... login > should reject a 200 that parses to null rather than throw a raw TypeError
 FAIL  ... login > should reject a 200 whose body has no user key instead of resolving
      Tests  2 failed | 38 passed (40)

# getCurrentUser regressed to the flagged clear-and-return-null:
 FAIL  ... getCurrentUser > should return the last known user on an unreadable 200, so drift detection stays quiet
 FAIL  ... getCurrentUser > should treat a 200 that parses to null as unreadable, not as a logout
      Tests  2 failed | 38 passed (40)
```

**Post-repair verification**

```
$ npx tsc --noEmit
TypeScript: No errors found
$ ./node_modules/.bin/vitest run src/services/authService.test.ts
      Tests  40 passed (40)       # 30 pre-existing + 10 new
$ ./node_modules/.bin/vitest run
 Test Files  86 passed (86)
      Tests  1014 passed (1014)
$ npm run lint
ESLint: 0 errors, 1 warnings in 1 files   # block-navigation.js, pre-existing
```

`eslint` initially failed with 2 `preserve-caught-error` **errors** on the new
rethrows (an error thrown from inside a `catch` must carry `{ cause }`); both
now pass the caught `parseError` through, so the friendly message reaches the
UI while the underlying `SyntaxError` stays attached for diagnostics.

### 2026-09-02 - Completed by completing-todos skill (run 2026-09-02-0458)

- Verification: all 3 acceptance criteria passed. AC1 is annotated rather than
  silently ticked — `getCurrentUser()` renders no message, so it is met in
  intent, not in letter.
- Review: 3 findings, all repaired. One of them (finding 1) reversed this
  todo's own first-pass conclusion; both the wrong reasoning and the correction
  are kept in the Work Log, since the wrong version is the instructive part.
- New guards were mutation-checked individually, not just left green.
- No `source_review` frontmatter, so there is no `## Finding Status` line to
  check off anywhere.
