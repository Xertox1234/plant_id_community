import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import IdentificationCard from './IdentificationCard';
import type { ThreadIdentification } from '@/types';

const IDENTIFICATION: ThreadIdentification = {
  image: {
    id: 7,
    url: 'http://localhost:8000/media/images/plant.jpg',
    // Post-M7 the backend never sends a filename here: `alt` is the author's
    // own text or "". "" is the common case for an identification photo.
    alt: '',
    width: 800,
    height: 600,
  },
  provider: 'plant_id',
  candidates: [
    { name: 'Swiss cheese plant', scientific_name: 'Monstera deliciosa', confidence: 0.82 },
    {
      name: 'Heartleaf philodendron',
      scientific_name: 'Philodendron hederaceum',
      confidence: 0.11,
    },
  ],
  created_at: '2026-07-31T10:00:00Z',
};

describe('IdentificationCard', () => {
  it('lists every candidate with its confidence as a percentage', () => {
    render(<IdentificationCard identification={IDENTIFICATION} />);

    expect(screen.getByText('Swiss cheese plant')).toBeInTheDocument();
    expect(screen.getByText('Monstera deliciosa')).toBeInTheDocument();
    expect(screen.getByText('82%')).toBeInTheDocument();
    // The runner-up is shown too — the card must not present one guess as
    // the answer.
    expect(screen.getByText('Heartleaf philodendron')).toBeInTheDocument();
    expect(screen.getByText('11%')).toBeInTheDocument();
  });

  it('says the suggestion is unconfirmed, and names the provider', () => {
    render(<IdentificationCard identification={IDENTIFICATION} />);

    expect(screen.getByText(/not a confirmed identification/i)).toBeInTheDocument();
    expect(screen.getByText(/plant_id/)).toBeInTheDocument();
  });

  it('describes the photo by its role when the author supplied no alt (M7)', () => {
    render(<IdentificationCard identification={IDENTIFICATION} />);

    const img = screen.getByRole('img');
    expect(img).toHaveAttribute('src', IDENTIFICATION.image!.url);
    // An identification photo has exactly one role on the page, so naming that
    // role beats silence when there is nothing authored to say.
    expect(img).toHaveAccessibleName('Photo the author submitted for identification');
  });

  it('prefers the author-supplied alt over the role fallback (M7)', () => {
    render(
      <IdentificationCard
        identification={{
          ...IDENTIFICATION,
          image: { ...IDENTIFICATION.image!, alt: 'A yellowing monstera leaf with brown spots' },
        }}
      />
    );

    // Before M7 this position held the upload filename, which is why the card
    // hardcoded a role sentence. Now that it carries the author's own words,
    // they win — they say what the role sentence cannot.
    expect(screen.getByRole('img')).toHaveAccessibleName(
      'A yellowing monstera leaf with brown spots'
    );
  });

  it('falls back to text-only when the photo is gone (SET_NULL)', () => {
    render(<IdentificationCard identification={{ ...IDENTIFICATION, image: null }} />);

    expect(screen.queryByRole('img')).not.toBeInTheDocument();
    // The candidates — the reason the card exists — still render.
    expect(screen.getByText('Swiss cheese plant')).toBeInTheDocument();
  });

  it('omits the provider parenthetical when the backend sent none', () => {
    render(<IdentificationCard identification={{ ...IDENTIFICATION, provider: '' }} />);

    expect(screen.getByText(/Suggested by the Plant ID app/)).toBeInTheDocument();
    expect(screen.queryByText(/\(\)/)).not.toBeInTheDocument();
  });

  it('links to the accepted answer once the topic is solved', () => {
    render(<IdentificationCard identification={IDENTIFICATION} solvedPostId={99} />);

    const link = screen.getByRole('link', { name: /see the accepted answer/i });
    expect(link).toHaveAttribute('href', '#post-99');
  });

  it('shows no answer link while the topic is unsolved', () => {
    render(<IdentificationCard identification={IDENTIFICATION} solvedPostId={null} />);

    expect(screen.queryByRole('link', { name: /accepted answer/i })).not.toBeInTheDocument();
  });

  it('is a labelled landmark, not an anonymous div', () => {
    render(<IdentificationCard identification={IDENTIFICATION} />);

    expect(screen.getByRole('region', { name: /what the app suggested/i })).toBeInTheDocument();
  });
});
