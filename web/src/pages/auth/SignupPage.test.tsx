import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AuthErrorCode } from '../../types/auth';
import SignupPage from './SignupPage';

// Mock useAuth so we can drive signup() outcomes. vi.hoisted is required because
// the vi.mock factory is hoisted above the imports (see LoginPage.test.tsx).
const { mockSignup } = vi.hoisted(() => ({ mockSignup: vi.fn() }));

vi.mock('../../components/auth/GoogleSignInButton', () => ({
  default: ({ disabled, acceptedTerms }: { disabled?: boolean; acceptedTerms?: boolean }) => (
    <button type="button" disabled={disabled} data-accepted={String(!!acceptedTerms)}>
      Sign up with Google
    </button>
  ),
}));

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

const tickConsent = () => fireEvent.click(screen.getByRole('checkbox'));

describe('SignupPage', () => {
  beforeEach(() => {
    mockSignup.mockReset();
  });

  it('disables Create account and Google sign-up until consent is ticked', () => {
    renderSignupPage();
    const create = screen.getByRole('button', { name: /create account/i });
    const google = screen.getByRole('button', { name: 'Sign up with Google' });
    expect(screen.getByRole('checkbox')).not.toBeChecked();
    expect(create).toBeDisabled();
    expect(google).toBeDisabled();
    tickConsent();
    expect(create).toBeEnabled();
    expect(google).toBeEnabled();
    expect(google).toHaveAttribute('data-accepted', 'true');
  });

  it('links the Privacy Policy and Terms, and drops the old plain-text notice', () => {
    renderSignupPage();
    expect(screen.getByRole('link', { name: 'Privacy Policy' })).toHaveAttribute(
      'href',
      '/privacy'
    );
    expect(screen.getByRole('link', { name: 'Terms of Service' })).toHaveAttribute(
      'href',
      '/terms'
    );
    expect(screen.queryByText(/by creating an account/i)).not.toBeInTheDocument();
  });

  it('sends accepted_terms: true when submitting', async () => {
    mockSignup.mockResolvedValue({ success: true });
    renderSignupPage();
    fillValidForm();
    tickConsent();
    submit();
    await waitFor(() => expect(mockSignup).toHaveBeenCalledTimes(1));
    expect(mockSignup).toHaveBeenCalledWith(expect.objectContaining({ accepted_terms: true }));
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
    tickConsent();

    submit();

    expect(await screen.findByText('A user with that email already exists.')).toBeInTheDocument();
    expect(screen.queryByText(/\[object Object\]/)).not.toBeInTheDocument();
  });

  // Audit M26 (todo 278): same persistent-live-region contract as LoginPage.
  it('swaps the server error into a live region that was already mounted', async () => {
    mockSignup.mockResolvedValue({
      success: false,
      error: { message: 'That email is already registered.', code: AuthErrorCode.EMAIL_EXISTS },
    });
    const { container } = renderSignupPage();

    const region = container.querySelector('[aria-live="assertive"]');
    expect(region).toBeInTheDocument();
    expect(region).toHaveTextContent('');

    fillValidForm();
    tickConsent();
    submit();

    await waitFor(() => expect(region).toHaveTextContent('That email is already registered.'));
    // Same element — not a remount.
    expect(container.querySelector('[aria-live="assertive"]')).toBe(region);
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  // The 14-char strength rule belongs on signup (new password), NOT on login.
  it('enforces the 14-char password rule on signup', () => {
    renderSignupPage();

    fillValidForm('shortpw'); // 7 chars
    tickConsent();

    submit();

    expect(screen.getByText('Password must be at least 14 characters long')).toBeInTheDocument();
    expect(mockSignup).not.toHaveBeenCalled();
  });
});
