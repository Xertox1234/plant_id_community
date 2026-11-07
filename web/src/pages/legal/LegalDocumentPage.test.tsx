import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import LegalDocumentPage from './LegalDocumentPage';

// Override hook: null means "use the real markdown".
let override: string | null = null;
vi.mock('../../content/legal', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../content/legal')>();
  return {
    ...actual,
    getLegalMarkdown: (...args: Parameters<typeof actual.getLegalMarkdown>) =>
      override ?? actual.getLegalMarkdown(...args),
  };
});

afterEach(() => {
  override = null;
});

function renderAt(url: string) {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route path="/privacy" element={<LegalDocumentPage doc="privacy" />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('LegalDocumentPage', () => {
  it('renders the French H1 at ?lang=fr', () => {
    renderAt('/privacy?lang=fr');
    expect(
      screen.getByRole('heading', { level: 1, name: /politique de confidentialité/i })
    ).toBeInTheDocument();
  });

  it('links the switcher to ?lang=en|fr|es', () => {
    renderAt('/privacy?lang=en');
    expect(screen.getByRole('link', { name: 'English' })).toHaveAttribute(
      'href',
      '/privacy?lang=en'
    );
    expect(screen.getByRole('link', { name: 'Français' })).toHaveAttribute(
      'href',
      '/privacy?lang=fr'
    );
    expect(screen.getByRole('link', { name: 'Español' })).toHaveAttribute(
      'href',
      '/privacy?lang=es'
    );
  });

  it('strips a <script> from the markdown', () => {
    override = '# Hi\n\n<script>window.__pwned = 1</script>\n\nSafe text';
    const { container } = renderAt('/privacy?lang=en');
    expect(container.querySelector('script')).toBeNull();
    expect(screen.getByText('Safe text')).toBeInTheDocument();
  });

  it('shows the policy version in a footer line', () => {
    renderAt('/privacy?lang=en');
    expect(screen.getByText('Version 2026-11-06')).toBeInTheDocument();
  });

  it('omits the footer when the document has no version comment', () => {
    override = '# Hi';
    renderAt('/privacy?lang=en');
    expect(screen.queryByText(/^Version /)).toBeNull();
  });
});
