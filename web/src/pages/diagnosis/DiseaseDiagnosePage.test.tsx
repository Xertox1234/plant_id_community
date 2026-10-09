import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import DiseaseDiagnosePage from './DiseaseDiagnosePage';
import { diseaseService } from '../../services/diseaseService';
import { PLANT_CONDITIONS } from '../../types/diagnosis';

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
    expect(screen.getByText('88%')).toBeInTheDocument();
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

  // Todo 459. plant_condition is a choices field on the backend; free text was
  // a guaranteed 400. The field is a <select> of the five model keys, and the
  // chosen KEY (not its label) is what reaches submitDiagnosis.
  it('posts the chosen plant condition key', async () => {
    vi.mocked(diseaseService.submitDiagnosis).mockResolvedValue({
      request_id: 'r4',
      status: 'failed',
    });
    vi.mocked(diseaseService.getDiagnosisResults).mockResolvedValue({
      request_id: 'r4',
      status: 'failed',
      results: [],
    });

    render(<DiseaseDiagnosePage />);
    await userEvent.upload(
      screen.getByLabelText('upload'),
      new File(['i'], 'a.jpg', { type: 'image/jpeg' })
    );
    await userEvent.type(screen.getByLabelText(/symptoms/i), 'wilting');
    await userEvent.selectOptions(
      screen.getByLabelText(/plant condition/i),
      'Poor - significant damage'
    );
    await userEvent.click(screen.getByRole('button', { name: /diagnose/i }));

    await waitFor(() => expect(diseaseService.submitDiagnosis).toHaveBeenCalledTimes(1));
    expect(vi.mocked(diseaseService.submitDiagnosis).mock.calls[0][0].plant_condition).toBe('poor');
  });

  it('offers the five model choices plus a not-specified option that sends nothing', async () => {
    vi.mocked(diseaseService.submitDiagnosis).mockResolvedValue({
      request_id: 'r5',
      status: 'failed',
    });
    vi.mocked(diseaseService.getDiagnosisResults).mockResolvedValue({
      request_id: 'r5',
      status: 'failed',
      results: [],
    });

    render(<DiseaseDiagnosePage />);
    const select = screen.getByLabelText(/plant condition/i);
    expect(select.tagName).toBe('SELECT');
    expect(Array.from((select as HTMLSelectElement).options).map((o) => o.value)).toEqual([
      '',
      'excellent',
      'good',
      'fair',
      'poor',
      'critical',
    ]);
    expect(select).toHaveValue('');

    await userEvent.upload(
      screen.getByLabelText('upload'),
      new File(['i'], 'a.jpg', { type: 'image/jpeg' })
    );
    await userEvent.type(screen.getByLabelText(/symptoms/i), 'wilting');
    await userEvent.click(screen.getByRole('button', { name: /diagnose/i }));

    await waitFor(() => expect(diseaseService.submitDiagnosis).toHaveBeenCalledTimes(1));
    expect(vi.mocked(diseaseService.submitDiagnosis).mock.calls[0][0].plant_condition).toBe(
      undefined
    );
  });

  // Todo 502. The select's keys and labels were a hand-kept copy of the model
  // choices; nothing failed if the model gained, lost or renamed one. Read the
  // choices straight out of models.py and compare them with what renders.
  // The read needs the backend tree next to web/: web-ci.yml, the only Vitest
  // job, checks out the whole repo, and a missing file throws rather than
  // passing (todo 515).
  it('offers exactly the plant_condition choices declared on the backend model', () => {
    const models = readFileSync(
      join(__dirname, '../../../../backend/apps/plant_identification/models.py'),
      'utf8'
    );
    // Bound the match to the plant_condition declaration -- its `CharField(`
    // through the field-level `)` on its own 4-space line -- and look for the
    // choices list only inside it. Unbounded, a lazy `[\s\S]*?choices=\[` ran
    // on to the NEXT field's list once this one moved to a constant or
    // TextChoices, and the failure diff blamed that field (todo 515).
    const field = models.match(/^ {4}plant_condition = models\.CharField\(([\s\S]*?)^ {4}\)/m);
    expect(field, 'plant_condition declaration not found in models.py').not.toBeNull();
    const choices = field![1].match(/choices=\[([\s\S]*?)\]/);
    expect(choices, 'plant_condition has no inline choices=[...] list').not.toBeNull();
    const backendChoices = [...choices![1].matchAll(/\(\s*"([^"]+)",\s*"([^"]+)"\s*\)/g)].map(
      (m) => [m[1], m[2]]
    );
    expect(backendChoices.length).toBeGreaterThan(0);
    // Every tuple in the list, parsed or not. One the key/label regex cannot
    // read -- `("dormant", _("Dormant"))`, single quotes -- used to be dropped
    // silently, and when web lacked it too the tie passed on exactly the drift
    // it guards (todo 515).
    const tupleLines = choices![1].match(/^\s*\(/gm) ?? [];
    expect(backendChoices).toHaveLength(tupleLines.length);

    render(<DiseaseDiagnosePage />);
    const options = Array.from(
      (screen.getByLabelText(/plant condition/i) as HTMLSelectElement).options
    )
      .filter((o) => o.value !== '')
      .map((o) => [o.value, o.textContent]);

    expect(options).toEqual(backendChoices);
    expect([...PLANT_CONDITIONS]).toEqual(backendChoices.map(([key]) => key));
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
