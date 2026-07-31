import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import DiseaseDiagnosePage from './DiseaseDiagnosePage';
import { diseaseService } from '../../services/diseaseService';

vi.mock('../../services/diseaseService');
// FileUpload renders an <input type=file>; we drive it directly.
vi.mock('../../components/PlantIdentification/FileUpload', () => ({
  default: ({ onFileSelect }: { onFileSelect: (f: File | null) => void }) => (
    <input
      type="file"
      aria-label="upload"
      onChange={(e) => onFileSelect(e.target.files?.[0] ?? null)}
    />
  ),
}));

describe('DiseaseDiagnosePage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('submits and renders a diagnosis result', async () => {
    vi.mocked(diseaseService.submitDiagnosis).mockResolvedValue({
      request_id: 'r1',
      status: 'diagnosed',
    });
    vi.mocked(diseaseService.getDiagnosisResults).mockResolvedValue({
      request_id: 'r1',
      status: 'diagnosed',
      results: [
        {
          id: 1,
          uuid: 'u1',
          request_id: 'r1',
          suggested_disease_name: 'Black Spot',
          suggested_disease_type: 'fungal',
          confidence_score: 0.88,
          confidence_percentage: 88,
          diagnosis_source: 'api_plant_health',
          severity_assessment: 'moderate',
          symptoms_identified: 'black spots',
          recommended_treatments: 'fungicide',
          immediate_actions: 'remove affected leaves',
          notes: '',
          is_primary: true,
          display_name: 'Black Spot',
        },
      ],
    });

    render(<DiseaseDiagnosePage />);
    const file = new File(['img'], 'leaf.jpg', { type: 'image/jpeg' });
    await userEvent.upload(screen.getByLabelText('upload'), file);
    await userEvent.type(screen.getByLabelText(/symptoms/i), 'black spots on leaves');
    await userEvent.click(screen.getByRole('button', { name: /diagnose/i }));

    await waitFor(() => expect(screen.getByText('Black Spot')).toBeInTheDocument());
    expect(screen.getByText(/88% confidence/)).toBeInTheDocument();
  });

  it('shows an error when status is failed', async () => {
    vi.mocked(diseaseService.submitDiagnosis).mockResolvedValue({
      request_id: 'r2',
      status: 'failed',
    });
    vi.mocked(diseaseService.getDiagnosisResults).mockResolvedValue({
      request_id: 'r2',
      status: 'failed',
      results: [],
    });

    render(<DiseaseDiagnosePage />);
    await userEvent.upload(
      screen.getByLabelText('upload'),
      new File(['i'], 'a.jpg', { type: 'image/jpeg' })
    );
    await userEvent.type(screen.getByLabelText(/symptoms/i), 'wilting');
    await userEvent.click(screen.getByRole('button', { name: /diagnose/i }));

    await waitFor(() => expect(screen.getByText(/diagnosis unavailable/i)).toBeInTheDocument());
  });

  it('disables submit until an image and symptoms are provided', () => {
    render(<DiseaseDiagnosePage />);
    expect(screen.getByRole('button', { name: /diagnose/i })).toBeDisabled();
  });

  // Audit M26 (todo 278). The failure text lands in a live region that was
  // already in the DOM — a region mounted together with its content generally
  // announces nothing.
  it('swaps the error into a live region that was already mounted', async () => {
    vi.mocked(diseaseService.submitDiagnosis).mockResolvedValue({
      request_id: 'r3',
      status: 'failed',
    });
    vi.mocked(diseaseService.getDiagnosisResults).mockResolvedValue({
      request_id: 'r3',
      status: 'failed',
      results: [],
    });

    const { container } = render(<DiseaseDiagnosePage />);

    const region = container.querySelector('[aria-live="assertive"]');
    expect(region).toBeInTheDocument();
    expect(region).toHaveTextContent('');
    expect(region).toHaveClass('sr-only');

    await userEvent.upload(
      screen.getByLabelText('upload'),
      new File(['i'], 'a.jpg', { type: 'image/jpeg' })
    );
    await userEvent.type(screen.getByLabelText(/symptoms/i), 'wilting');
    await userEvent.click(screen.getByRole('button', { name: /diagnose/i }));

    await waitFor(() => expect(region).toHaveTextContent(/diagnosis unavailable/i));
    // Same node, not a remount — the property the whole migration turns on.
    expect(container.querySelector('[aria-live="assertive"]')).toBe(region);
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  // Tailwind v4 implements space-y as margin-BOTTOM on `:not(:last-child)`, so
  // appending an always-mounted region after the button silently gave the
  // button 24px of trailing whitespace in the idle state. The region shares a
  // wrapper with the button now; this pins that the container's direct-child
  // list is unchanged, which is the thing that regressed.
  it('keeps the live region out of the space-y child list', () => {
    const { container } = render(<DiseaseDiagnosePage />);

    const spaced = container.querySelector('.space-y-6');
    const region = container.querySelector('[aria-live="assertive"]');
    expect(spaced).toBeInTheDocument();
    expect(region?.parentElement).not.toBe(spaced);
    // And the button is still the last element in its own slot, so nothing
    // downstream of it picks up a margin it did not have before.
    expect(spaced?.lastElementChild?.contains(region!)).toBe(true);
  });
});
