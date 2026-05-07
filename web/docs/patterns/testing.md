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
