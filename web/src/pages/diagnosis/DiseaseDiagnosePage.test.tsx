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

const MODELS_PY = join(__dirname, '../../../../backend/apps/plant_identification/models.py');

type InlineChoices = { error: string } | { choices: [string, string][]; residue: string };

// Read a CharField's inline `choices=[...]` out of models.py source (todos 502,
// 515, 556). Bound the match to the field's declaration: from its `CharField(`
// up to the next line that starts at the field's own 4-space indent -- its
// closing `)` when the declaration spans lines, the next field when it is a
// one-liner -- so it can never run on into another field's list. Unbounded,
// a lazy match blamed the NEXT field's choices once this one moved to a
// constant or TextChoices (todo 515).
//
// `#` comments are dropped first, whole-line and trailing alike (todo 590): a
// `#` inside a quoted string is kept. Every `("key", "label")` tuple is
// parsed, a trailing comma inside it (Black's magic one) allowed, and whatever
// the parse did not consume is returned as the residue: anything there but
// whitespace and commas is a choice this parser cannot read -- a list-form
// `["dormant", "Dormant"]`, a `*EXTRA` spread, a gettext `_("...")` label,
// single quotes -- which a line count missed (todo 556). What follows the
// closing `]` up to the next `,` or `)` -- `choices=[...] + EXTRA` -- is
// residue too (todo 590), its parentheses balanced two levels deep so a call
// such as `+ list(EXTRA)` is reported whole, not cut at its own `)` (todo 610).
// Known limits: a `]` inside a label ends the list early, and a third level of
// parentheses cuts the tail at its own `(` -- `+ list(chain(f(A), B))` is
// reported as `+ list`, still residue, so the drift is still caught (todo 634).
function readInlineChoices(source: string, field: string): InlineChoices {
  const decl = source.match(
    new RegExp(`^ {4}${field} = models\\.CharField\\(((?:(?!\\n {4}\\S)[\\s\\S])*)`, 'm')
  );
  if (!decl) return { error: `${field} declaration not found in models.py` };
  // Strings are matched first so a `#` inside one is not taken for a comment.
  const body = decl[1].replace(/"(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*'|#[^\n]*/g, (m) =>
    m.startsWith('#') ? '' : m
  );
  const list = body.match(/choices=\[([\s\S]*?)\]((?:[^,()]|\((?:[^()]|\([^()]*\))*\))*)/);
  if (!list) return { error: `${field} has no inline choices=[...] list` };
  const tuple = /\(\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,?\s*\)/g;
  const choices = [...list[1].matchAll(tuple)].map((m) => [m[1], m[2]] as [string, string]);
  const residue = (list[1].replace(tuple, '') + ' ' + list[2]).replace(/[\s,]+/g, ' ').trim();
  return { choices, residue };
}

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
    const read = readInlineChoices(readFileSync(MODELS_PY, 'utf8'), 'plant_condition');
    if ('error' in read) {
      expect.fail(`${read.error}: move this guard to wherever the choices now live`);
    }
    const { choices: backendChoices, residue } = read;
    expect(
      backendChoices.length,
      'no ("key", "label") tuple parsed from plant_condition choices; update readInlineChoices'
    ).toBeGreaterThan(0);
    // A choice the parser cannot read used to be dropped silently, and when
    // web lacked it too the tie passed on exactly the drift it guards (todos
    // 515, 556).
    expect(
      residue,
      `plant_condition choices hold entries readInlineChoices cannot parse: ${residue}`
    ).toBe('');

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

