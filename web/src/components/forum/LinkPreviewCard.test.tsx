import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import LinkPreviewCard from './LinkPreviewCard';
import { API_URL } from '@/services/blogService';
import type { LinkPreviewBlockValue } from '@/types/blog';

const FULL_URL = 'https://microsoft.com/en-us/windows/some/long/path?x=1';
const SHORT = 'https://microsoft.com/…';

function card(overrides: Partial<LinkPreviewBlockValue> = {}): LinkPreviewBlockValue {
  return {
    url: FULL_URL,
    title: 'Windows 11',
    description: 'The newest Windows.',
    site_name: 'Microsoft',
    domain: 'microsoft.com',
    image_url: '/media/forum/link-previews/' + 'a'.repeat(64) + '.webp',
    ...overrides,
  };
}

describe('LinkPreviewCard (todo 428)', () => {
  it('shows the shortened address, never the full URL, and opens the link in a new tab', () => {
    const { container } = render(<LinkPreviewCard preview={card()} variant="post" />);

    const link = screen.getByRole('link');
    expect(link).toHaveAttribute('href', FULL_URL);
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    expect(screen.getByText(SHORT)).toBeInTheDocument();
    expect(container.textContent).not.toContain(FULL_URL);
    expect(container.textContent).not.toContain('/en-us/');
  });

  it('carries the full URL in the title attribute, so hovering shows it', () => {
    render(<LinkPreviewCard preview={card()} variant="post" />);

    expect(screen.getByRole('link')).toHaveAttribute('title', FULL_URL);
  });

  it('speaks the title and the short address, never the full URL', () => {
    render(<LinkPreviewCard preview={card()} variant="post" />);

    const link = screen.getByRole('link');
    expect(link).toHaveAccessibleName(`Windows 11, ${SHORT}`);
    // With no description of its own, a link's `title` becomes its
    // accessible description and the full URL would be read out after all.
    expect(link).toHaveAccessibleDescription('Opens in a new tab');
  });

  it('falls back to the short address, not the full URL, when the page gave no title', () => {
    const { container } = render(
      <LinkPreviewCard
        preview={card({ title: '', site_name: '', domain: '', description: '' })}
        variant="post"
      />
    );

    expect(screen.getByRole('link')).toHaveAccessibleName(SHORT);
    expect(container.textContent).not.toContain(FULL_URL);
    // The title already is the address; the address line is not repeated.
    expect(screen.getAllByText(SHORT)).toHaveLength(1);
  });

  it('shows a stored card image from our own media origin', () => {
    const { container } = render(<LinkPreviewCard preview={card()} variant="post" />);

    expect(container.querySelector('img')).toHaveAttribute(
      'src',
      `${API_URL}/media/forum/link-previews/${'a'.repeat(64)}.webp`
    );
  });

  it('renders nothing for a link that is not http(s)', () => {
    const { container } = render(
      <LinkPreviewCard preview={card({ url: 'javascript:alert(1)' })} variant="post" />
    );

    expect(container).toBeEmptyDOMElement();
  });

  it('keeps the composer preview image https-only', () => {
    const { container } = render(
      <LinkPreviewCard preview={card({ image_url: 'http://cdn.example.com/og.png' })} />
    );

    expect(container.querySelector('img')).toBeNull();
  });
});
