import { describe, expect, it } from 'vitest';
import { boardTone } from './forumTones';

describe('boardTone', () => {
  it('is deterministic for a given slug', () => {
    expect(boardTone('12-plant-care')).toBe(boardTone('12-plant-care'));
  });
  it('returns a valid TileTone for any slug', () => {
    const valid = ['sage', 'pollen', 'bloom', 'orchid'];
    for (const slug of ['a', 'plant-care', '99-show-and-tell', '']) {
      expect(valid).toContain(boardTone(slug));
    }
  });
});
