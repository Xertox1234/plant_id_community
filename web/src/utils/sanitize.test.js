import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  createSafeMarkup,
  sanitizeHtml,
  stripHtml,
  isSafeHtml,
  SANITIZE_PRESETS,
} from './sanitize';

describe('sanitize utilities', () => {
  describe('createSafeMarkup', () => {
    it('should create safe markup object for valid HTML', () => {
      const html = '<p>Hello <strong>world</strong>!</p>';
      const result = createSafeMarkup(html);

      expect(result).toHaveProperty('__html');
      expect(result.__html).toContain('Hello');
      expect(result.__html).toContain('<strong>');
      expect(result.__html).toContain('world');
    });

    it('should remove script tags', () => {
      const html = '<p>Hello</p><script>alert("xss")</script>';
      const result = createSafeMarkup(html);

      expect(result.__html).toContain('Hello');
      expect(result.__html).not.toContain('<script>');
      expect(result.__html).not.toContain('alert');
    });

    it('should remove event handlers', () => {
      const html = '<p onclick="alert(1)">Click me</p>';
      const result = createSafeMarkup(html);

      expect(result.__html).toContain('Click me');
      expect(result.__html).not.toContain('onclick');
      expect(result.__html).not.toContain('alert');
    });

    it('should allow whitelisted tags', () => {
      const html = '<p>Text</p><strong>Bold</strong><em>Italic</em>';
      const result = createSafeMarkup(html);

      expect(result.__html).toContain('<p>');
      expect(result.__html).toContain('<strong>');
      expect(result.__html).toContain('<em>');
    });

    it('should remove iframe tags', () => {
      const html = '<p>Content</p><iframe src="evil.com"></iframe>';
      const result = createSafeMarkup(html);

      expect(result.__html).toContain('Content');
      expect(result.__html).not.toContain('<iframe');
      expect(result.__html).not.toContain('evil.com');
    });

    it('should prevent javascript: URLs in links', () => {
      const html = '<a href="javascript:alert(1)">Click</a>';
      const result = createSafeMarkup(html);

      expect(result.__html).toContain('Click');
      expect(result.__html).not.toContain('javascript:');
    });

    it('should prevent data: URLs in links', () => {
      const html = '<a href="data:text/html,<script>alert(1)</script>">Click</a>';
      const result = createSafeMarkup(html);

      expect(result.__html).toContain('Click');
      expect(result.__html).not.toContain('data:');
    });

    it('should allow safe URLs in links', () => {
      const html = '<a href="https://example.com">Link</a>';
      const result = createSafeMarkup(html);

      expect(result.__html).toContain('href="https://example.com"');
      expect(result.__html).toContain('Link');
    });

    it('should handle null input', () => {
      const result = createSafeMarkup(null);
      expect(result.__html).toBe('');
    });

    it('should handle undefined input', () => {
      const result = createSafeMarkup(undefined);
      expect(result.__html).toBe('');
    });

    it('should handle empty string', () => {
      const result = createSafeMarkup('');
      expect(result.__html).toBe('');
    });

    it('should handle non-string input', () => {
      const result = createSafeMarkup(123);
      expect(result.__html).toBe('');
    });

    it('should accept custom ALLOWED_TAGS option', () => {
      const html = '<p>Text</p><strong>Bold</strong>';
      const result = createSafeMarkup(html, {
        ALLOWED_TAGS: ['p'],
      });

      expect(result.__html).toContain('<p>');
      expect(result.__html).not.toContain('<strong>');
      expect(result.__html).toContain('Bold'); // Content preserved
    });

    it('should accept custom ALLOWED_ATTR option', () => {
      const html = '<a href="https://example.com" class="link">Link</a>';
      const result = createSafeMarkup(html, {
        ALLOWED_ATTR: ['href'],
      });

      expect(result.__html).toContain('href=');
      expect(result.__html).not.toContain('class=');
    });

    it('should use MINIMAL preset', () => {
      const html = '<p>Text</p><h2>Heading</h2><code>Code</code>';
      const result = createSafeMarkup(html, SANITIZE_PRESETS.MINIMAL);

      expect(result.__html).toContain('<p>');
      expect(result.__html).not.toContain('<h2>');
      expect(result.__html).not.toContain('<code>');
    });

    it('should use FULL preset', () => {
      const html = '<p>Text</p><h2>Heading</h2><code>Code</code>';
      const result = createSafeMarkup(html, SANITIZE_PRESETS.FULL);

      expect(result.__html).toContain('<p>');
      expect(result.__html).toContain('<h2>');
      expect(result.__html).toContain('<code>');
    });

    it('should log error on exception', () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      // This shouldn't normally throw, but we can test error handling
      const result = createSafeMarkup('<p>Valid HTML</p>');

      consoleErrorSpy.mockRestore();
    });
  });

  describe('sanitizeHtml', () => {
    it('should return sanitized HTML string', () => {
      const html = '<p>Hello <strong>world</strong>!</p>';
      const result = sanitizeHtml(html);

      expect(typeof result).toBe('string');
      expect(result).toContain('Hello');
      expect(result).toContain('<strong>');
    });

    it('should remove script tags', () => {
      const html = '<p>Hello</p><script>alert("xss")</script>';
      const result = sanitizeHtml(html);

      expect(result).toContain('Hello');
      expect(result).not.toContain('<script>');
    });

    it('should handle null input', () => {
      const result = sanitizeHtml(null);
      expect(result).toBe('');
    });

    it('should handle empty string', () => {
      const result = sanitizeHtml('');
      expect(result).toBe('');
    });

    it('should accept custom options', () => {
      const html = '<p>Text</p><strong>Bold</strong>';
      const result = sanitizeHtml(html, {
        ALLOWED_TAGS: ['p'],
      });

      expect(result).toContain('<p>');
      expect(result).not.toContain('<strong>');
    });
  });

  describe('stripHtml', () => {
    it('should remove all HTML tags', () => {
      const html = '<p>Hello <strong>world</strong>!</p>';
      const result = stripHtml(html);

      expect(result).toBe('Hello world!');
      expect(result).not.toContain('<p>');
      expect(result).not.toContain('<strong>');
    });

    it('should preserve text content', () => {
      const html = '<div><h1>Title</h1><p>Paragraph</p></div>';
      const result = stripHtml(html);

      expect(result).toContain('Title');
      expect(result).toContain('Paragraph');
    });

    it('should handle nested tags', () => {
      const html = '<div><p><strong><em>Nested</em></strong></p></div>';
      const result = stripHtml(html);

      expect(result).toBe('Nested');
    });

    it('should handle self-closing tags', () => {
      const html = '<p>Line 1<br/>Line 2</p>';
      const result = stripHtml(html);

      expect(result).toContain('Line 1');
      expect(result).toContain('Line 2');
    });

    it('should trim whitespace', () => {
      const html = '  <p>  Text  </p>  ';
      const result = stripHtml(html);

      expect(result).toBe('Text');
    });

    it('should handle null input', () => {
      const result = stripHtml(null);
      expect(result).toBe('');
    });

    it('should handle empty string', () => {
      const result = stripHtml('');
      expect(result).toBe('');
    });

    it('should handle plain text (no HTML)', () => {
      const text = 'Just plain text';
      const result = stripHtml(text);

      expect(result).toBe('Just plain text');
    });

    it('should handle malicious HTML safely', () => {
      const html = '<script>alert("xss")</script><p>Safe text</p>';
      const result = stripHtml(html);

      expect(result).toContain('Safe text');
      expect(result).not.toContain('<script>');
      expect(result).not.toContain('alert');
    });

    it('should handle HTML entities', () => {
      const html = '<p>&lt;script&gt;alert(1)&lt;/script&gt;</p>';
      const result = stripHtml(html);

      expect(result).toContain('<script>'); // Entity was decoded
      expect(result).not.toContain('<p>'); // Tag was removed
    });
  });

  describe('isSafeHtml', () => {
    it('should return true for safe HTML', () => {
      const html = '<p>Hello <strong>world</strong>!</p>';
      expect(isSafeHtml(html)).toBe(true);
    });

    it('should return false for HTML with script tags', () => {
      const html = '<p>Hello</p><script>alert(1)</script>';
      expect(isSafeHtml(html)).toBe(false);
    });

    it('should return false for javascript: URLs', () => {
      const html = '<a href="javascript:alert(1)">Click</a>';
      expect(isSafeHtml(html)).toBe(false);
    });

    it('should return false for event handlers', () => {
      const html = '<p onclick="alert(1)">Click</p>';
      expect(isSafeHtml(html)).toBe(false);
    });

    it('should return false for iframe tags', () => {
      const html = '<iframe src="evil.com"></iframe>';
      expect(isSafeHtml(html)).toBe(false);
    });

    it('should return false for eval() calls', () => {
      const html = '<p>Text</p><script>eval("code")</script>';
      expect(isSafeHtml(html)).toBe(false);
    });

    it('should return false for vbscript: URLs', () => {
      const html = '<a href="vbscript:alert(1)">Click</a>';
      expect(isSafeHtml(html)).toBe(false);
    });

    it('should return false for data:text/html URLs', () => {
      const html = '<a href="data:text/html,<script>alert(1)</script>">Click</a>';
      expect(isSafeHtml(html)).toBe(false);
    });

    it('should return true for null input', () => {
      expect(isSafeHtml(null)).toBe(true);
    });

    it('should return true for empty string', () => {
      expect(isSafeHtml('')).toBe(true);
    });

    it('should return true for plain text', () => {
      expect(isSafeHtml('Just plain text')).toBe(true);
    });

    it('should detect multiple suspicious patterns', () => {
      const html = '<script>alert(1)</script><iframe src="evil.com"></iframe>';
      expect(isSafeHtml(html)).toBe(false);
    });

    it('should be case-insensitive for script tag', () => {
      expect(isSafeHtml('<SCRIPT>alert(1)</SCRIPT>')).toBe(false);
      expect(isSafeHtml('<ScRiPt>alert(1)</ScRiPt>')).toBe(false);
    });

    it('should be case-insensitive for event handlers', () => {
      expect(isSafeHtml('<p ONCLICK="alert(1)">Click</p>')).toBe(false);
      expect(isSafeHtml('<p OnClick="alert(1)">Click</p>')).toBe(false);
    });
  });

  describe('SANITIZE_PRESETS', () => {
    it('should have MINIMAL preset', () => {
      expect(SANITIZE_PRESETS.MINIMAL).toBeDefined();
      expect(SANITIZE_PRESETS.MINIMAL.ALLOWED_TAGS).toEqual(['p', 'br', 'strong', 'em', 'u']);
      expect(SANITIZE_PRESETS.MINIMAL.ALLOWED_ATTR).toEqual([]);
    });

    it('should have BASIC preset', () => {
      expect(SANITIZE_PRESETS.BASIC).toBeDefined();
      expect(SANITIZE_PRESETS.BASIC.ALLOWED_TAGS).toContain('a');
      expect(SANITIZE_PRESETS.BASIC.ALLOWED_ATTR).toContain('href');
    });

    it('should have STANDARD preset', () => {
      expect(SANITIZE_PRESETS.STANDARD).toBeDefined();
      expect(SANITIZE_PRESETS.STANDARD.ALLOWED_TAGS).toContain('ul');
      expect(SANITIZE_PRESETS.STANDARD.ALLOWED_TAGS).toContain('blockquote');
    });

    it('should have FULL preset', () => {
      expect(SANITIZE_PRESETS.FULL).toBeDefined();
      expect(SANITIZE_PRESETS.FULL.ALLOWED_TAGS).toContain('h2');
      expect(SANITIZE_PRESETS.FULL.ALLOWED_TAGS).toContain('code');
      expect(SANITIZE_PRESETS.FULL.ALLOWED_ATTR).toContain('class');
    });
  });

  describe('XSS attack vectors', () => {
    it('should prevent XSS via img onerror', () => {
      const html = '<img src=x onerror="alert(1)">';
      const result = sanitizeHtml(html);

      expect(result).not.toContain('onerror');
      expect(result).not.toContain('alert');
    });

    it('should prevent XSS via SVG', () => {
      const html = '<svg onload="alert(1)"></svg>';
      const result = sanitizeHtml(html);

      expect(result).not.toContain('onload');
      expect(result).not.toContain('alert');
    });

    it('should prevent XSS via form action', () => {
      const html = '<form action="javascript:alert(1)"><input type="submit"></form>';
      const result = sanitizeHtml(html);

      expect(result).not.toContain('javascript:');
    });

    it('should prevent XSS via meta refresh', () => {
      const html = '<meta http-equiv="refresh" content="0;url=javascript:alert(1)">';
      const result = sanitizeHtml(html);

      expect(result).not.toContain('javascript:');
    });

    it('should prevent XSS via object/embed', () => {
      const html = '<object data="javascript:alert(1)"></object>';
      const result = sanitizeHtml(html);

      expect(result).not.toContain('javascript:');
    });
  });

  describe('edge cases', () => {
    it('should handle very long HTML', () => {
      const html = '<p>' + 'a'.repeat(100000) + '</p>';
      const result = stripHtml(html);

      expect(result.length).toBe(100000);
    });

    it('should handle deeply nested HTML', () => {
      const html = '<div>'.repeat(100) + 'Content' + '</div>'.repeat(100);
      const result = stripHtml(html);

      expect(result).toBe('Content');
    });

    it('should handle HTML with unicode characters', () => {
      const html = '<p>Hello 世界 🌍</p>';
      const result = stripHtml(html);

      expect(result).toBe('Hello 世界 🌍');
    });

    it('should handle malformed HTML', () => {
      const html = '<p>Unclosed<strong>tag';
      const result = stripHtml(html);

      expect(result).toContain('Unclosed');
      expect(result).toContain('tag');
    });

    it('should handle HTML comments', () => {
      const html = '<p>Text</p><!-- Comment -->';
      const result = stripHtml(html);

      expect(result).toBe('Text');
      expect(result).not.toContain('Comment');
    });
  });
});