// The reader's own cases (todo 556), each a probe from PR #946's review. They
// run against a fixed fixture, not models.py, so adding, removing or
// reordering a real plant_condition choice fails only the drift guard above,
// with its own message, and never these parser tests (todo 590).
describe('readInlineChoices', () => {
  const LAST = '            ("b", "Bee - two"),\n';
  const FIXTURE =
    '    plant_condition = models.CharField(\n' +
    '        max_length=20,\n' +
    '        choices=[\n' +
    '            ("a", "Ay - one"),\n' +
    LAST +
    '        ],\n' +
    '        blank=True,\n' +
    '    )\n' +
    '    location = models.CharField(\n' +
    '        choices=[("in", "Indoors")],\n' +
    '    )\n';
  const FIXTURE_CHOICES = [
    ['a', 'Ay - one'],
    ['b', 'Bee - two'],
  ];
  const withLast = (replacement: string) => FIXTURE.replace(LAST, replacement);
  const ok = (source: string) => {
    const read = readInlineChoices(source, 'plant_condition');
    if ('error' in read) expect.fail(read.error);
    return read;
  };

  it('parses the fixture with nothing left over', () => {
    const read = ok(FIXTURE);
    expect(read.choices).toEqual(FIXTURE_CHOICES);
    expect(read.residue).toBe('');
  });

  // The real declaration, with no count or line pinned: what it holds is the
  // drift guard's business, this only says the parser reads it whole.
  it('reads the real models.py declaration with nothing left over', () => {
    const read = ok(readFileSync(MODELS_PY, 'utf8'));
    expect(read.choices.length).toBeGreaterThan(0);
    expect(read.residue).toBe('');
  });

  it.each([
    // Its own `]` ends the list early (the known limit), but what precedes it
    // is still left over, so the drift is still caught.
    ['a list-form choice', LAST + '            ["dormant", "Dormant"],\n', '["dormant" "Dormant"'],
    ['a spread', LAST + '            *EXTRA_CONDITIONS,\n', '*EXTRA_CONDITIONS'],
    [
      'a gettext label',
      LAST + '            ("dormant", _("Dormant")),\n',
      '("dormant" _("Dormant"))',
    ],
    ['single quotes', LAST + "            ('dormant', 'Dormant'),\n", "('dormant' 'Dormant')"],
  ])('reports %s as residue instead of passing', (_name, replacement, residue) => {
    const read = ok(withLast(replacement));
    expect(read.choices).toEqual(FIXTURE_CHOICES);
    expect(read.residue).toBe(residue);
  });

  // Todo 590: the residue covered only the text inside `[...]`, so a choice
  // concatenated on after it passed with nothing left over.
  it.each([
    ['a concatenated constant', ' + EXTRA_CONDITIONS', '+ EXTRA_CONDITIONS'],
    // Todo 610: the tail stopped at the call's own `)`, reporting `+ list(EXTRA`.
    ['a concatenated call', ' + list(EXTRA)', '+ list(EXTRA)'],
    ['a nested call', ' + list(chain(A, B))', '+ list(chain(A B))'],
    ['a concatenation on the next line', '\n        + EXTRA_CONDITIONS', '+ EXTRA_CONDITIONS'],
  ])('reports %s after the list as residue', (_name, tail, residue) => {
    const read = ok(FIXTURE.replace('        ],\n', `        ]${tail},\n`));
    expect(read.choices).toEqual(FIXTURE_CHOICES);
    expect(read.residue).toBe(residue);
  });

  // Todo 634: the tail balances parentheses two levels deep and no further. A
  // third level stops the tail at the `(` it cannot balance, so the residue is
  // cut short -- but never empty, so the guard still fails. Pinned so a change
  // to the depth (or a recursive parser) has a case that tells them apart.
  it('cuts a three-level call after the list short, but still reports it', () => {
    const read = ok(FIXTURE.replace('        ],\n', '        ] + list(chain(f(A), B)),\n'));
    expect(read.choices).toEqual(FIXTURE_CHOICES);
    expect(read.residue).toBe('+ list');
  });

  it('ignores a commented-out tuple', () => {
    const read = ok(withLast(LAST + '            # ("dormant", "Dormant"),\n'));
    expect(read.choices).toEqual(FIXTURE_CHOICES);
    expect(read.residue).toBe('');
  });

  // Todo 590: only whole-line comments were dropped, so a valid list with a
  // trailing note failed the guard.
  it('ignores a trailing comment on a tuple line', () => {
    const read = ok(withLast('            ("b", "Bee - two"),  # note, with ("x", "X")\n'));
    expect(read.choices).toEqual(FIXTURE_CHOICES);
    expect(read.residue).toBe('');
  });

  it('keeps a # inside a label', () => {
    const read = ok(withLast('            ("b", "Bee #2"),  # note\n'));
    expect(read.choices).toEqual([
      ['a', 'Ay - one'],
      ['b', 'Bee #2'],
    ]);
    expect(read.residue).toBe('');
  });

  it('parses a Black-exploded tuple with its magic trailing comma', () => {
    const read = ok(
      withLast(
        '            (\n                "b",\n                "Bee - two",\n            ),\n'
      )
    );
    expect(read.choices).toEqual(FIXTURE_CHOICES);
    expect(read.residue).toBe('');
  });

  it('parses a one-line choices list', () => {
    const read = ok(
      '    plant_condition = models.CharField(\n        choices=[("a", "A"), ("b", "B")], blank=True\n    )\n'
    );
    expect(read.choices).toEqual([
      ['a', 'A'],
      ['b', 'B'],
    ]);
    expect(read.residue).toBe('');
  });

  it('does not read the next field when the declaration is a one-liner', () => {
    const source =
      '    plant_condition = models.CharField(max_length=20, blank=True)\n' +
      '    location = models.CharField(\n        choices=[("in", "Indoors")],\n    )\n';
    expect(readInlineChoices(source, 'plant_condition')).toEqual({
      error: 'plant_condition has no inline choices=[...] list',
    });
  });
});
