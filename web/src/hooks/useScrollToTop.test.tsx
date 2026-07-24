import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { useScrollToTop } from './useScrollToTop';

function Probe() {
  useScrollToTop();
  return null;
}

const scrollSpy = vi.fn();

describe('useScrollToTop', () => {
  beforeEach(() => {
    window.scrollTo = scrollSpy;
    scrollSpy.mockClear();
  });

  it('scrolls to the top on navigation when there is no hash (M31)', () => {
    render(
      <MemoryRouter initialEntries={['/forum/3-plant-care']}>
        <Probe />
      </MemoryRouter>
    );
    expect(scrollSpy).toHaveBeenCalledWith({ top: 0, behavior: 'auto' });
  });

  it('does not scroll when the URL carries a hash so deep links still work', () => {
    render(
      <MemoryRouter initialEntries={['/forum/3-plant-care/12-x#post-5']}>
        <Probe />
      </MemoryRouter>
    );
    expect(scrollSpy).not.toHaveBeenCalled();
  });
});
