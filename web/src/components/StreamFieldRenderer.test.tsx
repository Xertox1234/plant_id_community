/**
 * StreamFieldRenderer Tests
 *
 * Tests for Wagtail StreamField block rendering component.
 * Priority: Phase 1 - Critical security component (XSS protection).
 */

import { describe, it, expect } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import StreamFieldRenderer from './StreamFieldRenderer';
import type { StreamFieldBlock } from '@/types/blog';

describe('StreamFieldRenderer', () => {
  describe('Block anchors (todo 289 / M13)', () => {
    const blocks: StreamFieldBlock[] = [
      { id: 'a', type: 'heading', value: 'Watering' },
      { id: 'b', type: 'paragraph', value: '<p>Less often than you think.</p>' },
    ];

    it('emits block-N ids only when anchorPrefix is given', () => {
      // A RAG citation lands on `#block-<raw_data index>` (the only key present
      // on every page — headings carry no ids and programmatic content has no
      // block uuids). Opt-in per renderer: a thread page mounts one renderer per
      // post, so unconditional ids would collide.
      const { container, unmount } = render(
        <StreamFieldRenderer blocks={blocks} anchorPrefix="block" />
      );
      expect(container.querySelector('#block-0')).toHaveTextContent('Watering');
      expect(container.querySelector('#block-1')).toHaveTextContent('Less often than you think.');
      unmount();

      const plain = render(<StreamFieldRenderer blocks={blocks} />);
      expect(plain.container.querySelector('[id^="block-"]')).toBeNull();
    });
  });

  describe('Basic Rendering', () => {
    it('renders null when blocks array is empty', () => {
      const { container } = render(<StreamFieldRenderer blocks={[]} />);
      expect(container.firstChild).toBeNull();
    });

    it('renders null when blocks is null', () => {
      const { container } = render(<StreamFieldRenderer blocks={null} />);
      expect(container.firstChild).toBeNull();
    });

    it('renders multiple blocks', () => {
      const blocks: StreamFieldBlock[] = [
        { id: '1', type: 'heading', value: 'Heading 1' },
        { id: '2', type: 'heading', value: 'Heading 2' },
      ];

      render(<StreamFieldRenderer blocks={blocks} />);

      expect(screen.getByText('Heading 1')).toBeInTheDocument();
      expect(screen.getByText('Heading 2')).toBeInTheDocument();
    });
  });

  describe('Block Types', () => {
    it('renders heading block', () => {
      const blocks: StreamFieldBlock[] = [{ id: '1', type: 'heading', value: 'Test Heading' }];
      render(<StreamFieldRenderer blocks={blocks} />);

      const heading = screen.getByText('Test Heading');
      expect(heading).toBeInTheDocument();
      expect(heading.tagName).toBe('H2');
    });

    it('renders paragraph block with sanitized HTML', async () => {
      const blocks: StreamFieldBlock[] = [
        { id: '1', type: 'paragraph', value: '<p>Safe paragraph text</p>' },
      ];
      render(<StreamFieldRenderer blocks={blocks} />);

      await waitFor(() => {
        expect(screen.getByText('Safe paragraph text')).toBeInTheDocument();
      });
    });

    it('renders image block as an <img> with the rendition url and alt', () => {
      const blocks: StreamFieldBlock[] = [
        {
          id: '1',
          type: 'image',
          value: { id: 7, url: 'https://cdn.example/img.jpg', alt: 'a seedling' },
        },
      ];
      render(<StreamFieldRenderer blocks={blocks} />);

      const img = screen.getByRole('img', { name: 'a seedling' });
      expect(img).toHaveAttribute('src', 'https://cdn.example/img.jpg');
    });

    it('renders the AUTHORED alt on a post image, and an empty alt stays empty (M7)', () => {
      // Two halves of the same contract. The backend now serves
      // Image.description (what the author typed) and deliberately does NOT
      // fall back to the filename, so an image with no description arrives as
      // alt: "". The renderer must pass that through untouched — a "helpful"
      // fallback here (filename, "image", the post title) would re-introduce
      // exactly the noise M7 removed for screen-reader users.
      const blocks: StreamFieldBlock[] = [
        {
          id: '1',
          type: 'image',
          value: {
            id: 7,
            url: 'https://cdn.example/IMG_2481.jpg',
            alt: 'A monstera leaf with brown edges',
          },
        },
        {
          id: '2',
          type: 'image',
          value: { id: 8, url: 'https://cdn.example/IMG_2482.jpg', alt: '' },
        },
      ];
      render(<StreamFieldRenderer blocks={blocks} />);

      expect(screen.getByRole('img', { name: 'A monstera leaf with brown edges' })).toHaveAttribute(
        'src',
        'https://cdn.example/IMG_2481.jpg'
      );

      // A decorative image is alt="" — presentational to a screen reader, and
      // therefore absent from the accessibility tree entirely.
      const decorative = document.querySelector('img[src="https://cdn.example/IMG_2482.jpg"]');
      expect(decorative).toHaveAttribute('alt', '');
      expect(screen.queryByRole('img', { name: /IMG_2482/ })).not.toBeInTheDocument();
    });

    it('renders quote block with string value', () => {
      const blocks: StreamFieldBlock[] = [{ id: '1', type: 'quote', value: 'Test quote text' }];
      render(<StreamFieldRenderer blocks={blocks} />);

      expect(screen.getByText('Test quote text')).toBeInTheDocument();
    });

    it('renders quote block with object value and attribution', () => {
      const blocks: StreamFieldBlock[] = [
        {
          id: '1',
          type: 'quote',
          value: {
            quote: 'Test quote',
            attribution: 'Author Name',
          },
        },
      ];

      render(<StreamFieldRenderer blocks={blocks} />);

      expect(screen.getByText('Test quote')).toBeInTheDocument();
      expect(screen.getByText('— Author Name')).toBeInTheDocument();
    });

    it('renders quote block with canonical quote_text field', async () => {
      const blocks: StreamFieldBlock[] = [
        {
          id: '1',
          type: 'quote',
          value: {
            quote_text: '<p>Canonical quote</p>',
            attribution: 'Backend Author',
          },
        },
      ];

      render(<StreamFieldRenderer blocks={blocks} />);

      await waitFor(() => {
        expect(screen.getByText('Canonical quote')).toBeInTheDocument();
      });
      expect(screen.getByText('— Backend Author')).toBeInTheDocument();
    });

    it('renders code block', () => {
      const blocks: StreamFieldBlock[] = [
        {
          id: '1',
          type: 'code',
          value: {
            code: 'console.log("test");',
            language: 'javascript',
          },
        },
      ];

      render(<StreamFieldRenderer blocks={blocks} />);

      const codeElement = screen.getByText('console.log("test");');
      expect(codeElement).toBeInTheDocument();
      expect(codeElement.className).toContain('language-javascript');
    });

    it('renders plant_spotlight block with all fields', async () => {
      const blocks: StreamFieldBlock[] = [
        {
          id: '1',
          type: 'plant_spotlight',
          value: {
            heading: 'Monstera Deliciosa',
            description: '<p>A beautiful tropical plant</p>',
            image: {
              id: 1,
              url: 'https://example.com/monstera.jpg',
            },
            care_level: 'Easy',
          },
        },
      ];

      render(<StreamFieldRenderer blocks={blocks} />);

      expect(screen.getByText(/Monstera Deliciosa/)).toBeInTheDocument();
      expect(screen.getByText('Care Level: Easy')).toBeInTheDocument();

      await waitFor(() => {
        expect(screen.getByText('A beautiful tropical plant')).toBeInTheDocument();
      });
    });

    it('renders plant_spotlight block with canonical backend fields', async () => {
      const blocks: StreamFieldBlock[] = [
        {
          id: '1',
          type: 'plant_spotlight',
          value: {
            plant_name: 'Pothos',
            scientific_name: 'Epipremnum aureum',
            description: '<p>Hardy trailing plant</p>',
            image: {
              id: 2,
              url: 'https://example.com/pothos.jpg',
              alt: 'Golden pothos',
            },
            care_difficulty: 'moderate',
          },
        },
      ];

      render(<StreamFieldRenderer blocks={blocks} />);

      expect(screen.getByText(/Pothos/)).toBeInTheDocument();
      expect(screen.getByText('Epipremnum aureum')).toBeInTheDocument();
      expect(screen.getByText('Care Difficulty: Moderate')).toBeInTheDocument();
      expect(screen.getByAltText('Golden pothos')).toHaveAttribute(
        'src',
        'https://example.com/pothos.jpg'
      );

      await waitFor(() => {
        expect(screen.getByText('Hardy trailing plant')).toBeInTheDocument();
      });
    });

    it('renders call_to_action block', () => {
      const blocks: StreamFieldBlock[] = [
        {
          id: '1',
          type: 'call_to_action',
          value: {
            heading: 'Join Us!',
            description: 'Become a member today',
            button_text: 'Sign Up',
            button_url: '/signup',
          },
        },
      ];

      render(<StreamFieldRenderer blocks={blocks} />);

      expect(screen.getByText('Join Us!')).toBeInTheDocument();
      expect(screen.getByText('Become a member today')).toBeInTheDocument();

      const button = screen.getByText('Sign Up');
      expect(button).toBeInTheDocument();
      expect(button.closest('a')).toHaveAttribute('href', '/signup');
    });

    it('renders call_to_action block with canonical backend fields', async () => {
      const blocks: StreamFieldBlock[] = [
        {
          id: '1',
          type: 'call_to_action',
          value: {
            cta_title: 'Start Plant Care',
            cta_description: '<p>Track your garden today</p>',
            button_text: 'Open Planner',
            button_url: '/planner',
            button_style: 'secondary',
          },
        },
      ];

      render(<StreamFieldRenderer blocks={blocks} />);

      expect(screen.getByText('Start Plant Care')).toBeInTheDocument();
      await waitFor(() => {
        expect(screen.getByText('Track your garden today')).toBeInTheDocument();
      });
      expect(screen.getByText('Open Planner').closest('a')).toHaveAttribute('href', '/planner');
    });

    it('does not render an empty call_to_action link when button text is missing', () => {
      const blocks: StreamFieldBlock[] = [
        {
          id: '1',
          type: 'call_to_action',
          value: {
            cta_title: 'Informational CTA',
            cta_description: 'No action required',
            button_url: '/unused',
          },
        },
      ];

      const { container } = render(<StreamFieldRenderer blocks={blocks} />);

      expect(screen.getByText('Informational CTA')).toBeInTheDocument();
      expect(container.querySelector('a')).not.toBeInTheDocument();
    });

    // Removed tests for list and embed blocks (blocks no longer supported - TODO #033)

    it('renders unsupported block type with warning', () => {
      // Deliberately an out-of-union type to exercise the default/fallback path
      // for unknown backend blocks.
      const blocks: StreamFieldBlock[] = [
        {
          id: '1',
          type: 'unknown_block_type',
          value: 'Some value',
        },
      ] as unknown as StreamFieldBlock[];

      render(<StreamFieldRenderer blocks={blocks} />);

      expect(screen.getByText('Unsupported block type')).toBeInTheDocument();
      expect(screen.getByText('unknown_block_type')).toBeInTheDocument();
    });
  });

  describe('XSS Protection', () => {
    it('sanitizes malicious script tags in paragraph blocks', async () => {
      const blocks: StreamFieldBlock[] = [
        {
          id: '1',
          type: 'paragraph',
          value: '<p>Safe text</p><script>alert("XSS")</script>',
        },
      ];

      render(<StreamFieldRenderer blocks={blocks} />);

      await waitFor(() => {
        expect(screen.getByText('Safe text')).toBeInTheDocument();
      });

      // Script should be removed
      expect(screen.queryByText(/alert.*XSS/)).not.toBeInTheDocument();
    });

    it('neutralizes script/onerror payloads in string-shaped quote blocks', async () => {
      // Audit 2026-07-11 M32: quote blocks arrive VERBATIM from the backend
      // (plain-text-by-contract; only paragraphs are nh3-cleaned server-side)
      // and are reachable via direct API POST — the renderer's `<`-heuristic
      // DOMPurify path is the only defense and was previously untested.
      const blocks: StreamFieldBlock[] = [
        {
          id: 'q1',
          type: 'quote',
          value: '<script>alert(1)</script><img src="x" onerror="alert(2)">quoted text',
        },
      ];

      const { container } = render(<StreamFieldRenderer blocks={blocks} />);

      await waitFor(() => {
        expect(screen.getByText(/quoted text/)).toBeInTheDocument();
      });
      expect(container.querySelector('script')).toBeNull();
      expect(container.querySelector('[onerror]')).toBeNull();
    });

    it('renders heading and code payloads as inert escaped text', () => {
      // Heading/code render as plain JSX children — React escapes them; pin it.
      const blocks: StreamFieldBlock[] = [
        { id: 'h1', type: 'heading', value: '<img src=x onerror=alert(4)>' },
        {
          id: 'c1',
          type: 'code',
          value: { language: 'html', code: '<script>alert(5)</script>' },
        },
      ];

      const { container } = render(<StreamFieldRenderer blocks={blocks} />);

      expect(container.querySelector('script')).toBeNull();
      expect(container.querySelector('[onerror]')).toBeNull();
      // The literal payload text is displayed (escaped), not executed.
      expect(container.textContent).toContain('<img src=x onerror=alert(4)>');
      expect(container.textContent).toContain('<script>alert(5)</script>');
    });

    it('sanitizes malicious onclick attributes', async () => {
      const blocks: StreamFieldBlock[] = [
        {
          id: '1',
          type: 'paragraph',
          value: '<p onclick="alert(\'XSS\')">Click me</p>',
        },
      ];

      const { container } = render(<StreamFieldRenderer blocks={blocks} />);

      await waitFor(() => {
        const paragraph = container.querySelector('p');
        expect(paragraph).not.toHaveAttribute('onclick');
      });
    });

    it('sanitizes malicious iframe tags in paragraph', async () => {
      const blocks: StreamFieldBlock[] = [
        {
          id: '1',
          type: 'paragraph',
          value: '<p>Text</p><iframe src="javascript:alert(\'XSS\')"></iframe>',
        },
      ];

      render(<StreamFieldRenderer blocks={blocks} />);

      await waitFor(() => {
        expect(screen.getByText('Text')).toBeInTheDocument();
      });

      // Iframe should be removed or sanitized
      const iframes = document.querySelectorAll('iframe');
      iframes.forEach((iframe) => {
        expect(iframe.src).not.toContain('javascript:');
      });
    });

    it('sanitizes XSS in plant_spotlight description', async () => {
      const blocks: StreamFieldBlock[] = [
        {
          id: '1',
          type: 'plant_spotlight',
          value: {
            heading: 'Test Plant',
            description: '<script>alert("XSS")</script><p>Safe description</p>',
          },
        },
      ];

      render(<StreamFieldRenderer blocks={blocks} />);

      await waitFor(() => {
        expect(screen.getByText('Safe description')).toBeInTheDocument();
      });

      expect(screen.queryByText(/alert.*XSS/)).not.toBeInTheDocument();
    });

    it('allows safe HTML tags in paragraph', async () => {
      const blocks: StreamFieldBlock[] = [
        {
          id: '1',
          type: 'paragraph',
          value: '<p><strong>Bold</strong> and <em>italic</em> text</p>',
        },
      ];

      render(<StreamFieldRenderer blocks={blocks} />);

      await waitFor(() => {
        expect(screen.getByText('Bold')).toBeInTheDocument();
        expect(screen.getByText('italic')).toBeInTheDocument();
      });
    });

    it('preserves safe embedded images in paragraph StreamField rich text', async () => {
      const blocks: StreamFieldBlock[] = [
        {
          id: '1',
          type: 'paragraph',
          value:
            '<p>Plant photo</p><img src="https://example.com/plant.jpg" alt="Healthy plant" title="Plant" />',
        },
      ];

      render(<StreamFieldRenderer blocks={blocks} />);

      await waitFor(() => {
        expect(screen.getByAltText('Healthy plant')).toHaveAttribute(
          'src',
          'https://example.com/plant.jpg'
        );
      });
    });

    it('sanitizes unsafe embedded image URLs in paragraph StreamField rich text', async () => {
      const blocks: StreamFieldBlock[] = [
        {
          id: '1',
          type: 'paragraph',
          value: '<p>Plant photo</p><img src="javascript:alert(1)" alt="Unsafe plant" />',
        },
      ];

      render(<StreamFieldRenderer blocks={blocks} />);

      await waitFor(() => {
        const image = screen.getByAltText('Unsafe plant');
        expect(image).not.toHaveAttribute('src', expect.stringContaining('javascript:'));
      });
    });
  });

  describe('Edge Cases', () => {
    // Removed tests for image and list blocks (no longer supported - TODO #033)

    it('handles quote with only attribution', () => {
      const blocks: StreamFieldBlock[] = [
        {
          id: '1',
          type: 'quote',
          value: {
            attribution: 'Author Only',
          },
        },
      ];

      render(<StreamFieldRenderer blocks={blocks} />);

      expect(screen.getByText('— Author Only')).toBeInTheDocument();
    });

    it('handles blocks without IDs (uses index as key)', () => {
      const blocks: StreamFieldBlock[] = [
        { type: 'heading', value: 'Heading 1' },
        { type: 'heading', value: 'Heading 2' },
      ];

      render(<StreamFieldRenderer blocks={blocks} />);

      expect(screen.getByText('Heading 1')).toBeInTheDocument();
      expect(screen.getByText('Heading 2')).toBeInTheDocument();
    });

    it('handles code block without language', () => {
      const blocks: StreamFieldBlock[] = [
        {
          id: '1',
          type: 'code',
          value: {
            code: 'plain text code',
          },
        },
      ];

      render(<StreamFieldRenderer blocks={blocks} />);

      const codeElement = screen.getByText('plain text code');
      expect(codeElement.className).toContain('language-text');
    });

    // Removed test for embed block (no longer supported - TODO #033)
  });

  describe('Mention highlighting', () => {
    it('styles mentions in paragraphs when mentionHighlight is set', () => {
      const { container } = render(
        <StreamFieldRenderer
          blocks={[{ type: 'paragraph', value: '<p>Thanks @bob_botanist!</p>' }]}
          mentionHighlight
        />
      );
      const span = container.querySelector('span.text-primary.font-medium');
      expect(span?.textContent).toBe('@bob_botanist');
    });
  });

  describe('Forum allowlist tightening (M32)', () => {
    it('keeps forum-allowed marks but strips headings/img in forum paragraphs', () => {
      const { container } = render(
        <StreamFieldRenderer
          blocks={[
            {
              type: 'paragraph',
              value:
                '<h1>Big</h1><strong>bold</strong> <a href="https://x.example">link</a> <img src="https://x.example/p.jpg" alt="pic">',
            },
          ]}
          mentionHighlight
        />
      );
      // nh3-allowed marks survive.
      expect(container.querySelector('strong')?.textContent).toBe('bold');
      expect(container.querySelector('a')?.getAttribute('href')).toBe('https://x.example');
      // Headings and inline images are dropped to match the server allowlist;
      // the heading's text is kept (unwrapped), the image has none.
      expect(container.querySelector('h1')).toBeNull();
      expect(container.querySelector('img')).toBeNull();
      expect(container.textContent).toContain('Big');
    });

    it('leaves blog paragraphs on the broad STREAMFIELD allowlist (img preserved)', () => {
      const { container } = render(
        <StreamFieldRenderer
          blocks={[
            {
              type: 'paragraph',
              value: '<p>x</p><img src="https://x.example/p.jpg" alt="pic">',
            },
          ]}
        />
      );
      // No mentionHighlight → blog path → the inline image survives, proving the
      // tightening is forum-scoped and did not regress blog rendering.
      expect(container.querySelector('img')?.getAttribute('src')).toBe('https://x.example/p.jpg');
    });
  });

  describe('Performance', () => {
    it('renders many blocks efficiently', () => {
      const blocks: StreamFieldBlock[] = Array.from({ length: 50 }, (_, i) => ({
        id: `${i}`,
        type: 'heading' as const,
        value: `Heading ${i}`,
      }));

      const { container } = render(<StreamFieldRenderer blocks={blocks} />);

      const headings = container.querySelectorAll('h2');
      expect(headings).toHaveLength(50);
    });
  });

  describe('Forum quote blocks (todo 276 / audit M1)', () => {
    // The composer now emits `quote` (forumBody.ts lifts a top-level blockquote
    // into its own block), so this value is no longer direct-POST-only. The
    // server still leaves it unsanitized ("text by contract", api/sanitize.py),
    // so the FORUM path must escape it rather than run it through the broad blog
    // STREAMFIELD DOMPurify preset.
    it('renders a forum quote as escaped text, never as markup', () => {
      const blocks: StreamFieldBlock[] = [
        { id: 'q1', type: 'quote', value: '<script>alert(1)</script><b>bold</b>' },
      ];

      const { container } = render(<StreamFieldRenderer blocks={blocks} mentionHighlight />);

      // Visible as literal characters...
      expect(screen.getByText('<script>alert(1)</script><b>bold</b>')).toBeInTheDocument();
      // ...having produced no live nodes.
      expect(container.querySelector('script')).toBeNull();
      expect(container.querySelector('b')).toBeNull();
    });

    it('preserves the paragraph joins forumBody.ts writes into a quote value', () => {
      const blocks: StreamFieldBlock[] = [{ id: 'q2', type: 'quote', value: 'one\n\ntwo' }];

      const { container } = render(<StreamFieldRenderer blocks={blocks} mentionHighlight />);

      // whitespace-pre-line is what renders the "\n\n" join as two lines rather
      // than collapsing it to "one two".
      const quote = container.querySelector('blockquote div');
      expect(quote?.className).toContain('whitespace-pre-line');
      expect(quote?.textContent).toBe('one\n\ntwo');
    });

    it('leaves the BLOG quote path on rich text (trusted Wagtail editors)', () => {
      // No mentionHighlight -> blog content keeps the sanitized-HTML path, so
      // the forum fix must not regress blog rendering.
      const blocks: StreamFieldBlock[] = [{ id: 'q3', type: 'quote', value: '<em>styled</em>' }];

      const { container } = render(<StreamFieldRenderer blocks={blocks} />);

      expect(container.querySelector('em')).not.toBeNull();
    });
  });
});
