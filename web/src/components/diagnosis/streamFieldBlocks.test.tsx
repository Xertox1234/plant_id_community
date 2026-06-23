/**
 * streamFieldBlocks Tests
 *
 * Covers every diagnosis StreamField block renderer plus the unknown-type
 * fallback, driven through the `StreamFieldBlock` registry dispatcher.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { StreamFieldBlock } from './streamFieldBlocks';
import type { DiagnosisBlock } from '@/types';

vi.mock('../../utils/logger', () => ({
  logger: { warn: vi.fn() },
}));

import { logger } from '../../utils/logger';

describe('StreamFieldBlock', () => {
  it('renders a heading block as an h3', () => {
    render(<StreamFieldBlock block={{ type: 'heading', value: 'Care Heading' }} />);
    const heading = screen.getByText('Care Heading');
    expect(heading.tagName).toBe('H3');
  });

  it('renders a paragraph block', () => {
    render(<StreamFieldBlock block={{ type: 'paragraph', value: 'Some guidance text' }} />);
    expect(screen.getByText('Some guidance text')).toBeInTheDocument();
  });

  it('renders a treatment_step block with title, description, and frequency', () => {
    render(
      <StreamFieldBlock
        block={{
          type: 'treatment_step',
          value: { title: 'Apply spray', description: 'Use fungicide', frequency: 'Every 7 days' },
        }}
      />
    );
    expect(screen.getByText('Apply spray')).toBeInTheDocument();
    expect(screen.getByText('Use fungicide')).toBeInTheDocument();
    expect(screen.getByText('Frequency: Every 7 days')).toBeInTheDocument();
  });

  it('omits frequency from a treatment_step block when not provided', () => {
    render(
      <StreamFieldBlock
        block={{
          type: 'treatment_step',
          value: { title: 'Repot', description: 'Move to bigger pot' },
        }}
      />
    );
    expect(screen.getByText('Repot')).toBeInTheDocument();
    expect(screen.queryByText(/Frequency:/)).not.toBeInTheDocument();
  });

  it('renders a symptom_check block', () => {
    render(
      <StreamFieldBlock
        block={{
          type: 'symptom_check',
          value: { symptom: 'Leaf spots', what_to_look_for: 'Brown circular marks' },
        }}
      />
    );
    expect(screen.getByText('Symptom Check: Leaf spots')).toBeInTheDocument();
    expect(screen.getByText('Brown circular marks')).toBeInTheDocument();
  });

  it('renders a prevention_tip block', () => {
    render(<StreamFieldBlock block={{ type: 'prevention_tip', value: 'Water in the morning' }} />);
    expect(screen.getByText('Prevention Tip')).toBeInTheDocument();
    expect(screen.getByText('Water in the morning')).toBeInTheDocument();
  });

  it('renders a list_block with all items', () => {
    render(
      <StreamFieldBlock
        block={{ type: 'list_block', value: { items: ['First', 'Second', 'Third'] } }}
      />
    );
    expect(screen.getByText('First')).toBeInTheDocument();
    expect(screen.getByText('Second')).toBeInTheDocument();
    expect(screen.getByText('Third')).toBeInTheDocument();
  });

  it('renders an image block with src, alt, and caption', () => {
    render(
      <StreamFieldBlock
        block={{
          type: 'image',
          value: {
            url: 'https://example.com/leaf.jpg',
            alt_text: 'Healthy leaf',
            caption: 'A leaf',
          },
        }}
      />
    );
    const img = screen.getByAltText('Healthy leaf');
    expect(img).toHaveAttribute('src', 'https://example.com/leaf.jpg');
    expect(screen.getByText('A leaf')).toBeInTheDocument();
  });

  it('falls back to default alt text and omits caption when absent on an image block', () => {
    const { container } = render(
      <StreamFieldBlock block={{ type: 'image', value: { url: 'https://example.com/x.jpg' } }} />
    );
    expect(screen.getByAltText('Care instruction image')).toBeInTheDocument();
    // No caption provided → the italic caption <p> must not render.
    expect(container.querySelector('p')).toBeNull();
  });

  it('renders nothing and warns for an unknown block type', () => {
    const unknownBlock = { type: 'mystery', value: 'whatever' } as unknown as DiagnosisBlock;
    const { container } = render(<StreamFieldBlock block={unknownBlock} />);
    expect(container.firstChild).toBeNull();
    expect(logger.warn).toHaveBeenCalledWith(
      '[StreamFieldBlock] Unknown block type',
      expect.objectContaining({ component: 'StreamFieldBlock' })
    );
  });

  it('renders nothing for a block type that collides with an Object.prototype key', () => {
    // A plain-object registry inherits prototype members; a 'constructor' type
    // must still hit the guard (not resolve Object.prototype.constructor).
    const protoBlock = { type: 'constructor', value: 'x' } as unknown as DiagnosisBlock;
    const { container } = render(<StreamFieldBlock block={protoBlock} />);
    expect(container.firstChild).toBeNull();
    expect(logger.warn).toHaveBeenCalledWith(
      '[StreamFieldBlock] Unknown block type',
      expect.objectContaining({ component: 'StreamFieldBlock' })
    );
  });
});
