import { describe, it, expect } from 'vitest';
import { slugifyTitle, parseLeadingId, categoryPath, threadPath, postAnchor } from './forumUrls';
import type { Category, Thread } from '../types/forum';

describe('forumUrls', () => {
  it('slugifies titles', () => {
    expect(slugifyTitle('How to care for Succulents?!')).toBe('how-to-care-for-succulents');
    expect(slugifyTitle('  Multiple   spaces ')).toBe('multiple-spaces');
    expect(slugifyTitle('')).toBe('topic');
  });

  it('parses the leading integer id from an id-slug param', () => {
    expect(parseLeadingId('12-how-to-care')).toBe(12);
    expect(parseLeadingId('7')).toBe(7);
    expect(parseLeadingId('not-a-number')).toBeNull();
  });

  it('builds id-anchored category and thread paths', () => {
    const category = { id: '3', name: 'Plant Care', slug: 'plant-care' } as Category;
    const thread = {
      id: '12',
      title: 'Succulent help',
      slug: 'succulent-help',
      category,
    } as Thread;
    expect(categoryPath(category)).toBe('/forum/3-plant-care');
    expect(threadPath(category, thread)).toBe('/forum/3-plant-care/12-succulent-help');
  });

  it('postAnchor builds a #post-N fragment', () => {
    expect(postAnchor(42)).toBe('#post-42');
    expect(postAnchor('42')).toBe('#post-42');
  });
});
