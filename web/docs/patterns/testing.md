# Web Frontend Testing Patterns

**Stack**: Vitest (unit/component, 492 tests), Playwright (E2E, 107 tests)

---

## Test What Behaviour, Not Implementation

React component tests must test user-visible behaviour, not internal state:

```typescript
// ✅ Behaviour test
test('shows error message when email is invalid', async () => {
  render(<LoginForm />);
  await userEvent.type(screen.getByLabelText('Email'), 'notanemail');
  await userEvent.click(screen.getByRole('button', { name: 'Login' }));
  expect(screen.getByText('Invalid email address')).toBeInTheDocument();
});

// ❌ Implementation test — breaks on refactor
test('sets hasError state to true for invalid email', () => {
  const { result } = renderHook(() => useLoginForm());
  act(() => result.current.setEmail('notanemail'));
  expect(result.current.hasError).toBe(true);
});
```

---

## No Unresolved act() Warnings

`act()` warnings indicate async state updates not wrapped in `act()`. They are not cosmetic:

- They can hide timing-dependent bugs
- They indicate the component has unfinished work at assertion time

Resolve by awaiting state changes:

```typescript
await act(async () => {
  await userEvent.click(button);
});
```

---

## External APIs Must Be Mocked

In Vitest unit/component tests, mock all external API calls. In E2E (Playwright) tests, use a test server or recorded fixtures.

```typescript
vi.mock('../services/apiService', () => ({
  identifyPlant: vi.fn().mockResolvedValue({ species: 'Rosa', confidence: 0.95 }),
}));
```

---

## E2E Test Documentation

New user-facing flows require a test case entry in `web/E2E_TESTING_GUIDE.md`. Format:

```markdown
### TC-XX: [Feature Name]

**Setup**: [prerequisites]
**Steps**: 1. ... 2. ... 3. ...
**Expected**: [visible outcome]
```

---

## Testing a Page That Uses `useAuth` + Router

Component tests for a page that calls `useAuth()` and React Router hooks
(`useNavigate`/`useLocation`) need three things. Canonical recipe — see
`src/pages/auth/LoginPage.test.tsx`:

```typescript
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import LoginPage from './LoginPage';

// 1. vi.hoisted: the vi.mock factory is hoisted ABOVE the imports, so it cannot
//    close over a plain top-level const (temporal-dead-zone error). Create the
//    mock fn inside vi.hoisted so the factory can reference it.
const { mockLogin } = vi.hoisted(() => ({ mockLogin: vi.fn() }));
vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({ login: mockLogin }),
}));

// 2. MemoryRouter supplies real useNavigate/useLocation — no need to mock them.
const renderPage = () =>
  render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>
  );

it('submits with a short existing password', async () => {
  mockLogin.mockResolvedValue({ success: true });
  renderPage();
  // 3. Query by PLACEHOLDER, not getByLabelText: the field <label> carries a
  //    required "*" span, so an exact label match ("Password") fails.
  fireEvent.change(screen.getByPlaceholderText('Enter your password'), {
    target: { value: 'shortpw' },
  });
  fireEvent.click(screen.getByRole('button', { name: /sign in/i }));
  await waitFor(() => expect(mockLogin).toHaveBeenCalled());
});
```

Gotchas:

- `vi.hoisted` is mandatory — a bare `const mockLogin = vi.fn()` referenced in the
  factory throws "Cannot access 'mockLogin' before initialization".
- Prefer `getByPlaceholderText` / `getByRole` over `getByLabelText` when labels
  include a required-`*` span or other non-text nodes.
- Test-fixture passwords (`password: '...'`) trip detect-secrets — add
  `// pragma: allowlist secret` on the literal's line, and put it on a `const` so
  Prettier can't shift the comment off that line.

---

## Mocking browser navigation (`window.location.assign`) in jsdom

jsdom makes `window.location.assign` (and `.replace`/`.reload`) **non-configurable**,
so `vi.spyOn(window.location, 'assign')` throws `TypeError: Cannot redefine
property: assign`. Replace the whole `window.location` property instead, and
restore it in `afterEach` (the property itself *is* configurable; its methods
are not). Canonical — `src/components/auth/GoogleSignInButton.test.tsx`:

```typescript
describe('GoogleSignInButton', () => {
  const assignMock = vi.fn();
  let originalLocation: Location;

  beforeEach(() => {
    originalLocation = window.location;
    Object.defineProperty(window, 'location', {
      configurable: true,
      writable: true,
      value: { assign: assignMock, href: '' }, // only stub what the component reads
    });
    assignMock.mockReset();
  });

  afterEach(() => {
    Object.defineProperty(window, 'location', {
      configurable: true,
      writable: true,
      value: originalLocation,
    });
  });

  it('redirects on click', async () => {
    render(<GoogleSignInButton />);
    fireEvent.click(screen.getByRole('button', { name: 'Sign in with Google' }));
    await waitFor(() => expect(assignMock).toHaveBeenCalledWith(expectedUrl));
  });
});
```

