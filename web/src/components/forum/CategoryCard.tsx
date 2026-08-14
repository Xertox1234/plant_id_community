import { memo } from 'react';
import { Link } from 'react-router-dom';
import Timestamp from '../ui/Timestamp';
import { categoryPath } from '../../utils/forumUrls';
import { IconLeaf, IconReply } from './ForumIcons';
import type { Category } from '@/types';

interface CategoryCardProps {
  category: Category;
}

/**
 * CategoryCard Component — a Field Notes ledger entry for a board.
 *
 * One ruled entry per board: mono stat line, board name in the display face,
 * description, and subcategory chips. Rendered inside a `.wf-ledger` list.
 */
function CategoryCard({ category }: CategoryCardProps) {
  const hasChildren = category.children && category.children.length > 0;

  return (
    <div className="wf-entry px-2 py-5">
      {/* Category Header - Clickable Link */}
      <Link to={categoryPath(category)} viewTransition className="wf-entry-link block">
        <div className="flex items-start gap-4">
          {/* Icon */}
          {category.icon && (
            <div className="text-3xl leading-none pt-1" aria-hidden="true">
              {category.icon}
            </div>
          )}

          {/* Category Info */}
          <div className="flex-1 min-w-0">
            {/* Collection-label line: counts + freshness in the ledger's voice */}
            <div className="wf-label flex flex-wrap items-center gap-x-2 gap-y-1 mb-1.5">
              <span className="inline-flex items-center gap-1">
                <IconLeaf size={12} /> {category.thread_count || 0} threads
              </span>
              <span aria-hidden="true">·</span>
              <span className="inline-flex items-center gap-1">
                <IconReply size={12} /> {category.post_count || 0} posts
              </span>
              <span aria-hidden="true">·</span>
              {/* Last activity (audit L2) — the signal that tells a newcomer
                  whether a board is alive. A board with no live topics says so
                  in words rather than rendering an empty slot. */}
              {category.last_post_at ? (
                <Timestamp iso={category.last_post_at} prefix="Last activity" />
              ) : (
                <span>No activity yet</span>
              )}
            </div>

            <h3 className="wf-title wf-entry-title text-ink transition-colors">{category.name}</h3>

            {category.description && (
              <p className="text-ink-2 text-sm leading-relaxed mt-1.5 max-w-prose">
                {category.description}
              </p>
            )}
          </div>
        </div>
      </Link>

      {/* Subcategories (if any) - Outside main link to avoid nested anchors */}
      {hasChildren && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="wf-label">Subcategories</span>
          {category.children.map((child) => (
            <Link
              key={child.id}
              to={categoryPath(child)}
              className="wf-label inline-flex min-h-11 items-center rounded-full border border-line px-3 transition-colors hover:border-line-2 hover:bg-surface-2 hover:text-ink-2"
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
    </div>
  );
}

export default memo(CategoryCard);
