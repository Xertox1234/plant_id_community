import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AuthErrorCode } from '../../types/auth';
import LoginPage from './LoginPage';

// Mock useAuth so we can drive login() outcomes and assert call behavior.
// vi.hoisted is required: the vi.mock factory is hoisted above the imports, so it
// cannot close over a plain top-level const (temporal-dead-zone error).
const { mockLogin } = vi.hoisted(() => ({ mockLogin: vi.fn() }));

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({ login: mockLogin }),
}));

function renderLoginPage() {
  return render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>
  );
}

// Query by placeholder, not label: the field label includes a required "*" span,
// which makes an exact getByLabelText('Password') match brittle.
function fillForm(email: string, password: string) {
  fireEvent.change(screen.getByPlaceholderText('you@example.com'), {
    target: { value: email },
  });
  fireEvent.change(screen.getByPlaceholderText('Enter your password'), {
    target: { value: password },
  });
}

const submit = () => fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

describe('LoginPage', () => {
  beforeEach(() => {
    mockLogin.mockReset();
  });

  // Regression for PR #379: the login form wrongly ran the 14-char *new-password*
  // strength rule, locking out every account whose password predates that rule
  // (including the bootstrap superuser). Login must accept any non-empty password.
  it('accepts a short existing password — the 14-char rule must not apply on login', async () => {
    mockLogin.mockResolvedValue({ success: true });
    renderLoginPage();

    fillForm('test@example.com', 'shortpw'); // 7 chars — under the 14-char rule

    submit();

    expect(screen.queryByText(/14 characters/i)).not.toBeInTheDocument();
    await waitFor(() =>
      expect(mockLogin).toHaveBeenCalledWith({
        email: 'test@example.com',
        password: 'shortpw', // pragma: allowlist secret
      })
    );
  });

  it('still requires that a password was entered', () => {
    renderLoginPage();

    fillForm('test@example.com', '');

    submit();

    expect(screen.getByText('Password is required')).toBeInTheDocument();
    expect(mockLogin).not.toHaveBeenCalled();
  });

  // Guards the "[object Object]" fix: the page must render error.message, not the
  // whole AuthError object.
  it('shows the readable server error message, not "[object Object]"', async () => {
    mockLogin.mockResolvedValue({
      success: false,
      error: {
        message: 'Invalid email or password.',
        code: AuthErrorCode.INVALID_CREDENTIALS,
      },
    });
    renderLoginPage();

    fillForm('test@example.com', 'somepassword');

    submit();

    expect(await screen.findByText('Invalid email or password.')).toBeInTheDocument();
    expect(screen.queryByText(/\[object Object\]/)).not.toBeInTheDocument();
  });
});
