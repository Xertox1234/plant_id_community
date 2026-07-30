import { memo } from 'react';
import { Link } from 'react-router-dom';
import Timestamp from '../ui/Timestamp';
import { categoryPath } from '../../utils/forumUrls';
import type { Category } from '@/types';

interface CategoryCardProps {
  category: Category;
}

/**
 * CategoryCard Component
 *
 * Displays a forum category with stats and subcategories.
 * Used in category list view.
 */
function CategoryCard({ category }: CategoryCardProps) {
  const hasChildren = category.children && category.children.length > 0;

  return (
    <div className="bg-surface-2 rounded-lg shadow-md hover:shadow-lg transition-shadow p-6">
      {/* Category Header - Clickable Link */}
      <Link to={categoryPath(category)} className="block">
        <div className="flex items-start gap-4">
          {/* Icon */}
          {category.icon && (
            <div className="text-4xl" aria-hidden="true">
              {category.icon}
            </div>
          )}

          {/* Category Info */}
          <div className="flex-1">
            <h3 className="text-xl font-bold text-ink hover:text-primary transition-colors">
              {category.name}
            </h3>

            {category.description && <p className="text-ink-2 mt-1">{category.description}</p>}

            {/* Stats */}
            <div className="flex flex-wrap gap-x-4 gap-y-1 mt-3 text-sm text-ink-3">
              <span>
                <strong className="text-ink-2">{category.thread_count || 0}</strong> threads
              </span>
              <span aria-hidden="true">•</span>
              <span>
                <strong className="text-ink-2">{category.post_count || 0}</strong> posts
              </span>
              <span aria-hidden="true">•</span>
              {/* Last activity (audit L2) — the signal that tells a newcomer
                  whether a board is alive. A board with no live topics says so
                  in words rather than rendering an empty slot. */}
              {category.last_post_at ? (
                <Timestamp iso={category.last_post_at} prefix="Last activity" />
              ) : (
                <span>No activity yet</span>
              )}
            </div>
          </div>
        </div>
      </Link>

      {/* Subcategories (if any) - Outside main link to avoid nested anchors */}
      {hasChildren && (
        <div className="mt-4 pt-4 border-t border-line">
          <div className="flex flex-wrap gap-2">
            <span className="text-sm text-ink-3">Subcategories:</span>
            {category.children.map((child) => (
              <Link
                key={child.id}
                to={categoryPath(child)}
                className="px-3 py-1 bg-surface-2 hover:bg-surface-3 text-sm text-ink-2 rounded-full transition-colors"
              >
                {child.icon && <span className="mr-1">{child.icon}</span>}
                {child.name}
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default memo(CategoryCard);
