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
  it('passes a clean file', () => {
    const files = [{ name: 'c.md', text: '# Title\n\nBody' }];
    expect(findUnpublishable(files)).toEqual([]);
  });
});
