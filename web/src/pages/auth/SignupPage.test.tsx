import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AuthErrorCode } from '../../types/auth';
import SignupPage from './SignupPage';

// Mock useAuth so we can drive signup() outcomes. vi.hoisted is required because
// the vi.mock factory is hoisted above the imports (see LoginPage.test.tsx).
const { mockSignup } = vi.hoisted(() => ({ mockSignup: vi.fn() }));

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({ signup: mockSignup }),
}));

function renderSignupPage() {
  return render(
    <MemoryRouter>
      <SignupPage />
    </MemoryRouter>
  );
}

// Query by unique placeholders (labels carry a required "*" span).
function setField(placeholder: string, value: string) {
  fireEvent.change(screen.getByPlaceholderText(placeholder), { target: { value } });
}

// Strong enough to clear the 14-char rule — a test fixture, not a real credential.
const STRONG_PASSWORD = 'a-very-strong-password'; // pragma: allowlist secret

function fillValidForm(password = STRONG_PASSWORD) {
  setField('johndoe', 'newuser');
  setField('you@example.com', 'new@example.com');
  setField('At least 14 characters', password);
  setField('Re-enter your password', password);
}

const submit = () => fireEvent.click(screen.getByRole('button', { name: /create account/i }));

describe('SignupPage', () => {
  beforeEach(() => {
    mockSignup.mockReset();
  });

  // Guards the "[object Object]" fix: the page must render error.message, not the
  // whole AuthError object (String({message,code}) → the literal "[object Object]").
  it('renders the readable server error message, not "[object Object]"', async () => {
    mockSignup.mockResolvedValue({
      success: false,
      error: {
        message: 'A user with that email already exists.',
        code: AuthErrorCode.EMAIL_EXISTS,
      },
    });
    renderSignupPage();

    fillValidForm();

    submit();

    expect(await screen.findByText('A user with that email already exists.')).toBeInTheDocument();
    expect(screen.queryByText(/\[object Object\]/)).not.toBeInTheDocument();
  });

  // The 14-char strength rule belongs on signup (new password), NOT on login.
  it('enforces the 14-char password rule on signup', () => {
    renderSignupPage();

    fillValidForm('shortpw'); // 7 chars

    submit();

    expect(screen.getByText('Password must be at least 14 characters long')).toBeInTheDocument();
    expect(mockSignup).not.toHaveBeenCalled();
  });
});