A minimal `{ assign, href }` stub is enough when the component under test reads
nothing else off `location` and renders without a Router.

---

## Disambiguate `getByRole` by exact name when controls share a label substring

A `name` **regex** does a *substring* match, so `getByRole('button', { name:
/sign in/i })` matches BOTH `"Sign in"` and `"Sign in with Google"` once a page
has both → `TestingLibraryElementError: Found multiple elements`. When two
controls share a label substring, switch to an **exact string** `name` (full,
normalised accessible-name match):

```typescript
// ✅ exact — targets only the password submit button
screen.getByRole('button', { name: 'Sign in' });
screen.getByRole('button', { name: 'Sign in with Google' });

// ❌ substring regex — ambiguous once a second "Sign in…" control exists
screen.getByRole('button', { name: /sign in/i });
```

This bit `LoginPage.test.tsx` the moment the Google button landed next to the
password submit. The `/regex/` form is still fine when only one control matches.

---

## TipTap `suggestion.render()`'s DOM Lifecycle Isn't Exercised by a Headless Editor Test

A TipTap `suggestion.render()` factory returns `onStart`/`onUpdate`/`onExit`
callbacks that ProseMirror's suggestion plugin calls directly against a real,
mounted `EditorView` (triggered by actual cursor movement). A Vitest test that
constructs a headless `new Editor({...})` — no mounted view, no real
selection — can exercise the extension's pure-logic helpers just fine, but
never triggers `onStart`/`onUpdate` at all: there's no attached view for the
suggestion plugin to call them against.

```typescript
// Exercised by a headless Editor test — pure logic, no DOM/view needed:
resolveMentionSuggestions('foo'); // debounce/token logic testable in isolation
editor.getHTML(); // renderHTML/renderText output

// NOT exercised by the same test file — needs a mounted view:
suggestion: {
  render: () => ({
    onStart: (props) => {
      if (!shouldRender(props)) return; // orphan-dropdown guard — untested
      dropdown = document.createElement('div');
      document.body.appendChild(dropdown); // ProseMirror calls this directly
    },
  }),
}
```

Gotchas:

- Don't assume a green `*.test.ts` file for a TipTap extension covers its
  `render()` lifecycle just because the file has `describe` blocks for that
  extension — check whether any test actually drives `onStart`/`onUpdate`, or
  only the extension's pure-logic helpers.
- To actually exercise `onStart`/`onUpdate`/`onExit`, use Playwright against a
  real mounted editor — a headless `Editor` in Vitest structurally can't reach
  them. `e2e/forum-mention.spec.js` (todo 336) is that spec for the forum
  composer: real keystrokes in the NEW-THREAD editor (same `TipTapEditor` +
  `ForumMention` as the reply composer, which itself has no E2E layer — a
  fresh local forum has no topic to open), the dropdown asserted in `<body>`
  with a non-origin `clientRect`, Enter committing exactly one mention node,
  Escape leaving the count unchanged, and teardown on an in-app route change
  (a `page.goto()` wipes `<body>` and can never fail). It lives in the `*-authenticated` projects only
  (session + `users/search/` need auth) — a new spec of this kind must be
  added to BOTH the authenticated `testMatch` and every unauthenticated
  project's `testIgnore` in `playwright.config.ts`, and it must be `.js`.
