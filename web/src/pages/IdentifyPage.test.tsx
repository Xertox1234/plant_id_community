import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import IdentifyPage from './IdentifyPage';

// vi.hoisted: the vi.mock factories are hoisted above the imports, so they
// cannot close over a plain top-level const.
const { mockNavigate } = vi.hoisted(() => ({ mockNavigate: vi.fn() }));
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => mockNavigate };
});

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ isAuthenticated: true }),
}));

vi.mock('../services/plantIdService', () => ({
  plantIdService: { identifyPlant: vi.fn(), savePlantToCollection: vi.fn() },
}));

// FileUpload owns a real <input type=file>; the page only needs the callback.
vi.mock('../components/PlantIdentification/FileUpload', () => ({
  default: ({ onFileSelect }: { onFileSelect: (f: File | null) => void }) => (
    <input
      type="file"
      aria-label="upload"
      onChange={(e) => onFileSelect(e.target.files?.[0] ?? null)}
    />
  ),
}));

/**
 * Audit M26 (todo 278). The save-failure live region is the reason this file
 * exists: it was the one migrated site whose region sat inside a conditionally
 * rendered ancestor, which makes "persistent" a lie — the node is recreated
 * along with its content, and a screen reader announces nothing.
 */
describe('IdentifyPage', () => {
  beforeEach(() => {
    mockNavigate.mockReset();
  });

  it('mounts the save-error live region on first paint, before any results exist', () => {
    const { container } = render(
      <MemoryRouter>
        <IdentifyPage />
      </MemoryRouter>
    );

    // No file chosen, no results, nothing loading — the region must still be here.
    expect(screen.queryByText(/identify another plant/i)).not.toBeInTheDocument();

    const region = container.querySelector('[aria-live="assertive"]');
    expect(region).toBeInTheDocument();
    expect(region).toHaveTextContent('');
    expect(region).toHaveClass('sr-only');
  });

  it('does not use role="alert" — the anti-pattern this replaced', () => {
    render(
      <MemoryRouter>
        <IdentifyPage />
      </MemoryRouter>
    );

    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});
