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
