import { describe, it, expect } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import PageMeta from './PageMeta';

describe('PageMeta', () => {
  it('sets document.title', async () => {
    render(<PageMeta title="Test Title · PlantID" />);
    await waitFor(() => expect(document.title).toBe('Test Title · PlantID'));
  });

  it('renders a meta description', async () => {
    render(<PageMeta title="X" description="A helpful description" />);
    await waitFor(() =>
      expect(document.querySelector('meta[name="description"]')?.getAttribute('content')).toBe(
        'A helpful description'
      )
    );
  });

  it('renders OG tags when og is provided', async () => {
    render(<PageMeta title="X" og={{ title: 'OG Title', url: 'https://x/y', type: 'article' }} />);
    await waitFor(() => {
      expect(document.querySelector('meta[property="og:title"]')?.getAttribute('content')).toBe(
        'OG Title'
      );
      expect(document.querySelector('meta[property="og:url"]')?.getAttribute('content')).toBe(
        'https://x/y'
      );
      expect(document.querySelector('meta[property="og:type"]')?.getAttribute('content')).toBe(
        'article'
      );
    });
  });

  it('omits OG tags when og is not provided', () => {
    render(<PageMeta title="No OG · PlantID" />);
    expect(document.querySelector('meta[property="og:title"]')).toBeNull();
  });
});
