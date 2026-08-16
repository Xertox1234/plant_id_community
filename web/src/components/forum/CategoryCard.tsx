import { memo } from 'react';
import { Link } from 'react-router-dom';
import { MessagesSquare, Reply } from 'lucide-react';
import Card from '../ui/Card';
import Tile from '../ui/Tile';
import Timestamp from '../ui/Timestamp';
import { categoryPath } from '../../utils/forumUrls';
import { boardIdentity } from '../../utils/forumTones';
import type { Category } from '@/types';

interface CategoryCardProps {
  category: Category;
}

/**
 * CategoryCard — a Canopy board row.
 *
 * Gradient card with the board's accent tile, name, description, and a mono
 * stat line. Subcategory chips sit OUTSIDE the row link (nested anchors are
 * invalid HTML).
 */
function CategoryCard({ category }: CategoryCardProps) {
  const hasChildren = !!(category.children && category.children.length > 0);
  const { tone, Icon } = boardIdentity(category.slug);

  return (
    <Card interactive className="p-card">
      <Link to={categoryPath(category)} viewTransition className="flex items-start gap-4">
        <Tile tone={tone} aria-hidden="true">
          {category.icon ? (
            <span className="text-xl leading-none">{category.icon}</span>
          ) : (
            <Icon className="h-5 w-5" />
          )}
        </Tile>
        <div className="min-w-0 flex-1">
          <h3 className="gt-h3 text-ink">{category.name}</h3>
          {category.description && (
            <p className="mt-1 line-clamp-2 max-w-prose text-sm leading-relaxed text-ink-2">
              {category.description}
            </p>
          )}
          <div className="gt-label mt-2.5 flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="inline-flex items-center gap-1">
              <MessagesSquare className="h-3 w-3" aria-hidden="true" />
              {category.thread_count || 0} threads
            </span>
            <span aria-hidden="true">·</span>
            <span className="inline-flex items-center gap-1">
              <Reply className="h-3 w-3" aria-hidden="true" />
              {category.post_count || 0} posts
            </span>
            <span aria-hidden="true">·</span>
            {category.last_post_at ? (
              <Timestamp iso={category.last_post_at} prefix="Last activity" />
            ) : (
              <span>No activity yet</span>
            )}
          </div>
        </div>
      </Link>

      {hasChildren && (
        <div className="mt-3 flex flex-wrap items-center gap-2 sm:pl-[62px]">
          <span className="gt-label">Subcategories</span>
          {category.children.map((child) => (
            <Link
              key={child.id}
              to={categoryPath(child)}
              className="gt-label inline-flex min-h-11 items-center rounded-pill border border-line px-3 transition-colors hover:border-line-2 hover:bg-surface-2 hover:text-ink-2"
            >
              {child.icon && (
                <span className="mr-1" aria-hidden="true">
                  {child.icon}
                </span>
              )}
              {child.name}
            </Link>
          ))}
        </div>
      )}
    </Card>
  );
}

export default memo(CategoryCard);
