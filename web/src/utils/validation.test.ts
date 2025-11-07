import { describe, it, expect } from 'vitest';
import {
  validateSlug,
  validateToken,
  validateContentType,
  sanitizeSearchQuery,
  validateEmail,
  validateUrl,
  validateInteger,
  validatePagination,
  validateCategorySlug,
  validateFileType,
} from './validation';

describe('validation utilities', () => {
  describe('validateSlug', () => {
    it('should accept valid slugs', () => {
      expect(validateSlug('my-blog-post')).toBe('my-blog-post');
      expect(validateSlug('post-2025')).toBe('post-2025');
      expect(validateSlug('my_blog_post')).toBe('my_blog_post');
      expect(validateSlug('post-123-test')).toBe('post-123-test');
      expect(validateSlug('a')).toBe('a'); // Single character
      expect(validateSlug('A-B-C')).toBe('A-B-C'); // Mixed case
    });

    it('should reject null or undefined', () => {
      expect(() => validateSlug(null)).toThrow('Slug is required and must be a string');
      expect(() => validateSlug(undefined)).toThrow('Slug is required and must be a string');
    });

    it('should reject empty string', () => {
      expect(() => validateSlug('')).toThrow('Slug is required and must be a string');
    });

    it('should reject non-string types', () => {
      expect(() => validateSlug(123 as unknown as string)).toThrow('Slug is required and must be a string');
      expect(() => validateSlug({} as unknown as string)).toThrow('Slug is required and must be a string');
      expect(() => validateSlug([] as unknown as string)).toThrow('Slug is required and must be a string');
    });

    it('should reject slugs exceeding 200 characters', () => {
      const longSlug = 'a'.repeat(201);
      expect(() => validateSlug(longSlug)).toThrow('Slug is too long (maximum 200 characters)');
    });

    it('should accept slugs exactly 200 characters', () => {
      const exactSlug = 'a'.repeat(200);
      expect(validateSlug(exactSlug)).toBe(exactSlug);
    });

    it('should reject special characters', () => {
      expect(() => validateSlug('my-post!')).toThrow('Invalid slug format');
      expect(() => validateSlug('my@post')).toThrow('Invalid slug format');
      expect(() => validateSlug('my#post')).toThrow('Invalid slug format');
      expect(() => validateSlug('my$post')).toThrow('Invalid slug format');
      expect(() => validateSlug('my%post')).toThrow('Invalid slug format');
      expect(() => validateSlug('my post')).toThrow('Invalid slug format'); // Space
    });

    it('should reject path traversal patterns', () => {
      expect(() => validateSlug('../admin')).toThrow('Invalid slug: path traversal patterns are not allowed');
      expect(() => validateSlug('..\\admin')).toThrow('Invalid slug: path traversal patterns are not allowed');
      expect(() => validateSlug('post/../etc')).toThrow('Invalid slug: path traversal patterns are not allowed');
      expect(() => validateSlug('/etc/passwd')).toThrow('Invalid slug: path traversal patterns are not allowed');
      expect(() => validateSlug('C:\\Windows')).toThrow('Invalid slug: path traversal patterns are not allowed');
    });

    it('should reject suspicious patterns', () => {
      expect(() => validateSlug('---')).toThrow('Invalid slug: suspicious pattern detected');
      expect(() => validateSlug('___')).toThrow('Invalid slug: suspicious pattern detected');
      expect(() => validateSlug('post---test')).toThrow('Invalid slug: suspicious pattern detected');
      expect(() => validateSlug('post___test')).toThrow('Invalid slug: suspicious pattern detected');
    });

    it('should reject XSS attempts', () => {
      // <script> tags contain '/' which triggers path traversal check
      expect(() => validateSlug('<script>alert(1)</script>')).toThrow('Invalid slug: path traversal patterns are not allowed');
      expect(() => validateSlug('javascript:alert(1)')).toThrow('Invalid slug format');
      expect(() => validateSlug('onload=alert(1)')).toThrow('Invalid slug format');
    });

    it('should reject SQL injection attempts', () => {
      expect(() => validateSlug("'; DROP TABLE users--")).toThrow('Invalid slug format');
      expect(() => validateSlug('1 OR 1=1')).toThrow('Invalid slug format');
    });
  });

  describe('validateToken', () => {
    it('should accept valid UUID v4 tokens', () => {
      const validTokens = [
        '550e8400-e29b-41d4-a716-446655440000',
        '123e4567-e89b-42d3-a456-426614174000',
        'c73bcdcc-2669-4bf6-81d3-e4ae73fb11fd',
        'C73BCDCC-2669-4BF6-81D3-E4AE73FB11FD', // Uppercase
      ];

      validTokens.forEach((token) => {
        expect(validateToken(token)).toBe(token);
      });
    });

    it('should reject null or undefined', () => {
      expect(() => validateToken(null)).toThrow('Token is required and must be a string');
      expect(() => validateToken(undefined)).toThrow('Token is required and must be a string');
    });

    it('should reject empty string', () => {
      expect(() => validateToken('')).toThrow('Token is required and must be a string');
    });

    it('should reject non-UUID formats', () => {
      expect(() => validateToken('not-a-uuid')).toThrow('Invalid token format: must be a valid UUID v4');
      expect(() => validateToken('12345678-1234-1234-1234-123456789abc')).toThrow(
        'Invalid token format: must be a valid UUID v4'
      );
      expect(() => validateToken('550e8400e29b41d4a716446655440000')).toThrow(
        'Invalid token format: must be a valid UUID v4'
      ); // Missing hyphens
    });

    it('should reject UUID v1 format (not v4)', () => {
      // UUID v1 has different version/variant bits
      expect(() => validateToken('550e8400-e29b-11d4-a716-446655440000')).toThrow(
        'Invalid token format: must be a valid UUID v4'
      );
    });

    it('should reject tokens with wrong length', () => {
      expect(() => validateToken('550e8400-e29b-41d4-a716-44665544000')).toThrow(
        'Invalid token format: must be a valid UUID v4'
      ); // Too short
      expect(() => validateToken('550e8400-e29b-41d4-a716-4466554400000')).toThrow(
        'Invalid token format: must be a valid UUID v4'
      ); // Too long
    });

    it('should reject path traversal attempts', () => {
      expect(() => validateToken('../admin')).toThrow('Invalid token format: must be a valid UUID v4');
    });

    it('should reject XSS attempts', () => {
      expect(() => validateToken('<script>alert(1)</script>')).toThrow(
        'Invalid token format: must be a valid UUID v4'
      );
    });
  });

  describe('validateContentType', () => {
    it('should accept valid content types', () => {
      expect(validateContentType('blog.BlogPostPage')).toBe('blog.BlogPostPage');
      expect(validateContentType('app.Model')).toBe('app.Model');
      expect(validateContentType('my_app.MyModel')).toBe('my_app.MyModel');
      expect(validateContentType('app1.model2')).toBe('app1.model2');
    });

    it('should reject null or undefined', () => {
      expect(() => validateContentType(null)).toThrow('Content type is required and must be a string');
      expect(() => validateContentType(undefined)).toThrow('Content type is required and must be a string');
    });

    it('should reject empty string', () => {
      expect(() => validateContentType('')).toThrow('Content type is required and must be a string');
    });

    it('should reject content types exceeding 100 characters', () => {
      const longType = 'a'.repeat(101);
      expect(() => validateContentType(longType)).toThrow('Content type is too long (maximum 100 characters)');
    });

    it('should reject special characters', () => {
      expect(() => validateContentType('blog!Post')).toThrow('Invalid content type format');
      expect(() => validateContentType('blog@Post')).toThrow('Invalid content type format');
      expect(() => validateContentType('blog-Post')).toThrow('Invalid content type format');
      expect(() => validateContentType('blog_Post')).toThrow('Invalid content type format'); // Underscore not allowed
      expect(() => validateContentType('blog Post')).toThrow('Invalid content type format'); // Space
    });

    it('should require app.model format (must contain dot)', () => {
      expect(() => validateContentType('BlogPostPage')).toThrow(
        'Invalid content type format: must be in app.model format'
      );
      expect(() => validateContentType('blogpostpage')).toThrow(
        'Invalid content type format: must be in app.model format'
      );
    });

    it('should reject path traversal patterns', () => {
      expect(() => validateContentType('../etc/passwd')).toThrow(
        'Invalid content type: path traversal patterns are not allowed'
      );
      expect(() => validateContentType('blog..admin')).toThrow(
        'Invalid content type: path traversal patterns are not allowed'
      );
      expect(() => validateContentType('blog/Post')).toThrow(
        'Invalid content type: path traversal patterns are not allowed'
      );
      expect(() => validateContentType('blog\\Post')).toThrow(
        'Invalid content type: path traversal patterns are not allowed'
      );
    });

    it('should reject XSS attempts', () => {
      // <script> tags contain '/' which triggers path traversal check
      expect(() => validateContentType('<script>.alert</script>')).toThrow('Invalid content type: path traversal patterns are not allowed');
      expect(() => validateContentType('javascript:alert(1)')).toThrow('Invalid content type format');
    });
  });

  describe('sanitizeSearchQuery', () => {
    it('should return sanitized query for valid input', () => {
      expect(sanitizeSearchQuery('hello world')).toBe('hello world');
      expect(sanitizeSearchQuery('plant care')).toBe('plant care');
      expect(sanitizeSearchQuery('123 test')).toBe('123 test');
    });

    it('should trim whitespace', () => {
      expect(sanitizeSearchQuery('  hello world  ')).toBe('hello world');
      expect(sanitizeSearchQuery('\thello\t')).toBe('hello');
      expect(sanitizeSearchQuery('\nhello\n')).toBe('hello');
    });

    it('should remove control characters', () => {
      expect(sanitizeSearchQuery('hello\x00world')).toBe('helloworld');
      expect(sanitizeSearchQuery('test\x01query')).toBe('testquery');
      expect(sanitizeSearchQuery('test\x7Fquery')).toBe('testquery');
    });

    it('should limit length to 200 characters', () => {
      const longQuery = 'a'.repeat(300);
      const result = sanitizeSearchQuery(longQuery);
      expect(result.length).toBe(200);
    });

    it('should return empty string for null or undefined', () => {
      expect(sanitizeSearchQuery(null)).toBe('');
      expect(sanitizeSearchQuery(undefined)).toBe('');
    });

    it('should return empty string for empty input', () => {
      expect(sanitizeSearchQuery('')).toBe('');
    });

    it('should return empty string for non-string types', () => {
      expect(sanitizeSearchQuery(123 as unknown as string)).toBe('');
      expect(sanitizeSearchQuery({} as unknown as string)).toBe('');
      expect(sanitizeSearchQuery([] as unknown as string)).toBe('');
    });

    it('should preserve special characters (not a validator, just sanitizer)', () => {
      expect(sanitizeSearchQuery('hello-world')).toBe('hello-world');
      expect(sanitizeSearchQuery('hello@world.com')).toBe('hello@world.com');
      expect(sanitizeSearchQuery('50%')).toBe('50%');
    });

    it('should handle unicode characters', () => {
      expect(sanitizeSearchQuery('café')).toBe('café');
      expect(sanitizeSearchQuery('你好')).toBe('你好');
      expect(sanitizeSearchQuery('🌱')).toBe('🌱');
    });
  });

  describe('validateEmail', () => {
    it('should accept valid email addresses', () => {
      expect(validateEmail('user@example.com')).toBe('user@example.com');
      expect(validateEmail('test.user@example.com')).toBe('test.user@example.com');
      expect(validateEmail('user+tag@example.co.uk')).toBe('user+tag@example.co.uk');
      expect(validateEmail('user_123@example-domain.com')).toBe('user_123@example-domain.com');
    });

    it('should convert to lowercase', () => {
      expect(validateEmail('User@Example.Com')).toBe('user@example.com');
      expect(validateEmail('TEST@EXAMPLE.COM')).toBe('test@example.com');
    });

    it('should trim whitespace', () => {
      expect(validateEmail('  user@example.com  ')).toBe('user@example.com');
      expect(validateEmail('\tuser@example.com\n')).toBe('user@example.com');
    });

    it('should reject null or undefined', () => {
      expect(() => validateEmail(null)).toThrow('Email is required and must be a string');
      expect(() => validateEmail(undefined)).toThrow('Email is required and must be a string');
    });

    it('should reject empty string', () => {
      expect(() => validateEmail('')).toThrow('Email is required and must be a string');
    });

    it('should reject invalid formats', () => {
      expect(() => validateEmail('invalid')).toThrow('Invalid email address format');
      expect(() => validateEmail('invalid@')).toThrow('Invalid email address format');
      expect(() => validateEmail('@example.com')).toThrow('Invalid email address format');
      expect(() => validateEmail('user@')).toThrow('Invalid email address format');
      expect(() => validateEmail('user@example')).toThrow('Invalid email address format'); // No TLD
    });

    it('should reject emails with spaces', () => {
      expect(() => validateEmail('user @example.com')).toThrow('Invalid email address format');
      expect(() => validateEmail('user@ example.com')).toThrow('Invalid email address format');
      expect(() => validateEmail('user@example .com')).toThrow('Invalid email address format');
    });

    it('should reject multiple @ signs', () => {
      expect(() => validateEmail('user@@example.com')).toThrow('Invalid email address format');
      expect(() => validateEmail('user@example@com')).toThrow('Invalid email address format');
    });
  });

  describe('validateUrl', () => {
    it('should accept valid HTTP URLs', () => {
      expect(validateUrl('http://example.com')).toBe('http://example.com');
      expect(validateUrl('http://example.com/path')).toBe('http://example.com/path');
      expect(validateUrl('http://example.com:8080')).toBe('http://example.com:8080');
    });

    it('should accept valid HTTPS URLs', () => {
      expect(validateUrl('https://example.com')).toBe('https://example.com');
      expect(validateUrl('https://example.com/path/to/page')).toBe('https://example.com/path/to/page');
      expect(validateUrl('https://sub.example.com')).toBe('https://sub.example.com');
    });

    it('should reject null or undefined', () => {
      expect(() => validateUrl(null)).toThrow('URL is required and must be a string');
      expect(() => validateUrl(undefined)).toThrow('URL is required and must be a string');
    });

    it('should reject empty string', () => {
      expect(() => validateUrl('')).toThrow('URL is required and must be a string');
    });

    it('should reject invalid URL formats', () => {
      expect(() => validateUrl('not-a-url')).toThrow('Invalid URL format');
      expect(() => validateUrl('example.com')).toThrow('Invalid URL format'); // Missing protocol
      expect(() => validateUrl('://example.com')).toThrow('Invalid URL format');
    });

    it('should reject javascript: URLs (XSS)', () => {
      expect(() => validateUrl('javascript:alert(1)')).toThrow(
        'Invalid URL protocol: only HTTP and HTTPS are allowed'
      );
    });

    it('should reject data: URLs (XSS)', () => {
      expect(() => validateUrl('data:text/html,<script>alert(1)</script>')).toThrow(
        'Invalid URL protocol: only HTTP and HTTPS are allowed'
      );
    });

    it('should reject file: URLs (SSRF)', () => {
      expect(() => validateUrl('file:///etc/passwd')).toThrow(
        'Invalid URL protocol: only HTTP and HTTPS are allowed'
      );
    });

    it('should reject ftp: URLs', () => {
      expect(() => validateUrl('ftp://example.com')).toThrow(
        'Invalid URL protocol: only HTTP and HTTPS are allowed'
      );
    });

    it('should enforce HTTPS-only mode when enabled', () => {
      expect(() => validateUrl('http://example.com', true)).toThrow('Only HTTPS URLs are allowed');
      expect(validateUrl('https://example.com', true)).toBe('https://example.com');
    });

    it('should allow HTTP when HTTPS-only is disabled', () => {
      expect(validateUrl('http://example.com', false)).toBe('http://example.com');
      expect(validateUrl('https://example.com', false)).toBe('https://example.com');
    });
  });

  describe('validateInteger', () => {
    it('should accept valid integers as strings', () => {
      expect(validateInteger('42')).toBe(42);
      expect(validateInteger('0')).toBe(0);
      expect(validateInteger('-10')).toBe(-10);
      expect(validateInteger('100')).toBe(100);
    });

    it('should accept valid integers as numbers', () => {
      expect(validateInteger(42)).toBe(42);
      expect(validateInteger(0)).toBe(0);
      expect(validateInteger(-10)).toBe(-10);
    });

    it('should reject floats', () => {
      expect(() => validateInteger(3.14)).toThrow('Value must be a valid integer');
      expect(() => validateInteger('3.14')).toThrow('Value must be a valid integer');
      expect(() => validateInteger(42.5)).toThrow('Value must be a valid integer');
    });

    it('should reject NaN', () => {
      expect(() => validateInteger(NaN)).toThrow('Value must be a valid integer');
      expect(() => validateInteger('abc')).toThrow('Value must be a valid integer');
    });

    it('should reject null or undefined', () => {
      expect(() => validateInteger(null)).toThrow('Value must be a valid integer');
      expect(() => validateInteger(undefined)).toThrow('Value must be a valid integer');
    });

    it('should enforce minimum bound', () => {
      expect(() => validateInteger(5, { min: 10 })).toThrow('Value must be at least 10');
      expect(validateInteger(10, { min: 10 })).toBe(10);
      expect(validateInteger(15, { min: 10 })).toBe(15);
    });

    it('should enforce maximum bound', () => {
      expect(() => validateInteger(15, { max: 10 })).toThrow('Value must be at most 10');
      expect(validateInteger(10, { max: 10 })).toBe(10);
      expect(validateInteger(5, { max: 10 })).toBe(5);
    });

    it('should enforce both min and max bounds', () => {
      expect(() => validateInteger(0, { min: 1, max: 100 })).toThrow('Value must be at least 1');
      expect(() => validateInteger(101, { min: 1, max: 100 })).toThrow('Value must be at most 100');
      expect(validateInteger(50, { min: 1, max: 100 })).toBe(50);
    });

    it('should handle edge cases for bounds', () => {
      expect(validateInteger(0, { min: 0 })).toBe(0);
      expect(validateInteger(-1, { max: 0 })).toBe(-1);
      expect(validateInteger(0, { min: 0, max: 0 })).toBe(0);
    });
  });

  describe('validatePagination', () => {
    it('should accept valid pagination parameters', () => {
      const result = validatePagination({ page: '1', limit: '10' });
      expect(result).toEqual({ page: 1, limit: 10 });
    });

    it('should accept numbers as well as strings', () => {
      const result = validatePagination({ page: 2, limit: 20 });
      expect(result).toEqual({ page: 2, limit: 20 });
    });

    it('should enforce page minimum of 1', () => {
      expect(() => validatePagination({ page: '0', limit: '10' })).toThrow('Value must be at least 1');
      expect(() => validatePagination({ page: '-1', limit: '10' })).toThrow('Value must be at least 1');
    });

    it('should enforce page maximum of 10000', () => {
      expect(() => validatePagination({ page: '10001', limit: '10' })).toThrow('Value must be at most 10000');
    });

    it('should enforce limit minimum of 1', () => {
      expect(() => validatePagination({ page: '1', limit: '0' })).toThrow('Value must be at least 1');
    });

    it('should enforce limit maximum of 100', () => {
      expect(() => validatePagination({ page: '1', limit: '101' })).toThrow('Value must be at most 100');
    });

    it('should accept edge case values', () => {
      const result1 = validatePagination({ page: '1', limit: '1' });
      expect(result1).toEqual({ page: 1, limit: 1 });

      const result2 = validatePagination({ page: '10000', limit: '100' });
      expect(result2).toEqual({ page: 10000, limit: 100 });
    });

    it('should reject invalid page values', () => {
      expect(() => validatePagination({ page: 'abc', limit: '10' })).toThrow('Value must be a valid integer');
    });

    it('should reject invalid limit values', () => {
      expect(() => validatePagination({ page: '1', limit: 'xyz' })).toThrow('Value must be a valid integer');
    });
  });

  describe('validateCategorySlug', () => {
    it('should accept valid category slugs', () => {
      expect(validateCategorySlug('plant-care')).toBe('plant-care');
      expect(validateCategorySlug('indoor-plants')).toBe('indoor-plants');
      expect(validateCategorySlug('category_123')).toBe('category_123');
    });

    it('should reject invalid slugs (uses same validation as validateSlug)', () => {
      expect(() => validateCategorySlug('../admin')).toThrow(
        'Invalid slug: path traversal patterns are not allowed'
      );
      // <script> tags contain '/' which triggers path traversal check
      expect(() => validateCategorySlug('<script>alert(1)</script>')).toThrow('Invalid slug: path traversal patterns are not allowed');
      expect(() => validateCategorySlug('invalid slug')).toThrow('Invalid slug format'); // Space
    });

    it('should reject null or undefined', () => {
      expect(() => validateCategorySlug(null)).toThrow('Slug is required and must be a string');
      expect(() => validateCategorySlug(undefined)).toThrow('Slug is required and must be a string');
    });
  });

  describe('validateFileType', () => {
    it('should accept valid file types', () => {
      expect(validateFileType('image.jpg', ['jpg', 'png', 'webp'])).toBe('image.jpg');
      expect(validateFileType('photo.png', ['jpg', 'png', 'webp'])).toBe('photo.png');
      expect(validateFileType('picture.WEBP', ['jpg', 'png', 'webp'])).toBe('picture.WEBP');
    });

    it('should be case-insensitive for extensions', () => {
      expect(validateFileType('IMAGE.JPG', ['jpg', 'png'])).toBe('IMAGE.JPG');
      expect(validateFileType('photo.PNG', ['jpg', 'png'])).toBe('photo.PNG');
      expect(validateFileType('file.JpG', ['jpg', 'png'])).toBe('file.JpG');
    });

    it('should reject null or undefined filename', () => {
      expect(() => validateFileType(null, ['jpg'])).toThrow('Filename is required and must be a string');
      expect(() => validateFileType(undefined, ['jpg'])).toThrow('Filename is required and must be a string');
    });

    it('should reject empty filename', () => {
      expect(() => validateFileType('', ['jpg'])).toThrow('Filename is required and must be a string');
    });

    it('should reject invalid allowed extensions', () => {
      expect(() => validateFileType('image.jpg', null)).toThrow('Allowed extensions must be a non-empty array');
      expect(() => validateFileType('image.jpg', [])).toThrow('Allowed extensions must be a non-empty array');
      expect(() => validateFileType('image.jpg', 'jpg' as unknown as string[])).toThrow('Allowed extensions must be a non-empty array');
    });

    it('should reject disallowed file types', () => {
      expect(() => validateFileType('script.js', ['jpg', 'png'])).toThrow(
        'Invalid file type: only jpg, png files are allowed'
      );
      expect(() => validateFileType('malware.exe', ['jpg', 'png'])).toThrow(
        'Invalid file type: only jpg, png files are allowed'
      );
    });

    it('should reject files without extension', () => {
      expect(() => validateFileType('noextension', ['jpg', 'png'])).toThrow(
        'Invalid file type: only jpg, png files are allowed'
      );
    });

    it('should handle multiple dots in filename', () => {
      expect(validateFileType('my.photo.jpg', ['jpg', 'png'])).toBe('my.photo.jpg');
      expect(() => validateFileType('my.photo.exe', ['jpg', 'png'])).toThrow(
        'Invalid file type: only jpg, png files are allowed'
      );
    });

    it('should handle hidden files', () => {
      expect(validateFileType('.hidden.jpg', ['jpg', 'png'])).toBe('.hidden.jpg');
      expect(() => validateFileType('.hidden.exe', ['jpg', 'png'])).toThrow(
        'Invalid file type: only jpg, png files are allowed'
      );
    });
  });

  describe('security attack vectors', () => {
    it('should prevent path traversal in slugs', () => {
      const attacks = [
        '../../../etc/passwd',
        '..\\..\\..\\windows\\system32',
        'post/../../admin',
        'post\\..\\..\\admin',
      ];

      attacks.forEach((attack) => {
        expect(() => validateSlug(attack)).toThrow();
      });
    });

    it('should prevent XSS in all validators', () => {
      const xssAttacks = [
        '<script>alert(1)</script>',
        'javascript:alert(1)',
        'onerror=alert(1)',
        '<img src=x onerror=alert(1)>',
        '<svg onload=alert(1)>',
      ];

      xssAttacks.forEach((attack) => {
        expect(() => validateSlug(attack)).toThrow();
        expect(() => validateContentType(attack)).toThrow();
        expect(() => validateEmail(attack)).toThrow();
      });
    });

    it('should prevent SSRF via URL validation', () => {
      const ssrfAttacks = [
        'file:///etc/passwd',
        'file://C:/Windows/System32',
        'ftp://internal.server',
        'gopher://internal.server',
      ];

      ssrfAttacks.forEach((attack) => {
        expect(() => validateUrl(attack)).toThrow('Invalid URL protocol');
      });
    });

    it('should prevent SQL injection in slugs', () => {
      const sqlInjections = [
        "'; DROP TABLE users--",
        "1' OR '1'='1",
        'admin\' --',
        '1 UNION SELECT * FROM users',
      ];

      sqlInjections.forEach((injection) => {
        expect(() => validateSlug(injection)).toThrow();
      });
    });

    it('should prevent double extension attacks in file validation', () => {
      expect(() => validateFileType('malware.jpg.exe', ['jpg', 'png'])).toThrow(
        'Invalid file type: only jpg, png files are allowed'
      );
    });

    it('should prevent null byte injection', () => {
      expect(sanitizeSearchQuery('test\x00injection')).toBe('testinjection');
      expect(() => validateSlug('test\x00injection')).toThrow('Invalid slug format');
    });
  });

  describe('edge cases', () => {
    it('should handle unicode in slugs correctly', () => {
      // Only ASCII letters, numbers, hyphens, underscores allowed
      expect(() => validateSlug('café')).toThrow('Invalid slug format');
      expect(() => validateSlug('植物')).toThrow('Invalid slug format');
    });

    it('should handle very long but valid inputs', () => {
      const longSlug = 'a'.repeat(200);
      expect(validateSlug(longSlug)).toBe(longSlug);

      const longQuery = 'a'.repeat(300);
      expect(sanitizeSearchQuery(longQuery).length).toBe(200);
    });

    it('should handle boundary values for integers', () => {
      expect(validateInteger(Number.MAX_SAFE_INTEGER)).toBe(Number.MAX_SAFE_INTEGER);
      expect(validateInteger(Number.MIN_SAFE_INTEGER)).toBe(Number.MIN_SAFE_INTEGER);
      expect(() => validateInteger(Infinity)).toThrow('Value must be a valid integer');
      expect(() => validateInteger(-Infinity)).toThrow('Value must be a valid integer');
    });

    it('should handle whitespace-only inputs', () => {
      // Whitespace-only strings become empty after trim, so "required" error is correct
      expect(() => validateSlug('   ')).toThrow('Slug is required and must be a string');
      expect(sanitizeSearchQuery('   ')).toBe('');
      expect(() => validateEmail('   ')).toThrow('Email is required and must be a string');
    });
  });
});
