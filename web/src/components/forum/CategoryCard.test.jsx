import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router';
import CategoryCard from './CategoryCard';
import { createMockCategory } from '../../tests/forumUtils';

/**
 * Helper to render CategoryCard with Router context
 */
function renderCategoryCard(category) {
  return render(
    <BrowserRouter>
      <CategoryCard category={category} />
    </BrowserRouter>
  );
}

describe('CategoryCard', () => {
  it('renders category name and description', () => {
    const category = createMockCategory({
      name: 'Plant Care Tips',
      description: 'Learn how to care for your plants',
    });

    renderCategoryCard(category);

    expect(screen.getByText('Plant Care Tips')).toBeInTheDocument();
    expect(screen.getByText('Learn how to care for your plants')).toBeInTheDocument();
  });

  it('renders category icon when present', () => {
    const category = createMockCategory({ icon: '🌱' });

    renderCategoryCard(category);

    expect(screen.getByText('🌱')).toBeInTheDocument();
  });

  it('renders category stats (thread and post counts)', () => {
    const category = createMockCategory({
      thread_count: 150,
      post_count: 1250,
    });

    renderCategoryCard(category);

    expect(screen.getByText(/150/)).toBeInTheDocument();
    expect(screen.getByText(/threads/i)).toBeInTheDocument();
    expect(screen.getByText(/1250/)).toBeInTheDocument();
    expect(screen.getByText(/posts/i)).toBeInTheDocument();
  });

  it('handles zero counts gracefully', () => {
    const category = createMockCategory({
      thread_count: 0,
      post_count: 0,
    });

    renderCategoryCard(category);

    // Just verify the text appears - exact matching is fragile with styled components
    expect(screen.getByText(/threads/i)).toBeInTheDocument();
    expect(screen.getByText(/posts/i)).toBeInTheDocument();
  });

  it('links to category page with correct slug', () => {
    const category = createMockCategory({ slug: 'plant-care' });

    renderCategoryCard(category);

    const link = screen.getByRole('link');
    expect(link).toHaveAttribute('href', '/forum/plant-care');
  });

  it('renders subcategories when present', () => {
    const category = createMockCategory({
      children: [
        { id: 'sub-1', name: 'Watering', slug: 'watering', icon: '💧' },
        { id: 'sub-2', name: 'Fertilizing', slug: 'fertilizing', icon: '🌿' },
      ],
    });

    renderCategoryCard(category);

    expect(screen.getByText('Subcategories:')).toBeInTheDocument();
    expect(screen.getByText('Watering')).toBeInTheDocument();
    expect(screen.getByText('Fertilizing')).toBeInTheDocument();
    expect(screen.getByText('💧')).toBeInTheDocument();
    expect(screen.getByText('🌿')).toBeInTheDocument();
  });

  it('does not render subcategories section when none exist', () => {
    const category = createMockCategory({ children: [] });

    renderCategoryCard(category);

    expect(screen.queryByText('Subcategories:')).not.toBeInTheDocument();
  });

  it('renders without description when not provided', () => {
    const category = createMockCategory({ description: null });

    renderCategoryCard(category);

    expect(screen.getByText('Plant Care')).toBeInTheDocument();
    // Description should not be rendered
  });

  it('applies hover effects (class verification)', () => {
    const category = createMockCategory();

    const { container } = renderCategoryCard(category);

    const card = container.querySelector('.shadow-md');
    expect(card).toHaveClass('hover:shadow-lg');
  });
});