- When a lifecycle guard like this is only reasoning-verified (traced against
  the library's own source) rather than test-exercised, say so explicitly in
  the PR/todo Work Log — a passing suite shouldn't imply coverage it doesn't
  have. See `forumMentionNode.ts`'s `shouldRender` guard and todo 253 slice
  4's Work Log for the precedent.
- **A `vi.mock` stub must forward the prop under test, or the behaviour is
  unobservable.** The forum composer tests stub `TipTapEditor` down to a bare
  `<textarea onChange=…>`, which is fine for typing but silently drops
  `content` — so a test asserting *restored* state (a saved draft, a loaded
  edit body) sees an empty field no matter what the page does, and the obvious
  reading is "the page is broken". Forward the prop
  (`defaultValue={content}` for an uncontrolled stub) and, where the value
  matters, assert it reached the *service* call too — that distinguishes real
  component state from a rendered default. See the M3 draft-restore test in
  `src/pages/forum/NewThreadPage.test.tsx`.
- jsdom implements `scrollIntoView` on **`HTMLElement.prototype`**, not
  `Element.prototype`. A test that stubs/spies `Element.prototype.scrollIntoView`
  gets **silently shadowed** — the real call resolves to jsdom's own
  `HTMLElement.prototype` no-op, so the spy records 0 calls and an assertion like
  `toHaveBeenCalledTimes(1)` fails even though the component scrolled correctly.
  Spy on `HTMLElement.prototype.scrollIntoView` (post-card wrappers are
  `HTMLElement`s). Cost a green-looking arrival-scroll test a full debug loop in
  the forum Wave 1 deep-link work — the production code was right, the spy target
  was wrong.

## jsdom Has No Layout: ProseMirror Transactions Throw on `Range` (todo 275)

Any TipTap/ProseMirror transaction that scrolls the selection — a document
replacement, `undo`, anything with `scrollIntoView` — throws in jsdom:

```
TypeError: target.getClientRects is not a function
  ❯ singleRect prosemirror-view/dist/index.js:521
  ❯ coordsAtPos → EditorView.scrollToSelection → updateStateInner
```

`coordsAtPos` calls `singleRect(textRange(node, from, to))`, so **the target is a
`Range`**, not the node. jsdom's `Range` implements neither `getClientRects` nor
`getBoundingClientRect`. Polyfilling `Text.prototype`/`Element.prototype` does
nothing — neither is on the call path.

**Check the exit code, not the pass count.** This surfaces as an *unhandled error*,
so the run prints `Test Files 1 passed (1)` / `Tests 25 passed (25)` and still
exits **1** — green at a glance locally, red in CI:

```bash
./node_modules/.bin/vitest --run src/components/forum/TipTapEditor.test.tsx; echo $?
```

Two fixes, in preference order:

1. **Disable the scroll in the component** where you control the chain:
   `editor.chain().focus(null, { scrollIntoView: false }).selectAll().insertContent(nodes).run()`.
   Verify the signature against the installed `@tiptap/core` (`focus(position, options)`),
   not the hosted docs. This is usually the better product behaviour too — replacing
   the document otherwise scroll-jumps the page to the caret right after a click the
   user made on the toolbar directly above it.
2. **Polyfill `Range.prototype` in the test file** when the scroll is internal and
   not configurable — e.g. TipTap's own Mod-z keybinding, where scroll-into-view
   lives inside the History extension:

```ts
beforeAll(() => {
  const proto = Range.prototype as unknown as Record<string, unknown>;
  if (typeof proto.getClientRects !== 'function') {
    proto.getClientRects = () => Object.assign([], { item: () => null });
  }
  if (typeof proto.getBoundingClientRect !== 'function') {
    proto.getBoundingClientRect = () => new DOMRect(0, 0, 0, 0);
  }
});
```

An empty rect list is the case `singleRect` already handles for an off-screen
selection, so this is inert padding rather than simulated layout — it does not let a
test assert anything false about geometry.

Prefer the polyfill over a test-only prop on the component. Driving undo through the
real Mod-z keybinding verifies the claim that matters ("the *user* can undo this");
an `onEditorReady` escape hatch added only for the test verifies a different one.

## Session-Scoped API State Belongs in the Service, Not Component State (todo 275)

A component that latches "the server told me this can never work" in `useState`
loses the latch on remount. The forum reply composer is remounted after every post
(`key={composerKey}` in `ThreadDetailPage`, the M25 autofocus behaviour), so a
per-instance flag re-offered — and re-failed — a 403-ing premium action on every
reply, while the code comment claimed the user was "not left clicking a dead
button".

Put a session-lifetime API fact in the service module and seed component state
from it:

```ts
// forumService.ts
let composeAssistUnavailable = false;
export const isComposeAssistUnavailable = () => composeAssistUnavailable;
export const markComposeAssistUnavailable = () => { composeAssistUnavailable = true; };
/** Test-only — module state otherwise leaks between cases in a file. */
export const resetComposeAssistAvailability = () => { composeAssistUnavailable = false; };

// component
const [unavailable, setUnavailable] = useState(isComposeAssistUnavailable);
```

Two things this costs you, both worth paying deliberately:

- **Write it from the caller, not inside the request function.** The caller already
  branches on the error, and a test that stubs the request out (`vi.spyOn(service,
  'improveDraft')`) never runs code inside it — so a latch set inside the request
  function is silently absent in exactly the tests that exercise the latch.
- **Reset it in `beforeEach`.** Module state persists across cases in a file, so one
  403 case will otherwise disable the control for every later case.

Pin the remount behaviour explicitly: render, trigger the failure, `unmount()`,
render again, and assert the control is still disabled. And prefer **mounted +
disabled** over unmounting the control — unmounting something the user just
activated drops keyboard focus to `<body>` with nothing to return to, and shifts
the toolbar under the pointer. (It also keeps the test honest: once a control is
always mounted, "still present" is a near-hollow assertion — assert
`toBeEnabled()`/`toBeDisabled()` instead.)

## Vitest Hook Bodies: Never Implicit-Return a Mock Call (PR #537)

Vitest treats a function returned from `beforeEach`/`afterEach` as a teardown
callback. Every `vi.fn()` method (`mockReset`, `mockResolvedValue`, …) returns
the mock itself — so an implicit-return arrow registers the mock AS the
teardown, and Vitest re-invokes it after the test:

```ts
// BROKEN — mockReset() returns the mock; Vitest calls it post-test,
// replaying any configured rejection as an unhandled rejection:
beforeEach(() => mockFetchUnreadCount.mockReset());

// CORRECT — block body, nothing returned:
beforeEach(() => {
  mockFetchUnreadCount.mockReset();
  mockFetchUnreadCount.mockResolvedValue(0);
});
```

The failure signature is a test whose own assertions pass but which fails with
the mock's configured rejection error. Reproduced in isolation twice during the
Canopy forum rebuild.

Related config trap: `vitest.config.ts` sets `mockReset: true` and
`restoreMocks: true`, which strip any return value chained inside a `vi.mock`
factory **before the first test runs**. Set mock return values in `beforeEach`
(block body, per the above), never in the factory.

Third face of the same trap — **setup.ts global polyfills must be plain
functions**, never `vi.fn().mockImplementation(...)`/`.mockResolvedValue(...)`:
`mockReset: true` wipes the implementation before every test, so the polyfill
returns `undefined` from the very first test on. It stays invisible until
production code gains its first caller — `useMediaQuery` becoming
`window.matchMedia`'s first caller broke 74 tests across 4 suites, and the same
defect sat dormant in the `navigator.share`/`navigator.clipboard` polyfills. A
bare argument-less `vi.fn()` (e.g. `window.scrollTo`) is safe: there is no
implementation to wipe. A test that needs a different posture (a matching media
query, a rejecting clipboard) installs its own stub and restores the global
afterward — don't teach the shared polyfill per-test behavior. See
`docs/LEARNINGS.md` 2026-08-15.

## A page that calls `useAnnounce()` needs `AnnouncerProvider` — or a hoisted mock — in its tests

`useAnnounce()` throws outside an `AnnouncerProvider`. In the app every routed
page is inside one (`main.tsx` wraps `<App />`), so the first place a new
`announce(...)` call fails is the page's own test file, which usually renders
the page bare inside a `MemoryRouter`. Two shapes, pick by what the test wants
to assert (audit 2026-09-04 M4):

```tsx
// 1. Assert the CALL — cheapest; SearchPage.test.tsx / UserProfilePage.test.tsx.
const announceMock = vi.hoisted(() => vi.fn());
vi.mock('../../contexts/AnnouncerContext', () => ({ useAnnounce: () => announceMock }));
// …
expect(announceMock).toHaveBeenCalledWith('Search failed', 'assertive');

// 2. Assert the REGION — proves the text reaches the live region; NewThreadPage.test.tsx.
render(<MemoryRouter><AnnouncerProvider><NewThreadPage /></AnnouncerProvider></MemoryRouter>);
await waitFor(() =>
  expect(document.querySelector('[data-announcer="assertive"]')).toHaveTextContent(
    'Failed to create thread'
  )
);
```

With shape 2 the same text is also in the inline banner, so `findByText` finds
two elements — use `findAllByText` for the banner and the `[data-announcer]`
selector for the region. `vi.hoisted` is required for shape 1: the `vi.mock`
factory is hoisted above imports, so a bare top-level `const` is not yet
defined when it runs.

## ThreadDetailPage post fixtures render from `body` blocks, not `content_html`

`createMockPost()` defaults `content_raw`/`content_html`, but the thread page
renders each post through the block renderer, so text placed in those fields
never reaches the DOM — a `getByText('…')` on it times out with no other
symptom. Give the fixture a block (audit 2026-09-04 M2 test):

```ts
createMockPost({
  id: '7',
  body: [{ id: 'b7', type: 'paragraph', value: '<p>thread B post</p>' }],
});
```

Same for a per-thread `fetchPosts` mock: key it on the call's `{ thread }`
argument (`mockImplementation(async ({ thread }) => …)`) rather than chaining
`mockResolvedValueOnce`, or the second thread's load consumes the wrong page.
