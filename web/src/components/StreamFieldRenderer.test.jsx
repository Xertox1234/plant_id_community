/**
 * StreamFieldRenderer Tests
 *
 * Tests for Wagtail StreamField block rendering component.
 * Priority: Phase 1 - Critical security component (XSS protection).
 */

import { describe, it, expect } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import StreamFieldRenderer from './StreamFieldRenderer';

describe('StreamFieldRenderer', () => {
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
      const blocks = [
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
      const blocks = [{ id: '1', type: 'heading', value: 'Test Heading' }];
      render(<StreamFieldRenderer blocks={blocks} />);

      const heading = screen.getByText('Test Heading');
      expect(heading).toBeInTheDocument();
      expect(heading.tagName).toBe('H2');
    });

    it('renders paragraph block with sanitized HTML', async () => {
      const blocks = [
        { id: '1', type: 'paragraph', value: '<p>Safe paragraph text</p>' },
      ];
      render(<StreamFieldRenderer blocks={blocks} />);

      await waitFor(() => {
        expect(screen.getByText('Safe paragraph text')).toBeInTheDocument();
      });
    });

    // Removed tests for image block (block no longer supported - TODO #033)

    it('renders quote block with string value', () => {
      const blocks = [{ id: '1', type: 'quote', value: 'Test quote text' }];
      render(<StreamFieldRenderer blocks={blocks} />);

      expect(screen.getByText('Test quote text')).toBeInTheDocument();
    });

    it('renders quote block with object value and attribution', () => {
      const blocks = [
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

    it('renders code block', () => {
      const blocks = [
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
      const blocks = [
        {
          id: '1',
          type: 'plant_spotlight',
          value: {
            heading: 'Monstera Deliciosa',
            description: '<p>A beautiful tropical plant</p>',
            image: {
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

    it('renders call_to_action block', () => {
      const blocks = [
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

    // Removed tests for list and embed blocks (blocks no longer supported - TODO #033)

    it('renders unsupported block type with warning', () => {
      const blocks = [
        {
          id: '1',
          type: 'unknown_block_type',
          value: 'Some value',
        },
      ];

      render(<StreamFieldRenderer blocks={blocks} />);

      expect(screen.getByText('Unsupported block type')).toBeInTheDocument();
      expect(screen.getByText('unknown_block_type')).toBeInTheDocument();
    });
  });

  describe('XSS Protection', () => {
    it('sanitizes malicious script tags in paragraph blocks', async () => {
      const blocks = [
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

    it('sanitizes malicious onclick attributes', async () => {
      const blocks = [
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
      const blocks = [
        {
          id: '1',
          type: 'paragraph',
          value:
            '<p>Text</p><iframe src="javascript:alert(\'XSS\')"></iframe>',
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
      const blocks = [
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
      const blocks = [
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
  });

  describe('Edge Cases', () => {
    // Removed tests for image and list blocks (no longer supported - TODO #033)

    it('handles quote with only attribution', () => {
      const blocks = [
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
      const blocks = [
        { type: 'heading', value: 'Heading 1' },
        { type: 'heading', value: 'Heading 2' },
      ];

      render(<StreamFieldRenderer blocks={blocks} />);

      expect(screen.getByText('Heading 1')).toBeInTheDocument();
      expect(screen.getByText('Heading 2')).toBeInTheDocument();
    });

    it('handles code block without language', () => {
      const blocks = [
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

  describe('Performance', () => {
    it('renders many blocks efficiently', () => {
      const blocks = Array.from({ length: 50 }, (_, i) => ({
        id: `${i}`,
        type: 'heading',
        value: `Heading ${i}`,
      }));

      const { container } = render(<StreamFieldRenderer blocks={blocks} />);

      const headings = container.querySelectorAll('h2');
      expect(headings).toHaveLength(50);
    });
  });
});
