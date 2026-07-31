import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import IdentifyPage from './IdentifyPage';
import { plantIdService } from '../services/plantIdService';
import { uploadPostImage } from '../services/forumService';
import type { PlantIdentificationResult } from '@/types';

// vi.hoisted: the vi.mock factories are hoisted above the imports, so they
// cannot close over a plain top-level const.
const { mockNavigate } = vi.hoisted(() => ({ mockNavigate: vi.fn() }));
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => mockNavigate };
});

// Mutable so a single test can exercise the signed-out branch; reset per test.
const { authState } = vi.hoisted(() => ({ authState: { isAuthenticated: true } }));
vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => authState,
}));

vi.mock('../services/plantIdService', () => ({
  plantIdService: { identifyPlant: vi.fn(), savePlantToCollection: vi.fn() },
}));

// "Ask the community" uploads the photo through the forum image endpoint.
vi.mock('../services/forumService', () => ({ uploadPostImage: vi.fn() }));

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

  /**
   * "Ask the community" (audit M6) — the flagship loop's entry point. The photo
   * is uploaded HERE so only JSON crosses into router state and an upload
   * failure lands on this page, not at composer submit.
   */
  describe('Ask the community', () => {
    const RESULTS = {
      plant_name: 'Swiss cheese plant',
      confidence: 0.82,
      source: 'plant_id',
      suggestions: [
        {
          plant_name: 'Swiss cheese plant',
          scientific_name: 'Monstera deliciosa',
          probability: 0.82,
          confidence: 0.82,
          source: 'plant_id',
        },
        {
          plant_name: 'Heartleaf philodendron',
          scientific_name: 'Philodendron hederaceum',
          probability: 0.11,
          confidence: 0.11,
          source: 'plant_id',
        },
      ],
    };

    async function identify() {
      const file = new File(['x'], 'plant.jpg', { type: 'image/jpeg' });
      await userEvent.upload(screen.getByLabelText('upload'), file);
      await userEvent.click(screen.getByRole('button', { name: /identify plant/i }));
      return screen.findByRole('button', { name: /ask the community/i });
    }

    beforeEach(() => {
      authState.isAuthenticated = true;
      vi.mocked(plantIdService.identifyPlant).mockResolvedValue(
        RESULTS as unknown as PlantIdentificationResult
      );
      vi.mocked(uploadPostImage).mockReset();
    });

    it('uploads the photo, then hands the top candidates to the composer', async () => {
      vi.mocked(uploadPostImage).mockResolvedValue({
        id: 42,
        url: 'http://localhost:8000/media/images/plant.jpg',
        alt: 'plant.jpg',
        width: 800,
        height: 600,
      });
      render(
        <MemoryRouter>
          <IdentifyPage />
        </MemoryRouter>
      );

      await userEvent.click(await identify());

      await waitFor(() =>
        expect(mockNavigate).toHaveBeenCalledWith('/forum/new-thread', {
          state: {
            identification: {
              image_id: 42,
              provider: 'plant_id',
              candidates: [
                {
                  name: 'Swiss cheese plant',
                  scientific_name: 'Monstera deliciosa',
                  confidence: 0.82,
                },
                {
                  name: 'Heartleaf philodendron',
                  scientific_name: 'Philodendron hederaceum',
                  confidence: 0.11,
                },
              ],
            },
            identificationPreviewUrl: 'http://localhost:8000/media/images/plant.jpg',
          },
        })
      );
    });

    it('sends a signed-out user to log in instead of a 401 upload', async () => {
      // Anonymous identification is allowed in DEBUG, but POST /forum/images/
      // is not — without this gate the button would just fail.
      authState.isAuthenticated = false;
      render(
        <MemoryRouter>
          <IdentifyPage />
        </MemoryRouter>
      );

      await userEvent.click(await identify());

      expect(mockNavigate).toHaveBeenCalledWith('/login', { state: { from: '/identify' } });
      expect(uploadPostImage).not.toHaveBeenCalled();
    });

    it('surfaces an upload failure here, and does not navigate', async () => {
      vi.mocked(uploadPostImage).mockRejectedValue(new Error('Upload failed'));
      const { container } = render(
        <MemoryRouter>
          <IdentifyPage />
        </MemoryRouter>
      );

      await userEvent.click(await identify());

      await waitFor(() =>
        expect(container.querySelector('[aria-live="assertive"]')).toHaveTextContent(
          'Upload failed'
        )
      );
      expect(mockNavigate).not.toHaveBeenCalledWith('/forum/new-thread', expect.anything());
    });
  });
});
