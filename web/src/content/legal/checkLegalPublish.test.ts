import { describe, it, expect } from 'vitest';
import { findUnpublishable } from '../../../scripts/check-legal-publish.mjs';

describe('findUnpublishable', () => {
  it('flags a file with a placeholder', () => {
    const files = [{ name: 'a.md', text: 'Hello [[COMPANY_NAME]]' }];
    expect(findUnpublishable(files)).toEqual(['a.md']);
  });
  it('flags a file with the DRAFT line', () => {
    const files = [{ name: 'b.md', text: '> DRAFT — pending legal review\n\n# T' }];
    expect(findUnpublishable(files)).toEqual(['b.md']);
  });
  it.each([
    ['a translated banner', '> BORRADOR — pendiente de revisión legal\n\n# T'],
    ['a French banner', '> **BROUILLON** — en attente\n\n# T'],
    ['a reworded banner', 'DRAFT: not final\n\n# T'],
  ])('flags %s', (_label, text) => {
    expect(findUnpublishable([{ name: 'd.md', text }])).toEqual(['d.md']);
  });
  it('does not flag a bare [[ in prose or a lower-case word', () => {
    const text = '# T\n\nUse [[ and ]] in examples. A brouillon is a draft.\nNo DRAFTING here.';
    expect(findUnpublishable([{ name: 'e.md', text }])).toEqual([]);
  });
  it('flags every shipped placeholder name', () => {
    for (const p of ['[[COMPANY_NAME]]', '[[PRIVACY_OFFICER_NAME]]', '[[GOVERNING_LAW]]']) {
      expect(findUnpublishable([{ name: 'f.md', text: `x ${p} y` }])).toEqual(['f.md']);
    }
  });
  it('passes a clean file', () => {
    const files = [{ name: 'c.md', text: '# Title\n\nBody' }];
    expect(findUnpublishable(files)).toEqual([]);
  });
});
